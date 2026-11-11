#!/usr/bin/env python3
"""Autoroute the placed board with Freerouting, then add ground pours.

    /usr/bin/python3 scripts/route_pcb.py [--freerouting PATH.jar] [--java JAVA]
                                          [--passes N] [--skip-route]

Steps: export Specctra DSN -> Freerouting (headless) -> import SES ->
outer-layer ground pours per isolation domain -> zone fill -> save.
The inner planes (In1 GND / ISO_GND, In2 +3V3 / ISO_+5V) are created by
layout_pcb.py and exported to Freerouting as power planes.
"""

import argparse
import os
import pathlib
import subprocess
import sys
import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fanout import fanout  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
PCB = HERE / "pcb" / "solartron_7075_interface.kicad_pcb"
WORK = HERE / "pcb" / "freerouting"

ap = argparse.ArgumentParser()
ap.add_argument("--freerouting", default=os.environ.get("FREEROUTING_JAR", "freerouting.jar"))
ap.add_argument("--java", default=os.environ.get("JAVA", "java"))
ap.add_argument("--passes", type=int, default=100)
ap.add_argument("--skip-route", action="store_true", help="only re-import an existing .ses")
ap.add_argument("--prep-only", metavar="OUT", help="stop after hand fan-out + plane vias, save to OUT")
args = ap.parse_args()

mm = pcbnew.FromMM
WORK.mkdir(exist_ok=True)
dsn = WORK / "solartron_7075_interface.dsn"
ses = WORK / "solartron_7075_interface.ses"

board = pcbnew.LoadBoard(str(PCB))

# Remove any previous routing / outer pours so the script is re-runnable.
for t in list(board.GetTracks()):
    board.Remove(t)
for z in list(board.Zones()):
    if not z.GetIsRuleArea() and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
        board.Remove(z)

# ---------------------------------------------------------------------------
# Hand fan-out for the RP2354A supply pins (0.4 mm pitch QFN): short locked
# F.Cu tracks from each supply pin to its decoupling cap. Coordinates assume
# U1 at (95, 17), rotated 180 deg, as placed by layout_pcb.py.
# ---------------------------------------------------------------------------
def pad_at(ref, num):
    f = board.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber() == str(num):
            q = p.GetPosition()
            return pcbnew.ToMM(q.x), pcbnew.ToMM(q.y), p
    raise KeyError(f"{ref}.{num}")


def track(net, pts, width=0.2):
    n = board.FindNet(net)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(width))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(n)
        t.SetLocked(True)
        board.Add(t)


