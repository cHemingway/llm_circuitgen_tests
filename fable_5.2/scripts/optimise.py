#!/usr/bin/python3
"""Pin swapping and placement search for the multimeter side of the board.

What is exchangeable (see pinmap.py) is assigned here instead of by hand:

* for a given placement the assignment is solved exactly: three minimum-length
  matchings (SKB pin -> register input, SKB pin -> pull-down resistor, command
  line -> driver output) plus the order of the registers in the serial chains.
  This swaps pins within a part and between parts in one go;
* placements come from a parametrised floorplan; candidates are compared by
  routing each of them completely with scripts/router.py (vias, track length,
  unrouted connections), several in parallel.

    optimise.py run            evaluate the candidate list, print the table
    optimise.py apply NAME     write pinmap.json / layout.json for candidate NAME

Run with the interpreter that has pcbnew (/usr/bin/python3).
"""
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

import gen_pcb
import pinmap as PMAP

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
WORK = os.environ.get('OPT_WORK', '/tmp/s7075_opt')
PY = sys.executable

RN = 'Resistor_SMD:R_Array_Convex_4x0603'
SOIC16 = 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm'
FOOT = {'U8': 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm', 'Q1': 'Package_TO_SOT_SMD:SOT-23',
        'U5': 'Package_DIP:SMDIP-8_W9.53mm', 'J1': 'solartron7075:DSUB-50_Pins_Vertical_P2.76x2.84mm_MountingHoles'}
for _u in PMAP.U165 + PMAP.U595:
    FOOT[_u] = SOIC16
for _u in PMAP.U165:
    for _r in PMAP.SER[_u]:
        FOOT[_r] = RN
for _r in PMAP.PD:
    FOOT[_r] = RN


# --------------------------------------------------------------------------- geometry
_fp = {}
_foot_all = False


def _footprints():
    """Footprint of every part, from the schematic."""
    global _foot_all
    if not _foot_all:
        comps, _ = gen_pcb.export_netlist()
        for ref, c in comps.items():
            FOOT.setdefault(ref, c['footprint'])
        _foot_all = True


def pads(ref, place):
    """{pad number: (x, y)} of a part, board coordinates in mm."""
    if ref == 'J1':                              # on the bottom side, mirrored: use the pin table
        return {str(n): skb_xy(n) for n in range(1, 51)}
    x, y, rot = tuple(place[ref])[:3] if ref in place else gen_pcb.PL_BASE[ref][:3]
    if ref not in FOOT:
        _footprints()
    fid = FOOT[ref]
    if fid not in _fp:
        _fp[fid] = gen_pcb.load_fp(fid)
    fp = _fp[fid]
    fp.SetOrientationDegrees(0)
    fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    fp.SetOrientationDegrees(rot)
    out = {}
    for p in fp.Pads():
        q = p.GetPosition()
        out.setdefault(p.GetNumber(), (ToMM(q.x), ToMM(q.y)))
    return out


