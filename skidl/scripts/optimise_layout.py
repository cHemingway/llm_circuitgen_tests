#!/usr/bin/env python3
"""Search for a tidier meter side: pin swaps between parts, and moved registers.

Usage: optimise_layout.py [board.kicad_pcb]   (KiCad's Python, needs numpy)

Second round after optimise_pins.py (which only swapped pins within parts).
Starting from the placed board, this also lets:
  * any meter output use any resistor-array channel and any 74HCT165 input
    (the 4 spare inputs become the link-check bits),
  * any command input use any 74HC595 output,
  * the 74HCT165s swap places along the bottom row, the U14/74HC595 trio swap
    places along the top row (RN9 follows U14, each decoupling cap follows its
    register), and any of them turn 180 degrees.
J1, the arrays, the optocouplers and everything on the host side stay put.

The cost is 10 mm per crossing of straight pad-to-pad lines plus their length,
over the J1/array/register signals, the register chains, and minimum spanning
trees of the SCLK, LATCH, /OE and MOSI nets. Prints before/after figures and
the tables for solartron_7075_interface.py and layout_pcb.py.
"""

import math
import pathlib
import random
import sys

import numpy as np
import pcbnew

HERE = pathlib.Path(__file__).resolve().parent.parent
BOARD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "pcb" / "solartron_7075_interface.kicad_pcb"
CROSS_MM = 10.0
D_PINS = {"D7": 6, "D6": 5, "D5": 4, "D4": 3, "D3": 14, "D2": 13, "D1": 12, "D0": 11}
Q_PINS = {"QA": 15, "QB": 1, "QC": 2, "QD": 3, "QE": 4, "QF": 5, "QG": 6, "QH": 7}
SR165 = ["U10", "U11", "U12", "U13", "U14"]
SR595 = ["U15", "U16"]
BOTTOM = ["U10", "U11", "U12", "U13"]
TOP = ["U14", "U15", "U16"]
ARRAYS = [f"RN{k}" for k in range(1, 10)]
# Pins of the moving parts on each shared net (U5-U8 drive them from the barrier)
BUSES = {"ISO_SCLK": ({"165": 2, "595": 11}, ("U5", "5")),
         "ISO_LATCH": ({"165": 1, "595": 12}, ("U7", "5")),
         "ISO_OE_N": ({"595": 13}, ("U8", "5")),
         "ISO_MOSI": ({"U15": 14}, ("U6", "5"))}
CHAINS = [(("U10", 9), ("U9", "3")), (("U11", 9), ("U10", "10")), (("U12", 9), ("U11", "10")),
          (("U13", 9), ("U12", "10")), (("U14", 9), ("U13", "10")), (("U15", 9), ("U16", "14"))]
EXTRA = {"SAMPLE_CONTACT_DRV": ("Q1", "1"), "LED_REMOTE": ("R13", "1")}


