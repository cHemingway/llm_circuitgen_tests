#!/usr/bin/env python3
"""
Pin-swap the DVM-side shift registers to untangle the ratsnest to the DD-50.

Every 74HCT165 data input (D0..D7) is interchangeable, and so is every
74HCT595 output (Q0..Q7), as long as the firmware knows the bit map. The
order in which the five 165s are daisy-chained is free as well. So any SKB
output can go to any 165 input, the 1-0-1-0 link-check constants fill the
four spare inputs, and any SKB command input can go to any 595 output. That
includes swaps between parts, not only within one part. Part positions are
not changed.

The script reads the placed layout and treats each net as straight
ratsnest lines (a minimum spanning tree for nets with more than two pads).
It then searches, with seeded simulated annealing, for the assignment
that minimises

    total ratsnest length + CROSSING_MM x number of ratsnest crossings

over the SKB nets, the CONTACT SAMPLE gate, the 165 chain (MISO_ISO,
SI_CHAIN_*) and the 595 chain (MOSI_ISO, SO_CHAIN_1).

    python3 scripts/pin_swap.py           # report only
    python3 scripts/pin_swap.py --write   # rewrite the generated blocks
    python3 scripts/pin_swap.py --plot docs/pin_swap.svg --before old.json

`--write` replaces the block between the `pin map` markers in main.ato
and the bit-map tables between the markers in README.md. Then run
`ato build` so the layout picks up the new nets.

Needs KiCad's pcbnew Python module (KiCad 9/10).
"""

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUT = ROOT / "layouts/default/default.kicad_pcb"
MAIN_ATO = ROOT / "main.ato"
README = ROOT / "README.md"

CROSSING_MM = 5.0  # cost of one ratsnest crossing, in mm of extra length
SEED = 7075
RESTARTS = 3
ITERATIONS = 60000

N_IN, N_OUT = 5, 2
# 74HCT165: data input pins, D0..D7 (= A..H); QH = pin 9, SER = pin 10
IN_PINS = {"11": 0, "12": 1, "13": 2, "14": 3, "3": 4, "4": 5, "5": 6, "6": 7}
IN_QH, IN_SER, IN_VCC, IN_GND = "9", "10", "16", ("8", "15")
# 74HCT595: outputs Q0..Q7; SER = pin 14, Q7S = pin 9
OUT_PINS = {"15": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}
OUT_SER, OUT_Q7S = "14", "9"

DVM_OUT = list(range(1, 37))  # SKB pins read through the 165s (dvm_out[n-1])
DVM_CMD = {  # SKB pin -> SolartronSKB member driven by a 595
    38: "front_panel_lockout",
    40: "sample_pulse",
    41: "ratio",
    42: "function_cmd[0]",
    43: "function_cmd[1]",
    44: "integration_time[0]",
    45: "integration_time[1]",
    46: "integration_time[2]",
    47: "autorange",
    48: "range_cmd[0]",
    49: "range_cmd[1]",
    50: "range_cmd[2]",
}
GATE = "G"  # 595 output driving the CONTACT SAMPLE MOSFET (SKB 39)
SIGNATURE = ["H0", "L0", "H1", "L1"]  # link-check constants: 1, 0, 1, 0

OUT_NAMES = {1: "1×10⁶"}
for d, first in enumerate(range(2, 26, 4)):
    for k, w in enumerate((8, 4, 2, 1)):
        OUT_NAMES[first + k] = f"{w}×10{'⁵⁴³²¹⁰'[d]}"
OUT_NAMES.update({26: "+ve", 27: "−ve", 28: "function A", 29: "function B",
                  30: "range (4)", 31: "range (2)", 32: "range (1)",
                  33: "PRINT pulse", 34: "PRINT level", 35: "DATA CAN CHANGE", 36: "OVERLOAD"})
CMD_NAMES = {
    38: "FRONT PANEL LOCKOUT (0 = locked out)",
    39: "CONTACT SAMPLE (1 = MOSFET closes 39 to 37)",
    40: "PULSE SAMPLE (pulse high for more than 100 µs)",
    41: "RATIO (0 = ratio)",
    42: "FUNCTION A", 43: "FUNCTION B",
    44: "Integration time (4)", 45: "Integration time (2)", 46: "Integration time (1)",
    47: "AUTORANGE (1 = autorange inhibited, use the commanded range)",
    48: "Range (1)", 49: "Range (2)", 50: "Range (4)",
}


