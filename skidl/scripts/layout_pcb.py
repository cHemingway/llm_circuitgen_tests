#!/usr/bin/env python3
"""Place the SKiDL-generated board and add outline, stack-up, rules and zones.

Input : output/solartron_7075_interface_unplaced.kicad_pcb  (from SKiDL / kinet2pcb)
Output: pcb/solartron_7075_interface.kicad_pcb               (placed, unrouted)

Run with KiCad's Python (needs the pcbnew module):
    /usr/bin/python3 scripts/layout_pcb.py

Board (top view, 4 layers, 1.6 mm):
  * J1 (DD-50 plug) on the BOTTOM side, left half: it plugs straight into the
    Solartron's 50-way socket and its two jackscrews hold the board flat on
    the back of the instrument.
  * Meter-side logic (74HCT165 x5, 74HC595 x2, resistor arrays) in the strips
    above and below J1's pin field.
  * A 4 mm copper-free isolation gap at x = ISO_X, crossed only by the five
    TLP2361 optocouplers and the B0509S isolated DC/DC module.
  * USB side (RP2354A, LDO, ESD, vertical USB-B on the TOP side) on the right.
"""

import math
import pathlib
import pcbnew

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE / "output" / "solartron_7075_interface_unplaced.kicad_pcb"
DST_DIR = HERE / "pcb"
DST = DST_DIR / "solartron_7075_interface.kicad_pcb"

W, H = 112.0, 44.0          # board size, mm
J1_C = (36.0, 22.0)         # centre of J1's pin field
ISO_X = 76.0                # centre of the isolation gap
ISO_GAP = 4.0               # copper-free gap width

mm = pcbnew.FromMM


def v(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


board = pcbnew.LoadBoard(str(SRC))


def fp(ref):
    f = board.FindFootprintByReference(ref)
    assert f, ref
    return f


def pad(ref, num):
    for p in fp(ref).Pads():
        if p.GetNumber() == str(num):
            return p
    raise KeyError(f"{ref}.{num}")


def pad_xy(ref, num):
    p = pad(ref, num).GetPosition()
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def pads_centre(f):
    xs = [p.GetPosition().x for p in f.Pads()]
    ys = [p.GetPosition().y for p in f.Pads()]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def place(ref, x, y, rot=0.0, bottom=False, cond=None):
    """Put the centre of ref's pads at (x, y).

    rot is the orientation in degrees; if cond is given, the four 90-degree
    orientations are tried (starting at rot) and the first for which
    cond(footprint) is true is kept.
    """
    f = fp(ref)
    if bottom and not f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for k in range(4):
        f.SetOrientationDegrees((rot + 90 * k) % 360)
        if cond is None or cond(f):
            break
    else:
        raise RuntimeError(f"no orientation satisfies condition for {ref}")
    cx, cy = pads_centre(f)
    pos = f.GetPosition()
    f.SetPosition(pcbnew.VECTOR2I(int(pos.x + mm(x) - cx), int(pos.y + mm(y) - cy)))
    return f


def px(f, num):
    for p in f.Pads():
        if p.GetNumber() == str(num):
            return p.GetPosition()
    raise KeyError(num)


def near(ref, ic, pin, dist=1.9, along=0.0, rot=None):
    """Place a 2-pad part just outside pad `pin` of `ic` (decoupling caps etc.)."""
    icf = fp(ic)
    c = icf.GetPosition()
    p = px(icf, pin)
    dx, dy = p.x - c.x, p.y - c.y
    # Unit vector pointing away from the IC body, snapped to the nearest axis
    if abs(dx) >= abs(dy):
        ux, uy = (1 if dx > 0 else -1), 0
    else:
        ux, uy = 0, (1 if dy > 0 else -1)
    x = pcbnew.ToMM(p.x) + ux * dist - uy * along
    y = pcbnew.ToMM(p.y) + uy * dist + ux * along
    if rot is None:
        rot = 90 if ux else 0  # cap body perpendicular to the IC edge
    place(ref, x, y, rot)


def at(ref, x, y, axis="h", toward=None, pad_num=1):
    """Place a 2-pad part at (x, y), body horizontal ('h') or vertical ('v').

    If `toward` = (ic_ref, pin) is given, the orientation is chosen so that
    pad `pad_num` is the one nearest that IC pin (short supply/signal stub,
    ground pad on the far side).
    """
    rots = (0, 180) if axis == "h" else (90, 270)
    best = None
    for r in rots:
        place(ref, x, y, r)
        if toward is None:
            return
        q = px(fp(toward[0]), toward[1])
        p1 = px(fp(ref), pad_num)
        d = math.hypot(p1.x - q.x, p1.y - q.y)
        if best is None or d < best[0]:
            best = (d, r)
    place(ref, x, y, best[1])


# ---------------------------------------------------------------------------
# Clean-up of the kinet2pcb output
# ---------------------------------------------------------------------------
# kinet2pcb puts every SKiDL no-connect pin on one net called "__NOCONNECT";
# that would tie all unused pins together, so detach them.
nc = board.FindNet("__NOCONNECT")
if nc:
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == "__NOCONNECT":
                p.SetNet(board.FindNet(""))  # net 0 = unconnected
    board.Remove(nc) if hasattr(board, "Remove") else None

# ---------------------------------------------------------------------------
# Stack-up and design rules (JLCPCB 4-layer capabilities, with margin)
# ---------------------------------------------------------------------------
board.SetCopperLayerCount(4)
board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)   # solid ground planes
board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)   # +3V3 / ISO_+5V planes

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = mm(0.1)   # autorouter neck-downs at fine-pitch pins (JLC 4-layer: 0.09 mm)
ds.m_MinClearance = mm(0.15)
ds.m_ViasMinSize = mm(0.5)
ds.m_MinThroughDrill = mm(0.2)  # QFN thermal vias are 0.2 mm
ds.m_HoleClearance = mm(0.25)
ds.m_CopperEdgeClearance = mm(0.3)
ds.m_SolderMaskMinWidth = mm(0.0)

