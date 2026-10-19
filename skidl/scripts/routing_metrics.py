#!/usr/bin/env python3
"""Routing figures for the meter-side signal nets of a routed board.

Usage: routing_metrics.py [board.kicad_pcb]

Groups the 2-pad signal nets between J1, the resistor arrays and the shift
registers, and reports per group: straight-line (ratsnest) length, ratsnest
crossings, routed track length and via count. Also prints board totals.
"""

import itertools
import math
import pathlib
import sys

import pcbnew

HERE = pathlib.Path(__file__).resolve().parent.parent
BOARD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "pcb" / "solartron_7075_interface.kicad_pcb"
to_mm = pcbnew.ToMM


def groups(board):
    """{group: {net: [(ref, pad, x, y), ...]}} for the meter-side signal nets."""
    pads = {}
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n:
                q = p.GetPosition()
                pads.setdefault(n, []).append((f.GetReference(), p.GetNumber(), to_mm(q.x), to_mm(q.y)))
    out = {"J1 -> arrays": {}, "arrays -> 74HCT165": {}, "74HC595 -> J1": {}}
    for n, pl in pads.items():
        refs = {r for r, *_ in pl}
        if len(pl) != 2:
            continue
        if "J1" in refs and any(r.startswith("RN") for r in refs):
            out["J1 -> arrays"][n] = pl
        elif any(r.startswith("RN") for r in refs) and refs & {"U10", "U11", "U12", "U13", "U14"}:
            out["arrays -> 74HCT165"][n] = pl
        elif "J1" in refs and refs & {"U15", "U16", "Q1"}:
            out["74HC595 -> J1"][n] = pl
    return out


def crossings(segs):
    def ccw(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    n = 0
    for (a, b), (c, d) in itertools.combinations(segs, 2):
        if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0:
            n += 1
    return n


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    tracks = {}
    vias = {}
    for t in board.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            vias[n] = vias.get(n, 0) + 1
        else:
            tracks[n] = tracks.get(n, 0.0) + to_mm(t.GetLength())
    print(f"{'group':22s} {'nets':>4s} {'airwire mm':>10s} {'crossings':>9s} {'track mm':>9s} {'vias':>5s}")
    allsegs = []
    for g, nets in groups(board).items():
        segs = [((pl[0][2], pl[0][3]), (pl[1][2], pl[1][3])) for pl in nets.values()]
        allsegs += segs
        air = sum(math.dist(a, b) for a, b in segs)
        print(f"{g:22s} {len(nets):4d} {air:10.1f} {crossings(segs):9d} "
              f"{sum(tracks.get(n, 0) for n in nets):9.1f} {sum(vias.get(n, 0) for n in nets):5d}")
    print(f"{'all three groups':22s} {'':4s} {'':10s} {crossings(allsegs):9d}")
    print(f"board: {sum(tracks.values()):.0f} mm of track, {sum(vias.values())} vias")


if __name__ == "__main__":
    main()
