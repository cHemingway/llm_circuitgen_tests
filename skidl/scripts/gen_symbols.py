#!/usr/bin/env python3
"""Generate the local KiCad symbol library (lib/Solartron7075.kicad_sym).

KiCad 10 ships DE9/DA15/DB25/DC37 D-sub symbols but no 50-way (DD-50) one, so
a simple two-sided box symbol is generated here: pins 1-25 on the left, 26-50
on the right and the shell ("SH") at the bottom, matching the pad names of
lib/Solartron7075.pretty/DSUB-50_Pins_Vertical_P2.77x2.84mm_MountingHoles.
"""

import pathlib

LIB = "Solartron7075"
SYM = "DD50_Pins_MountingHoles"
FP = f"{LIB}:DSUB-50_Pins_Vertical_P2.77x2.84mm_MountingHoles"
P = 2.54


def prop(name, value, x, y, hide=False):
    h = " (hide yes)" if hide else ""
    return (
        f'\t\t(property "{name}" "{value}" (at {x:.2f} {y:.2f} 0){h}\n'
        "\t\t\t(effects (font (size 1.27 1.27))))\n"
    )


def pin(num, name, x, y, rot, ptype="passive"):
    return (
        f"\t\t\t(pin {ptype} line (at {x:.2f} {y:.2f} {rot}) (length 3.81)\n"
        f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
        f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27)))))\n'
    )


def main():
    n_side = 25
    top = (n_side - 1) * P / 2
    w = 7.62
    s = "(kicad_symbol_lib\n\t(version 20251024)\n\t(generator \"skidl_solartron_gen\")\n"
    s += f'\t(symbol "{SYM}"\n\t\t(pin_names (offset 1.016) (hide yes))\n'
    s += "\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)\n"
    s += prop("Reference", "J", 0, top + 2 * P)
    s += prop("Value", SYM, 0, top + P)
    s += prop("Footprint", FP, 0, 0, hide=True)
    s += prop("Datasheet", "https://www.amphenol-icc.com/media/wysiwyg/files/documentation/datasheet/inputoutput/io_dsub_signal_pcb_deltad.pdf", 0, 0, hide=True)
    s += prop("Description", "50-pin D-Sub (DD-50) connector, pins (male), shell/mounting holes on pin SH", 0, 0, hide=True)
    s += prop("ki_keywords", "connector D-SUB DD50 male", 0, 0, hide=True)
    s += prop("ki_fp_filters", "DSUB*50*Pins*", 0, 0, hide=True)
    s += f'\t\t(symbol "{SYM}_1_1"\n'
    s += (
        f"\t\t\t(rectangle (start {-w:.2f} {top + P / 2:.2f}) (end {w:.2f} {-top - P:.2f})\n"
        "\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))\n"
    )
    for i in range(n_side):
        y = top - i * P
        s += pin(i + 1, str(i + 1), -w - 3.81, y, 0)
        s += pin(i + 26, str(i + 26), w + 3.81, y, 180)
    s += pin("SH", "SH", 0, -top - P - 3.81, 90)
    s += "\t\t)\n\t)\n)\n"
    out = pathlib.Path(__file__).resolve().parent.parent / "lib" / f"{LIB}.kicad_sym"
    out.write_text(s)
    print("wrote", out)


if __name__ == "__main__":
    main()
