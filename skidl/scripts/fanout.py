"""Plane fan-out: give every SMD pad on a plane net a short stub and a via.

Freerouting treats the inner planes as conduction areas but leaves most
pad-to-plane connections unrouted, so this pre-routes them: for each SMD pad
on GND / ISO_GND / +3V3 / ISO_+5V a via is dropped just outside the pad
(trying the outward direction first), only where it keeps clearance to every
other-net pad and via and stays inside its own plane's domain.
"""

import math
import pcbnew

PLANE_NETS = {
    "GND": "usb", "+3V3": "usb",
    "ISO_GND": "iso", "ISO_+5V": "iso",
}
VIA_D, VIA_DRILL = 0.6, 0.3
TRACK_W = 0.3
CLEAR = 0.22          # via copper to other-net copper
mm = pcbnew.FromMM
to_mm = pcbnew.ToMM


def _pad_rect(p, grow):
    bb = p.GetBoundingBox()
    return (to_mm(bb.GetLeft()) - grow, to_mm(bb.GetTop()) - grow,
            to_mm(bb.GetRight()) + grow, to_mm(bb.GetBottom()) + grow)


def _in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def fanout(board, iso_x, gap, skip_refs=()):
    pads = [p for f in board.GetFootprints() for p in f.Pads()]
    vias, tracks = [], []
    for t in board.GetTracks():  # respect anything already routed
        if t.GetClass() == "PCB_VIA":
            q = t.GetPosition()
            vias.append((to_mm(q.x), to_mm(q.y), t.GetNetname()))
        else:
            a, b = t.GetStart(), t.GetEnd()
            tracks.append((to_mm(a.x), to_mm(a.y), to_mm(b.x), to_mm(b.y), t.GetNetname()))
    bb = board.GetBoardEdgesBoundingBox()
    W, H = to_mm(bb.GetRight()), to_mm(bb.GetBottom())
    gl, gr = iso_x - gap / 2, iso_x + gap / 2
    rule_areas = [z for z in board.Zones() if z.GetIsRuleArea()]

    def ok(x, y, net, own_pad):
        r = VIA_D / 2
        if not (r + 0.4 <= x <= W - r - 0.4 and r + 0.4 <= y <= H - r - 0.4):
            return False
        dom = PLANE_NETS[net]
        if dom == "iso" and x > gl - r - 0.3:
            return False
        if dom == "usb" and x < gr + r + 0.3:
            return False
        for z in rule_areas:
            if z.Outline().Collide(pcbnew.VECTOR2I(mm(x), mm(y)), mm(r)):
                return False
        for p in pads:
            if p is own_pad:
                continue
            same = p.GetNetname() == net
            g = r + (0.1 if same else CLEAR)
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) or \
                    p.IsOnLayer(own_pad.GetLayer()):
                if _in_rect(x, y, _pad_rect(p, g)):
                    return False
            elif _in_rect(x, y, _pad_rect(p, r + 0.1)):
                # Pad on the other side: keep vias off them too.
                return False
        for vx, vy, vnet in vias:
            if math.hypot(vx - x, vy - y) < VIA_D + (0.15 if vnet == net else CLEAR):
                return False
        for (x1, y1, x2, y2, tnet) in tracks:
            if tnet == net:
                continue
            if _seg_dist(x, y, x1, y1, x2, y2) < r + TRACK_W / 2 + CLEAR:
                return False
        # The stub from the pad to the via must clear other-net pads and tracks
        pc = own_pad.GetPosition()
        sx, sy = to_mm(pc.x), to_mm(pc.y)
        for (x1, y1, x2, y2, tnet) in tracks:
            if tnet != net and _seg_seg_dist(sx, sy, x, y, x1, y1, x2, y2) < TRACK_W + CLEAR:
                return False
        steps = max(2, int(math.hypot(x - sx, y - sy) / 0.1))
        for p in pads:
            if p is own_pad or p.GetNetname() == net or not p.IsOnLayer(own_pad.GetLayer()):
                continue
            rect = _pad_rect(p, TRACK_W / 2 + CLEAR)
            for k in range(steps + 1):
                t = k / steps
                if _in_rect(sx + (x - sx) * t, sy + (y - sy) * t, rect):
                    return False
        return True

    added = 0
    failed = []
    for f in board.GetFootprints():
        if f.GetReference() in skip_refs:
            continue
        fc = f.GetPosition()
        for p in f.Pads():
            net = p.GetNetname()
            if net not in PLANE_NETS or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if p.GetSize().x < mm(0.3) or p.GetSize().y < mm(0.3):
                continue  # fine-pitch IC pins connect through their decoupling caps
            if min(p.GetSize().x, p.GetSize().y) > mm(2.5):
                continue  # exposed pads carry their own thermal vias
            if p.GetShape() == pcbnew.PAD_SHAPE_CUSTOM:
                continue  # e.g. SOT-89 tab: left to the pour / autorouter
            pc = p.GetPosition()
            px, py = to_mm(pc.x), to_mm(pc.y)
            # Outward direction: from the footprint centre through the pad
            dx, dy = px - to_mm(fc.x), py - to_mm(fc.y)
            if abs(dx) < 1e-3 and abs(dy) < 1e-3:
                dx, dy = 0.0, -1.0
            if abs(dx) >= abs(dy):
                out = (math.copysign(1, dx), 0.0)
            else:
                out = (0.0, math.copysign(1, dy))
            half = max(to_mm(p.GetSize().x), to_mm(p.GetSize().y)) / 2
            dirs = [out, (out[1], out[0]), (-out[1], -out[0]),
                    (out[0] + out[1], out[1] + out[0]), (out[0] - out[1], out[1] - out[0]),
                    (-out[0], -out[1])]
            done = False
            for d in (half + 0.55, half + 0.85, half + 1.25, half + 1.7):
                for ux, uy in dirs:
                    n = math.hypot(ux, uy)
                    vx, vy = px + ux / n * d, py + uy / n * d
                    if ok(vx, vy, net, p):
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy)))
                        v.SetWidth(mm(VIA_D))
                        v.SetDrill(mm(VIA_DRILL))
                        v.SetNet(p.GetNet())
                        board.Add(v)
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(pc)
                        t.SetEnd(v.GetPosition())
                        t.SetWidth(mm(TRACK_W))
                        t.SetLayer(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                        t.SetNet(p.GetNet())
                        board.Add(t)
                        vias.append((vx, vy, net))
                        tracks.append((px, py, vx, vy, net))
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                failed.append(f"{f.GetReference()}.{p.GetNumber()}")
    return added, failed


def _seg_dist(x, y, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    L = vx * vx + vy * vy
    t = 0 if L == 0 else max(0, min(1, ((x - x1) * vx + (y - y1) * vy) / L))
    return math.hypot(x - (x1 + t * vx), y - (y1 + t * vy))


def _seg_seg_dist(ax, ay, bx, by, cx, cy, dx, dy):
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    A, B, Cp, D = (ax, ay), (bx, by), (cx, cy), (dx, dy)
    d1, d2 = cross(Cp, D, A), cross(Cp, D, B)
    d3, d4 = cross(A, B, Cp), cross(A, B, D)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(_seg_dist(ax, ay, cx, cy, dx, dy), _seg_dist(bx, by, cx, cy, dx, dy),
               _seg_dist(cx, cy, ax, ay, bx, by), _seg_dist(dx, dy, ax, ay, bx, by))