def load(path):
    b = pcbnew.LoadBoard(str(path))
    pos, net, centre = {}, {}, {}
    for f in b.GetFootprints():
        r = f.GetReference()
        xs, ys = [], []
        for p in f.Pads():
            q = p.GetPosition()
            pos[(r, p.GetNumber())] = (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
            net[(r, p.GetNumber())] = p.GetNetname().lstrip("/")
            xs.append(pcbnew.ToMM(q.x))
            ys.append(pcbnew.ToMM(q.y))
        if xs:
            centre[r] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return pos, net, centre


def is_signal(n):
    return n not in ("ISO_+5V", "ISO_GND") and not n.startswith("unconnected-")


class Layout:
    """Placement of the moving parts plus the signal-to-pin assignment."""

    def __init__(self, pos, net, centre):
        self.fixed = pos
        self.j1 = {net[("J1", str(n))]: pos[("J1", str(n))] for n in range(1, 51)}
        # Slots: where each register is now; offsets of its pads at 0 degrees
        self.slot_xy = {u: centre[u] for u in BOTTOM + TOP}
        self.offset = {}
        for u in BOTTOM + TOP:
            cx, cy = centre[u]
            self.offset[u] = {p: (pos[(u, str(p))][0] - cx, pos[(u, str(p))][1] - cy) for p in range(1, 17)}
        rn9_c = centre["RN9"]
        self.rn9_offset = {p: (pos[("RN9", str(p))][0] - centre["U14"][0], pos[("RN9", str(p))][1] - centre["U14"][1])
                           for p in range(1, 9)}
        del rn9_c
        self.where = {u: u for u in BOTTOM + TOP}   # register -> slot (named by its first occupant)
        self.rot = {u: 0 for u in BOTTOM + TOP}
        self.arr = {}                               # signal -> (array, channel 1-4)
        for r in ARRAYS:
            for c in range(1, 5):
                self.arr[net[(r, str(c))]] = (r, c)
        self.reg = {u: {d: net[(u, str(p))].removesuffix("_R") for d, p in D_PINS.items()} for u in SR165}
        self.out = {u: {q: net[(u, str(p))] for q, p in Q_PINS.items()} for u in SR595}

    def copy(self):
        c = object.__new__(Layout)
        c.fixed, c.j1, c.slot_xy, c.offset, c.rn9_offset = self.fixed, self.j1, self.slot_xy, self.offset, self.rn9_offset
        c.where, c.rot = dict(self.where), dict(self.rot)
        c.arr = dict(self.arr)
        c.reg = {u: dict(m) for u, m in self.reg.items()}
        c.out = {u: dict(m) for u, m in self.out.items()}
        return c

    def pad(self, ref, pin):
        pin = int(pin)
        if ref in self.where:
            sx, sy = self.slot_xy[self.where[ref]]
            dx, dy = self.offset[ref][pin]
            s = -1 if self.rot[ref] else 1
            return sx + s * dx, sy + s * dy
        if ref == "RN9":
            sx, sy = self.slot_xy[self.where["U14"]]
            dx, dy = self.rn9_offset[pin]
            return sx + dx, sy + dy
        return self.fixed[(ref, str(pin))]

    def segments(self):
        seg = []
        for s, (r, c) in self.arr.items():
            seg.append((self.j1[s], self.pad(r, c)))
        for u, m in self.reg.items():
            for d, s in m.items():
                if is_signal(s):
                    r, c = self.arr[s]
                    seg.append((self.pad(r, 9 - c), self.pad(u, D_PINS[d])))
        for u, m in self.out.items():
            for q, s in m.items():
                if is_signal(s):
                    dst = self.pad(*EXTRA[s]) if s in EXTRA else self.j1[s]
                    seg.append((self.pad(u, Q_PINS[q]), dst))
        for (a, pa), (b, pb) in CHAINS:
            seg.append((self.pad(a, pa), self.pad(b, pb)))
        for pins, src in BUSES.values():
            pts = [self.pad(*src)]
            for kind, p in pins.items():
                refs = SR165 if kind == "165" else SR595 if kind == "595" else [kind]
                pts += [self.pad(u, p) for u in refs]
            seg += mst(pts)
        return np.array(seg)

    def cost(self):
        s = self.segments()
        a, b = s[:, 0], s[:, 1]
        length = np.hypot(*(b - a).T).sum()
        A, B, C, D = a[:, None], b[:, None], a[None, :], b[None, :]
        x = (ccw(A, B, C) * ccw(A, B, D) < 0) & (ccw(C, D, A) * ccw(C, D, B) < 0)
        n = int(np.triu(x, 1).sum())
        return CROSS_MM * n + length, n, length


def ccw(p, q, r):
    return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])


def mst(pts):
    pts = np.array(pts)
    n = len(pts)
    inside = [0]
    d = np.hypot(*(pts - pts[0]).T)
    parent = np.zeros(n, int)
    d[0] = np.inf
    edges = []
    for _ in range(n - 1):
        k = int(np.argmin(d))
        edges.append((tuple(pts[parent[k]]), tuple(pts[k])))
        inside.append(k)
        nd = np.hypot(*(pts - pts[k]).T)
        upd = nd < d
        upd[inside] = False
        d[upd], parent[upd] = nd[upd], k
        d[inside] = np.inf
    return edges


