#!/bin/sh
# Full build of the Solartron 7075 USB interface. Silent manta stages mean the
# design passed; any diagnostic stops the build.
set -eu
cd "$(dirname "$0")"

TOP=solartron-7075-usb
RULES=solartron7075.mantaRules
OUT=output

rm -rf build
mkdir -p build "$OUT"

manta fmt --check src/*.manta
manta compile -o build/ src/*.manta
manta check --top "$TOP" -L build/ --rules "$RULES" -Werror
manta link  --top "$TOP" -L build/ --rules "$RULES" -Werror \
            --bom "$OUT/solartron7075-bom.csv" -o "$OUT/solartron7075.mantaNets"
manta export --format kicad --footprint-map solartron7075.fpmap -Werror \
             -o "$OUT/solartron7075.net" "$OUT/solartron7075.mantaNets"
manta render -Werror -o "$OUT/solartron7075.html" "$OUT/solartron7075.mantaNets"

python3 tools/gen_footprints.py
python3 tools/lcsc_bom.py "$OUT/solartron7075-bom.csv" "$OUT/solartron7075-bom-lcsc.csv"
python3 tools/verify_netlist.py "$OUT/solartron7075.mantaNets" > "$OUT/verify.txt"
tail -n 1 "$OUT/verify.txt"
