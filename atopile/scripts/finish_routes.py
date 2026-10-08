#!/usr/bin/env python3
"""
Route the connections Freerouting left open, with a small grid router.

For every net whose copper is still in more than one piece (KiCad's
connectivity, with the zones filled in memory), the two closest pieces are
joined by an A* search on a 0.05 mm grid over F.Cu and B.Cu, with through
vias. Clearances follow the net classes plus a margin for the grid:
  * track centre: width/2 + clearance from other nets' copper, the board
    edge and the isolation keep-out strip
  * via: 0.6 mm pad + clearance on both outer layers, 0.25 mm hole to hole,
    never inside an SMD pad
The search runs in a window around the gap (widened if it fails), so it
only touches the area of the open connection.

    python3 scripts/finish_routes.py           # report what it would add
    python3 scripts/finish_routes.py --write   # add the tracks and vias

Run after scripts/import_routing.py, then check with KiCad's DRC
(scripts/export_pcb.py does that).

Needs KiCad's pcbnew Python module (KiCad 9/10) and numpy; writes through
atopile's Python (see scripts/import_routing.py).
"""

import argparse
import heapq
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_routing  # noqa: E402

LAYOUT = import_routing.LAYOUT
RES = 0.05  # grid pitch, mm
GRID_MARGIN = 0.04  # covers diagonal steps between grid points
CLEARANCE = {"Default": 0.15, "Power": 0.2}
WIDTH = {"Default": 0.2, "Power": 0.4}
POWER_NETS = ("VBUS", "+5V")
VIA_D, VIA_DRILL, HOLE_GAP = 0.6, 0.3, 0.25
EDGE = 0.3  # copper to board edge
BOARD_W, BOARD_H = 78.0, 60.0
BARRIER_KEEPOUT = 1.6
VIA_COST = 1.5  # mm of track a via is worth
BEND_COST = 0.3  # mm per 45 degrees of turn
WINDOWS = (3.0, 6.0, 12.0)  # search margins around the gap, mm
LAYERS = ("F.Cu", "B.Cu")


def mm(v):
    import pcbnew

    return pcbnew.ToMM(v)