def move(st, rng):
    """Apply one random move in place."""
    k = rng.random()
    if k < 0.30:
        s1, s2 = rng.sample(sorted(st.arr), 2)
        st.arr[s1], st.arr[s2] = st.arr[s2], st.arr[s1]
    elif k < 0.65:
        slots = [(u, d) for u in SR165 for d in D_PINS]
        (u1, d1), (u2, d2) = rng.sample(slots, 2)
        st.reg[u1][d1], st.reg[u2][d2] = st.reg[u2][d2], st.reg[u1][d1]
    elif k < 0.85:
        slots = [(u, q) for u in SR595 for q in Q_PINS]
        (u1, q1), (u2, q2) = rng.sample(slots, 2)
        st.out[u1][q1], st.out[u2][q2] = st.out[u2][q2], st.out[u1][q1]
    elif k < 0.93:
        row = BOTTOM if rng.random() < 0.6 else TOP
        a, b = rng.sample(row, 2)
        st.where[a], st.where[b] = st.where[b], st.where[a]
    else:
        u = rng.choice(BOTTOM + TOP)
        st.rot[u] ^= 1


def anneal(start, rng, steps, t0=40.0, t1=0.05):
    st = start.copy()
    cur = st.cost()[0]
    best = (cur, st.copy())
    for i in range(steps):
        t = t0 * (t1 / t0) ** (i / steps)
        trial = st.copy()
        move(trial, rng)
        c = trial.cost()[0]
        if c <= cur or rng.random() < math.exp((cur - c) / t):
            st, cur = trial, c
            if c < best[0]:
                best = (c, st.copy())
    return best


def tables(st):
    slot_name = {}
    print("BOTTOM_ROW = [  # left to right: (register, rotated 180 degrees)")
    for slot in sorted(BOTTOM, key=lambda u: st.slot_xy[u][0]):
        u = next(r for r in BOTTOM if st.where[r] == slot)
        print(f'    ("{u}", {bool(st.rot[u])}),  # x = {st.slot_xy[slot][0]:.1f}')
        slot_name[u] = slot
    print("]\nTOP_ROW = [")
    for slot in sorted(TOP, key=lambda u: st.slot_xy[u][0]):
        u = next(r for r in TOP if st.where[r] == slot)
        print(f'    ("{u}", {bool(st.rot[u])}),  # x = {st.slot_xy[slot][0]:.1f}')
    print("]\nARRAYS = [  # RN1..RN9: signals on channels 1-4")
    for r in ARRAYS:
        ch = sorted((c, s) for s, (rr, c) in st.arr.items() if rr == r)
        print(f"    {[s for _, s in ch]!r},")
    print("]\nREGS_165 = [  # U10..U14: inputs D7..D0 (1 / 0 = link-check bit)")
    bit = 1
    for u in SR165:
        row = []
        for d in ("D7", "D6", "D5", "D4", "D3", "D2", "D1", "D0"):
            s = st.reg[u][d]
            if is_signal(s):
                row.append(s)
            else:
                row.append(bit)
                bit ^= 1
        print(f"    {row!r},")
    print("]\nREGS_595 = {  # outputs QA..QH (None = unused)")
    for u in SR595:
        print(f'    "{u}": {[s if is_signal(s) else None for s in (st.out[u][q] for q in Q_PINS)]!r},')
    print("}")


def main():
    pos, net, centre = load(BOARD)
    base = Layout(pos, net, centre)
    c0 = base.cost()
    print(f"current: {c0[1]} crossings, {c0[2]:.1f} mm of straight lines (cost {c0[0]:.0f})")
    rng = random.Random(7075)
    runs = [anneal(base, rng, 120000) for _ in range(4)]
    for c, s in runs:
        cc = s.cost()
        print(f"  run: {cc[1]} crossings, {cc[2]:.1f} mm (cost {c:.0f})")
    best = min(runs, key=lambda r: r[0])[1]
    c1 = best.cost()
    print(f"best:    {c1[1]} crossings, {c1[2]:.1f} mm of straight lines (cost {c1[0]:.0f})\n")
    tables(best)


if __name__ == "__main__":
    main()