netclasses = ds.m_NetSettings
default_nc = netclasses.GetDefaultNetclass()
default_nc.SetClearance(mm(0.18))
default_nc.SetTrackWidth(mm(0.2))
default_nc.SetViaDiameter(mm(0.6))
default_nc.SetViaDrill(mm(0.3))

power = pcbnew.NETCLASS("Power")
power.SetClearance(mm(0.2))
power.SetTrackWidth(mm(0.4))
power.SetViaDiameter(mm(0.7))
power.SetViaDrill(mm(0.35))
netclasses.SetNetclass("Power", power)
# GND / +3V3 / DVDD / LX stay at 0.2 mm: they have to leave the RP2354A's
# 0.4 mm-pitch pads (and are fed mostly through the inner planes anyway).
for n in ("VBUS_RAW", "+5V_USB", "ISO_+9V", "ISO_+5V", "ISO_GND"):
    netclasses.SetNetclassPatternAssignment(n, "Power")

# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------
jx, jy = J1_C


# J1 on the bottom: row 3 (pins 34-50, meter inputs) towards the top edge,
# pin 1 at the left -> pins 1-36 (meter outputs) mostly face the bottom strip.
def j1_ok(f):
    p1, p17, p34 = px(f, 1), px(f, 17), px(f, 34)
    return p1.x < p17.x and p34.y < p1.y


place("J1", jx, jy, 0, bottom=True, cond=j1_ok)

# --- Bottom strip: 4 x 74HCT165 fed by row 1 and row 2 of J1 ---------------
# (ref, x) ; each register gets two resistor arrays directly above it.
SR_Y = 36.6
RN_Y = 28.6
bottom_regs = [("U13", 17.0, ("RN7", "RN8")),   # pins 18-25  10^1, 10^0
               ("U12", 29.0, ("RN5", "RN6")),   # pins 2-9    10^5, 10^4
               ("U10", 41.0, ("RN1", "RN2")),   # pins 26-33  status
               ("U11", 53.0, ("RN3", "RN4"))]   # pins 10-17  10^3, 10^2
for ref, x, (rn_a, rn_b) in bottom_regs:
    # pin 1 top-left: D4..D7 (pins 3-6) on the left column, D0..D3 on the right
    place(ref, x, SR_Y, 0, cond=lambda f: px(f, 1).x < px(f, 16).x and px(f, 1).y < px(f, 8).y)
    # Rn.1-4 (connector side) on top, Rn.5-8 (register side) below
    for rn, dx in ((rn_a, +2.6), (rn_b, -2.6)):
        place(rn, x + dx, RN_Y, 0, cond=lambda f: px(f, 1).y < px(f, 8).y)

# Decoupling for the bottom-strip registers: right of VCC (pin 16)
for ref, x, _ in bottom_regs:
    cap = {"U10": "C26", "U11": "C27", "U12": "C28", "U13": "C29"}[ref]
    at(cap, x + 5.6, SR_Y - 4.4, "h", (ref, 16))

