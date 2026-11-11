#!/usr/bin/env python3
"""Export documentation and fabrication outputs with kicad-cli.

    docs/        schematic PDF, board plots, renders
    production/  gerbers + drill (zip), JLCPCB-style BOM and CPL, DRC / ERC reports
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))
NAME = 'solartron7075_usb_interface'
SCH = os.path.join(OUT, NAME + '.kicad_sch')
PCB = os.path.join(OUT, NAME + '.kicad_pcb')
DOCS = os.path.join(OUT, 'docs')
PROD = os.path.join(OUT, 'production')


def run(*args, ok=(0,)):
    r = subprocess.run(['kicad-cli'] + list(args), capture_output=True, text=True)
    if r.returncode not in ok:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('kicad-cli %s failed' % ' '.join(args[:3]))
    return r.stdout


def refkey(r):
    head = r.rstrip('0123456789')
    return (head, int(r[len(head):] or 0))


def main():
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(PROD, exist_ok=True)
    # --- checks ---------------------------------------------------------------
    run('sch', 'erc', '--severity-all', '-o', os.path.join(PROD, 'erc_report.txt'), SCH, ok=(0, 5))
    run('pcb', 'drc', '--severity-all', '--schematic-parity', '-o', os.path.join(PROD, 'drc_report.txt'), PCB, ok=(0, 5))
    # --- documentation ---------------------------------------------------------
    run('sch', 'export', 'pdf', '-o', os.path.join(DOCS, 'schematic.pdf'), SCH)
    common = ['pcb', 'export', 'pdf', '--mode-single', '--include-border-title']
    run(*common, '--layers', 'F.Cu,F.SilkS,F.Fab,Edge.Cuts', '-o', os.path.join(DOCS, 'pcb_top.pdf'), PCB)
    run(*common, '--layers', 'B.Cu,B.SilkS,B.Fab,Edge.Cuts', '--mirror', '-o', os.path.join(DOCS, 'pcb_bottom_mirrored.pdf'), PCB)
    run(*common, '--layers', 'In1.Cu,Edge.Cuts', '-o', os.path.join(DOCS, 'pcb_in1_ground_planes.pdf'), PCB)
    run(*common, '--layers', 'In2.Cu,Edge.Cuts', '-o', os.path.join(DOCS, 'pcb_in2_power_planes.pdf'), PCB)
    for side in ('top', 'bottom'):
        try:
            run('pcb', 'render', '--side', side, '--quality', 'basic', '-w', '2000', '-h', '1100',
                '-o', os.path.join(DOCS, 'render_%s.png' % side), PCB)
        except SystemExit:
            print('render failed (no GPU / models?) - skipped')
    # --- gerbers / drill -------------------------------------------------------
    gdir = os.path.join(PROD, 'gerbers')
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    run('pcb', 'export', 'gerbers', '--layers',
        'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
        '--subtract-soldermask', '--no-protel-ext', '-o', gdir + '/', PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--excellon-separate-th',
        '--generate-map', '--map-format', 'pdf', '-o', gdir + '/', PCB)
    with zipfile.ZipFile(os.path.join(PROD, NAME + '_gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            if not f.endswith('.pdf'):
                z.write(os.path.join(gdir, f), f)
    # --- BOM -------------------------------------------------------------------
    tmp = os.path.join(PROD, '_bom.csv')
    run('sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,LCSC,MPN,Manufacturer,Description,${DNP}',
        '--labels', 'Reference,Value,Footprint,LCSC,MPN,Manufacturer,Description,DNP', '--exclude-dnp', '-o', tmp, SCH)
    rows = [r for r in csv.DictReader(open(tmp)) if not r['Reference'].startswith('TP')]
    os.remove(tmp)
    groups = {}
    for r in rows:
        key = (r['Value'], r['Footprint'], r['LCSC'], r['MPN'])
        groups.setdefault(key, []).append(r)
    out = []
    for key, rs in groups.items():
        refs = sorted((r['Reference'] for r in rs), key=refkey)
        out.append((refkey(refs[0]), refs, rs[0]))
    out.sort()
    with open(os.path.join(PROD, 'bom_jlcpcb.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'MPN', 'Manufacturer', 'Qty', 'Description'])
        for _, refs, r in out:
            w.writerow([r['Value'], ','.join(refs), r['Footprint'].split(':')[-1], r['LCSC'], r['MPN'], r['Manufacturer'],
                        len(refs), r['Description']])
    # --- placement (CPL) ---------------------------------------------------------
    tmp = os.path.join(PROD, '_pos.csv')
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--use-drill-file-origin',
        '--exclude-dnp', '-o', tmp, PCB)
    with open(os.path.join(PROD, 'cpl_jlcpcb.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Val', 'Package', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        for r in sorted(csv.DictReader(open(tmp)), key=lambda r: refkey(r['Ref'])):
            w.writerow([r['Ref'], r['Val'], r['Package'], r['PosX'] + 'mm', r['PosY'] + 'mm', r['Rot'], r['Side'].capitalize()])
    os.remove(tmp)
    print('exported to', DOCS, 'and', PROD)


if __name__ == '__main__':
    main()
