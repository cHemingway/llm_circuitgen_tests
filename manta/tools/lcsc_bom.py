#!/usr/bin/env python3
"""Group manta's per-designator BOM into one line per LCSC part, in the column
layout JLCPCB's assembly service reads (Comment, Designator, Footprint,
LCSC Part #), with the manufacturer part number alongside.

Usage: python3 tools/lcsc_bom.py output/solartron7075-bom.csv output/solartron7075-bom-lcsc.csv
"""

import csv
import re
import sys


def natural(designator):
    m = re.match(r"([A-Z]+)(\d+)$", designator)
    return (m.group(1), int(m.group(2))) if m else (designator, 0)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    groups = {}
    for row in csv.DictReader(open(src)):
        if row["fitted"] != "TRUE":
            continue
        key = row["lcsc"]
        g = groups.setdefault(key, {"row": row, "des": set()})
        g["des"].add(row["designator"])
    with open(dst, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #",
                    "Manufacturer", "MPN", "Quantity"])
        for key, g in sorted(groups.items(), key=lambda kv: natural(min(kv[1]["des"], key=natural))):
            r = g["row"]
            des = sorted(g["des"], key=natural)
            w.writerow([r["value"], ",".join(des), r["footprint"], key,
                        r["manufacturer"], r["mpn"], len(des)])
    print(f"wrote {dst}: {len(groups)} lines")


if __name__ == "__main__":
    main()
