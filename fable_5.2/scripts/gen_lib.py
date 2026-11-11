#!/usr/bin/env python3
"""Generate the project-local symbol and footprint libraries.

KiCad's stock libraries have no 50-way (DD-50) D-sub and no TPIC6C595, so
those two parts (plus isolated-domain power symbols) are generated here.
"""
import os
from sx import parse, dump, find, first, Sym

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'lib')
KSYM = '/usr/share/kicad/symbols/'
LIBNAME = 'solartron7075'


def S(x):
    return Sym(x)


def font(hide=False):
    e = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]
    if hide:
        e.append([S('hide'), S('yes')])
    return e


def prop(name, val, x, y, hide=False, just=None):
    e = font(hide)
    if just:
        e.append([S('justify'), S(just)])
    return [S('property'), name, val, [S('at'), x, y, 0], e]


def pin(etype, x, y, ang, name, num, length=2.54, hide_name=False):
    return [S('pin'), S(etype), S('line'), [S('at'), x, y, ang], [S('length'), length],
            [S('name'), name, [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]],
            [S('number'), str(num), [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]]]


def rect(x1, y1, x2, y2):
    return [S('rectangle'), [S('start'), x1, y1], [S('end'), x2, y2],
            [S('stroke'), [S('width'), 0.254], [S('type'), S('default')]],
            [S('fill'), [S('type'), S('background')]]]