# ---------------------------------------------------------------- geometry
def seg_dist(X, Y, a, b):
    """Distance from grid points to segment ab."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L == 0:
        return np.hypot(X - ax, Y - ay)
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0.0, 1.0)
    return np.hypot(X - (ax + t * dx), Y - (ay + t * dy))


def poly_dist(X, Y, pts):
    """Distance from grid points to a polygon (0 inside)."""
    d = np.full(X.shape, np.inf)
    inside = np.zeros(X.shape, dtype=bool)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        d = np.minimum(d, seg_dist(X, Y, a, b))
        (x1, y1), (x2, y2) = a, b
        if y1 != y2:
            cross = ((y1 > Y) != (y2 > Y)) & (X < (x2 - x1) * (Y - y1) / (y2 - y1) + x1)
            inside ^= cross
    d[inside] = 0.0
    return d


class Copper:
    """One piece of copper: pad polygon, or track/via capsule, on given layers."""

    def __init__(self, net, layers, poly=None, cap=None, hole=None, smd=False, item=None):
        self.net, self.layers, self.poly, self.cap = net, layers, poly, cap
        self.hole, self.smd, self.item = hole, smd, item
        pts = poly if poly is not None else [cap[0], cap[1]]
        r = 0 if poly is not None else cap[2]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.bbox = (min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r)

    def dist(self, X, Y):
        if self.poly is not None:
            return poly_dist(X, Y, self.poly)
        a, b, r = self.cap
        return seg_dist(X, Y, a, b) - r


def collect(board):
    import pcbnew

    items = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            layers = tuple(L for L, lid in zip(LAYERS, (pcbnew.F_Cu, pcbnew.B_Cu)) if pad.IsOnLayer(lid))
            hole = None
            if pad.HasHole():
                ds = pad.GetDrillSize()
                hole = (mm(pad.GetPosition().x), mm(pad.GetPosition().y), mm(max(ds.x, ds.y)) / 2)
            lid = pcbnew.F_Cu if "F.Cu" in layers else pcbnew.B_Cu
            if not layers:  # NPTH: hole only
                items.append(Copper("", (), cap=((hole[0], hole[1]), (hole[0], hole[1]), 0.0), hole=hole))
                continue
            o = pad.GetEffectivePolygon(lid).Outline(0)
            poly = [(mm(o.CPoint(i).x), mm(o.CPoint(i).y)) for i in range(o.PointCount())]
            items.append(Copper(pad.GetNetname(), layers, poly=poly, hole=hole,
                                smd=not pad.HasHole(), item=pad))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = (mm(t.GetPosition().x), mm(t.GetPosition().y))
            items.append(Copper(t.GetNetname(), LAYERS, cap=(p, p, mm(t.GetWidth(pcbnew.F_Cu)) / 2),
                                hole=(p[0], p[1], mm(t.GetDrillValue()) / 2), item=t))
        else:
            a = (mm(t.GetStart().x), mm(t.GetStart().y))
            b = (mm(t.GetEnd().x), mm(t.GetEnd().y))
            items.append(Copper(t.GetNetname(), (t.GetLayerName(),), cap=(a, b, mm(t.GetWidth()) / 2), item=t))
    return items


# ---------------------------------------------------------------- open connections
def open_pairs(board, items):
    """For each net in several pieces: the closest pair of items in two pieces."""
    conn = board.GetConnectivity()
    conn.RecalculateRatsnest()
    by_net = {}
    for c in items:
        if c.item is not None and c.net:
            by_net.setdefault(c.net, []).append(c)
    pairs = []
    for net, cs in by_net.items():
        uid = {c.item.m_Uuid.AsString(): i for i, c in enumerate(cs)}
        parent = list(range(len(cs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i, c in enumerate(cs):
            for o in conn.GetConnectedItems(c.item):
                j = uid.get(o.m_Uuid.AsString())
                if j is not None:
                    parent[find(i)] = find(j)
        groups = {}
        for i in range(len(cs)):
            groups.setdefault(find(i), []).append(cs[i])
        if len(groups) < 2:
            continue
        g = list(groups.values())
        # join the pieces one by one, closest first (a spanning tree)
        joined, rest = [g[0]], g[1:]
        while rest:
            best = None
            for a in joined:
                for k, b in enumerate(rest):
                    d = piece_gap(a, b)
                    if best is None or d < best[0]:
                        best = (d, a, k)
            d, a, k = best
            pairs.append((net, a, rest[k]))
            joined.append(rest.pop(k))
    return pairs


def points(piece):
    for c in piece:
        if c.poly is not None:
            xs, ys = zip(*c.poly)
            yield (sum(xs) / len(xs), sum(ys) / len(ys))
        else:
            yield c.cap[0]
            yield c.cap[1]


def piece_gap(a, b):
    return min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in points(a) for q in points(b))


# ---------------------------------------------------------------- router
def route(net, src, dst, items, window):
    cls = "Power" if net in POWER_NETS else "Default"
    w, clr = WIDTH[cls], CLEARANCE[cls] + GRID_MARGIN
    pa = list(points(src))
    pb = list(points(dst))
    xs = [p[0] for p in pa + pb]
    ys = [p[1] for p in pa + pb]
    x0, x1 = min(xs) - window, max(xs) + window
    y0, y1 = min(ys) - window, max(ys) + window
    x0, x1 = max(x0, -BOARD_W / 2), min(x1, BOARD_W / 2)
    y0, y1 = max(y0, -BOARD_H / 2), min(y1, BOARD_H / 2)
    gx = np.arange(x0, x1 + RES / 2, RES)
    gy = np.arange(y0, y1 + RES / 2, RES)
    X, Y = np.meshgrid(gx, gy)

    # board edge and barrier keep-out
    edge = np.minimum.reduce([X + BOARD_W / 2, BOARD_W / 2 - X, Y + BOARD_H / 2, BOARD_H / 2 - Y])
    barrier = np.abs(Y) - BARRIER_KEEPOUT
    track_ok = {L: (edge >= EDGE + w / 2 + GRID_MARGIN) & (barrier >= w / 2 + GRID_MARGIN) for L in LAYERS}
    via_ok = (edge >= EDGE + VIA_D / 2 + GRID_MARGIN) & (barrier >= VIA_D / 2 + GRID_MARGIN)
    start = {L: np.zeros(X.shape, bool) for L in LAYERS}
    goal = {L: np.zeros(X.shape, bool) for L in LAYERS}
    src_ids, dst_ids = {id(c) for c in src}, {id(c) for c in dst}

    for c in items:
        bx0, by0, bx1, by1 = c.bbox
        reach = VIA_D / 2 + clr + 0.5
        if bx1 < x0 - reach or bx0 > x1 + reach or by1 < y0 - reach or by0 > y1 + reach:
            continue
        if c.hole is not None:
            hx, hy, hr = c.hole
            via_ok &= np.hypot(X - hx, Y - hy) >= VIA_DRILL / 2 + hr + HOLE_GAP + GRID_MARGIN
        if not c.layers:
            continue
        d = c.dist(X, Y)
        if c.net == net:
            for L in c.layers:
                if id(c) in src_ids:
                    start[L] |= d <= 0.001
                if id(c) in dst_ids:
                    goal[L] |= d <= 0.001
            if c.smd:
                via_ok &= d >= VIA_D / 2 + GRID_MARGIN  # no via in pad
            continue
        for L in c.layers:
            track_ok[L] &= d >= w / 2 + clr
        if any(L in c.layers for L in LAYERS):
            via_ok &= d >= VIA_D / 2 + clr
    if not any(start[L].any() for L in LAYERS) or not any(goal[L].any() for L in LAYERS):
        return None

    ny, nx = X.shape
    gpts = np.array(pb)

    def h(iy, ix):
        return float(np.min(np.hypot(gpts[:, 0] - gx[ix], gpts[:, 1] - gy[iy])))

    li = {L: k for k, L in enumerate(LAYERS)}
    # state: (layer, iy, ix, direction 0-7, or 8 = free after a via/start)
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    dist = {}
    prev = {}
    heap = []
    for L in LAYERS:
        for iy, ix in zip(*np.nonzero(start[L])):
            node = (li[L], int(iy), int(ix), 8)
            dist[node] = 0.0
            heapq.heappush(heap, (h(iy, ix), 0.0, node))
    ok = [track_ok[L] for L in LAYERS]
    end = None
    while heap:
        f, g, node = heapq.heappop(heap)
        if g > dist.get(node, math.inf):
            continue
        layer, iy, ix, d0 = node
        if goal[LAYERS[layer]][iy, ix]:
            end = node
            break
        for k, (dx, dy) in enumerate(dirs):
            turn = 0 if d0 == 8 else min((k - d0) % 8, (d0 - k) % 8)
            if turn > 2:  # no turns sharper than 90 degrees
                continue
            jy, jx = iy + dy, ix + dx
            if 0 <= jy < ny and 0 <= jx < nx and (ok[layer][jy, jx] or goal[LAYERS[layer]][jy, jx]):
                n2 = (layer, jy, jx, k)
                g2 = g + RES * math.hypot(dx, dy) + BEND_COST * turn
                if g2 < dist.get(n2, math.inf):
                    dist[n2], prev[n2] = g2, node
                    heapq.heappush(heap, (g2 + h(jy, jx), g2, n2))
        if via_ok[iy, ix]:
            n2 = (1 - layer, iy, ix, 8)
            if ok[1 - layer][iy, ix] or goal[LAYERS[1 - layer]][iy, ix]:
                g2 = g + VIA_COST
                if g2 < dist.get(n2, math.inf):
                    dist[n2], prev[n2] = g2, node
                    heapq.heappush(heap, (g2 + h(iy, ix), g2, n2))
    if end is None:
        return None

    path = [end]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()

    # path -> straight segments and vias
    segments, vias = [], []
    run = [path[0]]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            flush(run, segments, gx, gy, w, net)
            vias.append({"at": [round(gx[a[2]], 4), round(gy[a[1]], 4)], "size": VIA_D, "drill": VIA_DRILL, "net": net})
            run = [b]
        else:
            run.append(b)
    flush(run, segments, gx, gy, w, net)
    length = sum(math.hypot(s["end"][0] - s["start"][0], s["end"][1] - s["start"][1]) for s in segments)
    return segments, vias, length


def flush(run, segments, gx, gy, w, net):
    """Merge a same-layer run of grid steps into straight segments."""
    if len(run) < 2:
        return
    corners = [run[0]]
    for a, b, c in zip(run, run[1:], run[2:]):
        if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
            corners.append(b)
    corners.append(run[-1])
    for a, b in zip(corners, corners[1:]):
        segments.append({
            "start": [round(gx[a[2]], 4), round(gy[a[1]], 4)],
            "end": [round(gx[b[2]], 4), round(gy[b[1]], 4)],
            "width": w, "layer": LAYERS[a[0]], "net": net,
        })


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="add the tracks and vias to the layout")
    args = ap.parse_args()

    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    items = collect(board)
    pairs = open_pairs(board, items)
    print(f"{len(pairs)} open connection(s)")
    added = {"segments": [], "vias": []}
    failed = 0
    for net, a, b in pairs:
        for window in WINDOWS:
            r = route(net, a, b, items, window)
            if r:
                break
        if not r:
            print(f"  {net}: no route found")
            failed += 1
            continue
        segs, vias, length = r
        print(f"  {net}: {length:.1f} mm, {len(segs)} segments, {len(vias)} via(s)")
        added["segments"] += segs
        added["vias"] += vias
        # later routes must clear this one
        for s in segs:
            items.append(Copper(net, (s["layer"],), cap=(tuple(s["start"]), tuple(s["end"]), s["width"] / 2)))
        for v in vias:
            p = tuple(v["at"])
            items.append(Copper(net, LAYERS, cap=(p, p, VIA_D / 2), hole=(p[0], p[1], VIA_DRILL / 2)))
    if args.write and (added["segments"] or added["vias"]):
        import_routing.write_layout(added, replace=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
