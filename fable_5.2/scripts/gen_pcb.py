#!/usr/bin/python3
"""Build the PCB (placement, outline, planes, isolation keep-out, pre-routes)
from the schematic netlist using KiCad's pcbnew Python API.

Run with the system Python that ships the pcbnew module (/usr/bin/python3).
Stages:
    gen_pcb.py place     -> <project>.kicad_pcb, unrouted  (+ .kicad_pro / .kicad_dru)
    gen_pcb.py dsn       -> _autoroute/board.dsn for Freerouting
    gen_pcb.py ses       -> import _autoroute/board.ses, fill zones, save
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

import netlist
import pinmap

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))
NAME = 'solartron7075_usb_interface'
PCB = os.path.join(OUT, NAME + '.kicad_pcb')
SCH = os.path.join(OUT, NAME + '.kicad_sch')
AR = os.path.join(OUT, '_autoroute')
KFP = '/usr/share/kicad/footprints/'
LIBNAME = 'solartron7075'

W, H = 116.0, 50.0            # board size, mm
OX, OY = 40.0, 40.0           # board origin on the page
DX, DY = 36.0, 25.0           # centre of the D-sub (J1)
BX = 85.0                     # centre line of the isolation barrier
ISO_EDGE, MCU_EDGE = 81.3, 88.7   # copper limits of the two domains


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


# ---------------------------------------------------------------------------
# placement: ref -> (x, y, rotation, side)
# ---------------------------------------------------------------------------
PL = {}


def put(ref, x, y, rot=0, side='F'):
    PL[ref] = (x, y, rot, side)


put('J1', DX, DY, 0, 'B')

# --- status-input shift registers above the connector -----------------------
CY = 8.3
for ref, cx, ser_hi, ser_lo, cap in (('U11', 10.5, 'RN6', 'RN8', 'C32'), ('U13', 26.0, 'RN14', 'RN16', 'C34'),
                                    ('U12', 41.5, 'RN10', 'RN12', 'C33'), ('U10', 57.0, 'RN2', 'RN4', 'C31')):
    put(ref, cx, CY, 0)
    put(ser_hi, cx + 5.6, CY, 180)      # D0..D3 (pins 11-14, right-hand side)
    put(ser_lo, cx - 5.6, CY, 0)        # D4..D7 (pins 3-6, left-hand side)
    put(cap, cx + 2.2, 1.9, 0)
# pull-down arrays, one row just above the connector pins
for ref, x in (('RN7', 18.6), ('RN15', 22.8), ('RN9', 29.8), ('RN17', 34.0),
               ('RN3', 40.6), ('RN11', 44.8), ('RN5', 51.6), ('RN13', 55.8)):
    put(ref, x, 18.3, 90)

# --- below the connector: command drivers, U14 ------------------------------
put('U16', 19.4, 37.2, 180)
put('U15', 37.4, 37.2, 180)
put('C37', 21.6, 43.8, 180)
put('C36', 39.6, 43.8, 180)
put('Q1', 45.6, 38.4, 0)
put('R25', 45.6, 41.2, 0)
put('R26', 45.2, 35.2, 0)
put('R27', 45.2, 33.2, 0)
put('U14', 57.0, 39.3, 0)
put('RN20', 51.4, 39.3, 0)
put('RN18', 62.6, 39.3, 180)
put('C35', 59.2, 32.9, 0)
put('RN21', 55.3, 31.2, 270)
put('RN19', 50.0, 31.2, 270)

# --- isolated supply and ISO side of the optocouplers ------------------------
put('PS1', 88.81, 4.0, 270)
put('U9', 70.3, 6.6, 180)
put('C27', 77.9, 8.9, 90)
put('C28', 77.9, 5.0, 90)
put('C29', 73.4, 11.9, 0)
put('C30', 70.0, 11.9, 0)
put('U5', BX, 16.0, 180)
put('U6', BX, 27.5, 180)
put('U7', BX, 39.0, 0)
put('R15', 77.2, 17.27, 0)
put('R16', 77.2, 14.73, 0)
put('C22', 74.3, 18.5, 90)
put('R17', 77.2, 28.77, 0)
put('R18', 77.2, 26.23, 0)
put('C23', 74.3, 30.0, 90)
put('R21', 77.2, 35.19, 180)
put('R22', 77.2, 42.81, 180)
put('U8', 71.4, 39.6, 0)
put('C25', 71.4, 33.6, 0)
put('D3', 66.4, 47.6, 0)
put('R23', 69.6, 47.6, 0)
put('R24', 66.5, 20.4, 0)

# --- MCU / USB side ----------------------------------------------------------
put('R12', 92.6, 12.19, 180)
put('R11', 92.6, 19.81, 180)
put('R14', 92.6, 23.69, 180)
put('R13', 92.6, 31.31, 180)
put('C24', 92.6, 35.19, 0)
put('R19', 92.6, 37.73, 180)
put('R20', 92.6, 40.27, 180)
put('J2', 108.5, 5.5, 0)
put('C26', 92.4, 4.0, 90)
put('FB1', 94.4, 4.0, 90)
put('F1', 96.9, 4.2, 90)
put('U2', 94.9, 9.6, 0)
put('C2', 91.9, 9.2, 90)
put('C3', 97.7, 9.6, 90)
put('R1', 93.5, 14.7, 0)
put('C1', 96.5, 14.7, 0)
UX, UY = 106.2, 29.0
put('U1', UX, UY, 0)
put('U3', UX - 0.9, 17.8, 0)
put('U4', 97.0, 22.2, 90)
put('C21', 97.0, 17.3, 0)
put('RN1', 97.0, 27.6, 90)
put('TP1', 97.6, 31.0, 0)
put('TP2', 95.2, 31.0, 0)
# decoupling (power pad towards the chip).  The caps sit beside unused pins so that the
# GPIO (left), crystal and SWD (bottom) escapes stay open; DVDD pins 6 and 23 and
# VREG_FB reach +1V1 through vias under the package (see preroute()).
put('C4', UX - 5.2, UY - 3.7, 180)      # IOVDD pin 1
put('C5', UX - 5.2, UY + 2.3, 180)      # IOVDD pin 11
put('C12', UX - 5.2, UY + 4.0, 180)     # DVDD pin 6 (via under package)
put('C15', UX - 6.0, UY + 6.2, 180)     # 10u bulk
put('C6', UX - 1.9, UY + 5.3, 270)      # IOVDD pin 20
put('C13', UX + 2.0, UY + 5.3, 270)     # DVDD pin 23 (via under package)
put('C7', UX + 3.2, UY + 5.3, 270)      # IOVDD pin 30
put('C8', UX + 5.2, UY + 1.0, 0)        # IOVDD pin 38
put('C14', UX + 5.2, UY - 0.8, 0)       # DVDD pin 39
put('C9', UX + 5.2, UY - 2.7, 0)        # ADC_AVDD / IOVDD pins 44, 45
put('C10', UX - 0.9, UY - 5.3, 90)      # USB_OTP_VDD pin 53
put('C11', UX - 2.0, UY - 5.3, 90)      # QSPI_IOVDD pin 54
# core regulator, Raspberry Pi reference arrangement above pins 47..49
put('C16', UX + 2.0, UY - 5.1, 0)
put('C17', UX + 2.0, UY - 6.1, 0)
put('L1', UX + 2.0, UY - 7.9, 0)
put('C18', UX + 4.8, UY - 4.7, 0)
put('R5', UX + 4.8, UY - 6.0, 180)
put('R2', UX - 0.3, UY - 7.7, 90)
put('R3', UX - 1.4, UY - 7.7, 90)
put('Y1', UX - 2.3, UY + 9.4, 90)
put('R6', UX - 2.6, UY + 6.75, 0)
put('C20', UX - 5.2, UY + 8.3, 180)
put('C19', UX - 1.4, UY + 12.5, 90)
put('R7', UX + 4.9, UY + 7.6, 90)
put('J3', 106.4, 46.5, 0)
put('SW1', 96.2, 45.6, 0)
put('R8', 99.6, 41.4, 0)
put('SW2', 113.0, 44.3, 90)
put('D1', 114.3, 17.9, 90)
put('R10', 114.3, 21.1, 90)
put('D2', 114.3, 32.6, 270)
put('R9', 114.3, 29.4, 90)

# Placement of the multimeter-side parts and the position of the silkscreen titles as
# chosen by scripts/optimise.py (pin swapping + placement search).  The values above are
# the original hand placement and remain the starting point / fallback.
PL_BASE = dict(PL)
SILK = {'title': (34.0, 14.75), 'sub': (30.0, 47.6), 'j1': (4.0, 40.5, 90), 'tx': (97.6, 32.7), 'rx': (95.2, 32.7)}
LAYOUT = os.path.join(HERE, 'layout.json')
if os.path.exists(LAYOUT):
    _lay = json.load(open(LAYOUT))
    for _ref, _v in _lay.get('place', {}).items():
        put(_ref, *_v)
    SILK.update({k: tuple(v) for k, v in _lay.get('silk', {}).items()})

# isolation keep-out rectangles (x1, y1, x2, y2): full width everywhere except in the
# band around the DC-DC converter pins, where only the strip between pins 2 and 3 is kept clear
BARRIER = [(ISO_EDGE + 0.3, 6.6, MCU_EDGE - 0.3, H),
           (ISO_EDGE + 0.3, 0, MCU_EDGE - 0.3, 1.4),
           (BX - 0.8, 1.4, BX + 0.8, 6.6)]

# straddling parts: which pins are on the isolated side
SPLIT = {'U5': ['5', '6', '7', '8'], 'U6': ['5', '6', '7', '8'], 'U7': ['1', '2', '3', '4'], 'PS1': ['3', '4']}


# ---------------------------------------------------------------------------
def domains(comps, nets):
    """Classify every net as 'ISO' (multimeter side) or 'MCU' (USB side)."""
    pin_net = {}
    for n, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[(ref, pin)] = n
    dom = {'GND': 'MCU', '+3V3': 'MCU', 'VBUS': 'MCU', '+1V1': 'MCU', 'GND_ISO': 'ISO', '+5V_ISO': 'ISO', '+9V_ISO': 'ISO'}
    for ref, pins in SPLIT.items():
        for (r, p), n in pin_net.items():
            if r == ref:
                dom.setdefault(n, 'ISO' if p in pins else 'MCU')
    changed = True
    while changed:
        changed = False
        cdom = {}
        for (r, p), n in pin_net.items():
            if r in SPLIT:
                continue
            if n in dom:
                if cdom.get(r, dom[n]) != dom[n]:
                    raise RuntimeError('component %s bridges the isolation barrier' % r)
                cdom[r] = dom[n]
        for (r, p), n in pin_net.items():
            if r in cdom and n not in dom:
                dom[n] = cdom[r]
                changed = True
    missing = [n for n in nets if n not in dom]
    if missing:
        raise RuntimeError('unclassified nets: %s' % missing)
    return dom


CLASSES = {
    # name: (track, clearance)
    'Default': (0.2, 0.15),
    'PWR': (0.3, 0.15),
    'PWR_WIDE': (0.5, 0.15),
    'VREG_LX': (0.15, 0.12),
    'ISO': (0.2, 0.15),
    'ISO_PWR': (0.5, 0.15),
}


def short(net):
    """Net name without the sheet path that KiCad prepends to local labels."""
    return net.rsplit('/', 1)[-1] if net.startswith('/') else net


FULL = {}      # short net name -> full name, filled from the netlist


def net_class(full, dom):
    net = short(full)
    if net == 'VREG_LX':
        return 'VREG_LX'
    if dom[full] == 'ISO':
        return 'ISO_PWR' if net in ('GND_ISO', '+5V_ISO', '+9V_ISO') else 'ISO'
    if net in ('VBUS', 'VBUS_CONN', 'VBUS_DCDC'):
        return 'PWR_WIDE'
    if net in ('GND', '+3V3', '+1V1', 'VREG_AVDD'):
        return 'PWR'
    return 'Default'


def write_project(nets, dom):
    path = os.path.join(OUT, NAME + '.kicad_pro')
    tmp = tempfile.mkdtemp()
    b = pcbnew.NewBoard(os.path.join(tmp, 't.kicad_pcb'))
    pcbnew.SaveBoard(os.path.join(tmp, 't.kicad_pcb'), b)
    pro = json.load(open(os.path.join(tmp, 't.kicad_pro')))
    pro['meta']['filename'] = NAME + '.kicad_pro'
    base = pro['net_settings']['classes'][0]
    classes = []
    for i, (cn, (tw, cl)) in enumerate(CLASSES.items()):
        c = dict(base)
        c.update({'name': cn, 'track_width': tw, 'clearance': cl, 'via_diameter': 0.6, 'via_drill': 0.3})
        if cn != 'Default':
            c['priority'] = i
        classes.append(c)
    pro['net_settings']['classes'] = classes
    pro['net_settings']['netclass_patterns'] = []
    pro['net_settings']['netclass_assignments'] = {n: [net_class(n, dom)] for n in sorted(nets) if net_class(n, dom) != 'Default'}
    r = pro['board']['design_settings']['rules']
    r.update({'min_clearance': 0.12, 'min_track_width': 0.15, 'min_via_diameter': 0.5, 'min_via_annular_width': 0.1,
              'min_through_hole_diameter': 0.3, 'min_hole_clearance': 0.2, 'min_hole_to_hole': 0.25,
              'min_copper_edge_clearance': 0.3, 'min_silk_clearance': 0.0, 'min_text_height': 0.7,
              'min_text_thickness': 0.08})
    pro['board']['design_settings']['track_widths'] = [0.0, 0.15, 0.2, 0.3, 0.5]
    pro['board']['design_settings']['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.6, 'drill': 0.3}]
    sev = pro['board']['design_settings'].setdefault('rule_severities', {})
    sev.update({'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore'})
    pro.setdefault('schematic', {})
    pro['schematic'].setdefault('legacy_lib_dir', '')
    pro['schematic'].setdefault('legacy_lib_list', [])
    json.dump(pro, open(path, 'w'), indent=2, sort_keys=True)
    open(os.path.join(OUT, NAME + '.kicad_dru'), 'w').write('''(version 1)

# Anything on the multimeter (isolated) side must stay well away from anything on
# the USB / MCU side.  1.0 mm is the copper gap between pins 2 and 3 of the SIP-4
# DC-DC converter (PS1), the only place where the two domains come that close;
# everywhere else the rule-area keep-out under the optocouplers gives > 7 mm.
(rule "isolation_barrier"
	(condition "(A.NetClass == 'ISO' || A.NetClass == 'ISO_PWR') && (B.NetClass == 'Default' || B.NetClass == 'PWR' || B.NetClass == 'PWR_WIDE' || B.NetClass == 'VREG_LX')")
	(constraint clearance (min 1.0mm)))

# RP2354 core regulator switch node: routed between the pads of the 0402 input /
# output capacitors exactly as in the Raspberry Pi reference layout.
(rule "vreg_lx_between_cap_pads"
	(condition "A.NetClass == 'VREG_LX' || B.NetClass == 'VREG_LX'")
	(constraint clearance (min 0.12mm)))
''')


# ---------------------------------------------------------------------------
def load_fp(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(OUT, 'lib', lib + '.pretty') if lib == LIBNAME else KFP + lib + '.pretty'
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError('footprint not found: ' + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_zone(board, net, layer, pts, name, prio=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(board.GetNetcodeFromNetname(net))
    z.SetZoneName(name)
    z.SetAssignedPriority(prio)
    o = z.Outline()
    o.NewOutline()
    for (x, y) in pts:
        o.Append(P(x, y))
    z.SetLocalClearance(FromMM(0.2))
    z.SetMinThickness(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.25))
    z.SetThermalReliefSpokeWidth(FromMM(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


def add_keepout(board, pts, name, layers):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    o = z.Outline()
    o.NewOutline()
    for (x, y) in pts:
        o.Append(P(x, y))
    board.Add(z)
    return z


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def add_text(board, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, thick=None, mirror=False, just=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick or size * 0.15))
    t.SetTextAngleDegrees(rot)
    if mirror:
        t.SetMirrored(True)
    if just == 'left':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif just == 'right':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


def add_line(board, x1, y1, x2, y2, layer, width=0.15):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(x1, y1))
    s.SetEnd(P(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(FromMM(width))
    board.Add(s)


def track(board, net, pts, width, layer=pcbnew.F_Cu, lock=True):
    code = board.GetNetcodeFromNetname(FULL.get(net, net))
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(layer)
        t.SetNetCode(code)
        t.SetLocked(lock)
        board.Add(t)


def via(board, net, x, y, lock=True, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(pcbnew.PADSTACK.ALL_LAYERS, FromMM(dia))
    v.SetDrill(FromMM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(board.GetNetcodeFromNetname(FULL.get(net, net)))
    v.SetLocked(lock)
    board.Add(v)
    return v


def pad_xy(board, ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            pos = p.GetPosition()
            return (ToMM(pos.x) - OX, ToMM(pos.y) - OY)
    raise KeyError((ref, num))


# ---------------------------------------------------------------------------
def export_netlist():
    fd, net = tempfile.mkstemp(suffix='.net')       # private file: several builds may run in parallel
    os.close(fd)
    try:
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net, SCH],
                       check=True, capture_output=True)
        return netlist.load(net)
    finally:
        os.remove(net)


def stage_place():
    comps, nets = export_netlist()
    for n in nets:
        FULL[short(n)] = n
    pinmap.verify_netlist(pinmap.load(), nets)     # schematic really implements the pin map
    dom = domains(comps, nets)
    write_project(nets, dom)
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)
    board.SetCopperLayerCount(4)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
    board.SetLayerName(pcbnew.In1_Cu, 'In1.Cu')
    bds = board.GetDesignSettings()
    bds.SetBoardThickness(FromMM(1.6))
    bds.SetAuxOrigin(P(0, H))
    try:
        bds.SetGridOrigin(P(0, H))
    except Exception:
        pass
    tb = board.GetTitleBlock()
    tb.SetTitle('Solartron 7075 opto-isolated USB interface')
    tb.SetRevision('A')
    tb.SetDate('2026-11-11')
    tb.SetCompany('RP2354A, plugs into SKB of the 70754 Parallel BCD Interface Unit')

    # nets
    for n in sorted(nets):
        board.Add(pcbnew.NETINFO_ITEM(board, n))
    pin_net = {}
    for n, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[(ref, pin)] = n

    missing = [r for r in comps if r not in PL]
    extra = [r for r in PL if r not in comps]
    if missing or extra:
        raise RuntimeError('placement mismatch: missing %s extra %s' % (missing, extra))

    for ref in sorted(comps):
        c = comps[ref]
        x, y, rot, side = PL[ref]
        fp = load_fp(c['footprint'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        board.Add(fp)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        if side == 'B':
            # mirror left-right: seen from the top side J1 pin 1 ends up top-right
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPath(pcbnew.KIID_PATH(c['sheet_tstamps'] + c['tstamps'][0]))
        fp.SetSheetname(c['sheet_names'].rstrip('/') or '/')
        for k in ('LCSC', 'MPN', 'Manufacturer'):
            v = c['fields'].get(k, '')
            if v:
                fp.SetField(k, v)
                f = fp.GetField(k)
                if f:
                    f.SetVisible(False)
        if c['fields'].get('Datasheet'):
            fp.SetField('Datasheet', c['fields']['Datasheet'])
        if c.get('description'):
            fp.SetField('Description', c['description'])
        for k in ('Datasheet', 'Description'):
            f = fp.GetField(k) if fp.HasField(k) else None
            if f:
                f.SetVisible(False)
        for pad in fp.Pads():
            n = pin_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNetCode(board.GetNetcodeFromNetname(n))
        if ref == 'PS1':
            for pad in fp.Pads():
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        if ref.startswith('TP'):
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)

    # outline
    for (a, b) in zip(rect(0, 0, W, H), rect(0, 0, W, H)[1:] + rect(0, 0, W, H)[:1]):
        add_line(board, a[0], a[1], b[0], b[1], pcbnew.Edge_Cuts, 0.1)

    # isolation keep-out (no copper on any layer); narrow only between PS1 pins 2 and 3
    cu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    for r_ in BARRIER:
        add_keepout(board, rect(*r_), 'isolation barrier', cu)

    # planes
    # the plane outlines run up to the middle of the barrier; the keep-out rule areas
    # above remove the fill everywhere except right at the DC-DC converter pins
    add_zone(board, 'GND_ISO', pcbnew.In1_Cu, rect(0, 0, BX - 0.55, H), 'GND_ISO plane')
    add_zone(board, 'GND', pcbnew.In1_Cu, rect(BX + 0.55, 0, W, H), 'GND plane')
    add_zone(board, '+5V_ISO', pcbnew.In2_Cu, rect(0, 0, BX - 0.55, H), '+5V_ISO plane')
    add_zone(board, '+3V3', pcbnew.In2_Cu, rect(BX + 0.55, 0, W, H), '+3V3 plane')

    preroute(board)
    silk(board)
    pcbnew.SaveBoard(PCB, board, True)
    print('placed %d footprints, %d nets' % (len(comps), len(nets)))


def preroute(board):
    """RP2354 core regulator, following the Raspberry Pi reference placement:
    VIN cap and output cap stacked directly above pins 47-49, switch node routed
    between their pads straight up to the inductor."""
    vin, lx, pg, fb = pad_xy(board, 'U1', 49), pad_xy(board, 'U1', 48), pad_xy(board, 'U1', 47), pad_xy(board, 'U1', 50)
    c16_1, c16_2 = pad_xy(board, 'C16', 1), pad_xy(board, 'C16', 2)
    c17_1, c17_2 = pad_xy(board, 'C17', 1), pad_xy(board, 'C17', 2)
    l1_1, l1_2 = pad_xy(board, 'L1', 1), pad_xy(board, 'L1', 2)
    track(board, '+3V3', [vin, (vin[0], c16_1[1])], 0.2)
    track(board, 'GND', [pg, (pg[0], c16_2[1])], 0.2)
    track(board, 'GND', [c16_2, c17_2], 0.3)
    gx = c16_2[0] + 0.85
    track(board, 'GND', [c16_2, (gx, c16_2[1] - 0.5), c17_2], 0.3)
    via(board, 'GND', gx, c16_2[1] - 0.5)
    track(board, 'VREG_LX', [lx, (lx[0], c17_1[1] - 0.75), (l1_2[0] - 0.2, l1_2[1] + 0.55), (l1_2[0], l1_2[1] + 0.3)], 0.15)
    track(board, '+1V1', [(l1_1[0], l1_1[1] + 0.4), (l1_1[0], c17_1[1] - 0.45), c17_1], 0.3)
    # VREG_FB (50) and the DVDD pins 6 / 23 escape inwards to vias under the package and
    # join +1V1 on the bottom layer, which keeps the outside of those pin rows free
    track(board, '+1V1', [fb, (fb[0], fb[1] + 1.05)], 0.2)
    via(board, '+1V1', fb[0], fb[1] + 1.05)
    p6, p23 = pad_xy(board, 'U1', 6), pad_xy(board, 'U1', 23)
    track(board, '+1V1', [p6, (p6[0] + 1.05, p6[1])], 0.2)
    via(board, '+1V1', p6[0] + 1.05, p6[1])
    track(board, '+1V1', [p23, (p23[0], p23[1] - 1.05)], 0.2)
    via(board, '+1V1', p23[0], p23[1] - 1.05)
    # ground vias in the exposed pad
    for dx, dy in ((-0.9, 0.9), (0.9, 0.9), (0.9, -0.9)):
        via(board, 'GND', UX + dx, UY + dy)


def silk(board):
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    add_text(board, 'SOLARTRON 7075 USB INTERFACE', SILK['title'][0], SILK['title'][1], 1.3, F, thick=0.2,
             rot=(SILK['title'] + (0,))[2])
    add_text(board, 'RP2354A opto-isolated  rev A', SILK['sub'][0], SILK['sub'][1], 1.0, F, rot=(SILK['sub'] + (0,))[2])
    add_text(board, 'J1 on other side', SILK['j1'][0], SILK['j1'][1], 0.8, F, rot=(SILK['j1'] + (0,))[2])
    for y1, y2 in ((9.6, 10.4), (21.6, 22.0), (33.1, 33.5), (44.6, 46.3), (48.1, 49.5)):
        add_line(board, BX, y1, BX, y2, F, 0.3)
    add_text(board, 'ISOLATION', BX, 47.2, 0.8, F)
    add_text(board, 'DVM', 80.6, 49.0, 0.8, F)
    add_text(board, 'USB', 89.4, 49.0, 0.8, F)
    add_text(board, 'USB', 108.5, 16.0, 1.0, F)
    add_text(board, 'BOOT', 96.2, 41.9, 0.8, F)
    add_text(board, 'RESET', 113.0, 39.6, 0.8, F)
    add_text(board, 'SWD', 102.0, 48.6, 0.8, F)
    add_text(board, 'PWR', 114.3, 15.8, 0.7, F)
    add_text(board, 'ACT', 114.3, 34.7, 0.7, F)
    add_text(board, 'ISO PWR', 68.0, 45.9, 0.7, F)
    add_text(board, 'TX', SILK['tx'][0], SILK['tx'][1], 0.7, F)
    add_text(board, 'RX', SILK['rx'][0], SILK['rx'][1], 0.7, F)
    add_text(board, '4-40 UNC', DX - 30.555, DY + 4.4, 0.7, F)
    add_text(board, '4-40 UNC', DX + 30.555, DY + 4.4, 0.7, F)
    # bottom side: pin-1 hint and identification (mirrored text)
    add_text(board, 'Solartron 7075 USB interface rev A', 36, 36.5, 1.2, B, mirror=True)
    add_text(board, 'THIS SIDE TO MULTIMETER (70754 SKB)', 36, 39.5, 1.0, B, mirror=True)
    add_text(board, '1', DX + 22.08 + 2.2, DY - 2.84 - 2.4, 1.0, B, mirror=True)
    add_text(board, '50', DX - 22.08 - 2.4, DY + 2.84 + 2.4, 1.0, B, mirror=True)


def place_refs(board):
    """Put reference designators on the silkscreen where there is room (next to the
    part, clear of pads, other parts and other text); hide them where there is none.
    Every footprint keeps its reference on the F.Fab layer for the assembly drawing."""
    SZ = 0.7
    boxes = []                      # occupied rectangles (x1, y1, x2, y2), board mm

    def bb(item):
        b = item.GetBoundingBox()
        return (ToMM(b.GetLeft()) - OX, ToMM(b.GetTop()) - OY, ToMM(b.GetRight()) - OX, ToMM(b.GetBottom()) - OY)

    def free(r):
        if r[0] < 0.7 or r[1] < 0.7 or r[2] > W - 0.7 or r[3] > H - 0.7:
            return False
        if r[2] > ISO_EDGE and r[0] < MCU_EDGE and False:
            return False
        return not any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3] for o in boxes)

    fps = [fp for fp in board.GetFootprints()]
    court = {}
    for fp in fps:
        if fp.GetLayer() != pcbnew.F_Cu:
            for p in fp.Pads():                       # through-hole pads of J1 show on the top side too
                r = bb(p)
                boxes.append((r[0] - 0.15, r[1] - 0.15, r[2] + 0.15, r[3] + 0.15))
            continue
        c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        r = (ToMM(c.GetLeft()) - OX, ToMM(c.GetTop()) - OY, ToMM(c.GetRight()) - OX, ToMM(c.GetBottom()) - OY)
        if r[2] - r[0] < 0.1:
            r = bb(fp)
        court[fp.GetReference()] = r
        boxes.append(r)
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            boxes.append(bb(d))
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            x, y = ToMM(p.x) - OX, ToMM(p.y) - OY
            boxes.append((x - 0.2, y - 0.2, x + 0.2, y + 0.2))
    shown = hidden = 0
    order = sorted(court, key=lambda r: -(court[r][2] - court[r][0]) * (court[r][3] - court[r][1]))
    for ref in order:
        fp = board.FindFootprintByReference(ref)
        t = fp.Reference()
        x1, y1, x2, y2 = court[ref]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        w, h = 0.62 * len(ref) + 0.1, SZ + 0.1
        cands = [(cx, y1 - h / 2 - 0.1, 0), (cx, y2 + h / 2 + 0.1, 0), (x2 + w / 2 + 0.15, cy, 0), (x1 - w / 2 - 0.15, cy, 0),
                 (x1 - h / 2 - 0.1, cy, 90), (x2 + h / 2 + 0.1, cy, 90)]
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(FromMM(SZ), FromMM(SZ)))
        t.SetTextThickness(FromMM(0.11))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        for (x, y, rot) in cands:
            ww, hh = (w, h) if rot == 0 else (h, w)
            r = (x - ww / 2, y - hh / 2, x + ww / 2, y + hh / 2)
            if free(r):
                t.SetPosition(P(x, y))
                t.SetTextAngleDegrees(rot)
                t.SetVisible(True)
                boxes.append(r)
                shown += 1
                break
        else:
            t.SetVisible(False)
            hidden += 1
    print('reference designators on silkscreen: %d shown, %d hidden (see F.Fab / assembly drawing)' % (shown, hidden))


# ---------------------------------------------------------------------------
def stage_dsn():
    os.makedirs(AR, exist_ok=True)
    board = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ExportSpecctraDSN(board, os.path.join(AR, 'board.dsn'))
    print('DSN export:', ok)


def stage_route(bias=(1.0, 1.0)):
    import router
    comps, nets = export_netlist()
    for n in nets:
        FULL[short(n)] = n
    dom = domains(comps, nets)
    board = pcbnew.LoadBoard(PCB)
    widths = {n: CLASSES[net_class(n, dom)][0] for n in nets}
    widths[FULL['VREG_LX']] = 0.2
    r = router.Router(board, OX, OY, W, H, ['GND', 'GND_ISO', '+3V3', '+5V_ISO'], widths)
    r.hug_w = int(os.environ.get('ROUTER_HUG', router.HUG))
    for r_ in BARRIER:
        r.block_rect(*r_)
    r.add_pads()
    r.add_fixed()
    fails = r.fanout_planes()
    print('plane fan-out failures:', fails)
    failed = r.route_all(bias=bias)
    for (d, net, pa, pb) in failed:
        print('UNROUTED %-32s %s -> %s (%.1f mm)' % (r.names[net], pa, pb, d))
    ntr, nvia = r.write()
    print('tracks %d, vias %d, unrouted %d' % (ntr, nvia, len(failed)))
    place_refs(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board, True)
    return len(failed) + len(fails)


def stage_ses():
    board = pcbnew.LoadBoard(PCB)
    ok = pcbnew.ImportSpecctraSES(board, os.path.join(AR, 'board.ses'))
    print('SES import:', ok)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board, True)
    print('tracks:', len(board.GetTracks()))


if __name__ == '__main__':
    {'place': stage_place, 'dsn': stage_dsn, 'ses': stage_ses, 'route': stage_route}[sys.argv[1]]()