# ---------------------------------------------------------------- geometry
def load_layout():
    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    pads, nets = {}, {}  # (address, pad) -> (x, y) / net name
    for fp in board.GetFootprints():
        addr = next((f.GetText() for f in fp.GetFields() if f.GetName() == "atopile_address"), "")
        for pad in fp.Pads():
            p = pad.GetPosition()
            key = (addr, pad.GetNumber())
            pads[key] = (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
            nets[key] = pad.GetNetname()
    return pads, nets


def sin(k):
    return f"shift_in[{k}].package"


def sout(k):
    return f"shift_out[{k}].package"


def other_pads(pads, nets, net, exclude_prefix):
    return [xy for key, xy in pads.items() if nets[key] == net and not key[0].startswith(exclude_prefix)]


class Geometry:
    def __init__(self, pads, nets):
        self.dsub = {int(n): pads[("dvm.connector", n)] for (a, n) in pads if a == "dvm.connector" and n.isdigit()}
        self.in_slots = [(k, pin) for k in range(N_IN) for pin in IN_PINS]
        self.out_slots = [(k, pin) for k in range(N_OUT) for pin in OUT_PINS]
        self.pads = pads
        self.extra = {34: other_pads(pads, nets, net_of(nets, 34), "dvm.connector")}
        self.extra[34] = [xy for xy in self.extra[34] if not any(
            pads.get((sin(k), p)) == xy for k in range(N_IN) for p in IN_PINS)]
        self.gate_ends = [xy for key, xy in pads.items()
                          if key[0] in ("sample_fet", "sample_fet_pulldown") and nets[key] == nets[("sample_fet", "1")]]
        self.miso = other_pads(pads, nets, "MISO_ISO", "shift_in[")
        self.mosi = other_pads(pads, nets, "MOSI_ISO", "shift_out[")
        assert len(self.extra[34]) == 1 and len(self.gate_ends) == 2 and len(self.miso) == 1 and len(self.mosi) == 1

    def p(self, addr, pin):
        return self.pads[(addr, pin)]


def net_of(nets, skb_pin):
    return nets[("dvm.connector", str(skb_pin))]


def mst(points):
    """Edges of a minimum spanning tree (Prim) over a few points."""
    if len(points) < 2:
        return []
    done, todo, edges = [points[0]], list(points[1:]), []
    while todo:
        a, b = min(((a, b) for a in done for b in todo), key=lambda e: math.dist(*e))
        edges.append((a, b))
        done.append(b)
        todo.remove(b)
    return edges


def crosses(s, t):
    (a, b), (c, d) = s, t
    if a in (c, d) or b in (c, d):
        return False
    if (max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0])
            or max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1])):
        return False

    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 1e-9) - (v < -1e-9)

    return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0


