#!/bin/sh
# Export review and fabrication files from the last `npm run build`
# (dist/index/circuit.json) into outputs/. Exporting from circuit JSON
# avoids re-running the autorouter.
set -e
cd "$(dirname "$0")/.."
CJ="$(pwd)/dist/index/circuit.json"
FAB="$(pwd)/dist/fab/circuit.json"
OUT="$(pwd)/outputs"
mkdir -p "$OUT" "$(dirname "$FAB")"
npx tsci export "$CJ" -f schematic-svg -o "$OUT/schematic.svg"
# tsci's schematic-pdf is a 144 dpi bitmap; build a vector PDF from the SVG
node scripts/svg-to-pdf.mjs "$OUT/schematic.svg" "$OUT/schematic.pdf"
npx tsci export "$CJ" -f pcb-svg -o "$OUT/pcb-top.svg" --layer top
npx tsci export "$CJ" -f pcb-svg -o "$OUT/pcb-bottom.svg" --layer bottom
npx tsci export "$CJ" -f readable-netlist -o "$OUT/netlist.txt"
# Gerbers come from a copy with the paste layer and rotated pads fixed
node scripts/prepare-fab.mjs "$CJ" "$FAB"
npx tsci export "$FAB" -f gerbers -o "$OUT/gerbers.zip"
# Prints and renders are drawn from the Gerbers themselves
node scripts/pcb-prints.mjs "$OUT/gerbers.zip" "$OUT/pcb-prints.pdf" "$OUT/pcb-render"
cp dist/index/pcb.png "$OUT/pcb.png"
cp dist/index/schematic.png "$OUT/schematic.png"
