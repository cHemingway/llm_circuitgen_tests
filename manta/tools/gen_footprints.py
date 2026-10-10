#!/usr/bin/env python3
"""Generate the two KiCad footprints this board needs that KiCad's own library
does not have, into footprints/Solartron7075.pretty/.

  DSUB-50_Pins_Vertical_P2.77x2.84mm_MountingHoles
      Standard-density 50-way D-sub plug (shell D, three rows 17/16/17),
      straight PCB tails, plain mounting holes for 4-40 jackscrews. Laid out
      like KiCad's own DSUB-37_Pins_Vertical_P2.77x2.84mm_MountingHoles: pin 1
      at the origin, viewed from the mating face. Dimensions from Amphenol FCI
      drawing C-DSUB-0065 (DD50P364TXLF): mounting holes 61.11 mm apart and
      3.10 mm across, flange 66.65 mm long, rows 2.84 mm apart; flange height
      15.3 mm from the CAX and Ckmtw DD-50 drawings.

  L_Abracon_AOTA-B201610_Polarised
      Abracon AOTA-B201610S3R3-101-T land: two 1.00 x 1.60 mm pads with a
      1.00 mm gap, per the Abracon recommended land pattern. Pad 1 is the end
      beside the part's white polarity dot and carries a silkscreen dot.

Run from the project directory:  python3 tools/gen_footprints.py
"""

import os

OUT = os.path.join(os.path.dirname(__file__), "..", "footprints", "Solartron7075.pretty")


def font(size=1.0, thick=0.15):
    return f"(effects (font (size {size} {size}) (thickness {thick})))"


def line(x1, y1, x2, y2, layer, w):
    return (f"  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) "
            f"(stroke (width {w}) (type solid)) (layer \"{layer}\"))")


def rect(x1, y1, x2, y2, layer, w):
    return (f"  (fp_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) "
            f"(stroke (width {w}) (type solid)) (fill none) (layer \"{layer}\"))")


def circle(cx, cy, r, layer, w, fill="none"):
    return (f"  (fp_circle (center {cx:.3f} {cy:.3f}) (end {cx + r:.3f} {cy:.3f}) "
            f"(stroke (width {w}) (type solid)) (fill {fill}) (layer \"{layer}\"))")


def header(name, descr, tags, ref_xy, val_xy, attr):
    return "\n".join([
        f"(footprint \"{name}\"",
        "  (version 20240108)",
        "  (generator \"solartron7075_gen_footprints\")",
        "  (layer \"F.Cu\")",
        f"  (descr \"{descr}\")",
        f"  (tags \"{tags}\")",
        f"  (property \"Reference\" \"REF**\" (at {ref_xy[0]:.3f} {ref_xy[1]:.3f} 0) (layer \"F.SilkS\") {font()})",
        f"  (property \"Value\" \"{name}\" (at {val_xy[0]:.3f} {val_xy[1]:.3f} 0) (layer \"F.Fab\") {font()})",
        f"  (attr {attr})",
    ])