# ---------------------------------------------------------------- state
class State:
    """in_items[i] sits on geo.in_slots[i]; out_items[j] on geo.out_slots[j];
    chain_in[p] = 165 index at chain position p (p = 0 drives MISO);
    chain_out[p] = 595 index at chain position p (p = 0 is fed by MOSI)."""

    def __init__(self, geo, in_items, out_items, chain_in, chain_out, fixed=None):
        self.geo = geo
        self.in_items, self.out_items = list(in_items), list(out_items)
        self.chain_in, self.chain_out = list(chain_in), list(chain_out)
        self.segs = dict(fixed or {})  # nets the swaps don't change (counted for crossings)
        for i in range(len(in_items)):
            self.segs[self.in_net(i)] = self.in_segs(i)
        for j in range(len(out_items)):
            if self.out_net(j):
                self.segs[self.out_net(j)] = self.out_segs(j)
        self.segs.update(self.chain_segs())

    def copy(self):
        s = State.__new__(State)
        s.geo = self.geo
        s.in_items, s.out_items = list(self.in_items), list(self.out_items)
        s.chain_in, s.chain_out = list(self.chain_in), list(self.chain_out)
        s.segs = dict(self.segs)
        return s

    # nets ----------------------------------------------------------------
    def in_net(self, i):
        return ("in", self.in_items[i])

    def out_net(self, j):
        it = self.out_items[j]
        return None if it is None else ("out", it)

    def in_segs(self, i):
        g, item = self.geo, self.in_items[i]
        k, pin = g.in_slots[i]
        here = g.p(sin(k), pin)
        if isinstance(item, int):
            return mst([g.dsub[item], here, *g.extra.get(item, [])])
        if item.startswith("H"):
            return [(here, g.p(sin(k), IN_VCC))]
        return [(here, min((g.p(sin(k), q) for q in IN_GND), key=lambda q: math.dist(q, here)))]

    def out_segs(self, j):
        g, item = self.geo, self.out_items[j]
        k, pin = g.out_slots[j]
        here = g.p(sout(k), pin)
        if item == GATE:
            return mst([here, *g.gate_ends])
        return [(g.dsub[item], here)]

    def chain_segs(self):
        g, ci, co = self.geo, self.chain_in, self.chain_out
        segs = {("chain", "MISO_ISO"): [(g.p(sin(ci[0]), IN_QH), g.miso[0])]}
        for p in range(N_IN - 1):
            segs[("chain", f"SI_CHAIN_{p + 1}")] = [(g.p(sin(ci[p]), IN_SER), g.p(sin(ci[p + 1]), IN_QH))]
        segs[("chain", "MOSI_ISO")] = [(g.p(sout(co[0]), OUT_SER), g.mosi[0])]
        segs[("chain", "SO_CHAIN_1")] = [(g.p(sout(co[0]), OUT_Q7S), g.p(sout(co[1]), OUT_SER))]
        return segs

    # cost ----------------------------------------------------------------
    def length(self, nets=None):
        return sum(math.dist(*s) for n in (nets or self.segs) for s in self.segs[n])

    def crossings(self, nets=None):
        """Crossings between different nets; with `nets`, only pairs involving them."""
        segs = self.segs

        def count(a, b):
            return sum(crosses(s, t) for s in segs[a] for t in segs[b])

        if nets is None:
            names = list(segs)
            return sum(count(a, b) for i, a in enumerate(names) for b in names[i + 1:])
        pick = list(dict.fromkeys(nets))
        picked = set(pick)
        n = 0
        for i, a in enumerate(pick):
            n += sum(count(a, b) for b in segs if b not in picked)
            n += sum(count(a, b) for b in pick[i + 1:])
        return n

    def cost(self):
        return self.length() + CROSSING_MM * self.crossings()

    def local_cost(self, changed):
        return self.length(changed) + CROSSING_MM * self.crossings(changed)

    # moves ---------------------------------------------------------------
    def apply(self, move):
        kind, a, b = move
        if kind == "in":
            self.in_items[a], self.in_items[b] = self.in_items[b], self.in_items[a]
            changed = [self.in_net(a), self.in_net(b)]
            self.segs[changed[0]] = self.in_segs(a)
            self.segs[changed[1]] = self.in_segs(b)
        elif kind == "out":
            self.out_items[a], self.out_items[b] = self.out_items[b], self.out_items[a]
            changed = []
            for j in (a, b):
                if self.out_net(j):
                    changed.append(self.out_net(j))
                    self.segs[self.out_net(j)] = self.out_segs(j)
        else:
            chain = self.chain_in if kind == "chain_in" else self.chain_out
            chain[a], chain[b] = chain[b], chain[a]
            new = self.chain_segs()
            self.segs.update(new)
            changed = list(new)
        return changed

    def changed_by(self, move):
        kind, a, b = move
        if kind == "in":
            return [self.in_net(a), self.in_net(b)]
        if kind == "out":
            return [n for n in (self.out_net(a), self.out_net(b)) if n]
        return list(self.chain_segs())


def random_move(rng, s):
    r = rng.random()
    if r < 0.72:
        a, b = rng.sample(range(len(s.in_items)), 2)
        return ("in", a, b)
    if r < 0.94:
        a, b = rng.sample(range(len(s.out_items)), 2)
        return ("out", a, b)
    if r < 0.99:
        a, b = rng.sample(range(N_IN), 2)
        return ("chain_in", a, b)
    return ("chain_out", 0, 1)


