#!/usr/bin/env python3
"""
Export the atopile layout as a Specctra DSN for Freerouting.

In1.Cu and In2.Cu are KiCad "power" layers, so the DSN marks them as
planes and Freerouting routes no tracks there. scripts/plane_vias.py has
already joined every SMD pad on the four plane nets (GND, GND_ISO, +3V3,
+5V_ISO) to its plane, and the tracks and vias already in the layout (those
via drops and the pre-routed LDO block) are exported locked ("fix"), so
Freerouting only routes the remaining connections and leaves them alone.

    python3 scripts/plane_vias.py --write
    python3 scripts/export_dsn.py build/board.dsn
    java -jar freerouting-2.1.0.jar --gui.enabled=false \\
        --router.job_timeout=00:40:00 -de build/board.dsn -do build/board.ses
    python3 scripts/import_routing.py build/board.ses

Needs KiCad's pcbnew Python module (KiCad 9/10).
"""

import sys
from pathlib import Path

LAYOUT = Path(__file__).resolve().parent.parent / "layouts/default/default.kicad_pcb"


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    import pcbnew

    board = pcbnew.LoadBoard(str(LAYOUT))
    for t in board.GetTracks():
        t.SetLocked(True)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(out)):
        sys.exit("DSN export failed")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
