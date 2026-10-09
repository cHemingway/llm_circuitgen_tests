#!/usr/bin/env python3
"""
Import a Freerouting session (.ses) into the atopile layout.

KiCad's pcbnew reads the session, but a board saved by KiCad 10 can no
longer be read by atopile 0.15, so this works in two steps:

  1. (KiCad's Python) load layouts/default/default.kicad_pcb, import the
     session and list its tracks and vias;
  2. (atopile's Python) replace the routed tracks and vias in the layout
     with that list, keeping the file in atopile's format.

Tracks and vias that belong to a group (the pre-routed LDO block) are left
as they are; session copies of them are skipped.

`--add file.json` (used by scripts/plane_vias.py) adds tracks and vias
without removing any. `--clear` removes all routing except the grouped
(pre-routed LDO) tracks, to start again from an unrouted board.

    python3 scripts/export_dsn.py  ->  Freerouting  ->  board.ses
    python3 scripts/import_routing.py board.ses

ATO_PYTHON overrides the atopile interpreter
(default ~/.local/share/uv/tools/atopile/bin/python).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LAYOUT = Path(__file__).resolve().parent.parent / "layouts/default/default.kicad_pcb"
ATO_PYTHON = os.environ.get("ATO_PYTHON", str(Path.home() / ".local/share/uv/tools/atopile/bin/python"))


PLANE_NETS = ("GND", "GND_ISO", "+3V3", "+5V_ISO")


def lock_fixed(board) -> int:
    """Lock what the autorouter must keep: the plane via drops (every track
    and via on a plane net) and grouped tracks (the pre-routed LDO block).
    Signal routing from an earlier run stays movable. Returns the count."""
    n = 0
    for t in board.GetTracks():
        fixed = t.GetNetname() in PLANE_NETS or t.GetParentGroup() is not None
        t.SetLocked(fixed)
        n += fixed
    return n


def key(kind, *vals):
    return (kind, *(round(v, 3) if isinstance(v, float) else v for v in vals))


def read_session(ses: Path) -> dict:
    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    # The session holds the movable routing only. Lock the same tracks as
    # export_dsn.py did; the import replaces everything else.
    before = len(board.GetTracks())
    kept = lock_fixed(board)
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        sys.exit(f"KiCad could not import {ses}")
    routing = tracks_of(board)
    print(f"{ses}: {kept} locked tracks/vias kept; {len(board.GetTracks()) - kept} routed "
          f"(was {before - kept})")
    return routing


def tracks_of(board) -> dict:
    """All tracks and vias of a pcbnew board, as plain data."""
    import pcbnew

    mm = pcbnew.ToMM
    segments, vias = [], []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.append({
                "at": [mm(t.GetPosition().x), mm(t.GetPosition().y)],
                "size": mm(t.GetWidth(pcbnew.F_Cu)), "drill": mm(t.GetDrillValue()),
                "net": t.GetNetname(),
            })
        elif t.GetClass() == "PCB_TRACK":
            segments.append({
                "start": [mm(t.GetStart().x), mm(t.GetStart().y)],
                "end": [mm(t.GetEnd().x), mm(t.GetEnd().y)],
                "width": mm(t.GetWidth()), "layer": t.GetLayerName(), "net": t.GetNetname(),
            })
        else:
            sys.exit(f"unexpected track type {t.GetClass()}")
    return {"segments": segments, "vias": vias}


def apply(routing: dict, replace: bool = True) -> None:
    from faebryk.libs.kicad.fileformats import kicad

    pcb_file = kicad.loads(kicad.pcb.PcbFile, LAYOUT)
    pcb = pcb_file.kicad_pcb
    nets = {n.name: n.number for n in pcb.nets}
    grouped = {m for g in pcb.groups for m in g.members}

    kept = set()
    for s in pcb.segments:
        if s.uuid in grouped:
            kept.add(key("s", s.start.x, s.start.y, s.end.x, s.end.y, s.layer))
            kept.add(key("s", s.end.x, s.end.y, s.start.x, s.start.y, s.layer))
    for v in pcb.vias:
        if v.uuid in grouped:
            kept.add(key("v", v.at.x, v.at.y))
    n_kept = sum(1 for o in [*pcb.segments, *pcb.vias] if o.uuid in grouped)

    if replace:
        kicad.filter(pcb, "segments", pcb.segments, lambda s: s.uuid in grouped)
        kicad.filter(pcb, "vias", pcb.vias, lambda v: v.uuid in grouped)
        if len(pcb.arcs):
            kicad.filter(pcb, "arcs", pcb.arcs, lambda a: a.uuid in grouped)

    added = {"segments": 0, "vias": 0}
    for s in routing["segments"]:
        if key("s", *s["start"], *s["end"], s["layer"]) in kept:
            continue
        kicad.insert(pcb, "segments", pcb.segments, kicad.pcb.Segment(
            start=kicad.pcb.Xy(x=s["start"][0], y=s["start"][1]),
            end=kicad.pcb.Xy(x=s["end"][0], y=s["end"][1]),
            width=s["width"], layer=s["layer"], net=nets[s["net"]], uuid=kicad.gen_uuid(""),
        ))
        added["segments"] += 1
    for v in routing["vias"]:
        if key("v", *v["at"]) in kept:
            continue
        kicad.insert(pcb, "vias", pcb.vias, kicad.pcb.Via(
            at=kicad.pcb.Xy(x=v["at"][0], y=v["at"][1]), size=v["size"], drill=v["drill"],
            layers=["F.Cu", "B.Cu"], net=nets[v["net"]], uuid=kicad.gen_uuid(""),
        ))
        added["vias"] += 1

    kicad.dumps(pcb_file, LAYOUT)
    print(f"kept {n_kept} grouped tracks/vias; added {added['segments']} tracks and "
          f"{added['vias']} vias -> {LAYOUT}")


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] in ("--apply", "--add"):
        apply(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), replace=sys.argv[1] == "--apply")
        return 0
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--clear":
        write_layout({"segments": [], "vias": []}, replace=True)
        return 0
    routing = read_session(Path(sys.argv[1]))
    write_layout(routing, replace=True)
    return 0


def write_layout(routing: dict, replace: bool) -> None:
    """Hand the tracks/vias to atopile's Python, which edits the layout."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(routing, f)
    try:
        subprocess.run([ATO_PYTHON, __file__, "--apply" if replace else "--add", f.name], check=True)
    finally:
        os.unlink(f.name)


if __name__ == "__main__":
    sys.exit(main())