def anneal(start, rng):
    s = start.copy()
    cur = s.cost()
    best, best_cost = s.copy(), cur
    t0, t1 = 20.0, 0.05
    for it in range(ITERATIONS):
        t = t0 * (t1 / t0) ** (it / ITERATIONS)
        move = random_move(rng, s)
        before = s.local_cost(s.changed_by(move))
        undo = s.copy() if move[0].startswith("chain") else None
        changed = s.apply(move)
        delta = s.local_cost(changed) - before
        if delta <= 0 or rng.random() < math.exp(-delta / t):
            cur += delta
            if cur < best_cost - 1e-9:
                best, best_cost = s.copy(), cur
        elif undo is not None:
            s = undo
        else:
            s.apply(move)  # a swap is its own inverse
    return best


# ---------------------------------------------------------------- current map
def current_state(geo, nets):
    in_items, sig = [], iter(SIGNATURE)
    hv = iter(i for i in SIGNATURE if i.startswith("H"))
    lv = iter(i for i in SIGNATURE if i.startswith("L"))
    for k, pin in geo.in_slots:
        n = nets[(sin(k), pin)]
        m = re.match(r"SKB(\d\d)_", n)
        in_items.append(int(m.group(1)) if m else next(hv) if n == "+5V_ISO" else next(lv))
    del sig
    out_items = []
    gate_net = nets[("sample_fet", "1")]
    for k, pin in geo.out_slots:
        n = nets[(sout(k), pin)]
        m = re.match(r"SKB(\d\d)_", n)
        out_items.append(int(m.group(1)) if m else GATE if n == gate_net else None)

    head = next(k for k in range(N_IN) if nets[(sin(k), IN_QH)] == "MISO_ISO")
    chain_in = [head]
    while len(chain_in) < N_IN:
        ser = nets[(sin(chain_in[-1]), IN_SER)]
        chain_in.append(next(k for k in range(N_IN) if nets[(sin(k), IN_QH)] == ser))
    first = next(k for k in range(N_OUT) if nets[(sout(k), OUT_SER)] == "MOSI_ISO")
    return State(geo, in_items, out_items, chain_in, [first, 1 - first])


# ---------------------------------------------------------------- outputs
def bit_maps(s):
    """frame[b][bit] and command bit -> item"""
    by_slot = {slot: it for slot, it in zip(s.geo.in_slots, s.in_items)}
    frame = []
    for p, k in enumerate(s.chain_in):
        frame.append([by_slot[(k, next(pin for pin, d in IN_PINS.items() if d == bit))] for bit in range(8)])
    out_slot = {slot: it for slot, it in zip(s.geo.out_slots, s.out_items)}
    cmd = {}
    for p, k in enumerate(s.chain_out):
        for pin, q in OUT_PINS.items():
            cmd[8 * p + q] = out_slot[(k, pin)]
    return frame, cmd


