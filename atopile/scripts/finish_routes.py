#!/usr/bin/env python3
"""
Route the connections Freerouting left open, with a small grid router.

First, signal-net vias and track ends that lead nowhere (Freerouting
leaves some where it gave up on a connection) are removed. Then, for every
net whose copper is still in more than one piece (KiCad's connectivity,
with the zones filled in memory), the two closest pieces are joined by an
A* search on a 0.05 mm grid over F.Cu and B.Cu, with through
vias. Clearances follow the net classes plus a margin for the grid:
  * track centre: width/2 + clearance from other nets' copper, the board
    edge and the isolation keep-out strip
  * via: 0.6 mm pad + clearance on both outer layers, 0.25 mm hole to hole,
    never inside an SMD pad
The search runs in a window around the gap (widened if it fails), so it
only touches the area of the open connection. If some connections fail,
they are tried again first, before the others, and the better result is
kept. A connection that still fails is routed ignoring other signal nets'
tracks; the track segments and vias that path collides with are ripped up
and their nets reconnected in the next round (up to MAX_ROUNDS). Pads, the
plane via drops and the pre-routed LDO block never move.

    python3 scripts/finish_routes.py           # report what it would add
    python3 scripts/finish_routes.py --write   # clean up and add the tracks and vias

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
MAX_ROUNDS = 12
RIP_COST = 20.0  # cost per mm of crossing another net's track when ripping up
RIP_HISTORY = 2.0  # a net's crossing cost is multiplied by this each time it is ripped up
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
def item_key(item):
    """Identity of a board item. Pads of identical footprints share UUIDs,
    so a pad is named by its footprint reference and number instead."""
    if item.GetClass() == "PAD":
        return ("pad", item.GetParentFootprint().GetReference(), item.GetNumber())
    return ("item", item.m_Uuid.AsString())


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
        uid = {item_key(c.item): i for i, c in enumerate(cs)}
        parent = list(range(len(cs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i, c in enumerate(cs):
            for o in conn.GetConnectedItems(c.item):
                j = uid.get(item_key(o))
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
def route(net, src, dst, items, window, soft=()):
    """A* route from piece src to piece dst of net. items are hard
    obstacles; soft is [(Copper, cost per mm)] that may be crossed at a
    price (used for rip-up). Returns (segments, vias, length) or None."""
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
    # grid on absolute multiples of RES: the pads sit on that grid, so a
    # track can run exactly on a fine-pitch pin's centreline
    x0, y0 = math.floor(x0 / RES) * RES, math.floor(y0 / RES) * RES
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
    pen = {L: np.zeros(X.shape) for L in LAYERS}
    via_pen = np.zeros(X.shape)
    for c, cost in soft:
        bx0, by0, bx1, by1 = c.bbox
        if bx1 < x0 - 1 or bx0 > x1 + 1 or by1 < y0 - 1 or by0 > y1 + 1:
            continue
        d = c.dist(X, Y)
        for L in c.layers:
            pen[L] += np.where(d < w / 2 + clr, cost, 0.0)
        via_pen += np.where(d < VIA_D / 2 + clr, cost, 0.0)
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
                step = RES * math.hypot(dx, dy)
                g2 = g + step * (1.0 + pen[LAYERS[layer]][jy, jx]) + BEND_COST * turn
                if g2 < dist.get(n2, math.inf):
                    dist[n2], prev[n2] = g2, node
                    heapq.heappush(heap, (g2 + h(jy, jx), g2, n2))
        if via_ok[iy, ix]:
            n2 = (1 - layer, iy, ix, 8)
            if ok[1 - layer][iy, ix] or goal[LAYERS[1 - layer]][iy, ix]:
                g2 = g + VIA_COST + via_pen[iy, ix]
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
            vias.append({"at": [round(float(gx[a[2]]), 4), round(float(gy[a[1]]), 4)], "size": VIA_D, "drill": VIA_DRILL, "net": net})
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
            "start": [round(float(gx[a[2]]), 4), round(float(gy[a[1]]), 4)],
            "end": [round(float(gx[b[2]]), 4), round(float(gy[b[1]]), 4)],
            "width": w, "layer": LAYERS[a[0]], "net": net,
        })


def remove_dangling(board) -> int:
    """Remove signal-net vias and tracks with an end that leads nowhere,
    repeatedly, so a whole abandoned stub goes. Plane nets and grouped
    tracks are left alone. Returns how many items were removed."""
    import pcbnew

    pads = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads.setdefault(pad.GetNetCode(), []).append(pad)
    removed = 0
    while True:
        by_net = {}
        for t in board.GetTracks():
            if t.GetNetname() not in import_routing.PLANE_NETS and t.GetParentGroup() is None:
                by_net.setdefault(t.GetNetCode(), []).append(t)
        drop = []
        for code, ts in by_net.items():
            net_pads = pads.get(code, [])
            for t in ts:
                if t.GetClass() == "PCB_VIA":
                    n = sum(1 for o in ts if o.GetClass() != "PCB_VIA"
                            and (t.HitTest(o.GetStart()) or t.HitTest(o.GetEnd())))
                    n += sum(1 for p in net_pads if p.HitTest(t.GetPosition()))
                    if n <= 1:
                        drop.append(t)
                    continue
                for end in (t.GetStart(), t.GetEnd()):
                    if not (any(p.IsOnLayer(t.GetLayer()) and p.HitTest(end) for p in net_pads)
                            or any(o is not t and (o.GetClass() == "PCB_VIA" or o.GetLayer() == t.GetLayer())
                                   and o.HitTest(end) for o in ts)):
                        drop.append(t)
                        break
        if not drop:
            return removed
        for t in drop:
            board.Delete(t)
        removed += len(drop)


def route_all(pairs, items):
    """Route the pairs in order; returns (added tracks/vias, failed nets, log)."""
    items = list(items)
    added = {"segments": [], "vias": []}
    failed, log = [], []
    for net, a, b in pairs:
        r = None
        for window in WINDOWS:
            r = route(net, a, b, items, window)
            if r:
                break
        if not r:
            log.append(f"  {net}: no route found")
            failed.append(net)
            continue
        segs, vias, length = r
        log.append(f"  {net}: {length:.1f} mm, {len(segs)} segments, {len(vias)} via(s)")
        added["segments"] += segs
        added["vias"] += vias
        # later routes must clear this one
        for s in segs:
            items.append(Copper(net, (s["layer"],), cap=(tuple(s["start"]), tuple(s["end"]), s["width"] / 2)))
        for v in vias:
            p = tuple(v["at"])
            items.append(Copper(net, LAYERS, cap=(p, p, VIA_D / 2), hole=(p[0], p[1], VIA_DRILL / 2)))
    return added, failed, log


def movable(c, net=None):
    """A signal track or via that rip-up may remove."""
    return (c.item is not None and c.item.GetClass() in ("PCB_TRACK", "PCB_VIA") and c.net != net
            and c.net not in import_routing.PLANE_NETS and c.item.GetParentGroup() is None)


def seg_seg(a, b, c, d):
    """Distance between segments ab and cd (scalar)."""
    def pt(p, q, r):
        L = (r[0] - q[0]) ** 2 + (r[1] - q[1]) ** 2
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - q[0]) * (r[0] - q[0]) + (p[1] - q[1]) * (r[1] - q[1])) / L))
        return math.hypot(p[0] - q[0] - t * (r[0] - q[0]), p[1] - q[1] - t * (r[1] - q[1]))

    def side(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    if a != b and c != d and (side(c, d, a) > 0) != (side(c, d, b) > 0) and (side(a, b, c) > 0) != (side(a, b, d) > 0):
        return 0.0
    return min(pt(a, c, d), pt(b, c, d), pt(c, a, b), pt(d, a, b))


def add_to_board(board, routing):
    import pcbnew

    for sgm in routing["segments"]:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(sgm["start"][0]), pcbnew.FromMM(sgm["start"][1])))
        t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(sgm["end"][0]), pcbnew.FromMM(sgm["end"][1])))
        t.SetWidth(pcbnew.FromMM(sgm["width"]))
        t.SetLayer(board.GetLayerID(sgm["layer"]))
        t.SetNetCode(board.GetNetcodeFromNetname(sgm["net"]))
        board.Add(t)
    for v in routing["vias"]:
        t = pcbnew.PCB_VIA(board)
        t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(v["at"][0]), pcbnew.FromMM(v["at"][1])))
        t.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        t.SetWidth(pcbnew.FromMM(v["size"]))
        t.SetDrill(pcbnew.FromMM(v["drill"]))
        t.SetNetCode(board.GetNetcodeFromNetname(v["net"]))
        board.Add(t)


def rip_up(board, net, a, b, items, history):
    """Route net with other signal nets' tracks as soft obstacles (crossing
    costs RIP_COST per mm, more for nets ripped up before), rip up what
    the path hits and put the path on the board. Returns the ripped nets,
    or None."""
    fixed = [c for c in items if not movable(c, net)]
    soft = [(c, RIP_COST * RIP_HISTORY ** history.get(c.net, 0)) for c in items if movable(c, net)]
    r = None
    for window in WINDOWS:
        r = route(net, a, b, fixed, window, soft)
        if r:
            break
    if not r:
        return None
    segs, vias, _ = r
    path = [((tuple(x["start"]), tuple(x["end"])), x["width"] / 2, (x["layer"],)) for x in segs]
    path += [((tuple(v["at"]), tuple(v["at"])), VIA_D / 2, LAYERS) for v in vias]
    cls = "Power" if net in POWER_NETS else "Default"
    ripped = set()
    for c in items:
        if not movable(c, net):
            continue
        ca, cb, cr = c.cap
        clr = max(CLEARANCE[cls], CLEARANCE["Power" if c.net in POWER_NETS else "Default"])
        for (pa, pb), pr, layers in path:
            if set(layers) & set(c.layers) and seg_seg(pa, pb, ca, cb) < pr + cr + clr:
                board.Delete(c.item)
                ripped.add(c.net)
                break
    for n in ripped:
        history[n] = history.get(n, 0) + 1
    add_to_board(board, {"segments": segs, "vias": vias})
    return ripped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="clean up and add the tracks and vias to the layout")
    args = ap.parse_args()

    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    removed = remove_dangling(board)
    print(f"removed {removed} dangling vias/tracks")
    failed, history = [], {}
    for rnd in range(1, MAX_ROUNDS + 1):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        items = collect(board)
        pairs = open_pairs(board, items)
        print(f"round {rnd}: {len(pairs)} open connection(s)")
        if not pairs:
            break
        added, failed, log = route_all(pairs, items)
        if failed:
            again = [p for p in pairs if p[0] in failed] + [p for p in pairs if p[0] not in failed]
            added2, failed2, log2 = route_all(again, items)
            if len(failed2) < len(failed):
                added, failed, log = added2, failed2, ["  (failed nets routed first)"] + log2
        print("\n".join(log))
        add_to_board(board, added)
        if not failed:
            continue
        # rip up for each net that still fails, on the board as it now stands
        for target in failed:
            pcbnew.ZONE_FILLER(board).Fill(board.Zones())
            board.BuildConnectivity()
            items = collect(board)
            for net, a, b in open_pairs(board, items):
                if net == target:
                    ripped = rip_up(board, net, a, b, items, history)
                    print(f"  {net}: " + ("no route even with rip-up" if ripped is None
                                          else f"routed by ripping up {', '.join(sorted(ripped)) or 'nothing'}"))
                    break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    left = open_pairs(board, collect(board))
    print(f"open connections left: {len(left)}" + (f" ({', '.join(n for n, _, _ in left)})" if left else ""))
    if args.write:
        import_routing.write_layout(import_routing.tracks_of(board), replace=True)
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
