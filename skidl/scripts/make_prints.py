#!/usr/bin/env python3
"""Printable drawings of the board, and a render of the Gerbers themselves.

  pcb/print/pcb_prints.pdf     A4 pages with title block, black and white:
                               assembly top/bottom and each copper layer at 2:1,
                               and a 1:1 bottom view for checking the fit
                               against the meter's SKB socket
  pcb/print/gerber_preview.png the Gerber/drill files as rendered by gerbv
                               (independent of KiCad), top, bottom and planes

Run with KiCad's Python after the DRC step has saved the filled board.
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile

import pcbnew

HERE = pathlib.Path(__file__).resolve().parent.parent
BOARD = HERE / "pcb" / "solartron_7075_interface.kicad_pcb"
OUT = HERE / "pcb" / "print"
GERBERS = HERE / "pcb" / "fab" / "gerbers"
NAME = "solartron_7075_interface"

# (description for the title block, layers, extra kicad-cli options, scale)
PAGES = [
    ("Assembly, top side (F.Fab), viewed from top", "F.Fab,Edge.Cuts", ["--sp"], 2),
    ("Assembly, bottom side (B.Fab), viewed from below: J1 only", "B.Fab,Edge.Cuts",
     ["--sp", "--mirror"], 2),
    ("F.Cu, top copper, viewed from top", "F.Cu,Edge.Cuts", [], 2),
    ("In1.Cu, ISO_GND (left) / GND (right) planes, viewed from top", "In1.Cu,Edge.Cuts", [], 2),
    ("In2.Cu, ISO_+5V (left) / +3V3 (right) planes, viewed from top", "In2.Cu,Edge.Cuts", [], 2),
    ("B.Cu, bottom copper, viewed from below", "B.Cu,Edge.Cuts", ["--mirror"], 2),
    ("FIT CHECK 1:1 - print at 100 %, viewed from the meter side (below)",
     "B.Fab,B.Silkscreen,Edge.Cuts", ["--sp", "--mirror"], 1),
]


def kicad_pdfs(tmp):
    """One PDF per page, from copies of the board that only differ in title block
    (and, for 1:1, position: KiCad centres the board on the sheet only when scaling)."""
    pdfs = []
    for i, (desc, layers, opts, scale) in enumerate(PAGES, 1):
        board = pcbnew.LoadBoard(str(BOARD))
        tb = board.GetTitleBlock()
        tb.SetComment(2, f"Page {i}/{len(PAGES)}: {desc}")
        tb.SetComment(3, f"Scale {scale}:1")
        if scale == 1:
            # A4 landscape (the board's page): upper middle, clear of the title block
            bb = board.GetBoardEdgesBoundingBox()
            cx, cy = pcbnew.FromMM(297 / 2), pcbnew.FromMM(80)
            board.Move(pcbnew.VECTOR2I(cx - bb.GetCenter().x, cy - bb.GetCenter().y))
        src = tmp / f"p{i}" / f"{NAME}.kicad_pcb"
        src.parent.mkdir()
        shutil.copy(BOARD.with_suffix(".kicad_pro"), src.with_suffix(".kicad_pro"))
        board.Save(str(src))
        pdf = tmp / f"p{i}.pdf"
        subprocess.run(["kicad-cli", "pcb", "export", "pdf", "--mode-single", "-l", layers,
                        "--ibt", "--black-and-white", "--scale", str(scale), *opts,
                        "-o", str(pdf), str(src)], check=True, capture_output=True)
        pdfs.append(pdf)
    out = OUT / "pcb_prints.pdf"
    subprocess.run(["pdfunite", *map(str, pdfs), str(out)], check=True)
    print(f"{len(pdfs)} pages -> {out}")


def gerber_preview(tmp):
    if not shutil.which("gerbv"):
        print("gerbv not found, skipping the Gerber preview")
        return
    g = lambda s: str(GERBERS / f"{NAME}-{s}")  # noqa: E731
    drills = [g("PTH.drl"), g("NPTH.drl")]
    edge = g("Edge_Cuts.gm1")
    # Topmost first. Green = mask over substrate / copper, gold = mask openings.
    views = {
        "top": [(d, "#000000") for d in drills] + [
            (g("F_Silkscreen.gto"), "#f2f2f2"), (g("F_Mask.gts"), "#d4aa30"),
            (g("F_Cu.gtl"), "#3c8c46"), (edge, "#ffe000")],
        "bottom": [(d, "#000000") for d in drills] + [
            (g("B_Silkscreen.gbo"), "#f2f2f2"), (g("B_Mask.gbs"), "#d4aa30"),
            (g("B_Cu.gbl"), "#3c8c46"), (edge, "#ffe000")],
        "in1": [(d, "#000000") for d in drills] + [(g("In1_Cu.g1"), "#c87533"), (edge, "#ffe000")],
        "in2": [(d, "#000000") for d in drills] + [(g("In2_Cu.g2"), "#c87533"), (edge, "#ffe000")],
    }
    bg = {"top": "#14421f", "bottom": "#14421f", "in1": "#101010", "in2": "#101010"}
    labels = {"top": "Top (F.Cu, F.Mask, F.Silkscreen)",
              "bottom": "Bottom, viewed from below (B.Cu, B.Mask, B.Silkscreen)",
              "in1": "In1.Cu: ISO_GND (meter side) | GND (USB side)",
              "in2": "In2.Cu: ISO_+5V (meter side) | +3V3 (USB side)"}
    pngs = []
    for k, layers in views.items():
        png = tmp / f"g_{k}.png"
        cmd = ["gerbv", "-x", "png", "-D", "400", "-B", "2", "-b", bg[k], "-o", str(png)]
        for f, col in layers:
            cmd += ["-f", col + "ff"]
        cmd += [f for f, _ in layers]
        subprocess.run(cmd, check=True, capture_output=True)
        if k == "bottom":
            subprocess.run(["convert", str(png), "-flop", str(png)], check=True)
        subprocess.run(["convert", str(png), "-background", "white", "-fill", "black",
                        "-font", "DejaVu-Sans", "-pointsize", "36", f"label:{labels[k]}",
                        "+swap", "-gravity", "west", "-append", str(png)], check=True)
        pngs.append(str(png))
    out = OUT / "gerber_preview.png"
    subprocess.run(["convert", *pngs, "-background", "white", "-gravity", "north",
                    "-splice", "0x20", "-gravity", "west", "-append", "-resize", "50%", str(out)],
                   check=True)
    print(f"gerber preview -> {out}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not shutil.which("pdfunite"):
        sys.exit("pdfunite (poppler-utils) is needed to assemble the prints")
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        kicad_pdfs(tmp)
        gerber_preview(tmp)


if __name__ == "__main__":
    main()