def via(net, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetWidth(mm(0.6))
    v.SetDrill(mm(0.3))
    v.SetNet(board.FindNet(net))
    v.SetLocked(True)
    board.Add(v)


def P(ref, num):
    x, y, _ = pad_at(ref, num)
    return (x, y)


u1 = board.FindFootprintByReference("U1")
assert abs(pcbnew.ToMM(u1.GetPosition().x) - 95.0) < 1e-3 and abs(u1.GetOrientationDegrees() - 180) < 1e-3
c = lambda ref: P(ref, 1)
# left edge
track("+3V3", [P("U1", 38), c("C9")])
track("+1V1_DVDD", [P("U1", 39), (90.85, 17.4), (c("C18")[0], 17.97), c("C18")])
track("+3V3", [P("U1", 44), (c("C12")[0] + 0.1, 19.4), c("C12")])
track("+3V3", [P("U1", 45), (c("C12")[0] + 0.3, 19.8), c("C12")])
track("+3V3", [c("C12"), c("C10")])
track("VREG_AVDD", [P("U1", 46), (92.2, 20.95), (91.55, 21.6), c("C15")])
track("VREG_AVDD", [c("C15"), P("R3", 2)])
# bottom edge
track("GND", [P("U1", 47), (92.6, 21.2), (92.3, 21.5), (92.3, 21.75)])
via("GND", 92.3, 21.75)
track("VREG_LX", [P("U1", 48), (93.0, 22.2), (P("L1", 1)[0], 22.5), P("L1", 1)])
track("+3V3", [P("U1", 49), (93.4, 19.45), (95.0, 19.45), P("U1", 53)])   # VIN -> 53 (inside the pad ring)
track("+3V3", [P("U1", 53), (95.0, 21.2), (95.4, 21.6), (c("C14")[0], 21.6), c("C14")])
track("+3V3", [P("U1", 54), (95.4, 21.6)])
track("+3V3", [(95.4, 21.6), (95.6, 22.25)])   # plane via for the VIN/53/54 cluster
via("+3V3", 95.6, 22.25)
track("+3V3", [(c("C14")[0], 21.6), (c("C11")[0], 21.6), (c("C13")[0], 21.6), c("C13")])
track("+3V3", [(c("C11")[0], 21.6), c("C11")])
track("QSPI_SS", [P("U1", 60), (97.8, 21.15), (P("R8", 1)[0], 21.15), P("R8", 1)])
# USB D-/D+ straight down to their 27R series resistors
track("MCU_USB_DM", [P("U1", 51), (94.2, 22.9), (P("R6", 2)[0], 23.35), P("R6", 2)])
track("MCU_USB_DP", [P("U1", 52), (94.6, 22.5), (P("R5", 2)[0], 23.6), P("R5", 2)])
# VREG_FB -> DVDD at the inductor output (keeps the router out from under DP/DM)
track("+1V1_DVDD", [P("U1", 50), (93.8, 25.0), (93.2, 25.6), c("C16")])
track("+1V1_DVDD", [P("L1", 2), (P("L1", 2)[0], 24.9), (c("C16")[0], 25.5), c("C16")])
# top edge
track("+3V3", [P("U1", 30), (92.2, 12.9), (c("C8")[0], 12.9), c("C8")])
track("+3V3", [P("U1", 20), (96.2, 12.7), (99.2, 12.7), (c("C7")[0], 13.22), c("C7")])
track("+1V1_DVDD", [P("U1", 23), (95.0, 12.6), (c("C19")[0], 11.95), c("C19")])
# right edge
track("+3V3", [P("U1", 1), c("C5")])
track("+1V1_DVDD", [P("U1", 6), c("C17")])
track("+3V3", [P("U1", 11), c("C6")])

# Pre-route plane connections (pad -> stub -> via into In1/In2)
n_vias, failed = fanout(board, 76.0, 4.0)
print(f"fan-out: {n_vias} vias; no room for: {', '.join(failed) or 'none'}")

if args.prep_only:
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(args.prep_only)
    raise SystemExit(0)

if not args.skip_route:
    assert pcbnew.ExportSpecctraDSN(board, str(dsn)), "DSN export failed"
    cmd = [args.java, "-jar", args.freerouting, "-de", str(dsn), "-do", str(ses),
           "-mp", str(args.passes), "--gui.enabled=false"]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

assert pcbnew.ImportSpecctraSES(board, str(ses)), "SES import failed"


def cleanup(board):
    """Drop autorouter leftovers: vias/track ends that connect to nothing."""
    plane_nets = {"GND", "ISO_GND", "+3V3", "ISO_+5V"}
    removed = 0
    while True:
        pads = [p for f in board.GetFootprints() for p in f.Pads()]
        items = list(board.GetTracks())
        ends = {}
        for t in items:
            if t.GetClass() == "PCB_VIA":
                continue
            for pt in (t.GetStart(), t.GetEnd()):
                ends.setdefault((pt.x, pt.y, t.GetNetCode()), []).append(t)
        vias = {(t.GetPosition().x, t.GetPosition().y, t.GetNetCode()): t
                for t in items if t.GetClass() == "PCB_VIA"}

        def on_pad(pt, net, layer=None):
            for p in pads:
                if p.GetNetCode() == net and p.HitTest(pt) and (layer is None or p.IsOnLayer(layer)):
                    return True
            return False

        dead = []
        for key, v in vias.items():
            if v.GetNetname() in plane_nets:
                continue  # plane via: the inner plane is its second connection
            layers = {t.GetLayer() for t in ends.get(key, [])}
            if len(layers) < 2 and not on_pad(v.GetPosition(), v.GetNetCode()):
                dead.append(v)
        for t in items:
            if t.GetClass() == "PCB_VIA" or t in dead:
                continue
            for pt in (t.GetStart(), t.GetEnd()):
                key = (pt.x, pt.y, t.GetNetCode())
                if len(ends.get(key, [])) > 1 or key in vias or on_pad(pt, t.GetNetCode(), t.GetLayer()):
                    continue
                dead.append(t)
                break
        if not dead:
            return removed
        for t in dead:
            board.Remove(t)
        removed += len(dead)


print("cleanup removed", cleanup(board), "dangling items")

# Outer-layer ground pours: copies of the In1 ground planes on F.Cu and B.Cu.
for src in [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.In1_Cu]:
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = src.Duplicate(False)
        z.SetLayer(layer)
        board.Add(z)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(str(PCB))
print("saved", PCB)
