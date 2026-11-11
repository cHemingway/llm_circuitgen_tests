#!/bin/bash
# Regenerate the whole project from the scripts (KiCad 10, kicad-cli + pcbnew Python API).
set -e
cd "$(dirname "$0")"
PY=${KICAD_PYTHON:-/usr/bin/python3}       # interpreter that can "import pcbnew"
P=solartron7075_usb_interface

python3 gen_lib.py                         # project symbol + footprint libraries
python3 gen_sch.py                         # schematic sheets
$PY gen_pcb.py place                       # board outline, placement, planes, pre-routes
$PY gen_pcb.py route                       # fan-out + autoroute (scripts/router.py), zone fill

# re-save everything in the native KiCad 10 file format
( cd .. && for f in $P.kicad_sch mcu_usb.kicad_sch isolation.kicad_sch dvm_inputs.kicad_sch dvm_outputs.kicad_sch; do
    kicad-cli sch upgrade --force "$f" >/dev/null; done
  kicad-cli sym upgrade --force lib/solartron7075.kicad_sym >/dev/null
  kicad-cli fp upgrade --force lib/solartron7075.pretty >/dev/null )

python3 export.py                          # docs/ and production/
rm -rf __pycache__
