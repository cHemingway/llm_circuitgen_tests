"""A small two-layer grid router for the pcbnew board built by gen_pcb.py.

* 0.1 mm grid, octilinear A* with rip-up-and-retry
* nets that own an inner plane (GND, GND_ISO, +3V3, +5V_ISO) are only fanned
  out: every SMD pad gets a short stub to a via (or to copper that already
  reaches the plane)
* clearance bookkeeping is done with pre-inflated "owner" maps, one per
  width class, so that a cell is usable for a net iff no foreign copper is
  closer than (clearance + half the new copper's width)
"""
import heapq
import math
import os
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM

G = 0.1                      # grid pitch, mm
CLR = 0.15                   # copper clearance, mm
MARGIN = 0.025               # numerical safety margin
EDGE = 0.4                   # copper to board edge
VIA_D, VIA_DRILL = 0.6, 0.3
HW = [0.1, 0.15, 0.25, 0.3]  # half-width classes: 0.2 / 0.3 / 0.5 mm tracks, via
KVIA = 3
STEP, DIAG = 10, 14
VIA_COST = int(os.environ.get('ROUTER_VIA', 260))    # cost of a via in units of 0.01 mm of track
TURN = 3
HUG = 0                      # extra cost per cell that is not right next to an obstacle (see build_hug)


def kclass(width):
    return {0.2: 0, 0.3: 1, 0.5: 2}[width]


