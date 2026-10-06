"""
Placement sanity checks for the Solartron 7075 USB interface layout.

    ~/.local/share/uv/tools/atopile/bin/python scripts/check_layout.py

Checks:
  1. every pad lies inside the 78 x 60 mm outline (0.5 mm margin)
  2. no two footprints on the same face overlap (pads + silk/fab extents);
     through-hole pads count on both faces
  3. isolation: every pad on a USB-side net is at y < -BARRIER and every pad
     on a DVM-side net is at y > +BARRIER (domains found by walking the
     netlist without crossing the optocouplers / isolated DC-DC)
  4. nothing on the top face within the jackscrew-head keep-outs
"""

import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from faebryk.libs.kicad.fileformats import kicad

LAYOUT = Path(__file__).resolve().parent.parent / "layouts/default/default.kicad_pcb"
BOARD_W, BOARD_H = 78.0, 60.0
EDGE_MARGIN = 0.5
CLEARANCE = 0.2
BARRIER = 2.0
JACKSCREW_KEEPOUT_R = 4.0  # 4-40 jackscrew hex head / washer
BARRIER_PARTS = ("TLP2361", "IB0505LS")


def props(fp):
    return {p.name: p.value for p in fp.propertys}


def to_abs(fp, x, y):
    a = math.radians(fp.at.r or 0)
    return (
        fp.at.x + x * math.cos(a) + y * math.sin(a),
        fp.at.y - x * math.sin(a) + y * math.cos(a),
    )


def bbox(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b, gap):
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def main() -> int:
    pcb = kicad.loads(kicad.pcb.PcbFile, LAYOUT).kicad_pcb
    errors = []
    side_boxes = defaultdict(list)  # face -> [(ref, bbox)]
    pad_net = {}
    pad_xy = {}
    th_refs = set()
    jackscrews = []

    for fp in pcb.footprints:
        pr = props(fp)
        ref = pr["Reference"]
        face = "B" if fp.layer.startswith("B.") else "F"
        pts = []
        for pad in fp.pads:
            cx, cy = to_abs(fp, pad.at.x, pad.at.y)
            r = max(pad.size.w, pad.size.h or pad.size.w) / 2
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
            pad_xy[(ref, pad.name)] = (cx, cy)
            if pad.net is not None and pad.net.name:
                pad_net[(ref, pad.name)] = pad.net.name
            if "thru_hole" in str(pad.type):
                th_refs.add(ref)
            if not (
                -BOARD_W / 2 + EDGE_MARGIN <= cx <= BOARD_W / 2 - EDGE_MARGIN
                and -BOARD_H / 2 + EDGE_MARGIN <= cy <= BOARD_H / 2 - EDGE_MARGIN
            ):
                errors.append(f"{ref} pad {pad.name} outside board at ({cx:.2f},{cy:.2f})")
        body = []
        for ln in fp.fp_lines:
            if "SilkS" in ln.layer or "Fab" in ln.layer or "CrtYd" in ln.layer:
                body += [to_abs(fp, ln.start.x, ln.start.y), to_abs(fp, ln.end.x, ln.end.y)]
        box = bbox(pts + body) if (pts or body) else None
        if box is None:
            continue
        side_boxes[face].append((ref, bbox(pts + body)))
        if "DD50" in fp.name:
            jackscrews = [pad_xy[(ref, s)] for s in ("S1", "S2")]

    # 2. overlaps (TH footprints occupy both faces with their pads)
    for face in ("F", "B"):
        boxes = list(side_boxes[face])
        other = "B" if face == "F" else "F"
        for ref, box in side_boxes[other]:
            if ref in th_refs:
                # pads only on the other face
                pads = [xy for (r, _), xy in pad_xy.items() if r == ref]
                boxes.append((ref + "(pins)", bbox([(x - 0.8, y - 0.8) for x, y in pads] + [(x + 0.8, y + 0.8) for x, y in pads])))
        for (ra, a), (rb, b) in combinations(boxes, 2):
            if ra.split("(")[0] == rb.split("(")[0]:
                continue
            if "(pins)" in ra or "(pins)" in rb:
                # coarse pin-field box: only check pads of the other part
                pins_ref, other_ref, pins_box = (ra, rb, a) if "(pins)" in ra else (rb, ra, b)
                pr = pins_ref.split("(")[0]
                hit = [
                    n for (r, n), (x, y) in pad_xy.items()
                    if r == other_ref and pins_box[0] <= x <= pins_box[2] and pins_box[1] <= y <= pins_box[3]
                ]
                pins = [xy for (r, _), xy in pad_xy.items() if r == pr]
                for (r, n), (x, y) in pad_xy.items():
                    if r != other_ref:
                        continue
                    for px, py in pins:
                        if math.hypot(px - x, py - y) < 1.6:
                            errors.append(f"{face}: {other_ref} pad {n} too close to {pr} pin")
                            break
                continue
            if overlap(a, b, CLEARANCE):
                errors.append(f"{face}: {ra} overlaps {rb}")

    # 3. isolation barrier, by net domain
    part_nets = defaultdict(set)
    net_parts = defaultdict(set)
    barrier_refs = set()
    for fp in pcb.footprints:
        if any(k in fp.name for k in BARRIER_PARTS):
            barrier_refs.add(props(fp)["Reference"])
    for (ref, _), net in pad_net.items():
        part_nets[ref].add(net)
        net_parts[net].add(ref)

    def domain(start):
        seen, todo = {start}, [start]
        while todo:
            for ref in net_parts[todo.pop()]:
                if ref in barrier_refs:
                    continue
                for n in part_nets[ref] - seen:
                    seen.add(n)
                    todo.append(n)
        return seen

    usb, iso = domain("GND"), domain("GND_ISO")
    if usb & iso:
        errors.append(f"nets in both domains: {sorted(usb & iso)}")
    for key, net in pad_net.items():
        y = pad_xy[key][1]
        if net in usb and y > -BARRIER:
            errors.append(f"USB-side pad {key} ({net}) at y={y:.2f}")
        if net in iso and y < BARRIER:
            errors.append(f"DVM-side pad {key} ({net}) at y={y:.2f}")

    # 4. jackscrew head keep-outs on the top face
    for ref, box in side_boxes["F"]:
        for jx, jy in jackscrews:
            nx = min(max(jx, box[0]), box[2])
            ny = min(max(jy, box[1]), box[3])
            if math.hypot(nx - jx, ny - jy) < JACKSCREW_KEEPOUT_R:
                errors.append(f"{ref} inside jackscrew keep-out at ({jx:.1f},{jy:.1f})")

    print(f"USB-side nets: {len(usb)}, DVM-side nets: {len(iso)}")
    for e in errors:
        print("ERROR", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
