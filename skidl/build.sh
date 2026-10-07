#!/usr/bin/env bash
# Full rebuild: SKiDL description -> netlist/BOM -> single-page schematic ->
# placed + autorouted KiCad 10 board -> DRC/parity -> fabrication outputs.
#
#   SKIDL_PYTHON    Python with skidl 2.3+ installed (and KiCad's pcbnew importable)
#   KICAD_PYTHON    Python that provides KiCad 10's pcbnew module (Ubuntu: /usr/bin/python3)
#   FREEROUTING_JAR Freerouting 2.x executable jar (Maven Central: app.freerouting:freerouting)
#   JAVA            Java runtime for Freerouting (2.5 needs Java 25)
#   SKIDL_SCH=1     also emit SKiDL's own schematic (mis-connects nets here; see README)
set -euo pipefail
cd "$(dirname "$0")"
: "${SKIDL_PYTHON:=python3}"
: "${KICAD_PYTHON:=/usr/bin/python3}"
: "${FREEROUTING_JAR:?set FREEROUTING_JAR to the Freerouting executable jar}"
: "${JAVA:=java}"
export KICAD10_SYMBOL_DIR=${KICAD10_SYMBOL_DIR:-/usr/share/kicad/symbols}
export KICAD10_FOOTPRINT_DIR=${KICAD10_FOOTPRINT_DIR:-/usr/share/kicad/footprints}

B=pcb/solartron_7075_interface.kicad_pcb
FAB=pcb/fab

echo "== libraries";  python3 scripts/gen_dd50_footprint.py; python3 scripts/gen_symbols.py
echo "== SKiDL";      SKIDL_SCH=${SKIDL_SCH:-0} "$SKIDL_PYTHON" solartron_7075_interface.py
echo "== BOM";        python3 scripts/make_bom.py
echo "== schematic";  python3 scripts/gen_schematic.py --check
kicad-cli sch erc --severity-all -o pcb/erc_report.txt pcb/solartron_7075_interface.kicad_sch \
    | grep -E "Found" || true
mkdir -p pcb/render
kicad-cli sch export pdf -o pcb/render/schematic.pdf pcb/solartron_7075_interface.kicad_sch >/dev/null
if command -v pdftoppm >/dev/null; then  # PNG for the README (poppler-utils)
    pdftoppm -r 130 -png -singlefile pcb/render/schematic.pdf pcb/render/schematic
fi
echo "== placement";  "$KICAD_PYTHON" scripts/layout_pcb.py
echo "== routing";    "$KICAD_PYTHON" scripts/route_pcb.py --freerouting "$FREEROUTING_JAR" --java "$JAVA"
echo "== link to schematic"; "$KICAD_PYTHON" scripts/link_schematic.py
echo "== DRC"
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --severity-all --units mm \
    -o pcb/drc_report.txt "$B" || true
grep -E "^\*\* Found" pcb/drc_report.txt || true

echo "== fabrication outputs"
rm -rf "$FAB/gerbers"; mkdir -p "$FAB/gerbers"
kicad-cli pcb export gerbers -o "$FAB/gerbers/" \
    -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts "$B"
kicad-cli pcb export drill -o "$FAB/gerbers/" --format excellon --excellon-separate-th \
    --generate-map --map-format pdf "$B"
(cd "$FAB/gerbers" && rm -f ../gerbers.zip && zip -q ../gerbers.zip ./*)
kicad-cli pcb export pos --format csv --units mm --side both -o "$FAB/positions_kicad.csv" "$B"
python3 scripts/jlc_cpl.py "$FAB/positions_kicad.csv" "$FAB/cpl_jlcpcb.csv"

echo "== renders"
mkdir -p pcb/render
kicad-cli pcb render --side top --quality high -w 2000 -h 900 -o pcb/render/top.png "$B"
kicad-cli pcb render --side bottom --quality high -w 2000 -h 900 -o pcb/render/bottom.png "$B"
kicad-cli pcb render --rotate "320,0,330" --perspective --quality high -w 2000 -h 1200 \
    -o pcb/render/iso.png "$B"
kicad-cli pcb export pdf --mode-multipage -l F.Cu,F.Silkscreen,In1.Cu,In2.Cu,B.Cu,B.Silkscreen \
    --cl Edge.Cuts -o pcb/render/layers.pdf "$B" >/dev/null
echo "done"