class Router:
    def __init__(self, board, ox, oy, w, h, plane_nets, widths, log=print):
        self.b, self.ox, self.oy, self.w, self.h = board, ox, oy, w, h
        self.nx, self.ny = int(round(w / G)) + 1, int(round(h / G)) + 1
        self.N = self.nx * self.ny
        self.log = log
        self.plane_nets = set(plane_nets)
        self.widths = widths                  # net name -> track width
        self.names = [None]
        self.ids = {}
        # hard[k][layer]: 0 free, n single net, -1 blocked.  soft: routed (rippable) copper
        self.hard = [[np.zeros((self.ny, self.nx), np.int32) for _ in range(2)] for _ in HW]
        self.soft = [[np.zeros((self.ny, self.nx), np.int32) for _ in range(2)] for _ in HW]
        self.no_via = np.zeros((self.ny, self.nx), bool)
        self.comps = {}        # net id -> list of components: {'cells': set(node), 'plane': bool, 'pts': [(x, y)]}
        self.routes = {}       # net id -> list of route dicts
        self.ripcount = {}
        self.fixed_vias = []
        self.hug_w = HUG
        self.hug = None
        yy, xx = np.mgrid[0:self.ny, 0:self.nx]
        self.X, self.Y = xx * G, yy * G
        self._edges()

    # ------------------------------------------------------------------ utils
    def nid(self, name):
        if name not in self.ids:
            self.ids[name] = len(self.names)
            self.names.append(name)
        return self.ids[name]

    def cell(self, x, y):
        return int(round(x / G)), int(round(y / G))

    def _stamp_mask(self, maps, layer, net, dist, sl):
        """dist: signed distance field (mm) on slice sl; net -1 => block."""
        for k, hw in enumerate(HW):
            m = dist <= CLR + hw + MARGIN
            o = maps[k][layer][sl]
            if net < 0:
                o[m] = -1
            else:
                o[m] = np.where((o[m] == 0) | (o[m] == net), net, -1)

    def _bbox(self, x1, y1, x2, y2, pad=1.0):
        i1 = max(0, int((min(x1, x2) - pad) / G))
        i2 = min(self.nx, int((max(x1, x2) + pad) / G) + 2)
        j1 = max(0, int((min(y1, y2) - pad) / G))
        j2 = min(self.ny, int((max(y1, y2) + pad) / G) + 2)
        return (slice(j1, j2), slice(i1, i2))

    def _edges(self):
        d = np.minimum(np.minimum(self.X, self.w - self.X), np.minimum(self.Y, self.h - self.Y))
        for k, hw in enumerate(HW):
            for l in range(2):
                self.hard[k][l][d < EDGE + hw] = -1

    def block_rect(self, x1, y1, x2, y2, layers=(0, 1)):
        sl = self._bbox(x1, y1, x2, y2)
        X, Y = self.X[sl], self.Y[sl]
        dx = np.maximum(np.maximum(x1 - X, X - x2), 0)
        dy = np.maximum(np.maximum(y1 - Y, Y - y2), 0)
        d = np.hypot(dx, dy)
        for k, hw in enumerate(HW):
            for l in layers:
                self.hard[k][l][sl][d <= hw + 0.02] = -1

    def block_circle(self, cx, cy, r, layers=(0, 1)):
        sl = self._bbox(cx - r, cy - r, cx + r, cy + r)
        d = np.hypot(self.X[sl] - cx, self.Y[sl] - cy) - r
        for k, hw in enumerate(HW):
            for l in layers:
                self.hard[k][l][sl][d <= hw + 0.02] = -1

    # ------------------------------------------------------------------ pads
    def pad_dist(self, x, y, sx, sy, rot, r, sl):
        th = math.radians(rot)
        dx, dy = self.X[sl] - x, self.Y[sl] - y
        u = np.abs(dx * math.cos(th) - dy * math.sin(th)) - (sx / 2 - r)
        v = np.abs(dx * math.sin(th) + dy * math.cos(th)) - (sy / 2 - r)
        return np.hypot(np.maximum(u, 0), np.maximum(v, 0)) + np.minimum(np.maximum(u, v), 0) - r

    def add_pads(self):
        F = pcbnew.F_Cu
        for fp in self.b.GetFootprints():
            ref = fp.GetReference()
            for p in fp.Pads():
                pos = p.GetPosition()
                x, y = ToMM(pos.x) - self.ox, ToMM(pos.y) - self.oy
                lay = pcbnew.B_Cu if (p.IsOnLayer(pcbnew.B_Cu) and not p.IsOnLayer(F)) else F
                size = p.GetSize(lay)
                sx, sy = ToMM(size.x), ToMM(size.y)
                shape = p.GetShape(lay)
                if shape == pcbnew.PAD_SHAPE_RECTANGLE:
                    r = 0.0
                elif shape == pcbnew.PAD_SHAPE_ROUNDRECT:
                    r = p.GetRoundRectRadiusRatio(lay) * min(sx, sy)
                else:
                    r = min(sx, sy) / 2
                tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                layers = (0, 1) if tht else ((0,) if p.IsOnLayer(F) else (1,))
                if not (p.IsOnLayer(F) or p.IsOnLayer(pcbnew.B_Cu)):
                    continue                      # paste-only aperture
                name = p.GetNetname()
                net = self.nid(name) if name else -1
                sl = self._bbox(x - sx / 2 - sy / 2, y - sx / 2 - sy / 2, x + sx / 2 + sy / 2, y + sx / 2 + sy / 2)
                d = self.pad_dist(x, y, sx, sy, p.GetOrientationDegrees(), r, sl)
                for l in layers:
                    self._stamp_mask(self.hard, l, net, d, sl)
                if not (ref == 'U1' and p.GetNumber() == '61'):
                    self.no_via[sl] |= d <= VIA_DRILL / 2 + 0.12
                if net > 0:
                    jj, ii = np.nonzero(d <= -0.045)
                    if len(ii) == 0:
                        ci, cj = self.cell(x, y)
                        ii, jj = np.array([ci - sl[1].start]), np.array([cj - sl[0].start])
                    cells = set()
                    for l in layers:
                        base = l * self.N
                        cells.update(int(base + (j + sl[0].start) * self.nx + i + sl[1].start) for i, j in zip(ii, jj))
                    self.comps.setdefault(net, []).append(
                        {'cells': cells, 'plane': tht and name in self.plane_nets, 'pts': [(x, y)],
                         'small': min(sx, sy) < 0.35, 'area': sx * sy, 'tht': tht, 'ref': ref + '.' + p.GetNumber()})

    def add_fixed(self):
        """Tracks / vias already on the board (hand pre-routes): hard obstacles and part of their nets."""
        for t in self.b.GetTracks():
            net = self.nid(t.GetNetname())
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                x, y = ToMM(p.x) - self.ox, ToMM(p.y) - self.oy
                sl = self._bbox(x, y, x, y)
                d = np.hypot(self.X[sl] - x, self.Y[sl] - y) - VIA_D / 2
                for l in (0, 1):
                    self._stamp_mask(self.hard, l, net, d, sl)
                ci, cj = self.cell(x, y)
                cells = {l * self.N + cj * self.nx + ci for l in (0, 1)}
                self.comps.setdefault(net, []).append({'cells': cells, 'plane': t.GetNetname() in self.plane_nets,
                                                       'pts': [(x, y)], 'small': False, 'area': 1, 'tht': True, 'ref': 'via'})
            else:
                a, b = t.GetStart(), t.GetEnd()
                x1, y1, x2, y2 = (ToMM(a.x) - self.ox, ToMM(a.y) - self.oy, ToMM(b.x) - self.ox, ToMM(b.y) - self.oy)
                l = 0 if t.GetLayer() == pcbnew.F_Cu else 1
                sl = self._bbox(x1, y1, x2, y2)
                X, Y = self.X[sl], self.Y[sl]
                vx, vy = x2 - x1, y2 - y1
                L2 = vx * vx + vy * vy or 1e-9
                tt = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0, 1)
                d = np.hypot(X - (x1 + tt * vx), Y - (y1 + tt * vy)) - ToMM(t.GetWidth()) / 2
                self._stamp_mask(self.hard, l, net, d, sl)
                jj, ii = np.nonzero(d <= -0.03)
                cells = {int(l * self.N + (j + sl[0].start) * self.nx + i + sl[1].start) for i, j in zip(ii, jj)}
                for (px, py) in ((x1, y1), (x2, y2)):
                    ci, cj = self.cell(px, py)
                    cells.add(l * self.N + cj * self.nx + ci)
                self.comps.setdefault(net, []).append({'cells': cells, 'plane': False, 'pts': [(x1, y1), (x2, y2)],
                                                       'small': False, 'area': 1, 'tht': False, 'ref': 'trk'})
        for net, cl in self.comps.items():
            self._merge(net)

    def _merge(self, net):
        cl = self.comps[net]
        changed = True
        while changed:
            changed = False
            for a in range(len(cl)):
                for b in range(a + 1, len(cl)):
                    if cl[a]['cells'] & cl[b]['cells']:
                        cl[a]['cells'] |= cl[b]['cells']
                        cl[a]['plane'] = cl[a]['plane'] or cl[b]['plane']
                        cl[a]['pts'] += cl[b]['pts']
                        cl[a]['small'] = cl[a]['small'] and cl[b]['small']
                        cl[a]['ref'] += '+' + cl[b]['ref']
                        del cl[b]
                        changed = True
                        break
                if changed:
                    break

    # ------------------------------------------------------------------ maps for one net
    def passable(self, net, k, rip=False):
        out, pen = [], []
        if rip:
            lut = np.zeros(len(self.names) + 1, np.uint8)
            for m in range(1, len(self.names)):
                lut[m] = min(250, 12 * (1 + self.ripcount.get(m, 0)) ** 2)
            lut[net] = 0
        for l in range(2):
            h, s = self.hard[k][l], self.soft[k][l]
            hard_ok = (h == 0) | (h == net)
            ok = hard_ok & ((s == 0) | (s == net))
            out.append(bytearray(ok.astype(np.uint8).tobytes()))
            if rip:
                p = np.where(hard_ok & (s > 0) & (s != net), lut[np.maximum(s, 0)], 0).astype(np.uint8)
                pen.append(bytearray(p.tobytes()))
        return out, pen

    def via_ok(self, net, rip=False):
        ok = ~self.no_via
        okr = ok.copy()
        for l in range(2):
            h, s = self.hard[KVIA][l], self.soft[KVIA][l]
            hard_ok = (h == 0) | (h == net)
            ok &= hard_ok & ((s == 0) | (s == net))
            okr &= hard_ok & (s != -1)
        return bytearray(ok.astype(np.uint8).tobytes()), (bytearray(okr.astype(np.uint8).tobytes()) if rip else None)

    def build_hug(self):
        """Per-cell extra cost that makes tracks run right along pads, vias and other fixed
        copper instead of down the middle of a gap, so that a second track still fits
        (two tracks between neighbouring D-sub pins, one under a resistor array, ...)."""
        self.hug = []
        for k in range(len(HW)):
            row = []
            for l in range(2):
                blocked = self.hard[k][l] != 0
                near = blocked.copy()
                near[1:, :] |= blocked[:-1, :]
                near[:-1, :] |= blocked[1:, :]
                near[:, 1:] |= blocked[:, :-1]
                near[:, :-1] |= blocked[:, 1:]
                near[1:, 1:] |= blocked[:-1, :-1]
                near[:-1, :-1] |= blocked[1:, 1:]
                near[1:, :-1] |= blocked[:-1, 1:]
                near[:-1, 1:] |= blocked[1:, :-1]
                row.append(bytearray(np.where(near, 0, self.hug_w).astype(np.uint8).tobytes()))
            self.hug.append(row)

    # ------------------------------------------------------------------ search
    def astar(self, net, k, src, dst, goal_xy, bias=(1.0, 1.0), allow_via=True, plane_goal=False, rip=False,
              max_nodes=400000, max_cost=None, rip_cost=400):
        """src/dst: iterables of nodes.  Returns (path nodes, ripped net ids) or None."""
        nx, N = self.nx, self.N
        ok, pen = self.passable(net, k, rip)
        vok, vokr = self.via_ok(net, rip) if (allow_via or plane_goal) else (None, None)
        dstmask = bytearray(2 * N)
        for n in dst:
            dstmask[n] = 1
        gi, gj = self.cell(*goal_xy) if goal_xy else (0, 0)
        hx = int(STEP * bias[0])
        best = {}
        came = {}
        ddir = {}
        heap = []
        for n in src:
            best[n] = 0
            c = n % N
            i, j = c % nx, c // nx
            hh = 0 if goal_xy is None else STEP * max(abs(i - gi), abs(j - gj)) + (DIAG - STEP) * min(abs(i - gi), abs(j - gj))
            heap.append((hh, 0, n))
        heapq.heapify(heap)
        moves = [(1, 0, STEP), (-1, 0, STEP), (0, 1, STEP), (0, -1, STEP), (1, 1, DIAG), (1, -1, DIAG), (-1, 1, DIAG), (-1, -1, DIAG)]
        softk = self.soft[k]
        softv = self.soft[KVIA]
        hug = self.hug[k] if (self.hug and not plane_goal) else None
        count = 0
        GOAL = -1
        while heap:
            f, g, n = heapq.heappop(heap)
            if n == GOAL:
                break
            if best.get(n, 1 << 60) < g:
                continue
            if n >= 0 and dstmask[n]:
                came[GOAL] = n
                break
            count += 1
            if count > max_nodes or (max_cost and g > max_cost):
                return None
            l = n // N
            c = n - l * N
            i, j = c % nx, c // nx
            okl = ok[l]
            hugl = hug[l] if hug else None
            penl = pen[l] if rip else None
            pd = ddir.get(n, -1)
            hb, vb = (bias[0], bias[1]) if l == 0 else (bias[1], bias[0])
            for mi, (di, dj, cst) in enumerate(moves):
                i2, j2 = i + di, j + dj
                if i2 < 0 or j2 < 0 or i2 >= nx or j2 >= self.ny:
                    continue
                c2 = j2 * nx + i2
                extra = 0
                if not okl[c2]:
                    if rip and penl[c2]:
                        extra = penl[c2] * 30
                    else:
                        continue
                if di and dj:
                    # no corner cutting
                    if not (okl[j * nx + i2] or (rip and penl[j * nx + i2])) or not (okl[j2 * nx + i] or (rip and penl[j2 * nx + i])):
                        continue
                    cc = cst * (hb + vb) / 2
                else:
                    cc = cst * (hb if di else vb)
                g2 = g + cc + extra + (TURN if (pd != mi and pd != -1) else 0)
                if hugl:
                    g2 += hugl[c2]
                n2 = l * N + c2
                if g2 < best.get(n2, 1 << 60):
                    best[n2] = g2
                    came[n2] = n
                    ddir[n2] = mi
                    hh = 0 if goal_xy is None else STEP * max(abs(i2 - gi), abs(j2 - gj)) + (DIAG - STEP) * min(abs(i2 - gi), abs(j2 - gj))
                    heapq.heappush(heap, (g2 + hh, g2, n2))
            if vok is not None:
                good = vok[c]
                extra = 0
                if not good and rip and vokr[c]:
                    good, extra = True, rip_cost * 2
                if good:
                    if plane_goal:
                        if g > 0 and g + VIA_COST // 3 < best.get(GOAL, 1 << 60):
                            best[GOAL] = g + VIA_COST // 3 + extra
                            came[GOAL] = n
                            heapq.heappush(heap, (best[GOAL], best[GOAL], GOAL))
                    elif allow_via:
                        n2 = (1 - l) * N + c
                        if ok[1 - l][c] or (rip and pen[1 - l][c]):
                            g2 = g + VIA_COST + extra + (0 if ok[1 - l][c] else pen[1 - l][c] * 30)
                            if g2 < best.get(n2, 1 << 60):
                                best[n2] = g2
                                came[n2] = n
                                ddir[n2] = -1
                                hh = 0 if goal_xy is None else STEP * max(abs(i - gi), abs(j - gj)) + (DIAG - STEP) * min(abs(i - gi), abs(j - gj))
                                heapq.heappush(heap, (g2 + hh, g2, n2))
        else:
            return None
        if GOAL not in came:
            return None
        path = []
        n = came[GOAL]
        end_via = plane_goal and not dstmask[n]
        while True:
            path.append(n)
            if n not in came:
                break
            n = came[n]
        path.reverse()
        ripped = set()
        if rip:
            for a, b in zip(path, path[1:] + [None]):
                l, c = a // N, a % N
                j, i = c // nx, c % nx
                s = softk[l][j, i]
                if s > 0 and s != net:
                    ripped.add(int(s))
                if b is not None and b // N != l:
                    for ll in range(2):
                        s = softv[ll][j, i]
                        if s > 0 and s != net:
                            ripped.add(int(s))
            if end_via:
                c = path[-1] % N
                for ll in range(2):
                    s = softv[ll][c // nx, c % nx]
                    if s > 0 and s != net:
                        ripped.add(int(s))
        return path, end_via, ripped

    # ------------------------------------------------------------------ committing
    def _disc(self, r):
        n = int(r / G) + 1
        return [(di, dj) for di in range(-n, n + 1) for dj in range(-n, n + 1) if math.hypot(di, dj) * G <= r]

    def _stamp_cells(self, maps, layer, net, cells_ij, hw_own):
        ii = np.array([c[0] for c in cells_ij])
        jj = np.array([c[1] for c in cells_ij])
        for k, hw in enumerate(HW):
            disc = np.array(self._disc(hw_own + CLR + hw + MARGIN))
            I = (ii[:, None] + disc[None, :, 0]).ravel()
            J = (jj[:, None] + disc[None, :, 1]).ravel()
            m = (I >= 0) & (J >= 0) & (I < self.nx) & (J < self.ny)
            flat = np.unique(J[m] * self.nx + I[m])
            o = maps[k][layer].reshape(-1)
            cur = o[flat]
            o[flat] = np.where((cur == 0) | (cur == net), net, -1)

    def stamp_route(self, r):
        net, hw = r['net'], r['width'] / 2
        maps = self.hard if r.get('fan') else self.soft
        for l in range(2):
            cells = [(c % self.nx, c // self.nx) for (ll, c) in r['cells'] if ll == l]
            if cells:
                self._stamp_cells(maps, l, net, cells, hw)
        for (i, j) in r['vias']:
            for l in range(2):
                self._stamp_cells(maps, l, net, [(i, j)], VIA_D / 2)

    def rebuild_soft(self):
        for k in range(len(HW)):
            for l in range(2):
                self.soft[k][l][:] = 0
        for net, rl in self.routes.items():
            for r in rl:
                if not r.get('fan'):
                    self.stamp_route(r)

    def commit(self, net, width, path, end_via, fan=False):
        N, nx = self.N, self.nx
        cells = [(n // N, n % N) for n in path]
        vias = []
        for a, b in zip(cells, cells[1:]):
            if a[0] != b[0]:
                vias.append((a[1] % nx, a[1] // nx))
        if end_via:
            c = cells[-1][1]
            vias.append((c % nx, c // nx))
        r = {'net': net, 'width': width, 'cells': cells, 'vias': vias, 'path': path}
        if fan:
            r['fan'] = True
        self.routes.setdefault(net, []).append(r)
        self.stamp_route(r)
        nodes = set(path)
        for (i, j) in vias:
            nodes.add(j * nx + i)
            nodes.add(N + j * nx + i)
        return r, nodes

    # ------------------------------------------------------------------ high level
    def fanout_planes(self):
        todo = []
        for net, cl in self.comps.items():
            if self.names[net] in self.plane_nets:
                for c in cl:
                    if not c['plane']:
                        todo.append((c['small'], -c['area'], net, c))
        todo.sort(key=lambda t: (t[0], t[1]))
        fails = []
        for small, _, net, c in todo:
            if c['plane'] or c not in self.comps[net]:
                continue
            width = 0.2 if small else 0.3
            dst = set()
            for o in self.comps[net]:
                if o['plane']:
                    dst |= o['cells']
            res = self.astar(net, kclass(width), c['cells'], dst, None, plane_goal=True, allow_via=False,
                             max_nodes=60000, max_cost=STEP * 60)
            if res is None and width == 0.3:
                width = 0.2
                res = self.astar(net, 0, c['cells'], dst, None, plane_goal=True, allow_via=False, max_nodes=120000, max_cost=STEP * 120)
            if res is None:
                fails.append((self.names[net], c['ref']))
                continue
            path, end_via, _ = res
            r, nodes = self.commit(net, width, path, end_via, fan=True)
            c['cells'] |= nodes
            c['plane'] = True
            self._merge(net)
        return fails

    def net_edges(self):
        """MST edges over the components of each non-plane net: (length, net, pt_a, pt_b)."""
        edges = []
        for net, cl in self.comps.items():
            if self.names[net] in self.plane_nets or len(cl) < 2:
                continue
            pts = [c['pts'][0] for c in cl]
            intree = [0]
            rest = list(range(1, len(cl)))
            while rest:
                bd, ba, bb = 1e9, None, None
                for a in intree:
                    for b in rest:
                        d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in cl[a]['pts'] for q in cl[b]['pts'])
                        if d < bd:
                            bd, ba, bb = d, a, b
                edges.append((bd, net, pts[ba], pts[bb]))
                intree.append(bb)
                rest.remove(bb)
        edges.sort()
        return edges

    def comp_of(self, net, pt):
        ci, cj = self.cell(*pt)
        for c in self.comps[net]:
            if pt in c['pts']:
                return c
        return None

    def connect(self, net, pa, pb, bias, rip=False, max_nodes=400000):
        a, b = self.comp_of(net, pa), self.comp_of(net, pb)
        if a is None or b is None or a is b:
            return 'done', set()
        if len(a['cells']) > len(b['cells']):
            a, b, pa, pb = b, a, pb, pa
        width = self.widths.get(self.names[net], 0.2)
        if a['small'] or b['small']:
            width = min(width, 0.2)
        tgt = min(b['pts'], key=lambda q: math.hypot(q[0] - pa[0], q[1] - pa[1]))
        res = self.astar(net, kclass(width), a['cells'], b['cells'], tgt, bias=bias, rip=rip, max_nodes=max_nodes)
        if res is None and width > 0.2:
            width = 0.2
            res = self.astar(net, 0, a['cells'], b['cells'], tgt, bias=bias, rip=rip, max_nodes=max_nodes)
        if res is None:
            return 'fail', set()
        path, _, ripped = res
        if ripped:
            self.rip_nets(ripped)
        r, nodes = self.commit(net, width, path, False)
        r['ends'] = (pa, pb)
        a['cells'] |= b['cells'] | nodes
        a['pts'] += b['pts']
        a['plane'] = a['plane'] or b['plane']
        a['small'] = False
        self.comps[net].remove(b)
        return 'ok', ripped

    def rip_nets(self, nets):
        for m in nets:
            self.ripcount[m] = self.ripcount.get(m, 0) + 1
        for m in nets:
            self.routes[m] = [r for r in self.routes.get(m, []) if r.get('fan')]
        self.rebuild_soft()
        for m in nets:
            self.reset_comps(m)

    def reset_comps(self, net):
        self.comps[net] = [dict(c, cells=set(c['cells0']), pts=list(c['pts0']), plane=c['plane0'], small=c['small0'])
                           for c in self.base_comps[net]]
        for r in self.routes.get(net, []):
            pass

    def snapshot(self):
        self.base_comps = {}
        for net, cl in self.comps.items():
            for c in cl:
                c['cells0'], c['pts0'], c['plane0'], c['small0'] = set(c['cells']), list(c['pts']), c['plane'], c['small']
            self.base_comps[net] = [dict(c) for c in cl]

    def route_all(self, bias=(1.0, 1.0), passes=30, t_limit=1500):
        t0 = time.time()
        self.snapshot()
        if self.hug_w:
            self.build_hug()
        queue = self.net_edges()
        self.all_edges = list(queue)
        failed = []
        for it in range(passes):
            failed = []
            for (d, net, pa, pb) in queue:
                st, _ = self.connect(net, pa, pb, bias)
                if st == 'fail':
                    failed.append((d, net, pa, pb))
            self.log('pass %d: %d of %d connections failed (%.0fs)' % (it + 1, len(failed), len(queue), time.time() - t0))
            if not failed or it == passes - 1 or time.time() - t0 > t_limit:
                break
            # rip-up and retry: push each failed connection through, re-queue what it displaced
            requeue, still = [], []
            for (d, net, pa, pb) in failed:
                st, ripped = self.connect(net, pa, pb, bias, rip=True, max_nodes=900000)
                if st == 'fail':
                    still.append((d, net, pa, pb))
                for m in ripped:
                    requeue += [e for e in self.all_edges if e[1] == m]
            queue = sorted(set(requeue + still))
        # anything displaced by the last rip-up round gets one more ordinary attempt
        return failed

    # ------------------------------------------------------------------ output
    def simplify(self, cells):
        """cells: [(layer, cell)] -> list of (layer, [(x, y), ...]) polylines."""
        out = []
        cur = []
        for (l, c) in cells:
            pt = ((c % self.nx) * G, (c // self.nx) * G)
            if cur and cur[0] != l:
                out.append((cur[0], cur[1]))
                cur = []
            if not cur:
                cur = [l, [pt]]
            else:
                pts = cur[1]
                if len(pts) >= 2:
                    ax, ay = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
                    bx, by = pt[0] - pts[-1][0], pt[1] - pts[-1][1]
                    if abs(ax * by - ay * bx) < 1e-9 and ax * bx + ay * by > 0:
                        pts[-1] = pt
                        continue
                pts.append(pt)
        if cur:
            out.append((cur[0], cur[1]))
        return out

    def write(self):
        b = self.b
        ntr = nvia = 0
        for net, rl in self.routes.items():
            code = b.GetNetcodeFromNetname(self.names[net])
            for r in rl:
                for l, pts in self.simplify(r['cells']):
                    for p, q in zip(pts, pts[1:]):
                        t = pcbnew.PCB_TRACK(b)
                        t.SetStart(pcbnew.VECTOR2I(FromMM(self.ox + p[0]), FromMM(self.oy + p[1])))
                        t.SetEnd(pcbnew.VECTOR2I(FromMM(self.ox + q[0]), FromMM(self.oy + q[1])))
                        t.SetWidth(FromMM(r['width']))
                        t.SetLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)
                        t.SetNetCode(code)
                        b.Add(t)
                        ntr += 1
                for (i, j) in r['vias']:
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(FromMM(self.ox + i * G), FromMM(self.oy + j * G)))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetWidth(pcbnew.PADSTACK.ALL_LAYERS, FromMM(VIA_D))
                    v.SetDrill(FromMM(VIA_DRILL))
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    v.SetNetCode(code)
                    b.Add(v)
                    nvia += 1
        return ntr, nvia