def ato_block(s):
    L = ["    # --- BEGIN pin map: generated by scripts/pin_swap.py, do not edit by hand ---",
         "    # 165 chain, first register drives MISO (frame byte 0 = chain position 0)"]
    ci, co = s.chain_in, s.chain_out
    L.append(f"    opto_miso.input ~ shift_in[{ci[0]}].q7")
    for p in range(N_IN - 1):
        L.append(f"    shift_in[{ci[p]}].serial_in ~ shift_in[{ci[p + 1]}].q7")
        L.append(f'    shift_in[{ci[p]}].serial_in.line.suggest_net_name = "SI_CHAIN_{p + 1}"')
    L.append(f"    shift_in[{ci[-1]}].serial_in.line ~ power_iso.lv")
    L.append("")
    L.append("    # DVM outputs and the 1-0-1-0 link-check constants on the 165 inputs")
    for (k, pin), it in sorted(zip(s.geo.in_slots, s.in_items), key=lambda e: (e[0][0], -IN_PINS[e[0][1]])):
        d = IN_PINS[pin]
        if isinstance(it, int):
            L.append(f"    shift_in[{k}].d[{d}] ~ dvm.dvm_out[{it - 1}]")
        else:
            L.append(f"    shift_in[{k}].d[{d}].line ~ power_iso.{'hv' if it.startswith('H') else 'lv'}")
    L.append("")
    L.append("    # 595 chain, first register is fed by MOSI")
    L.append(f"    shift_out[{co[0]}].serial_in ~ opto_mosi.output")
    L.append(f"    shift_out[{co[1]}].serial_in ~ shift_out[{co[0]}].serial_out")
    L.append(f'    shift_out[{co[1]}].serial_in.line.suggest_net_name = "SO_CHAIN_1"')
    L.append("")
    L.append("    # DVM command inputs on the 595 outputs")
    for (k, pin), it in sorted(zip(s.geo.out_slots, s.out_items), key=lambda e: (e[0][0], OUT_PINS[e[0][1]])):
        q = OUT_PINS[pin]
        if it == GATE:
            L.append(f"    sample_fet.G ~ shift_out[{k}].q[{q}].line")
            L.append(f'    shift_out[{k}].q[{q}].line.suggest_net_name = "SAMPLE_CONTACT_GATE"')
        elif it is not None:
            L.append(f"    dvm.{DVM_CMD[it]} ~ shift_out[{k}].q[{q}]")
        else:
            L.append(f"    # shift_out[{k}].q[{q}] unused")
    L.append("    # --- END pin map ---")
    return "\n".join(L)


def readme_tables(s):
    frame, cmd = bit_maps(s)

    def cell(it):
        if isinstance(it, int):
            return f"{it} {OUT_NAMES[it]}"
        return "`1`" if it.startswith("H") else "`0`"

    L = ["<!-- BEGIN bit maps: generated by scripts/pin_swap.py -->",
         "### Read frame (MISO, MSB first)", "",
         "Each cell gives the SKB pin and its meaning. `1`/`0` are the link-check",
         "constants: firmware should check them on every read.", "",
         "| Byte | bit7 | bit6 | bit5 | bit4 | bit3 | bit2 | bit1 | bit0 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for b, bits in enumerate(frame):
        L.append(f"| {b} | " + " | ".join(cell(bits[i]) for i in range(7, -1, -1)) + " |")
    L += ["", "### Command word (MOSI bytes 3–4, CMD_HI = bits 15–8)", "",
          "| Bit | SKB pin | Signal (manual §9) |", "|---|---|---|"]
    for n in range(16):
        it = cmd[n]
        if it is None:
            L.append(f"| {n} | – | unused |")
        else:
            pin = 39 if it == GATE else it
            L.append(f"| {n} | {pin} | {CMD_NAMES[pin]} |")
    L += ["",
          "* FUNCTION, read as (43, 42): 11 = DC, 01 = AC, 10 = Ω, 00 = CHECK.",
          "* Integration time, read as (44, 45, 46) = (4)(2)(1): 011 = 1 ms, 100 = 20 ms,",
          "  101 = 100 ms, 110 = 1 s, 111 = 10 s.",
          "* Range, read as (50, 49, 48) = (4)(2)(1): 000 = 1000 V / 10 MΩ … 101 = 10 mV /",
          "  100 Ω, 110 = auto / 10 Ω, 111 = auto.",
          "<!-- END bit maps -->"]
    return "\n".join(L)


COLOURS = {"in": "#2f6fdf", "out": "#e07020", "chain": "#2a9d50"}


def svg(panels, path):
    """Ratsnest pictures of the DVM half of the board, one panel per state."""
    x0, x1, y0, y1, s = -40.0, 40.0, 1.0, 27.5, 9.0
    w, h = (x1 - x0) * s, (y1 - y0) * s + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h * len(panels):.0f}" '
           f'font-family="sans-serif" font-size="13">']
    for n, (title, segs, pads) in enumerate(panels):
        oy = n * h

        def X(x):
            return (x - x0) * s

        def Y(y):
            return oy + 30 + (y - y0) * s

        out.append(f'<rect x="0" y="{oy}" width="{w}" height="{h}" fill="#fafafa" stroke="#ccc"/>')
        out.append(f'<text x="8" y="{oy + 20}" font-weight="bold">{title}</text>')
        for (x, y), r in pads:
            out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{r * s:.1f}" fill="#b8a050"/>')
        for kind, a, b in segs:
            out.append(f'<line x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(b[0]):.1f}" y2="{Y(b[1]):.1f}" '
                       f'stroke="{COLOURS.get(kind, "#999")}" stroke-width="1.2" stroke-opacity="0.85"/>')
    out.append("</svg>")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def panel(title, s):
    segs = [(net[0] if net[0] != "in" or isinstance(net[1], int) else "const", a, b)
            for net, ss in s.segs.items() for a, b in ss]
    pads = [(xy, 0.8 if a == "dvm.connector" else 0.45) for (a, _), xy in s.geo.pads.items()
            if xy[1] > 1.5 and (a == "dvm.connector" or a.startswith("shift_") or a.startswith(
                ("drdy_buffer", "sample_fet", "opto_miso", "opto_mosi")))]
    return (f"{title}: {s.length():.0f} mm of ratsnest, {s.crossings()} crossings", segs, pads)


