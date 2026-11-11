#!/usr/bin/env python3
"""Convert KiCad's CSV placement file into JLCPCB's CPL column format.

Note: JLCPCB's part orientation conventions differ for some packages; check
their placement preview before ordering assembly.
"""
import csv
import pathlib
import sys

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
with src.open() as f, dst.open("w", newline="") as g:
    w = csv.writer(g)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in csv.DictReader(f):
        w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                    "Top" if r["Side"].lower().startswith("top") else "Bottom", r["Rot"]])
