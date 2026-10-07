#!/usr/bin/env python3
"""Link the board's footprints to the generated schematic's symbols.

kinet2pcb leaves every footprint without a symbol path, so KiCad cannot tie
the board to scripts/gen_schematic.py's schematic. This does what KiCad's
"Update PCB from Schematic" would: each footprint gets its symbol's path (root
sheet, uuid = the component tstamp from the SKiDL netlist) and BOM fields, and
nets take the schematic's names (local-label nets become "/NAME"), so
`kicad-cli pcb drc --schematic-parity` passes and cross-probing works.
"""

import json
import pathlib
import re
import subprocess
import sys
import tempfile

import pcbnew

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from gen_schematic import netlist_nets, read_netlist  # noqa: E402

BOARD = HERE / "pcb" / "solartron_7075_interface.kicad_pcb"
NET = HERE / "output" / "solartron_7075_interface.net"
SCH_FILE = "solartron_7075_interface.kicad_sch"
SCH = HERE / "pcb" / SCH_FILE
BOM_FIELDS = ("LCSC", "MPN", "Manufacturer")


def schematic_nets():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "sch.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(out), str(SCH)],
                       check=True, capture_output=True)
        return netlist_nets(out)


def main():
    comps, _, _ = read_netlist(NET)
    board = pcbnew.LoadBoard(str(BOARD))
    missing = []
    for fp in board.GetFootprints():
        c = comps.get(fp.GetReference())
        if not c:
            missing.append(fp.GetReference())
            continue
        fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        fp.SetSheetname("/")
        fp.SetSheetfile(SCH_FILE)
        for k in BOM_FIELDS:
            if c["fields"].get(k):
                fp.SetField(k, c["fields"][k])
                fp.GetField(k).SetVisible(False)
    if missing:
        sys.exit(f"footprints not in the netlist: {missing}")

    # Net names: match each board net to the schematic net with the same pads
    sch_nets = schematic_nets()
    by_pads = {frozenset(v): k for k, v in sch_nets.items()}
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() > 0:
                pads.setdefault(p.GetNetname(), set()).add((fp.GetReference(), p.GetNumber()))
    ns = board.GetDesignSettings().m_NetSettings
    classes = {}
    renamed = 0
    for name, net in board.GetNetsByName().items():
        name = str(name)
        if not name or name not in pads:
            continue
        new = by_pads.get(frozenset(pads[name]))
        if new is None:
            sys.exit(f"net {name} has no schematic counterpart")
        if net.GetNetClassName() != "Default":
            classes[new] = net.GetNetClassName()
        if new != name:
            if new != "/" + name:
                sys.exit(f"net {name} would be renamed to {new}")
            net.SetNetname(new)
            renamed += 1
    ns.ClearNetclassPatternAssignments()
    for n, cls in classes.items():
        ns.SetNetclassPatternAssignment(n, cls)

    # No-connect pins: KiCad gives each its own "unconnected-(...)" net
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    nc = 0
    for name, nodes in sch_nets.items():
        if not name.startswith("unconnected-("):
            continue
        (ref, num), = nodes
        for p in fps[ref].Pads():
            if p.GetNumber() == num:
                if p.GetNetCode() > 0:
                    sys.exit(f"{ref}.{num} is no-connect in the schematic but on {p.GetNetname()}")
                ni = board.FindNet(name)
                if ni is None:
                    ni = pcbnew.NETINFO_ITEM(board, name)
                    board.Add(ni)
                p.SetNet(ni)
                nc += 1
    board.Save(str(BOARD))

    # Project: point the top-level sheet at the schematic's root uuid
    pro = BOARD.with_suffix(".kicad_pro")
    cfg = json.loads(pro.read_text())
    root = re.search(r'\(uuid "([^"]+)"\)', SCH.read_text()).group(1)
    cfg["schematic"]["top_level_sheets"] = [
        {"filename": SCH_FILE, "name": SCH.stem, "uuid": root}]
    pro.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"linked {len(board.GetFootprints())} footprints to {SCH_FILE}, {renamed} nets renamed, "
          f"{nc} no-connect pads")


if __name__ == "__main__":
    main()