def replace_block(text, begin, end, new):
    i, j = text.index(begin), text.index(end)
    j = text.index("\n", j) if "\n" in text[j:] else len(text)
    line_start = text.rfind("\n", 0, i) + 1
    return text[:line_start] + new + text[j:]


def report(name, s):
    longest = max(s.segs, key=lambda n: s.length([n]))
    print(f"{name:8s} length {s.length():7.1f} mm   crossings {s.crossings():4d}   "
          f"cost {s.cost():7.1f}   longest {longest[1]} {s.length([longest]):.1f} mm")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="rewrite main.ato and README.md blocks")
    ap.add_argument("--plot", help="write an SVG of the ratsnest (before/after with --before)")
    ap.add_argument("--before", help="JSON of a previous map (from --save) to draw as 'before'")
    ap.add_argument("--save", help="save the current map as JSON")
    ap.add_argument("--no-search", action="store_true", help="only report the current map")
    args = ap.parse_args()

    pads, nets = load_layout()
    geo = Geometry(pads, nets)
    now = current_state(geo, nets)
    report("current", now)
    if args.save:
        Path(args.save).write_text(json.dumps(
            {"in": now.in_items, "out": now.out_items, "chain_in": now.chain_in, "chain_out": now.chain_out}))
    if args.plot:
        panels = []
        if args.before:
            d = json.loads(Path(args.before).read_text())
            old = State(geo, d["in"], d["out"], d["chain_in"], d["chain_out"])
            panels.append(panel("Before pin swap", old))
        panels.append(panel("After pin swap" if args.before else "Current", now))
        svg(panels, args.plot)
        print(f"wrote {args.plot}")
    if args.no_search:
        return 0

    best = now
    for r in range(RESTARTS):
        rng = random.Random(SEED + r)
        start = now.copy()
        if r:  # random restarts from shuffled maps
            rng.shuffle(start.in_items)
            rng.shuffle(start.out_items)
            start = State(geo, start.in_items, start.out_items, start.chain_in, start.chain_out)
        cand = anneal(start, rng)
        cand = State(geo, cand.in_items, cand.out_items, cand.chain_in, cand.chain_out)  # exact recount
        report(f"run {r}", cand)
        if cand.cost() < best.cost() - 1e-6:
            best = cand
    report("best", best)

    if best is now:
        print("current map is already the best found")
    if args.write:
        text = MAIN_ATO.read_text(encoding="utf-8")
        MAIN_ATO.write_text(replace_block(text, "# --- BEGIN pin map", "# --- END pin map", ato_block(best)),
                            encoding="utf-8")
        text = README.read_text(encoding="utf-8")
        README.write_text(replace_block(text, "<!-- BEGIN bit maps", "<!-- END bit maps", readme_tables(best)),
                          encoding="utf-8")
        print(f"wrote {MAIN_ATO.name} and {README.name}; now run `ato build`")
    else:
        print(ato_block(best))
    return 0


if __name__ == "__main__":
    sys.exit(main())
