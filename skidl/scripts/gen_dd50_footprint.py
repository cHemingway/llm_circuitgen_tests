#!/usr/bin/env python3
"""Generate a KiCad footprint for a 50-way (DD-50, shell size D) male D-sub,
vertical (straight) PCB mount, with plain mounting holes for jackscrews.

KiCad 10's Connector_Dsub library has no 50-way parts, so this footprint is
generated here. Dimensions follow the Amphenol "Delta D" straight solder-to-board
drawing (D50P24A4PA00LF) and the standard DD-50 layout:

  * 3 rows: 17 (pins 1-17), 16 (pins 18-33), 17 (pins 34-50)
  * pitch 2.77 mm along a row, 2.84 mm between rows, middle row offset 1.385 mm
  * mounting hole spacing 61.11 mm, flange 67.10 x 15.34 mm
  * PCB tails 0.6-0.8 mm -> 1.0 mm drill, 1.6 mm pads (as KiCad's generator)

Pad 1 is at the origin; the view is from the mating face of the plug, which
is the component side of the footprint. Place the part on B.Cu to have the
connector stick out of the bottom of the board.
"""

import math
import pathlib

NAME = "DSUB-50_Pins_Vertical_P2.77x2.84mm_MountingHoles"
PITCH_X = 2.77
PITCH_Y = 2.84
ROWS = [(1, 17, 0.0), (18, 16, PITCH_X / 2), (34, 17, 0.0)]  # first pin, count, x-offset
X0 = 16 * PITCH_X / 2  # centre of pin field
Y0 = PITCH_Y  # middle row
HOLE_SPACING = 61.11
FLANGE_W, FLANGE_H = 67.10, 15.34
D_TOP, D_H = 52.68, 11.08  # outside of the male shell (wide side at row 1)
D_ANGLE = math.radians(10)


def line(x1, y1, x2, y2, layer, w):
    return (
        f'\t(fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f})\n'
        f'\t\t(stroke (width {w}) (type solid)) (layer "{layer}"))\n'
    )


def rect(x1, y1, x2, y2, layer, w):
    return (
        f'\t(fp_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f})\n'
        f'\t\t(stroke (width {w}) (type solid)) (fill no) (layer "{layer}"))\n'
    )


def outline(layer, w, grow=0.0):
    out = ""
    # Flange
    fx1, fx2 = X0 - FLANGE_W / 2 - grow, X0 + FLANGE_W / 2 + grow
    fy1, fy2 = Y0 - FLANGE_H / 2 - grow, Y0 + FLANGE_H / 2 + grow
    out += rect(fx1, fy1, fx2, fy2, layer, w)
    # D-shaped shell (trapezoid approximation)
    top_half = D_TOP / 2
    bot_half = top_half - D_H * math.tan(D_ANGLE)
    ty, by = Y0 - D_H / 2, Y0 + D_H / 2
    pts = [(X0 - top_half, ty), (X0 + top_half, ty), (X0 + bot_half, by), (X0 - bot_half, by)]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
        out += line(xa, ya, xb, yb, layer, w)
    return out


def pad(num, x, y):
    shape = "rect" if num == 1 else "circle"
    return (
        f'\t(pad "{num}" thru_hole {shape} (at {x:.4f} {y:.4f}) (size 1.6 1.6) (drill 1)\n'
        f'\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no))\n'
    )


def main():
    body = f'(footprint "{NAME}"\n'
    body += '\t(version 20260206)\n\t(generator "skidl_solartron_gen")\n\t(layer "F.Cu")\n'
    body += (
        '\t(descr "50-pin D-Sub connector (DD-50), straight/vertical, THT-mount, pins (male), '
        'pitch 2.77x2.84mm, distance of mounting holes 61.11mm, '
        'e.g. Amphenol D50P24A4PA00LF")\n'
    )
    body += '\t(tags "50-pin D-Sub DD50 connector straight vertical THT pins male mounting holes 61.11mm")\n'
    body += (
        f'\t(property "Reference" "REF**" (at {X0:.2f} {Y0 - FLANGE_H / 2 - 1.2:.2f} 0) (layer "F.SilkS")\n'
        '\t\t(effects (font (size 1 1) (thickness 0.15))))\n'
        f'\t(property "Value" "{NAME}" (at {X0:.2f} {Y0 + FLANGE_H / 2 + 1.2:.2f} 0) (layer "F.Fab")\n'
        '\t\t(effects (font (size 1 1) (thickness 0.15))))\n'
    )
    body += '\t(attr through_hole)\n'
    body += outline("F.Fab", 0.1)
    body += outline("F.SilkS", 0.12, grow=0.11)
    cx1, cx2 = X0 - FLANGE_W / 2 - 0.5, X0 + FLANGE_W / 2 + 0.5
    cy1, cy2 = Y0 - FLANGE_H / 2 - 0.5, Y0 + FLANGE_H / 2 + 0.5
    body += rect(cx1, cy1, cx2, cy2, "F.CrtYd", 0.05)
    # Pin 1 marker
    body += line(-0.6, -2.2, 0.6, -2.2, "F.SilkS", 0.12)
    body += (
        f'\t(fp_text user "${{REFERENCE}}" (at {X0:.2f} {Y0:.2f} 0) (layer "F.Fab")\n'
        '\t\t(effects (font (size 1 1) (thickness 0.15))))\n'
    )
    for first, count, xoff in ROWS:
        row_y = {1: 0.0, 18: PITCH_Y, 34: 2 * PITCH_Y}[first]
        for i in range(count):
            body += pad(first + i, xoff + i * PITCH_X, row_y)
    for sx in (-1, 1):
        body += (
            f'\t(pad "SH" thru_hole circle (at {X0 + sx * HOLE_SPACING / 2:.4f} {Y0:.4f}) '
            '(size 5 5) (drill 3.2)\n'
            '\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no))\n'
        )
    body += ')\n'
    out = pathlib.Path(__file__).resolve().parent.parent / "lib" / "Solartron7075.pretty" / f"{NAME}.kicad_mod"
    out.write_text(body)
    print("wrote", out)


if __name__ == "__main__":
    main()
