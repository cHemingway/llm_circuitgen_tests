#!/usr/bin/env python3
"""
Export gerbers, drill files, 1:1 PDF prints and 3D renders of the PCB.

Works on a temporary copy of the atopile layout (so zone fills don't end up
in layouts/default/default.kicad_pcb), using kicad-cli:

  1. DRC with zone refill            -> fab/drc_report.rpt
  2. Gerbers + Excellon drill        -> fab/gerbers/, fab/<name>_gerbers.zip
  3. 1:1 prints (top, bottom-as-seen-from-the-meter, assembly, the two
     inner plane layers)
                                     -> fab/solartron_7075_usb_prints.pdf
  4. 3D renders (top, bottom, iso)   -> fab/renders/*.png

If DRC still reports unrouted connections, the zip is named *_UNROUTED_*
so it cannot be mistaken for a fabrication set.

Usage (from the atopile/ directory, after `ato build`):

    python3 scripts/export_pcb.py            # everything
    python3 scripts/export_pcb.py --no-render

Requires KiCad 9 or 10 (kicad-cli and its pcbnew Python module; made with
10.0.6) and pdfunite (poppler).
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUT = ROOT / "layouts/default/default.kicad_pcb"
PROJECT_FILE = LAYOUT.with_suffix(".kicad_pro")  # design rules (within JLCPCB 4-layer minimums)
FAB = ROOT / "fab"
NAME = "solartron_7075_usb"
WORK = LAYOUT.with_name(f"{NAME}.kicad_pcb")  # temp copy; same dir keeps ${KIPRJMOD} model paths valid
PAGE_NOTE = "@@PAGE_NOTE@@"
TITLE = "Solartron 7075 USB interface"

GERBER_LAYERS = [
    "F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "Edge.Cuts",
]

# (file stem, layers, extra kicad-cli args, page note)
PRINTS = [
    ("1_top", "F.Cu,F.SilkS,Edge.Cuts", [], "Top: copper + silkscreen"),
    ("2_bottom_mirrored", "B.Cu,B.SilkS,B.Fab,Edge.Cuts", ["--mirror"],
     "Bottom, mirrored = as seen from the meter. Hold against SKB to check the DD-50 fit"),
    ("3_assembly_top", "F.Fab,F.SilkS,Edge.Cuts", ["--sp"], "Top assembly drawing"),
    ("4_in1_ground", "In1.Cu,Edge.Cuts", [], "In1.Cu: GND | GND_ISO planes (top view)"),
    ("5_in2_supply", "In2.Cu,Edge.Cuts", [], "In2.Cu: +3V3 | +5V_ISO planes (top view)"),
]

RENDERS = [
    ("top", ["--side", "top"]),
    ("bottom", ["--side", "bottom"]),
    ("iso", ["--side", "top", "--rotate", "-40,0,30", "--perspective", "--zoom", "0.9"]),
]


def cli(*args):
    r = subprocess.run(["kicad-cli", *map(str, args)], capture_output=True, text=True)
    if r.returncode not in (0, 5):  # 5 = DRC found violations
        sys.exit(f"kicad-cli {' '.join(map(str, args[:3]))} failed:\n{r.stdout}\n{r.stderr}")
    return r


def prepare_copy(unrouted_note: bool):
    """Copy the layout and give it a title block for the prints."""
    text = LAYOUT.read_text(encoding="utf-8")
    if "(title_block" not in text:
        comment = "UNROUTED - placement only, not for fabrication" if unrouted_note else "Rev A"
        block = (
            f'\t(title_block\n\t\t(title "{TITLE}")\n'
            f'\t\t(date "{datetime.date.today().isoformat()}")\n\t\t(rev "A")\n'
            f'\t\t(company "atopile design (../*.ato)")\n'
            f'\t\t(comment 1 "{comment}")\n'
            f'\t\t(comment 2 "Print at 100% / actual size for fit checks")\n'
            f'\t\t(comment 3 "{PAGE_NOTE}")\n\t)\n'
        )
        text = text.replace('\t(paper "A4")\n', '\t(paper "A4")\n' + block, 1)
    WORK.write_text(text, encoding="utf-8")
    if PROJECT_FILE.exists():
        shutil.copy(PROJECT_FILE, WORK.with_suffix(".kicad_pro"))


def center_on_sheet() -> None:
    """atopile centres the board on the PCB origin, i.e. the sheet's top-left
    corner; move the copy onto the A4 sheet (clear of the title block) so the
    1:1 prints land on the page."""
    import pcbnew

    board = pcbnew.LoadBoard(str(WORK))
    centre = board.GetBoardEdgesBoundingBox().GetCenter()
    delta = pcbnew.VECTOR2I(pcbnew.FromMM(130) - centre.x, pcbnew.FromMM(95) - centre.y)
    for item in [*board.GetFootprints(), *board.GetTracks(), *board.GetDrawings(), *board.Zones()]:
        item.Move(delta)
    board.Save(str(WORK))


def run_drc():
    js = FAB / "drc.json"
    cli("pcb", "drc", "--refill-zones", "--save-board", "--severity-all", "--format", "json",
        "-o", js, WORK)
    cli("pcb", "drc", "--severity-all", "-o", FAB / "drc_report.rpt", WORK)
    data = json.loads(js.read_text(encoding="utf-8"))
    js.unlink()
    counts = Counter((v["severity"], v["type"]) for v in data.get("violations", []))
    unconnected = len(data.get("unconnected_items", []))
    return counts, unconnected


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-render", action="store_true", help="skip the 3D renders")
    args = ap.parse_args()
    if not LAYOUT.exists():
        sys.exit(f"{LAYOUT} not found - run `ato build` first")
    for tool in ("kicad-cli", "pdfunite"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found")

    if FAB.exists():
        shutil.rmtree(FAB)
    (FAB / "gerbers").mkdir(parents=True)
    try:
        # first pass only to learn whether the board is routed
        prepare_copy(unrouted_note=False)
        center_on_sheet()
        _, unconnected = run_drc()
        prepare_copy(unrouted_note=unconnected > 0)
        center_on_sheet()
        counts, unconnected = run_drc()

        print("DRC (fab/drc_report.rpt):")
        for (sev, typ), n in sorted(counts.items()):
            print(f"  {n:4d} {sev:8s} {typ}")
        print(f"  {unconnected:4d} unrouted connections")

        # --- gerbers + drill ---
        gdir = FAB / "gerbers"
        cli("pcb", "export", "gerbers", "-o", f"{gdir}/", "-l", ",".join(GERBER_LAYERS),
            "--subtract-soldermask", WORK)
        cli("pcb", "export", "drill", "-o", f"{gdir}/", "--format", "excellon", "--excellon-units", "mm",
            "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", WORK)
        suffix = "_UNROUTED" if unconnected else ""
        zpath = FAB / f"{NAME}{suffix}_gerbers.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(gdir.iterdir()):
                z.write(f, f.name)
        print(f"wrote {zpath.relative_to(ROOT)} ({len(list(gdir.iterdir()))} files)")

        # --- 1:1 prints ---
        pages = []
        board_text = WORK.read_text(encoding="utf-8")
        for stem, layers, extra, note in PRINTS:
            WORK.write_text(board_text.replace(PAGE_NOTE, note), encoding="utf-8")
            out = FAB / f"_{stem}.pdf"
            cli("pcb", "export", "pdf", "--mode-single", "-l", layers, "--ibt", "--scale", "1",
                *extra, "-o", out, WORK)
            pages.append(out)
        WORK.write_text(board_text, encoding="utf-8")
        prints = FAB / f"{NAME}_prints.pdf"
        subprocess.run(["pdfunite", *map(str, pages), str(prints)], check=True)
        for p in pages:
            p.unlink()
        print(f"wrote {prints.relative_to(ROOT)} ({len(pages)} pages, 1:1 on A4)")

        # --- 3D renders ---
        if not args.no_render:
            rdir = FAB / "renders"
            rdir.mkdir()
            for stem, extra in RENDERS:
                cli("pcb", "render", "-o", rdir / f"{stem}.png", "-w", "1600", "-h", "1200",
                    "--quality", "high", "--background", "opaque", *extra, WORK)
            print(f"wrote {rdir.relative_to(ROOT)}/ ({len(RENDERS)} renders)")
    finally:
        for f in WORK.parent.glob(f"{NAME}*"):
            f.unlink()

    if unconnected:
        print(f"NOTE: board is not routed ({unconnected} connections) - outputs are for fit checks only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