# --- Top strip: U14 (status 165) + 2 x 74HC595 driving row 3 ---------------
TOP_Y = 9.0
place("U14", 13.5, TOP_Y, 0, cond=lambda f: px(f, 1).x < px(f, 16).x and px(f, 1).y < px(f, 8).y)
place("RN9", 15.5, 16.6, 0, cond=lambda f: px(f, 1).y > px(f, 8).y)
at("C30", 13.5 + 5.6, TOP_Y - 4.4, "h", ("U14", 16))

place("U15", 31.0, TOP_Y, 0, cond=lambda f: px(f, 1).x < px(f, 16).x and px(f, 1).y < px(f, 8).y)
place("U16", 45.0, TOP_Y, 0, cond=lambda f: px(f, 1).x < px(f, 16).x and px(f, 1).y < px(f, 8).y)
at("C31", 31.0 + 5.6, TOP_Y - 4.4, "h", ("U15", 16))
at("C32", 45.0 + 5.6, TOP_Y - 4.4, "h", ("U16", 16))

# CONTACT SAMPLE MOSFET + gate pull-down, REMOTE LED
place("Q1", 24.0, 15.0, 0)
place("R12", 24.0, 11.5, 90)
place("D4", 55.5, 3.0, 0)
place("R13", 55.5, 6.0, 0)

# --- Isolation barrier: 5 optocouplers + DC/DC -------------------------------
# Forward channels (U5-U8): LED (pins 1,3) on the USB side (right).
# Return channel (U9): LED on the meter side (left), detector on the USB side.
opto_rows = [("U5", 5.0), ("U6", 11.0), ("U7", 17.0), ("U8", 23.0), ("U9", 29.0)]
for ref, y in opto_rows:
    led_right = ref != "U9"
    place(ref, ISO_X, y, 0,
          cond=(lambda f: px(f, 1).x > px(f, 4).x) if led_right else (lambda f: px(f, 1).x < px(f, 4).x))

# LED resistors on the LED side, detector decoupling on the detector side
for ref, y in opto_rows[:4]:
    r = {"U5": "R14", "U6": "R15", "U7": "R16", "U8": "R17"}[ref]
    c = {"U5": "C33", "U6": "C34", "U7": "C35", "U8": "C36"}[ref]
    place(r, ISO_X + 5.9, y, 90)
    place(c, ISO_X - 5.9, y, 90)
place("R18", ISO_X - 5.9, 29.0, 90)
place("C37", ISO_X + 5.9, 29.0, 90)

# B0509S: pins 1,2 (USB 5 V) right of the gap, pins 3,4 (isolated 9 V) left
place("PS1", ISO_X, 38.5, 0, cond=lambda f: px(f, 1).x > px(f, 4).x)
place("C22", ISO_X + 7.6, 38.5, 90)      # module input cap
place("C23", 67.6, 41.6, 0)              # module output cap
place("R10", 67.6, 36.0, 0)              # minimum-load bleed

# 78L05 and the meter-side supply
place("U4", 63.0, 37.5, 180)
place("C24", 63.0, 41.9, 0)
place("C25", 66.0, 33.0, 0)
place("D3", 62.0, 31.2, 0)
place("R11", 62.0, 33.0, 0)

# --- USB side ---------------------------------------------------------------
# RP2354A rotated 180 deg: GPIO20-24 (pins 32-36) face the optocouplers,
# the VREG/USB pins (46-54) face the USB connector below, XIN/XOUT/SWD/RUN
# (pins 21-26) face up.
U1 = ("U1",)
place("U1", 95.0, 17.0, 180)
for p_ in fp("U1").Pads():  # exposed pad + its thermal vias: solid to the planes
    if p_.GetNumber() == "61":
        p_.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    elif p_.GetNumber() == "47":  # VREG_PGND: has its own track + via
        p_.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
