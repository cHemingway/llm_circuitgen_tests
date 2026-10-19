#!/usr/bin/env python3
"""Search for a tidier pin assignment on the meter side (pin swaps within parts).

Usage: optimise_pins.py [board.kicad_pcb]   (KiCad's Python, needs numpy)

Reads pad positions and the current signal-to-pin mapping from the placed
board, then permutes, without moving any part or any signal to another part:
  * the D inputs of each 74HCT165 (the 4 fixed check bits of U14 included),
  * the 4 channels of each resistor array, and which side faces J1,
  * the outputs of each 74HC595 (U16's two spare outputs included).
The cost is 10 mm per crossing of the straight pad-to-pad lines plus their
total length, minimised by simulated annealing from several starts. Prints the
before/after figures and the new tables for solartron_7075_interface.py.
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
D_PINS = {"D0": 11, "D1": 12, "D2": 13, "D3": 14, "D4": 3, "D5": 4, "D6": 5, "D7": 6}
Q_PINS = {"QA": 15, "QB": 1, "QC": 2, "QD": 3, "QE": 4, "QF": 5, "QG": 6, "QH": 7}
SR165 = ["U10", "U11", "U12", "U13", "U14"]
SR595 = ["U15", "U16"]


def load(path):
    b = pcbnew.LoadBoard(str(path))
    pos, net = {}, {}
    for f in b.GetFootprints():
        for p in f.Pads():
            q = p.GetPosition()
            pos[(f.GetReference(), p.GetNumber())] = (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
            net[(f.GetReference(), p.GetNumber())] = p.GetNetname().lstrip("/")
    return pos, net


def model(pos, net):
    """Current assignment and the fixed geometry it refers to."""
    j1 = {net[("J1", str(n))]: ("J1", str(n)) for n in range(1, 51)}
    arrays = {}
    for r in sorted({k[0] for k in pos if k[0].startswith("RN")}, key=lambda r: int(r[2:])):
        chans, flip = [], None
        for c in range(1, 5):
            a, b = net[(r, str(c))], net[(r, str(9 - c))]
            sig, f = (a, 0) if b == a + "_R" else (b, 1)
            chans.append(sig)
            flip = f if flip is None else flip
            assert flip == f, f"{r}: mixed orientation"
        arrays[r] = dict(chans=chans, flip=flip)
    regs = {}
    for u in SR165:
        regs[u] = {d: net[(u, str(p))].removesuffix("_R") for d, p in D_PINS.items()}
    outs = {u: {q: net[(u, str(p))] for q, p in Q_PINS.items()} for u in SR595}
    return j1, arrays, regs, outs


def is_signal(n):
    return n not in ("ISO_+5V", "ISO_GND") and not n.startswith("unconnected-")


class State:
    def __init__(self, pos, j1, arrays, regs, outs):
        self.pos, self.j1 = pos, j1
        self.arrays = {r: dict(chans=list(a["chans"]), flip=a["flip"]) for r, a in arrays.items()}
        self.regs = {u: dict(m) for u, m in regs.items()}
        self.outs = {u: dict(m) for u, m in outs.items()}
        # Where a 595 output goes when it is not a J1 pin
        self.extra = {"SAMPLE_CONTACT_DRV": ("Q1", "1"), "LED_REMOTE": ("R13", "1")}

    def segments(self):
        seg = []
        where = {}
        for r, a in self.arrays.items():
            for c, s in enumerate(a["chans"], 1):
                conn, filt = (c, 9 - c) if a["flip"] == 0 else (9 - c, c)
                seg.append((self.pos[self.j1[s]], self.pos[(r, str(conn))]))
                where[s] = (r, str(filt))
        for u, m in self.regs.items():
            for d, s in m.items():
                if s in where:
                    seg.append((self.pos[where[s]], self.pos[(u, str(D_PINS[d]))]))
        for u, m in self.outs.items():
            for q, s in m.items():
                if is_signal(s):
                    dst = self.extra.get(s) or self.j1[s]
                    seg.append((self.pos[(u, str(Q_PINS[q]))], self.pos[dst]))
        return np.array(seg)

    def cost(self):
        s = self.segments()
        a, b = s[:, 0], s[:, 1]
        length = np.hypot(*(b - a).T).sum()

        def ccw(p, q, r):
            return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])

        A, B = a[:, None], b[:, None]
        C, D = a[None, :], b[None, :]
        x = (ccw(A, B, C) * ccw(A, B, D) < 0) & (ccw(C, D, A) * ccw(C, D, B) < 0)
        crossings = int(np.triu(x, 1).sum())
        return CROSS_MM * crossings + length, crossings, length

    def moves(self):
        return [("rn", r) for r in self.arrays] * 3 + [("flip", r) for r in self.arrays] + \
            [("reg", u) for u in self.regs] * 4 + [("out", u) for u in self.outs] * 4

    def apply(self, mv, rng):
        kind, key = mv
        if kind == "rn":
            ch = self.arrays[key]["chans"]
            i, j = rng.sample(range(4), 2)
            ch[i], ch[j] = ch[j], ch[i]
            return lambda: ch.__setitem__(slice(None), [ch[j] if k == i else ch[i] if k == j else v
                                                        for k, v in enumerate(ch)])
        if kind == "flip":
            a = self.arrays[key]
            a["flip"] ^= 1
            return lambda: a.__setitem__("flip", a["flip"] ^ 1)
        m = self.regs[key] if kind == "reg" else self.outs[key]
        i, j = rng.sample(sorted(m), 2)
        m[i], m[j] = m[j], m[i]
        return lambda: m.update({i: m[j], j: m[i]})


def anneal(start, rng, steps=60000, t0=30.0, t1=0.05):
    st = State(start.pos, start.j1, start.arrays, start.regs, start.outs)
    cur = st.cost()[0]
    best = (cur, State(st.pos, st.j1, st.arrays, st.regs, st.outs))
    mvs = st.moves()
    for k in range(steps):
        t = t0 * (t1 / t0) ** (k / steps)
        undo = st.apply(rng.choice(mvs), rng)
        c = st.cost()[0]
        if c <= cur or rng.random() < math.exp((cur - c) / t):
            cur = c
            if c < best[0]:
                best = (c, State(st.pos, st.j1, st.arrays, st.regs, st.outs))
        else:
            undo()
    return best


def main():
    pos, net = load(BOARD)
    j1, arrays, regs, outs = model(pos, net)
    base = State(pos, j1, arrays, regs, outs)
    c0 = base.cost()
    print(f"current: {c0[1]} crossings, {c0[2]:.1f} mm of straight lines")
    rng = random.Random(7075)
    results = [anneal(base, rng) for _ in range(6)]
    for c, s in results:
        print(f"  run: {s.cost()[1]} crossings, {s.cost()[2]:.1f} mm")
    best = min(results, key=lambda x: x[0])[1]
    c1 = best.cost()
    print(f"best:    {c1[1]} crossings, {c1[2]:.1f} mm of straight lines\n")
    print("ARRAYS = {  # ref: (signals on channels 1-4, connector side on pins 5-8)")
    for r, a in best.arrays.items():
        print(f'    "{r}": ({a["chans"]!r}, {bool(a["flip"])}),')
    print("}\nREGS_165 = {  # ref: inputs D7..D0 (1 / 0 = fixed check bit)")
    for u, m in best.regs.items():
        row = ["1" if m[d] == "ISO_+5V" else "0" if m[d] == "ISO_GND" else m[d] for d in
               ("D7", "D6", "D5", "D4", "D3", "D2", "D1", "D0")]
        print(f'    "{u}": {row!r},')
    print("}\nREGS_595 = {  # ref: outputs QA..QH (None = unused)")
    for u, m in best.outs.items():
        row = [m[q] if is_signal(m[q]) else None for q in Q_PINS]
        print(f'    "{u}": {row!r},')
    print("}")


if __name__ == "__main__":
    main()