def dsub50():
    name = "DSUB-50_Pins_Vertical_P2.77x2.84mm_MountingHoles"
    pitch, row = 2.77, 2.84
    pads = []
    # Row 1: pins 1-17; row 2: 18-33, offset half a pitch; row 3: 34-50.
    for n in range(1, 18):
        pads.append((n, (n - 1) * pitch, 0.0))
    for n in range(18, 34):
        pads.append((n, pitch / 2 + (n - 18) * pitch, row))
    for n in range(34, 51):
        pads.append((n, (n - 34) * pitch, 2 * row))
    cx, cy = 8 * pitch, row                 # centre of the contact field
    hole_half = 61.11 / 2
    fl_half_w, fl_half_h = 66.65 / 2, 15.3 / 2
    x1, x2 = cx - fl_half_w, cx + fl_half_w
    y1, y2 = cy - fl_half_h, cy + fl_half_h
    out = [header(
        name,
        "50-pin D-Sub connector, standard density shell D, straight/vertical, THT, "
        "pins (male), pitch 2.77x2.84mm, mounting holes 61.11mm apart for 4-40 jackscrews, "
        "Amphenol FCI DD50P364TXLF (drawing C-DSUB-0065)",
        "50-pin D-Sub DD-50 connector straight vertical THT pins male jackscrew",
        (cx, y1 - 1.5), (cx, y2 + 1.5), "through_hole")]
    out.append(rect(x1, y1, x2, y2, "F.Fab", 0.1))
    out.append(rect(x1 - 0.11, y1 - 0.11, x2 + 0.11, y2 + 0.11, "F.SilkS", 0.12))
    out.append(rect(x1 - 0.5, y1 - 0.5, x2 + 0.5, y2 + 0.5, "F.CrtYd", 0.05))
    # Pin 1 marker on the silkscreen, above pad 1 and inside the flange.
    out.append(line(-0.6, -1.6, 0.6, -1.6, "F.SilkS", 0.12))
    out.append(line(-0.6, -1.6, 0.0, -1.0, "F.SilkS", 0.12))
    out.append(line(0.6, -1.6, 0.0, -1.0, "F.SilkS", 0.12))
    out.append(f"  (fp_text user \"${{REFERENCE}}\" (at {cx:.3f} {y2 - 1.2:.3f} 0) (layer \"F.Fab\") {font()})")
    for n, x, y in pads:
        shape = "rect" if n == 1 else "circle"
        out.append(f"  (pad \"{n}\" thru_hole {shape} (at {x:.3f} {y:.3f}) (size 1.6 1.6) "
                   f"(drill 1) (layers \"*.Cu\" \"*.Mask\"))")
    for x in (cx - hole_half, cx + hole_half):
        out.append(f"  (pad \"SH\" thru_hole circle (at {x:.3f} {cy:.3f}) (size 4 4) "
                   f"(drill 3.2) (layers \"*.Cu\" \"*.Mask\"))")
    out.append(")")
    return name, "\n".join(out) + "\n"


def aota():
    name = "L_Abracon_AOTA-B201610_Polarised"
    px, pw, ph = 1.0, 1.0, 1.6              # pad centre offset, pad width and height
    out = [header(
        name,
        "Abracon AOTA-B201610 2.0x1.6mm polarity-marked power inductor, recommended land "
        "pattern (two 1.00x1.60mm pads, 1.00mm gap); pad 1 is the dotted end",
        "inductor Abracon AOTA polarised RP2350",
        (0, -1.8), (0, 1.8), "smd")]
    out.append(rect(-1.0, -0.8, 1.0, 0.8, "F.Fab", 0.1))
    out.append(circle(-0.6, -0.4, 0.15, "F.Fab", 0.1, "solid"))
    out.append(line(-0.38, -0.91, 0.38, -0.91, "F.SilkS", 0.12))
    out.append(line(-0.38, 0.91, 0.38, 0.91, "F.SilkS", 0.12))
    out.append(circle(-1.55, -1.15, 0.12, "F.SilkS", 0.12, "solid"))
    out.append(rect(-1.75, -1.05, 1.75, 1.05, "F.CrtYd", 0.05))
    out.append(f"  (fp_text user \"${{REFERENCE}}\" (at 0 0 0) (layer \"F.Fab\") {font(0.5, 0.08)})")
    for n, x in ((1, -px), (2, px)):
        out.append(f"  (pad \"{n}\" smd roundrect (at {x:.3f} 0) (size {pw} {ph}) "
                   f"(layers \"F.Cu\" \"F.Paste\" \"F.Mask\") (roundrect_rratio 0.25))")
    out.append(")")
    return name, "\n".join(out) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, text in (dsub50(), aota()):
        with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
            f.write(text)
        print("wrote", name)


if __name__ == "__main__":
    main()