u1 = lambda pin: ("U1", pin)
# Left edge supplies (pins 38, 39, 44, 45) - below the GPIO fan-out.
# Hand-made fan-out tracks for these pins are added by route_pcb.py.
at("C9", 89.8, 17.0, "h", u1(38))
at("C18", 89.8, 18.2, "h", u1(39))
at("C12", 89.8, 19.5, "h", u1(44))     # pins 44 + 45
at("C10", 89.8, 20.55, "h", u1(45))
at("C15", 89.8, 21.6, "h", u1(46))     # VREG_AVDD 4.7u
at("R3", 90.28, 23.1, "v", ("C15", 1), pad_num=2)  # 33R from 3V3
# Right edge (pins 1, 6, 11; GPIO5 = pin 8 status LED exits between them)
at("C5", 100.35, 19.8, "h", u1(1))
at("C17", 100.35, 17.8, "h", u1(6))
at("C6", 100.35, 15.8, "h", u1(11))
at("C7", 100.35, 13.9, "h", u1(20))     # IOVDD pin 20 (top edge, right corner)
at("C8", 89.8, 13.3, "h", u1(30))      # IOVDD pin 30 (top edge, left corner)
at("C19", 94.35, 10.8, "v", u1(23))    # DVDD pin 23
# Crystal above the chip, XOUT through R4
place("Y1", 96.6, 7.2, 180, cond=lambda f: px(f, 1).x > px(f, 3).x)
at("R4", 95.45, 9.9, "v", u1(22), pad_num=1)
at("C20", 99.6, 6.4, "v")
at("C21", 93.6, 7.6, "v")
# Core regulator below-left of the chip: LX (pin 48) drops straight into L1,
# VREG_VIN (49) is tied to pins 53/54 (+3V3) and their caps, C14 = 4.7u.
place("L1", 92.0, 23.4, 0, cond=lambda f: px(f, 1).x > px(f, 2).x)
place("C16", 91.4, 25.6, 0, cond=lambda f: px(f, 1).x > px(f, 2).x)  # DVDD 4.7u, pad 1 right
at("C14", 96.8, 22.4, "v", u1(53))     # VREG_VIN / 3V3 4.7u
at("C11", 97.85, 22.4, "v", u1(53))    # USB_OTP_VDD 100n
at("C13", 98.9, 22.4, "v", u1(54))     # QSPI_IOVDD 100n
at("R8", 100.1, 22.6, "v", u1(60))     # BOOTSEL series 1k
# USB series resistors under DP/DM
at("R6", 94.65, 24.4, "v", u1(51), pad_num=2)  # pad 2 = MCU side
at("R5", 95.7, 24.4, "v", u1(52), pad_num=2)
# Buttons, SWD, LEDs
place("SW2", 87.5, 3.8, 0)             # RESET (top left of the USB side)
at("R7", 91.9, 9.4, "v")               # RUN pull-up
place("J3", 96.0, 2.6, 90)             # SWD header, along the top edge
place("SW1", 106.0, 22.0, 90)          # BOOTSEL
at("D2", 104.2, 13.0, "h")             # status LED (GPIO5)
at("R9", 104.2, 15.0, "h")
at("D1", 108.5, 13.0, "h")             # 3V3 power LED
at("R2", 108.5, 15.0, "h")
# USB connector, ESD, fuse, LDO
place("J2", 104.0, 36.2, 0)
place("U3", 98.0, 28.0, 90)
at("C1", 109.5, 26.7, "h")             # shield RC
at("R1", 109.5, 28.5, "h")
place("F1", 90.0, 41.8, 0)
at("C2", 94.0, 41.8, "h")
place("U2", 88.0, 33.5, 0)             # AP2112K-3.3
at("C3", 88.0, 37.0, "h")
at("C4", 91.6, 33.5, "v")

# ---------------------------------------------------------------------------
# Board outline (plain rectangle)
# ---------------------------------------------------------------------------
for d in list(board.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(d)
rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECTANGLE)
rect.SetStart(v(0, 0))
rect.SetEnd(v(W, H))
rect.SetLayer(pcbnew.Edge_Cuts)
rect.SetWidth(mm(0.1))
board.Add(rect)


# ---------------------------------------------------------------------------
# Zones: ground planes per domain, isolation keep-out
# ---------------------------------------------------------------------------
def zone(net, layer, pts, prio=0, name=None):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    if name:
        z.SetZoneName(name)
    board.Add(z)
    return z


gl, gr = ISO_X - ISO_GAP / 2, ISO_X + ISO_GAP / 2
# Around the DC/DC module the domains come closer (its pins are 2.54 mm apart),
# so the plane outlines step in to reach its pads.
ps_top = min(pcbnew.ToMM(p.GetPosition().y) for p in fp("PS1").Pads()) - 3.0
ps_bot = min(H - 0.5, max(pcbnew.ToMM(p.GetPosition().y) for p in fp("PS1").Pads()) + 3.0)
NOTCH = 0.4
iso_poly = [(0, 0), (gl, 0), (gl, ps_top), (ISO_X - NOTCH, ps_top), (ISO_X - NOTCH, ps_bot),
            (gl, ps_bot), (gl, H), (0, H)]
usb_poly = [(gr, 0), (W, 0), (W, H), (gr, H), (gr, ps_bot), (ISO_X + NOTCH, ps_bot),
            (ISO_X + NOTCH, ps_top), (gr, ps_top)]