def sym_dd50():
    name = 'DD50_Plug_MountingHoles'
    body = [S('symbol'), name + '_0_1', rect(-7.62, 33.02, 7.62, -35.56)]
    pins = [S('symbol'), name + '_1_1']
    for n in range(1, 26):
        pins.append(pin('passive', -10.16, 30.48 - (n - 1) * 2.54, 0, str(n), n))
    for n in range(26, 51):
        pins.append(pin('passive', 10.16, 30.48 - (n - 26) * 2.54, 180, str(n), n))
    pins.append(pin('passive', 0, -38.1, 90, 'SHELL', 'SH'))
    return [S('symbol'), name,
            [S('pin_names'), [S('offset'), 1.016]],
            [S('exclude_from_sim'), S('no')], [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
            prop('Reference', 'J', -7.62, 35.56, just='left'),
            prop('Value', name, 0, -41.91),
            prop('Footprint', LIBNAME + ':DSUB-50_Pins_Vertical_P2.76x2.84mm_MountingHoles', 0, 0, hide=True),
            prop('Datasheet', 'https://www.lcsc.com/datasheet/lcsc_datasheet_2409280132_Amphenol-ICC-DD50P364TXLF_C5402574.pdf', 0, 0, hide=True),
            prop('Description', '50-way 3-row standard-density D-sub plug (DD-50P), straight PCB pins, plain 3.1 mm flange holes', 0, 0, hide=True),
            [S('property'), 'ki_keywords', 'DD50 DD-50 D-sub DSUB 50 plug male', [S('at'), 0, 0, 0], font(True)],
            [S('property'), 'ki_fp_filters', 'DSUB*50*Pins*', [S('at'), 0, 0, 0], font(True)],
            body, pins]


def sym_tpic():
    name = 'TPIC6C595'
    body = [S('symbol'), name + '_0_1', rect(-12.7, 15.24, 12.7, -15.24)]
    p = [S('symbol'), name + '_1_1']
    p.append(pin('power_in', 0, 17.78, 270, 'VCC', 1))
    p.append(pin('input', -15.24, 10.16, 0, 'SER_IN', 2))
    p.append(pin('input', -15.24, 5.08, 0, 'SRCK', 15))
    p.append(pin('input', -15.24, 2.54, 0, 'RCK', 10))
    p.append(pin('input', -15.24, -5.08, 0, '~{CLR}', 7))
    p.append(pin('input', -15.24, -7.62, 0, '~{G}', 8))
    for i, num in enumerate([3, 4, 5, 6, 11, 12, 13, 14]):
        p.append(pin('open_collector', 15.24, 10.16 - i * 2.54, 180, 'DRAIN%d' % i, num))
    p.append(pin('output', 15.24, -12.7, 180, 'SER_OUT', 9))
    p.append(pin('power_in', 0, -17.78, 90, 'GND', 16))
    return [S('symbol'), name,
            [S('exclude_from_sim'), S('no')], [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
            prop('Reference', 'U', -12.7, 16.51, just='left'),
            prop('Value', name, 2.54, 16.51, just='left'),
            prop('Footprint', 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', 0, 0, hide=True),
            prop('Datasheet', 'https://www.ti.com/lit/ds/symlink/tpic6c595.pdf', 0, 0, hide=True),
            prop('Description', 'Power logic 8-bit shift register, open-drain DMOS outputs 33 V / 100 mA, SOIC-16', 0, 0, hide=True),
            [S('property'), 'ki_keywords', 'shift register open drain 595 power logic', [S('at'), 0, 0, 0], font(True)],
            [S('property'), 'ki_fp_filters', 'SOIC*3.9x9.9mm*P1.27mm*', [S('at'), 0, 0, 0], font(True)],
            body, p]


def power_variant(src_name, new_name, descr):
    """Clone a stock power symbol under a new net name."""
    t = parse(open(KSYM + 'power.kicad_sym').read())
    src = [s for s in find(t, 'symbol') if s[1] == src_name][0]
    out = []
    for item in src:
        if isinstance(item, list) and item[0] == 'symbol':
            sub = parse(dump(item))
            sub[1] = new_name + item[1][len(src_name):]
            for pn in find(sub, 'pin'):
                first(pn, 'name')[1] = new_name
            out.append(sub)
        elif isinstance(item, list) and item[0] == 'property':
            it = parse(dump(item))
            if it[1] == 'Value':
                it[2] = new_name
            elif it[1] == 'Description':
                it[2] = descr
            elif it[1] == 'ki_keywords':
                it[2] = 'power-flag isolated'
            out.append(it)
        else:
            out.append(item)
    out[1] = new_name
    return out


def footprint_dd50():
    name = 'DSUB-50_Pins_Vertical_P2.76x2.84mm_MountingHoles'
    P, R = 2.76, 2.84
    L = []
    A = L.append
    A('(footprint "%s"' % name)
    A('\t(version 20241229)\n\t(generator "gen_lib.py")\n\t(layer "F.Cu")')
    A('\t(descr "50-pin 3-row standard-density D-Sub plug (DD-50P), straight/vertical THT, pitch 2.76x2.84mm, mounting-hole distance 61.11mm, plain 3.1mm flange holes for through jackscrews. Amphenol ICC DD50P364TXLF, drawing C-DSUB-0065")')
    A('\t(tags "DD-50 D-Sub 50 pin plug male vertical THT")')
    A('\t(property "Reference" "REF**" (at 0 -9.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    A('\t(property "Value" "%s" (at 0 9.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % name)
    A('\t(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27))))')
    A('\t(property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27))))')
    A('\t(attr through_hole)')

    def line(layer, x1, y1, x2, y2, w):
        A('\t(fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %s) (type solid)) (layer "%s"))' % (x1, y1, x2, y2, w, layer))

    def poly(layer, pts, w):
        for (a, b) in zip(pts, pts[1:] + pts[:1]):
            line(layer, a[0], a[1], b[0], b[1], w)
    # flange 66.65 x 14.99 (dims A, E), D-shell 55.07 x 13.31 max (dims H, J)
    fw, fh = 66.65 / 2, 14.99 / 2
    poly('F.Fab', [(-fw, -fh), (fw, -fh), (fw, fh), (-fw, fh)], 0.1)
    sh = [(-27.535, -5.54), (27.535, -5.54), (25.6, 5.54), (-25.6, 5.54)]
    poly('F.Fab', sh, 0.1)
    poly('F.SilkS', [(-fw - 0.11, -fh - 0.11), (fw + 0.11, -fh - 0.11), (fw + 0.11, fh + 0.11), (-fw - 0.11, fh + 0.11)], 0.12)
    poly('F.CrtYd', [(-fw - 0.5, -fh - 0.5), (fw + 0.5, -fh - 0.5), (fw + 0.5, fh + 0.5), (-fw - 0.5, fh + 0.5)], 0.05)
    # pin-1 marker
    poly('F.SilkS', [(-22.08 - 1.6, -2.84 - 2.2), (-22.08 - 0.6, -2.84 - 2.2), (-22.08 - 1.1, -2.84 - 1.5)], 0.12)
    A('\t(fp_text user "${REFERENCE}" (at 0 6.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    num = 1
    for row, count in enumerate([17, 16, 17]):
        y = (row - 1) * R
        x0 = -(count - 1) / 2 * P
        for i in range(count):
            shape = 'rect' if num == 1 else 'circle'
            A('\t(pad "%d" thru_hole %s (at %.3f %.3f) (size 1.6 1.6) (drill 1) (layers "*.Cu" "*.Mask") (remove_unused_layers no))' % (num, shape, x0 + i * P, y))
            num += 1
    for x in (-61.11 / 2, 61.11 / 2):
        A('\t(pad "SH" thru_hole circle (at %.3f 0) (size 6.4 6.4) (drill 3.2) (layers "*.Cu" "*.Mask") (remove_unused_layers no))' % x)
    A('\t(embedded_fonts no)')
    A(')')
    return name, '\n'.join(L) + '\n'


def footprint_dcdc():
    """SIP-4 isolated DC-DC (Mornsun B05xxS-1WR3 and clones: 11.6 x 6.0 x 10.2 mm).
    Same pinning as KiCad's Murata MEE1S footprint, but with narrower pads so that
    the copper gap between pin 2 (input) and pin 3 (output) is 1.04 mm instead of 0.29 mm."""
    name = 'Converter_DCDC_Mornsun_B05xxS-1WR3_SIP4_THT'
    L = []
    A = L.append
    A('(footprint "%s"' % name)
    A('\t(version 20241229)\n\t(generator "gen_lib.py")\n\t(layer "F.Cu")')
    A('\t(descr "Isolated 1W DC-DC converter, SIP-4, 11.6x6.0x10.2mm, pitch 2.54mm, Mornsun B05xxS-1WR3 / YLPTEC / EVISUN compatible; pin 1 -Vin, 2 +Vin, 3 -Vout, 4 +Vout")')
    A('\t(tags "DC-DC isolated SIP4 B0505S B0509S")')
    A('\t(property "Reference" "REF**" (at 1.75 -3.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    A('\t(property "Value" "%s" (at 1.75 10.9 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % name)
    A('\t(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27))))')
    A('\t(property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27))))')
    A('\t(attr through_hole)')
    x1, y1, x2, y2 = -1.25, -1.99, 4.75, 9.61

    def rectl(layer, d, w):
        pts = [(x1 - d, y1 - d), (x2 + d, y1 - d), (x2 + d, y2 + d), (x1 - d, y2 + d)]
        for (a, b) in zip(pts, pts[1:] + pts[:1]):
            A('\t(fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %s) (type solid)) (layer "%s"))' % (a[0], a[1], b[0], b[1], w, layer))
    rectl('F.Fab', 0, 0.1)
    rectl('F.SilkS', 0.11, 0.12)
    rectl('F.CrtYd', 0.25, 0.05)
    A('\t(fp_line (start -1.7 -0.8) (end -1.7 0.8) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    A('\t(fp_text user "${REFERENCE}" (at 1.75 3.81 90) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    for i in range(4):
        shape = 'rect' if i == 0 else 'oval'
        A('\t(pad "%d" thru_hole %s (at 0 %.2f) (size 2 1.5) (drill 1) (layers "*.Cu" "*.Mask") (remove_unused_layers no))' % (i + 1, shape, i * 2.54))
    A('\t(embedded_fonts no)')
    A('\t(model "${KICAD10_3DMODEL_DIR}/Converter_DCDC.3dshapes/Converter_DCDC_Murata_CRE1xxxxxxSC_THT.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))')
    A(')')
    return name, '\n'.join(L) + '\n'


def main():
    os.makedirs(LIB, exist_ok=True)
    lib = [S('kicad_symbol_lib'), [S('version'), 20241209], [S('generator'), 'gen_lib.py'],
           [S('generator_version'), '9.0'],
           sym_dd50(), sym_tpic(),
           power_variant('GND', 'GND_ISO', 'Power symbol: isolated (multimeter side) ground "GND_ISO"'),
           power_variant('+5V', '+5V_ISO', 'Power symbol: isolated (multimeter side) regulated +5 V "+5V_ISO"'),
           power_variant('+9V', '+9V_ISO', 'Power symbol: isolated (multimeter side) unregulated +9 V "+9V_ISO"')]
    open(os.path.join(LIB, LIBNAME + '.kicad_sym'), 'w').write(dump(lib) + '\n')
    pretty = os.path.join(LIB, LIBNAME + '.pretty')
    os.makedirs(pretty, exist_ok=True)
    for name, txt in (footprint_dd50(), footprint_dcdc()):
        open(os.path.join(pretty, name + '.kicad_mod'), 'w').write(txt)
    print('wrote libs to', os.path.normpath(LIB))


if __name__ == '__main__':
    main()
