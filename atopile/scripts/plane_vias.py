#!/usr/bin/env python3
"""
Drop every SMD pad on a plane net to its inner plane with a short stub and a
through via, so the autorouter only has to route the signals.

    plane net   plane layer
    GND         In1.Cu (USB half)
    GND_ISO     In1.Cu (DVM half)
    +3V3        In2.Cu (USB half)
    +5V_ISO     In2.Cu (DVM half)

Through-hole pads reach the planes on their own. The zones are filled in
memory first, and a pad whose copper already reaches its plane (through a
via drop from an earlier run, or the pre-routed LDO block's vias) is
skipped, so re-running only fills gaps. A group of pads joined by tracks
but not yet by a via (the LDO block's +3V3) gets one via.

For each pad the script tries via spots around it, nearest first, and takes
the first one that keeps:
  * 0.2 mm (+ margin) from other nets' copper, for the via and the stub
  * 0.25 mm between drill holes
  * out of the isolation keep-out strip, the board edge, the jackscrew
    head keep-outs (nothing within 4 mm of the jackscrews on top) and the
    NO_VIA_AREAS (the USB pair's channel and the VREG_LX path at the
    RP2354A)
On IC pins it prefers spots under the body, between the pad rows, and no
via goes in the escape zone of another net's IC pin (within 1.5 mm, on the
side away from the IC body), so the pins' escape routes stay free. Exposed pads (2 mm or more each way) get a
grid of vias inside the pad instead. An IC pin with no free spot is
strapped to an adjacent pin of the same net that has one.

Run after `ato build` and place_components.py, before scripts/export_dsn.py:

    python3 scripts/plane_vias.py           # report only
    python3 scripts/plane_vias.py --write   # add the stubs and vias to the layout

Needs KiCad's pcbnew Python module (KiCad 9/10); writes through atopile's
Python (see scripts/import_routing.py).
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_routing  # noqa: E402

LAYOUT = import_routing.LAYOUT
PLANE_NETS = {"GND": "In1.Cu", "GND_ISO": "In1.Cu", "+3V3": "In2.Cu", "+5V_ISO": "In2.Cu"}

VIA_D, VIA_DRILL = 0.6, 0.3  # default netclass via
STUB_W = 0.25
CLEARANCE = 0.2 + 0.02  # netclass clearance + margin
HOLE_GAP = 0.25 + 0.03
BOARD_W, BOARD_H, CORNER_R = 78.0, 60.0, 2.0
EDGE = 0.3 + 0.05  # copper-to-edge
BARRIER_KEEPOUT = 1.6  # half-width of the keep-out strip (place_components.py)
JACKSCREW_R = 4.0  # check_layout.py JACKSCREW_KEEPOUT_R
ESCAPE_R = 1.5  # keep vias out of IC pins' escape zones (mm from the pin)
ESCAPE_COST = 3.0
EP_MIN = 2.0  # pads at least this big each way get vias inside

# Areas kept free of via drops: (x0, y0, x1, y1) mm, and why
NO_VIA_AREAS = [
    ((0.6, -23.0, 5.4, -20.9), "USB DP/DM between RP2354A pins 51/52 and R7/R8"),
    ((5.5, -22.3, 7.1, -20.9), "VREG_LX between RP2354A pin 48 and L1"),
]
EP_PITCH = 1.0


def nm(v):
    import pcbnew

    return pcbnew.FromMM(v)


def mm(v):
    import pcbnew

    return pcbnew.ToMM(v)


def seg_dist(a, b, c, d):
    """Distance between segments ab and cd (points as (x, y) mm)."""
    def pt_seg(p, q, r):
        qx, qy, rx, ry = q[0], q[1], r[0], r[1]
        L = (rx - qx) ** 2 + (ry - qy) ** 2
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - qx) * (rx - qx) + (p[1] - qy) * (ry - qy)) / L))
        return math.hypot(p[0] - (qx + t * (rx - qx)), p[1] - (qy + t * (ry - qy)))

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    if a != b and c != d:
        d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
        if (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0):
            return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


class Obstacles:
    """Copper of every net and all drill holes, to check new items against.
    Pads are KiCad shapes; tracks and vias are capsules (a, b, radius) in mm."""

    def __init__(self, board):
        import pcbnew

        self.pcbnew = pcbnew
        self.pads = []  # (net, layer, SHAPE)
        self.caps = []  # (net, layer, a, b, r)
        self.holes = []  # (x, y, radius) mm
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if pad.IsOnLayer(layer):
                        self.pads.append((pad.GetNetname(), layer, pad.GetEffectiveShape(layer)))
                if pad.HasHole():
                    ds = pad.GetDrillSize()
                    p = pad.GetPosition()
                    self.holes.append((mm(p.x), mm(p.y), mm(max(ds.x, ds.y)) / 2))
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                self.add_via(t.GetNetname(), mm(p.x), mm(p.y), mm(t.GetWidth(pcbnew.F_Cu)) / 2,
                             mm(t.GetDrillValue()) / 2)
            else:
                a = (mm(t.GetStart().x), mm(t.GetStart().y))
                b = (mm(t.GetEnd().x), mm(t.GetEnd().y))
                self.caps.append((t.GetNetname(), t.GetLayer(), a, b, mm(t.GetWidth()) / 2))

    def clear(self, net, a, b, r, layers):
        pc = self.pcbnew
        c = CLEARANCE
        if a == b:
            q = pc.SHAPE_CIRCLE(pc.VECTOR2I(nm(a[0]), nm(a[1])), nm(r))
        else:
            q = pc.SHAPE_SEGMENT(pc.VECTOR2I(nm(a[0]), nm(a[1])), pc.VECTOR2I(nm(b[0]), nm(b[1])), nm(2 * r))
        for n, layer, shape in self.pads:
            if n != net and layer in layers and shape.Collide(q, nm(c)):
                return False
        for n, layer, ca, cb, cr in self.caps:
            if n != net and layer in layers and seg_dist(a, b, ca, cb) < r + cr + c:
                return False
        return True

    def holes_clear(self, x, y):
        r = VIA_DRILL / 2
        return all(math.hypot(x - hx, y - hy) >= r + hr + HOLE_GAP for hx, hy, hr in self.holes)

    def add_via(self, net, x, y, r=VIA_D / 2, hole_r=VIA_DRILL / 2):
        for layer in (self.pcbnew.F_Cu, self.pcbnew.B_Cu):
            self.caps.append((net, layer, (x, y), (x, y), r))
        self.holes.append((x, y, hole_r))

    def add_stub(self, net, a, b, w):
        self.caps.append((net, self.pcbnew.F_Cu, tuple(a), tuple(b), w / 2))


def on_board(x, y, jackscrews):
    r = VIA_D / 2
    hx, hy = BOARD_W / 2 - CORNER_R, BOARD_H / 2 - CORNER_R
    if abs(x) > BOARD_W / 2 - EDGE - r or abs(y) > BOARD_H / 2 - EDGE - r:
        return False
    if abs(x) > hx and abs(y) > hy and math.hypot(abs(x) - hx, abs(y) - hy) > CORNER_R - EDGE - r:
        return False
    if abs(y) < BARRIER_KEEPOUT + r + 0.1:
        return False
    if any(x0 - r <= x <= x1 + r and y0 - r <= y <= y1 + r for (x0, y0, x1, y1), _ in NO_VIA_AREAS):
        return False
    return all(math.hypot(x - jx, y - jy) >= JACKSCREW_R + r for jx, jy in jackscrews)


def ic_pins(board):
    """(x, y, outward unit vector, net) of every pin of a footprint with 6+
    pads: the pins whose escape routes the via drops should leave free."""
    out = []
    for fp in board.GetFootprints():
        if len(fp.Pads()) < 6:
            continue
        fx, fy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
        for pad in fp.Pads():
            px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
            d = math.hypot(px - fx, py - fy)
            if d > 0.5:  # not a centre (exposed) pad
                out.append((px, py, (px - fx) / d, (py - fy) / d, pad.GetNetname()))
    return out


def escape_cost(x, y, net, pins):
    for px, py, ux, uy, n in pins:
        if n != net and math.hypot(x - px, y - py) < ESCAPE_R and (x - px) * ux + (y - py) * uy > 0:
            return ESCAPE_COST
    return 0.0


def drop(pad, fp, obstacles, jackscrews, pins):
    """Best (stub start, via position, stub width) for one pad, or None."""
    pc = obstacles.pcbnew
    net = pad.GetNetname()
    own = pad.GetEffectiveShape(pc.F_Cu)
    px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
    fx, fy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
    size = pad.GetSize(pc.F_Cu)
    w = min(STUB_W, 0.75 * mm(min(size.x, size.y)))  # 0.15 mm on 0.4 mm-pitch QFN pins
    is_ic = len(fp.Pads()) >= 6
    inward = math.atan2(fy - py, fx - px)

    candidates = []
    for k in range(16):
        a = k * math.pi / 8
        dx, dy = math.cos(a), math.sin(a)
        # first distance at which the via clears its own pad by 0.15 mm
        t0 = next((t / 100 for t in range(30, 300, 5)
                   if not own.Collide(pc.SHAPE_CIRCLE(pc.VECTOR2I(nm(px + dx * t / 100), nm(py + dy * t / 100)),
                                                      nm(VIA_D / 2 + 0.15)), 0)), 3.0)
        for extra in (0.0, 0.3, 0.6, 1.0):
            t = t0 + extra
            cost = t
            if is_ic and math.cos(a - inward) < 0.7:
                cost += 2.0  # keep IC escape routes free: prefer under the body
            cost += escape_cost(px + dx * t, py + dy * t, net, pins)
            candidates.append((cost, t, dx, dy))
    for cost, t, dx, dy in sorted(candidates):
        vx, vy = px + dx * t, py + dy * t
        if not on_board(vx, vy, jackscrews) or not obstacles.holes_clear(vx, vy):
            continue
        if not obstacles.clear(net, (vx, vy), (vx, vy), VIA_D / 2, (pc.F_Cu, pc.B_Cu)):
            continue
        if not obstacles.clear(net, (px, py), (vx, vy), w / 2, (pc.F_Cu,)):
            continue
        return (px, py), (vx, vy), w
    return None


def strap_to_neighbour(pad, fp, net, dropped, obstacles):
    """Fallback for a pad with no via spot: a short track to an adjacent
    pin of the same IC and net that already has a via drop."""
    pc = obstacles.pcbnew
    px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
    size = pad.GetSize(pc.F_Cu)
    w = min(STUB_W, 0.75 * mm(min(size.x, size.y)))
    for other in sorted(fp.Pads(), key=lambda o: math.hypot(mm(o.GetPosition().x) - px, mm(o.GetPosition().y) - py)):
        ox, oy = mm(other.GetPosition().x), mm(other.GetPosition().y)
        if other.GetNetname() != net or other.GetNumber() + "@" + fp.GetReference() not in dropped:
            continue
        if math.hypot(ox - px, oy - py) > 1.0:
            break
        if obstacles.clear(net, (px, py), (ox, oy), w / 2, (pc.F_Cu,)):
            obstacles.add_stub(net, (px, py), (ox, oy), w)
            return {"start": [px, py], "end": [ox, oy], "width": w, "layer": "F.Cu", "net": net}
    return None


def ep_vias(pad, obstacles):
    """Grid of vias inside a large (exposed) pad."""
    pc = obstacles.pcbnew
    bb = pad.GetBoundingBox()
    x0, x1 = mm(bb.GetLeft()) + 0.5, mm(bb.GetRight()) - 0.5
    y0, y1 = mm(bb.GetTop()) + 0.5, mm(bb.GetBottom()) - 0.5
    nx, ny = int((x1 - x0) / EP_PITCH) + 1, int((y1 - y0) / EP_PITCH) + 1
    ox, oy = (x0 + x1 - (nx - 1) * EP_PITCH) / 2, (y0 + y1 - (ny - 1) * EP_PITCH) / 2
    out = []
    for i in range(nx):
        for j in range(ny):
            x, y = ox + i * EP_PITCH, oy + j * EP_PITCH
            if pad.HitTest(pc.VECTOR2I(nm(x), nm(y))) and obstacles.holes_clear(x, y):
                out.append((x, y))
                obstacles.add_via(pad.GetNetname(), x, y)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="add the stubs and vias to the layout")
    args = ap.parse_args()

    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    obstacles = Obstacles(board)
    jackscrews = [
        (mm(p.GetPosition().x), mm(p.GetPosition().y))
        for fp in board.GetFootprints() if "DD50" in fp.GetFPIDAsString()
        for p in fp.Pads() if p.GetNumber() in ("S1", "S2")
    ]
    if len(jackscrews) != 2:
        sys.exit("DD-50 jackscrew pads S1/S2 not found")
    pins = ic_pins(board)

    pads = [
        (fp, pad) for fp in board.GetFootprints() for pad in fp.Pads()
        if pad.GetNetname() in PLANE_NETS and pad.IsOnLayer(pcbnew.F_Cu)
        and pad.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN)
    ]
    # tight spots first: IC pins, then the rest, west to east
    pads.sort(key=lambda fp_pad: (len(fp_pad[0].Pads()) < 6, fp_pad[1].GetPosition().x))

    # what already reaches a plane
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    conn = board.GetConnectivity()
    conn.RecalculateRatsnest()
    done = set()  # pads joined to a plane, or to a pad that gets a via below

    def cluster(pad):
        return conn.GetConnectedItems(pad)

    segments, vias, skipped, failed = [], [], 0, []
    dropped, straps = set(), 0  # pads given a via here; pads strapped to a neighbour
    for fp, pad in pads:
        net = pad.GetNetname()
        pid = (fp.GetReference(), pad.GetNumber())
        items = cluster(pad)
        if pid in done or any(i.GetClass() == "ZONE" for i in items):
            skipped += 1
            continue
        done |= {(i.GetParentFootprint().GetReference(), i.GetNumber()) for i in items if i.GetClass() == "PAD"}
        size = pad.GetSize(pcbnew.F_Cu)
        if mm(size.x) >= EP_MIN and mm(size.y) >= EP_MIN:
            for x, y in ep_vias(pad, obstacles):
                vias.append({"at": [x, y], "size": VIA_D, "drill": VIA_DRILL, "net": net})
            continue
        found = drop(pad, fp, obstacles, jackscrews, pins)
        if found is None:
            strap = strap_to_neighbour(pad, fp, net, dropped, obstacles)
            if strap is None:
                failed.append(f"{fp.GetReference()}.{pad.GetNumber()} ({net})")
            else:
                segments.append(strap)
                straps += 1
            continue
        a, b, w = found
        obstacles.add_via(net, *b)
        obstacles.add_stub(net, a, b, w)
        segments.append({"start": list(a), "end": list(b), "width": w, "layer": "F.Cu", "net": net})
        vias.append({"at": list(b), "size": VIA_D, "drill": VIA_DRILL, "net": net})
        dropped.add(pad.GetNumber() + "@" + fp.GetReference())

    print(f"plane-net SMD pads: {len(pads)}; already connected: {skipped}; "
          f"new vias: {len(vias)} ({len(segments) - straps} stubs); strapped to the next pin: {straps}; "
          f"no spot found: {len(failed)}")
    for f in failed:
        print("   ", f)
    if args.write and (segments or vias):
        import_routing.write_layout({"segments": segments, "vias": vias}, replace=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