# In1: ground planes; In2: supply planes. (Outer-layer ground pours are added
# by route_pcb.py after autorouting, so the router sees them as free space.)
zone("ISO_GND", pcbnew.In1_Cu, iso_poly, name="ISO_GND")
zone("GND", pcbnew.In1_Cu, usb_poly, name="GND")
zone("ISO_+5V", pcbnew.In2_Cu, iso_poly, name="ISO_+5V")
zone("+3V3", pcbnew.In2_Cu, usb_poly, name="+3V3")

# Copper keep-out down the isolation gap (all layers). The DC/DC module's
# 2.54 mm pin pitch can't honour the full gap, so the keep-out narrows to
# 0.8 mm between its input and output pins.


def keepout(pts, name="ISOLATION_GAP"):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    board.Add(z)


keepout([(gl, 0), (gr, 0), (gr, ps_top), (gl, ps_top)])
keepout([(gl, ps_bot), (gr, ps_bot), (gr, H), (gl, H)])
# Narrow keep-out between the DC/DC module's input and output pins
keepout([(ISO_X - NOTCH, ps_top), (ISO_X + NOTCH, ps_top), (ISO_X + NOTCH, ps_bot), (ISO_X - NOTCH, ps_bot)])
# 0.5 mm routing keep-out ring along the board edge (the autorouter only
# knows its own clearance to the outline)
E = 0.5
for pts in ([(0, 0), (W, 0), (W, E), (0, E)], [(0, H - E), (W, H - E), (W, H), (0, H)],
            [(0, 0), (E, 0), (E, H), (0, H)], [(W - E, 0), (W, 0), (W, H), (W - E, H)]):
    keepout(pts, "EDGE")

# ---------------------------------------------------------------------------
# Silkscreen notes
# ---------------------------------------------------------------------------
def text(s, x, y, layer=pcbnew.F_SilkS, size=1.0, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(v(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetMirrored(mirror)
    board.Add(t)


text("SOLARTRON 7075 USB IF", 38.0, 1.4, size=1.0)
text("ISOLATED (METER EARTH)", 38.0, 43.0, size=0.8)
text("USB (HOST GND)", 103.0, 42.9, size=0.8)
text("J1 TO 7075 SKB", 36.0, 33.5, layer=pcbnew.B_SilkS, size=1.5, mirror=True)
text("4-40 UNC JACKSCREWS", 36.0, 36.0, layer=pcbnew.B_SilkS, size=1.0, mirror=True)

# Reference designators: small passives are too dense for readable silk, so
# their references stay on the fab layer only; everything else keeps silk
# references at 0.8 mm.
for f in board.GetFootprints():
    ref = f.Reference()
    r = f.GetReference()
    small = r[0] in "RCLF" or r.startswith("RN") or (r.startswith("D") and r[1:].isdigit())
    if small:
        ref.SetVisible(False)
    else:
        ref.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        ref.SetTextThickness(mm(0.12))
        # centre the reference on the part body (clear of the pads)
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
        cx_, cy_ = (cy.GetLeft() + cy.GetRight()) // 2, (cy.GetTop() + cy.GetBottom()) // 2
        off = {"J1": (0, 4.6), "Q1": (-2.4, 0), "PS1": (0, -4.6), "J3": (5.6, 0.4),
               "J2": (0, -4.5), "U4": (-4.0, 0), "U1": (-5.6, -5.2), "U3": (2.9, 0),
               "U2": (0, -2.4)}.get(r, (0, 0))
        if r == "Y1":
            ref.SetVisible(False)  # no free silk space next to the crystal
        ref.SetPosition(pcbnew.VECTOR2I(cx_ + mm(off[0]), cy_ + mm(off[1])))
        ref.SetTextAngleDegrees(0)

DST_DIR.mkdir(exist_ok=True)
board.Save(str(DST))
# Project library tables so KiCad finds the local DD-50 symbol/footprint
(DST_DIR / "fp-lib-table").write_text(
    '(fp_lib_table\n  (version 7)\n'
    '  (lib (name "Solartron7075")(type "KiCad")(uri "${KIPRJMOD}/../lib/Solartron7075.pretty")'
    '(options "")(descr "DD-50 vertical plug for the Solartron 7075 interface"))\n)\n')
(DST_DIR / "sym-lib-table").write_text(
    '(sym_lib_table\n  (version 7)\n'
    '  (lib (name "Solartron7075")(type "KiCad")(uri "${KIPRJMOD}/../lib/Solartron7075.kicad_sym")'
    '(options "")(descr "DD-50 plug symbol"))\n)\n')
print("saved", DST)
