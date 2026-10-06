#!/bin/sh
# Export review and fabrication files from the last `npm run build`
# (dist/index/circuit.json) into outputs/. Exporting from circuit JSON
# avoids re-running the autorouter.
set -e
cd "$(dirname "$0")/.."
CJ="$(pwd)/dist/index/circuit.json"
OUT="$(pwd)/outputs"
mkdir -p "$OUT"
npx tsci export "$CJ" -f schematic-svg -o "$OUT/schematic.svg"
# tsci's schematic-pdf is a 144 dpi bitmap; build a vector PDF from the SVG
node scripts/svg-to-pdf.mjs "$OUT/schematic.svg" "$OUT/schematic.pdf"
npx tsci export "$CJ" -f pcb-svg -o "$OUT/pcb-top.svg" --layer top
npx tsci export "$CJ" -f pcb-svg -o "$OUT/pcb-bottom.svg" --layer bottom
npx tsci export "$CJ" -f readable-netlist -o "$OUT/netlist.txt"
npx tsci export "$CJ" -f gerbers -o "$OUT/gerbers.zip"
cp dist/index/pcb.png "$OUT/pcb.png"
cp dist/index/schematic.png "$OUT/schematic.png"
