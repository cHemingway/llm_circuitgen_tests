#!/usr/bin/env python3
"""Build BOMs from the SKiDL netlist.

  output/bom.csv              grouped BOM with MPN / manufacturer / LCSC
  pcb/fab/bom_jlcpcb.csv      JLCPCB assembly format (Comment, Designator, Footprint, LCSC Part #)
"""

import csv
import pathlib
import re
from collections import OrderedDict

HERE = pathlib.Path(__file__).resolve().parent.parent
NET = HERE / "output" / "solartron_7075_interface.net"

# Off-board / mechanical items (not in the netlist)
EXTRA = [
    {"Qty": 2, "Refs": "-", "Value": "Jackscrew 4-40 UNC, >= 10 mm thread",
     "Footprint": "-", "MPN": "any D-sub jackscrew / thumbscrew (e.g. Norcomp 4-40 thumbscrew)",
     "Manufacturer": "-", "LCSC": "-",
     "Note": "fits through J1's 3.2 mm flange holes into the meter's socket screw-locks; check the "
             "thread on your 70754 (4-40 UNC is the D-sub standard)"},
]


def parse(path):
    txt = path.read_text()
    comps = []
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\(tstamps', txt, re.S):
        ref, body = m.group(1), m.group(2)
        val = re.search(r'\(value "([^"]*)"\)', body).group(1)
        fp = re.search(r'\(footprint "([^"]*)"\)', body)
        fields = dict(re.findall(r'\(field\s+\(name "([^"]+)"\)\s*"([^"]*)"\)', body))
        comps.append({"ref": ref, "value": val, "footprint": fp.group(1) if fp else "",
                      **fields})
    return comps


def refkey(r):
    m = re.match(r"([A-Za-z]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def main():
    comps = parse(NET)
    groups = OrderedDict()
    for c in sorted(comps, key=lambda c: refkey(c["ref"])):
        key = (c["value"], c["footprint"], c.get("LCSC", ""), c.get("MPN", ""))
        groups.setdefault(key, []).append(c)

    rows = []
    for (val, fp, lcsc, mpn), cs in groups.items():
        rows.append({"Qty": len(cs), "Refs": " ".join(c["ref"] for c in cs), "Value": val,
                     "Footprint": fp.split(":")[-1], "MPN": mpn,
                     "Manufacturer": cs[0].get("Manufacturer", ""), "LCSC": lcsc, "Note": ""})
    for r in rows:
        if r["LCSC"] == "C17502305":
            r["Note"] = ("THT; LCSC lists it but often without stock - any DD-50 male straight PCB "
                         "plug with 3.1 mm plain flange holes and the 2.77 x 2.84 mm grid fits")
        if r["Refs"].startswith("U5"):
            r["Note"] = "KiCad TLP2310 symbol used (identical SO6/5-lead pinout)"
        if r["Refs"] == "PS1":
            r["Note"] = "Mornsun-style SIP-4 pinout (1 -Vin, 2 +Vin, 3 0V, 4 +Vo)"
    rows += EXTRA

    out = HERE / "output" / "bom.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    fab = HERE / "pcb" / "fab"
    fab.mkdir(parents=True, exist_ok=True)
    with (fab / "bom_jlcpcb.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows[:-len(EXTRA)]:
            w.writerow([r["Value"] if r["Value"] else r["MPN"], ",".join(r["Refs"].split()),
                        r["Footprint"], r["LCSC"]])
    print(f"{len(comps)} parts in {len(rows) - len(EXTRA)} lines -> {out}")


if __name__ == "__main__":
    main()