def dist(a, b):
    """Length of the shortest 45-degree route between two points."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def hungarian(cost):
    """Minimum-cost assignment of every row to a distinct column (rows <= columns)."""
    n, m = len(cost), len(cost[0])
    INF = float('inf')
    u, v, p, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    res = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            res[p[j] - 1] = j - 1
    return res


def rot_off(ox, oy, rot):
    a = math.radians(rot)
    return ox * math.cos(a) + oy * math.sin(a), -ox * math.sin(a) + oy * math.cos(a)


# --------------------------------------------------------------------------- floorplans
J1X, J1Y = gen_pcb.DX, gen_pcb.DY


def skb_xy(n):
    """Position of SKB pin n seen from the component side (J1 is on the other side)."""
    if n <= 17:
        return J1X + 22.08 - 2.76 * (n - 1), J1Y - 2.84
    if n <= 33:
        return J1X + 20.70 - 2.76 * (n - 18), J1Y
    return J1X + 22.08 - 2.76 * (n - 34), J1Y + 2.84


def fp_orig(p=None):
    """The original hand placement: four registers above the connector, pull-downs in a
    row between them and the connector, the fifth register and the drivers below."""
    return {}, {r: ['1', '2', '3', '4'] for r in PMAP.PD}, {}


H5 = dict(pitch=11.04, xc=36.0, y=8.6, rot=270, dy=5.35, pd_y=31.4, x15=35.5, x16=20.0, y595=41.2, pd2_y=35.9)


def fp_h5(p=None):
    """All five 74HCT165 in one row above the connector, turned so that their two
    series arrays sit above and below each chip and the row is as wide as the pin
    field (11.04 mm = 8 pins per chip): the 37 status lines run almost straight up.
    The pull-downs are dead-end stubs, so they go to the other side of the pin field:
    vertical arrays under every second pin of the bottom row, two resistors fed from
    the gap on the left and two from the gap on the right, with that pin's own track
    passing under the array body.  The command drivers stay below the connector."""
    q = dict(H5)
    q.update(p or {})
    pl, terms = {}, {}
    for i, u in enumerate(PMAP.U165):
        x = round(q['xc'] + (2 - i) * q['pitch'], 1)
        y, rot = q['y'], q['rot']
        hi, lo = PMAP.SER[u]
        pl[u] = (x, y, rot)
        ox, oy = rot_off(q['dy'], 0, rot)
        pl[hi] = (round(x + ox, 2), round(y + oy, 2), (rot + 180) % 360)
        pl[lo] = (round(x - ox, 2), round(y - oy, 2), rot)
        ox, oy = rot_off(q['dy'], -3.4, rot)
        pl['C%d' % (31 + i)] = (round(x + ox, 2), round(y + oy, 2), rot)
    for i, n in enumerate(range(35, 50, 2)):
        pl[PMAP.PD[i]] = (round(skb_xy(n)[0], 2), q['pd_y'], 0)
        terms[PMAP.PD[i]] = ['1', '2', '6', '5']
    # the five lines of the bottom row that are inputs (34, 35, 36, 38) and SKB 1
    pl['RN19'] = (56.7, q['pd2_y'], 270)
    terms['RN19'] = ['1', '2', '3', '4']
    pl['RN21'] = (round(skb_xy(38)[0], 2), round(q['pd2_y'] + 0.3, 2), 0)
    terms['RN21'] = ['1', '2', '6', '5']
    y5 = q['y595']
    pl['U16'] = (q['x16'], y5, 180)
    pl['U15'] = (q['x15'], y5, 180)
    pl['C37'] = (q['x16'] + 2.2, y5 + 6.6, 180)
    pl['C36'] = (q['x15'] + 2.2, y5 + 6.6, 180)
    xq = q['x15'] + 6.0
    pl['R27'] = (xq, 34.7, 0)
    pl['R26'] = (xq, 36.4, 180)
    pl['Q1'] = (xq + 1.9, 39.6, 0)
    pl['R25'] = (xq + 1.9, 42.6, 180)
    silk = {'title': (34.0, 18.6), 'sub': (51.0, 47.5), 'j1': (4.0, 40.5, 90)}
    return pl, terms, silk


H5T = dict(pitch=11.04, xc=36.0, y=8.3, rot=270, dy=5.35, pd_y=18.9, x15=33.0, x16=18.5, y595=37.0, pd2_y=32.3)


def fp_h5t(p=None):
    """As h5, but the pull-down arrays stay between the registers and the connector:
    one vertical array above every second pin of the top row.  That pin's track runs
    under the array body (and can tee into a pad from the inside); the lines coming up
    through the gaps on either side tee into the pads on that side and carry on up.
    Pull-down stubs are then a few millimetres long and the command drivers can move
    up against the connector."""
    q = dict(H5T)
    q.update(p or {})
    pl, terms, silk = fp_h5(q)
    for i, n in enumerate(range(2, 17, 2)):
        pl[PMAP.PD[i]] = (round(skb_xy(n)[0], 2), q['pd_y'], 0)
        terms[PMAP.PD[i]] = ['1', '2', '6', '5']
    pl['RN19'] = (56.7, q['pd2_y'], 270)
    pl['RN21'] = (round(skb_xy(38)[0], 2), round(q['pd2_y'] - 0.3, 2), 0)
    xq = q['x15'] + 6.0
    pl['R27'] = (xq, 30.4, 0)
    pl['R26'] = (xq, 32.1, 180)
    pl['Q1'] = (xq + 1.9, 35.3, 0)
    pl['R25'] = (xq + 1.9, 38.3, 180)
    silk = {'title': (33.0, 46.0), 'sub': (33.0, 48.2), 'j1': (4.0, 40.5, 90)}
    return pl, terms, silk


FLOORPLANS = {'orig': fp_orig, 'h5': fp_h5, 'h5t': fp_h5t}


# --------------------------------------------------------------------------- assignment
def assign(place, terms):
    """Best pin assignment for a placement.  Returns (pinmap, estimated length in mm)."""
    j1 = pads('J1', place)
    pin_xy = {net: j1[str(PMAP.NET_PIN[net])] for net in PMAP.INPUT_NETS}
    u8 = pads('U8', place)
    upads = {u: pads(u, place) for u in PMAP.U165 + PMAP.U595}
    total = 0.0

    # status lines -> register inputs (through the series array next to each input)
    slots = []
    for u in PMAP.U165:
        for d in range(8):
            arr = pads(PMAP.SER[u][d // 4], place)
            slots.append((u, d, arr[str(d % 4 + 1)], upads[u][str(PMAP.D165[d])]))
    cost = []
    for net in PMAP.INPUT_NETS:
        row = [dist(pin_xy[net], s[2]) for s in slots]
        if net == 'DVM_PRINT_LEVEL':            # also feeds the data-ready buffer U8
            row = [c + dist(s[3], u8['5']) for c, s in zip(row, slots)]
        cost.append(row)
    res = hungarian(cost)
    total += sum(cost[i][j] for i, j in enumerate(res))
    inputs = {u: [None] * 8 for u in PMAP.U165}
    for i, j in enumerate(res):
        inputs[slots[j][0]][slots[j][1]] = PMAP.INPUT_NETS[i]

    # order of the registers in the chain: MISO <- first <- second ...
    best = None
    for perm in itertools.permutations(PMAP.U165):
        c = dist(u8['2'], upads[perm[0]]['9'])
        for a, b in zip(perm, perm[1:]):
            c += dist(upads[b]['9'], upads[a]['10'])
        if best is None or c < best[0]:
            best = (c, perm)
    total += best[0]
    chain165 = list(best[1])
    free = [(chain165.index(u), 7 - d, u, d) for u in PMAP.U165 for d in range(8) if inputs[u][d] is None]
    for k, (_, _, u, d) in enumerate(sorted(free)):
        inputs[u][d] = 'ID1' if k == 0 else 'ID0'

    # status lines -> pull-down resistors
    tpads = [(rn, pad, pads(rn, place)[pad]) for rn in PMAP.PD for pad in terms[rn]]
    cost = [[dist(pin_xy[net], t[2]) for t in tpads] for net in PMAP.INPUT_NETS]
    res = hungarian(cost)
    total += sum(cost[i][j] for i, j in enumerate(res))
    pulldown = {}
    for i, j in enumerate(res):
        pulldown.setdefault(tpads[j][0], {})[tpads[j][1]] = PMAP.INPUT_NETS[i]

    # command lines -> driver outputs
    q1 = pads('Q1', place)
    src = {net: (q1['1'] if net == 'PULSE_GATE' else j1[str(PMAP.skb(net))]) for net in PMAP.OUTPUT_NETS}
    oslots = [(u, d, upads[u][str(PMAP.D595[d])]) for u in PMAP.U595 for d in range(8)]
    cost = [[dist(src[net], s[2]) for s in oslots] for net in PMAP.OUTPUT_NETS]
    res = hungarian(cost)
    total += sum(cost[i][j] for i, j in enumerate(res))
    outputs = {u: [None] * 8 for u in PMAP.U595}
    for i, j in enumerate(res):
        outputs[oslots[j][0]][oslots[j][1]] = PMAP.OUTPUT_NETS[i]
    mosi = pads('U5', place)['6']
    best = min((dist(mosi, upads[a]['2']) + dist(upads[a]['9'], upads[b]['2']), [a, b])
               for a, b in (PMAP.U595, PMAP.U595[::-1]))
    total += best[0]
    pm = {'chain165': chain165, 'chain595': best[1], 'inputs': inputs, 'pulldown': pulldown, 'outputs': outputs,
          'mcu': PMAP.default_mcu()}
    PMAP.check(pm)
    return pm, total


def estimate(place, pm):
    """Estimated length of the exchangeable connections for an arbitrary assignment."""
    j1 = pads('J1', place)
    u8 = pads('U8', place)
    upads = {u: pads(u, place) for u in PMAP.U165 + PMAP.U595}
    t = 0.0
    for u in PMAP.U165:
        for d, net in enumerate(pm['inputs'][u]):
            if not net.startswith('ID'):
                t += dist(j1[str(PMAP.NET_PIN[net])], pads(PMAP.SER[u][d // 4], place)[str(d % 4 + 1)])
                if net == 'DVM_PRINT_LEVEL':
                    t += dist(upads[u][str(PMAP.D165[d])], u8['5'])
    for rn, m in pm['pulldown'].items():
        for pad, net in m.items():
            t += dist(j1[str(PMAP.NET_PIN[net])], pads(rn, place)[pad])
    q1 = pads('Q1', place)
    for u in PMAP.U595:
        for d, net in enumerate(pm['outputs'][u]):
            if net:
                t += dist(q1['1'] if net == 'PULSE_GATE' else j1[str(PMAP.skb(net))], upads[u][str(PMAP.D595[d])])
    ch = pm['chain165']
    t += dist(u8['2'], upads[ch[0]]['9']) + sum(dist(upads[b]['9'], upads[a]['10']) for a, b in zip(ch, ch[1:]))
    a, b = pm['chain595']
    t += dist(pads('U5', place)['6'], upads[a]['2']) + dist(upads[a]['9'], upads[b]['2'])
    return t


# --------------------------------------------------------------------------- MCU side
KX = 15.0                     # cost of one crossing between two estimated connections, in mm


def _cross(a, b, c, d):
    """True if segments a-b and c-d cross (touching end points do not count)."""
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = o(c, d, a), o(c, d, b), o(a, b, c), o(a, b, d)
    return (d1 * d2 < -1e-9) and (d3 * d4 < -1e-9)


def _score(paths):
    """paths: list of polylines, one per net.  Length + KX per crossing between different nets."""
    t = 0.0
    segs = []
    for i, pl in enumerate(paths):
        for a, b in zip(pl, pl[1:]):
            t += dist(a, b)
            segs.append((i, a, b))
    n = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][0] != segs[j][0] and _cross(segs[i][1], segs[i][2], segs[j][1], segs[j][2]):
                n += 1
    return t + KX * n, n


def _mst(pts):
    done, rest, t = [pts[0]], list(pts[1:]), 0.0
    while rest:
        d, q = min((dist(a, b), b) for a in done for b in rest)
        t += d
        done.append(q)
        rest.remove(q)
    return t


MCU0 = dict(u4=(97.0, 22.2, 90), c21=(97.0, 17.3, 0), rn1=(97.0, 27.6, 90), rn_style='row',
            tp1=(97.6, 31.0), tp2=(95.2, 31.0), u8=(71.4, 39.6, 0), c25=(71.4, 33.6, 0))


# chosen MCU-side placement: buffer and pull-up array turned round so that the GPIO lines reach the
# pull-ups first and the buffer outputs face the optocouplers; test pads moved out of the way
MCU_BEST = dict(u4=(97.0, 22.2, 270), c21=(97.0, 17.3, 0), rn1=(97.0, 27.6, 270), tp1=(97.0, 34.8), tp2=(94.8, 33.0))


def mcu_plan(p=None):
    """Placement of the movable parts between MCU and optocouplers (and of U8)."""
    q = dict(MCU0)
    q.update(p or {})
    if 'c21' not in (p or {}):         # decoupling capacitor in line with the supply pin of U4
        ox, oy = rot_off(4.9, -1.75, q["u4"][2])
        q['c21'] = (round(q['u4'][0] + ox, 2), round(q['u4'][1] + oy, 2), q['u4'][2])
    pl = {'U4': tuple(q['u4']), 'C21': tuple(q['c21']), 'RN1': tuple(q['rn1']), 'TP1': tuple(q['tp1']) + (0,),
          'TP2': tuple(q['tp2']) + (0,), 'U8': tuple(q['u8']), 'C25': tuple(q['c25'])}
    for k in ('r24', 'd2', 'r9'):
        if k in q:
            pl[k.upper()] = tuple(q[k])
    q['silk'] = {'tx': (q['tp1'][0], q['tp1'][1] + 1.7), 'rx': (q['tp2'][0], q['tp2'][1] + 1.7)}
    return pl, q['rn_style'], q['silk']


def assign_mcu(place, pm, style, cand=range(0, 19)):
    """Best GPIO / buffer gate / pull-up / optocoupler channel assignment for a placement.
    Connections are estimated as straight lines; crossings between them cost KX each."""
    P_ = lambda ref: pads(ref, place)
    u1, u4, u7, u8 = P_('U1'), P_('U4'), P_('U7'), P_('U8')
    gp = {g: u1[str(PMAP.GP2PIN[g])] for g in PMAP.GP2PIN}
    x, y, rot = place['RN1'][:3] if 'RN1' in place else gen_pcb.PL_BASE['RN1'][:3]
    rn = P_('RN1')
    if style == 'split':            # the four lines run past / under the array: two outside, two under the body
        rn_pads = ['1', '2', '6', '5']
        lanes = [(x + ox, y + oy) for ox, oy in (rot_off(lx, 0, rot) for lx in (-1.7, -0.2, 0.2, 1.7))]
    else:                           # four pads in a row on one side
        rn_pads = ['1', '2', '3', '4']
        lanes = [rn[p] for p in rn_pads]
    sigs = PMAP.DOWN
    chans = sorted(PMAP.DOWN_CH)
    cath = {c: P_(c[:2])[PMAP.DOWN_CH[c][0]] for c in chans}
    vo = {c: P_(c[:2])[PMAP.DOWN_CH[c][2]] for c in chans}
    loads = {'SCK': [P_(u)['2'] for u in PMAP.U165] + [P_(u)['15'] for u in PMAP.U595],
             'LATCH': [P_(u)['1'] for u in PMAP.U165] + [P_(u)['10'] for u in PMAP.U595],
             'MOSI': [P_(pm['chain595'][0])['2']], 'OEn': [P_(u)['8'] for u in PMAP.U595]}
    iso = {(s, c): _mst([vo[c]] + loads[s]) for s in sigs for c in chans}

    # uplink: which U8 gate and which U7 channel for MISO / DRDY
    src = {'MISO': P_(pm['chain165'][0])['9']}
    for u in PMAP.U165:
        for d, net in enumerate(pm['inputs'][u]):
            if net == 'DVM_PRINT_LEVEL':
                src['DRDY'] = P_(u)[str(PMAP.D165[d])]
    upch = sorted(PMAP.UP_CH)
    best_up = {}
    for perm in itertools.permutations(upch):
        chs = dict(zip(PMAP.UP, perm))
        b = None
        for g1, g2 in itertools.permutations(range(4), 2):
            gs = {'MISO': g1, 'DRDY': g2}
            paths = []
            for s in PMAP.UP:
                oe, a, yv = PMAP.GATES[gs[s]]
                paths += [[src[s], u8[str(a)]], [u8[str(yv)], u7[PMAP.UP_CH[chs[s]][0]]]]
            c = _score(paths)[0]
            if b is None or c < b[0]:
                b = (c, gs)
        best_up[perm] = b

    triples = [(a, b, c) for a in cand for b in cand for c in cand if PMAP.spi_ok(a, b, c)]
    best = None
    for gperm in itertools.permutations(range(4)):
        gate = dict(zip(sigs, gperm))
        A = {s: u4[str(PMAP.GATES[gate[s]][1])] for s in sigs}
        Y = {s: u4[str(PMAP.GATES[gate[s]][2])] for s in sigs}
        # stage A: optocoupler channels
        ba = None
        for cperm in itertools.permutations(chans):
            ch = dict(zip(sigs, cperm))
            c = _score([[Y[s], cath[ch[s]]] for s in sigs])[0] + sum(iso[(s, ch[s])] for s in sigs)
            if ba is None or c < ba[0]:
                ba = (c, ch)
        # stage B: GPIOs and pull-ups
        for lperm in itertools.permutations(range(4)):
            via = {s: lanes[lperm[i]] for i, s in enumerate(sigs)}
            for (sck, tx, rx) in triples:
                fixed = {'SCK': sck, 'MOSI': tx, 'MISO': rx}
                free = [g for g in cand if g not in fixed.values()]
                for uperm in best_up:
                    uc = dict(zip(PMAP.UP, uperm))
                    tgt = {'LATCH': via['LATCH'], 'OEn': via['OEn'], 'DRDY': u7[PMAP.UP_CH[uc['DRDY']][2]]}
                    names = list(tgt)
                    res = hungarian([[dist(gp[g], tgt[n]) for g in free] for n in names])
                    g_of = dict(fixed)
                    for n, j in zip(names, res):
                        g_of[n] = free[j]
                    paths = [[gp[g_of[s]], via[s], A[s]] for s in sigs]
                    paths += [[gp[g_of[s]], u7[PMAP.UP_CH[uc[s]][2]]] for s in PMAP.UP]
                    c, nx = _score(paths)
                    c += ba[0] + best_up[uperm][0]
                    if best is None or c < best[0]:
                        best = (c, dict(g_of), gate, {s: rn_pads[lperm[i]] for i, s in enumerate(sigs)}, ba[1], uc,
                                best_up[uperm][1], paths)
    c, g_of, gate, rn1, ch, uc, u8g, paths = best
    # UART test pads and the activity LED: nearest valid free pins
    tp = [P_('TP1')['1'], P_('TP2')['1']]
    bu = None
    for t in range(30):
        for r in range(30):
            if PMAP.uart_ok(t, r) and t not in g_of.values() and r not in g_of.values() and t != 25 and r != 25:
                cu = _score(paths + [[gp[t], tp[0]], [gp[r], tp[1]]])[0]
                if bu is None or cu < bu[0]:
                    bu = (cu, t, r)
    g_of.update({'UART_TX': bu[1], 'UART_RX': bu[2], 'LED_ACT': 25})
    mcu = {'gpio': g_of, 'gate': gate, 'rn1': rn1, 'chan': ch, 'up': uc, 'u8': u8g}
    return mcu, bu[0] - _score(paths)[0] + c


def estimate_mcu(place, pm, style='row'):
    """The same estimate for an arbitrary (e.g. the original) assignment."""
    P_ = lambda ref: pads(ref, place)
    m = pm['mcu']
    u1, u4, u7, u8, rn = P_('U1'), P_('U4'), P_('U7'), P_('U8'), P_('RN1')
    gp = {s: u1[str(PMAP.GP2PIN[g])] for s, g in m['gpio'].items()}
    paths = []
    t = 0.0
    for s in PMAP.DOWN:
        oe, a, yv = PMAP.GATES[m['gate'][s]]
        ch = m['chan'][s]
        paths += [[gp[s], rn[m['rn1'][s]], u4[str(a)]], [u4[str(yv)], P_(ch[:2])[PMAP.DOWN_CH[ch][0]]]]
    src = {'MISO': P_(pm['chain165'][0])['9']}
    for u in PMAP.U165:
        for d, net in enumerate(pm['inputs'][u]):
            if net == 'DVM_PRINT_LEVEL':
                src['DRDY'] = P_(u)[str(PMAP.D165[d])]
    for s in PMAP.UP:
        oe, a, yv = PMAP.GATES[m['u8'][s]]
        ch = PMAP.UP_CH[m['up'][s]]
        paths += [[gp[s], u7[ch[2]]], [src[s], u8[str(a)]], [u8[str(yv)], u7[ch[0]]]]
    paths += [[gp['UART_TX'], P_('TP1')['1']], [gp['UART_RX'], P_('TP2')['1']]]
    return _score(paths)


# --------------------------------------------------------------------------- evaluation by routing
def measure(pcb):
    b = pcbnew.LoadBoard(pcb)
    out = {'vias': 0, 'len': 0.0, 'vias_dvm': 0, 'vias_ctl': 0, 'vias_pwr': 0, 'vias_mcu': 0}
    iso_ctl = ('LATCH_ISO', 'SCK_ISO', 'MOSI_ISO', 'OEn_ISO', 'MISO_ISO', 'CMD_CHAIN', 'PRINT_LEVEL_S', 'PULSE_GATE')
    for t in b.GetTracks():
        n = t.GetNetname().rsplit('/', 1)[-1]
        if t.GetClass() == 'PCB_VIA':
            out['vias'] += 1
            if n in ('GND', 'GND_ISO', '+3V3', '+5V_ISO', '+1V1', '+9V_ISO', 'VBUS'):
                out['vias_pwr'] += 1
            elif n.startswith('DVM_'):
                out['vias_dvm'] += 1
            elif n in iso_ctl or n.startswith('SR_Q'):
                out['vias_ctl'] += 1
            else:
                out['vias_mcu'] += 1
        else:
            out['len'] += ToMM(t.GetLength())
    out['len'] = round(out['len'])
    return out


def evaluate(name, plan='orig', params=None, swap=True, hug=0, drc=False, via=260, mcu=None, mcu_swap=True):
    """Build candidate `name` in its own directory, route it and return the figures."""
    place, terms, silk = FLOORPLANS[plan](params)
    if swap:
        pm, est = assign(place, terms)
    else:
        pm = PMAP.default()
        est = estimate(place, pm)
    if mcu is not None:             # MCU side: move the buffer / pull-ups / test pads, re-assign GPIOs, gates, channels
        mpl, style, msilk = mcu_plan(mcu)
        place.update(mpl)
        silk = dict(silk, **msilk)
        if mcu_swap:
            # GPIO0..11 are the pins on the side of the package that faces the optocouplers
            pm['mcu'], est_m = assign_mcu(place, pm, style, cand=range(0, mcu.get('gpio_max', 11) + 1))
        else:
            pm['mcu'] = PMAP.default_mcu()
            est_m = estimate_mcu(place, pm)[0]
        PMAP.check(pm)
    else:
        pm['mcu'] = PMAP.default_mcu()
        est_m = estimate_mcu(place, pm)[0]
    wd = os.path.join(WORK, name)
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(os.path.join(wd, 'scripts'))
    for f in os.listdir(HERE):
        if f.endswith('.py'):
            shutil.copy(os.path.join(HERE, f), os.path.join(wd, 'scripts', f))
    shutil.copytree(os.path.join(ROOT, 'lib'), os.path.join(wd, 'lib'))
    json.dump(pm, open(os.path.join(wd, 'scripts', 'pinmap.json'), 'w'), indent=1)
    json.dump({'place': place, 'silk': silk}, open(os.path.join(wd, 'scripts', 'layout.json'), 'w'), indent=1)
    env = dict(os.environ, ROUTER_HUG=str(hug), ROUTER_VIA=str(via))
    log = ''
    for cmd in ([PY, 'gen_sch.py'], [PY, 'gen_pcb.py', 'place'], [PY, 'gen_pcb.py', 'route']):
        r = subprocess.run(cmd, cwd=os.path.join(wd, 'scripts'), env=env, capture_output=True, text=True)
        log += r.stdout + r.stderr
        if r.returncode:
            open(os.path.join(wd, 'log.txt'), 'w').write(log)
            return {'name': name, 'error': (r.stderr.strip().splitlines() or ['failed'])[-1]}
    open(os.path.join(wd, 'log.txt'), 'w').write(log)
    res = {'name': name, 'plan': plan, 'params': params or {}, 'swap': swap, 'hug': hug, 'est': round(est),
           'mcu': mcu, 'est_mcu': round(est_m)}
    res['unrouted'] = sum(1 for l in log.splitlines() if l.startswith('UNROUTED'))
    res['fanout_fail'] = [l for l in log.splitlines() if l.startswith('plane fan-out failures')][0].split(':', 1)[1].strip()
    res.update(measure(os.path.join(wd, gen_pcb.NAME + '.kicad_pcb')))
    if drc:
        rep = os.path.join(wd, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity', '-o', rep,
                        os.path.join(wd, gen_pcb.NAME + '.kicad_pcb')], capture_output=True)
        d = json.load(open(rep))
        sev = {}
        for v in d.get('violations', []):
            sev[v['severity'] + ':' + v['type']] = sev.get(v['severity'] + ':' + v['type'], 0) + 1
        res['drc'] = sev
        res['unconnected'] = len(d.get('unconnected_items', []))
        res['parity'] = len(d.get('schematic_parity', []))
    json.dump(res, open(os.path.join(wd, 'result.json'), 'w'), indent=1)
    return res


def run(cands, workers=4):
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(evaluate, **c) for c in cands]
        out = [f.result() for f in futs]
    print('%-22s %5s %5s %5s | %4s %4s %4s %4s | %5s %5s %s' % ('candidate', 'unrt', 'vias', 'len', 'dvm', 'ctl', 'pwr', 'mcu', 'est', 'estM', 'extra'))
    for r in out:
        if 'error' in r:
            print('%-22s ERROR %s' % (r['name'], r['error']))
            continue
        print('%-22s %5d %5d %5d | %4d %4d %4d %4d | %5d %5d %s %s' % (
            r['name'], r['unrouted'], r['vias'], r['len'], r['vias_dvm'], r['vias_ctl'], r['vias_pwr'], r['vias_mcu'], r['est'],
            r['est_mcu'],
            r['fanout_fail'] if r['fanout_fail'] != '[]' else '',
            'unconn %s parity %s %s' % (r['unconnected'], r['parity'], r['drc']) if 'drc' in r else ''))
    return out


def apply(name):
    wd = os.path.join(WORK, name, 'scripts')
    for f in ('pinmap.json', 'layout.json'):
        shutil.copy(os.path.join(wd, f), os.path.join(HERE, f))
    print('applied', name)


if __name__ == '__main__':
    if sys.argv[1] == 'apply':
        apply(sys.argv[2])
    elif sys.argv[1] == 'run':
        # default list: what pin swapping alone and pin swapping + moving parts each buy
        cands = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else [
            dict(name='orig', plan='orig', swap=False, drc=True),
            dict(name='orig_swap', plan='orig', swap=True, drc=True),
            dict(name='h5', plan='h5', swap=True, drc=True),
            dict(name='h5t', plan='h5t', swap=True, drc=True),
            dict(name='h5t_mcu_swap', plan='h5t', swap=True, drc=True, mcu=dict(c21=(97.0, 17.3, 0))),
            dict(name='h5t_mcu', plan='h5t', swap=True, drc=True, mcu=MCU_BEST),
        ]
        run(cands)
