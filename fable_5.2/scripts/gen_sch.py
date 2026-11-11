#!/usr/bin/env python3
"""Generate the KiCad schematic for the Solartron 7075 USB interface.

Pin numbers of J1 are those of SKB, the 50-way "Systems Interface" socket of
the 70754 Parallel BCD Interface Unit (service manual section 9, page 9.9).
"""
import json
import os
from schlib import Project, S, uid
from sx import dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))
NAME = 'solartron7075_usb_interface'
DATE = '2026-11-11'
REV = 'A'
LIBNAME = 'solartron7075'

P = Project(NAME, {LIBNAME: os.path.join(OUT, 'lib', LIBNAME + '.kicad_sym')})

# ---------------------------------------------------------------------------
# part tables (all LCSC numbers checked against the JLCPCB/LCSC catalogue)
# ---------------------------------------------------------------------------
RES = {('27', '0402'): ('C25100', '0402WGF270JTCE'), ('33', '0402'): ('C25105', '0402WGF330JTCE'),
       ('1k', '0402'): ('C11702', '0402WGF1001TCE'), ('10k', '0402'): ('C25744', '0402WGF1002TCE'),
       ('0', '0603'): ('C21189', '0603WAF0000T5E'), ('100', '0603'): ('C22775', '0603WAF1000T5E'),
       ('180', '0603'): ('C22828', '0603WAF1800T5E'), ('390', '0603'): ('C23151', '0603WAF3900T5E'),
       ('470', '0603'): ('C23179', '0603WAF4700T5E'), ('1k', '0603'): ('C21190', '0603WAF1001T5E'),
       ('4.7k', '0603'): ('C23162', '0603WAF4701T5E'), ('10k', '0603'): ('C25804', '0603WAF1002T5E'),
       ('1M', '0603'): ('C22935', '0603WAF1004T5E')}
CAP = {('100n', '0402'): ('C1525', 'CL05B104KO5NNNC', '16V X7R'), ('15p', '0402'): ('C1548', '0402CG150J500NT', '50V C0G'),
       ('4.7u', '0402'): ('C23733', 'CL05A475MP5NRNC', '10V X5R'), ('100n', '0603'): ('C14663', 'CC0603KRX7R9BB104', '50V X7R'),
       ('4.7n', '0603'): ('C106218', 'CC0603KRX7R9BB472', '50V X7R'), ('4.7u', '0603'): ('C19666', 'CL10A475KO8NNNC', '16V X5R'),
       ('10u', '0603'): ('C19702', 'CL10A106KP8NNNC', '10V X5R'), ('10u', '0805'): ('C15850', 'CL21A106KAYNNNE', '25V X5R')}
FPSZ = {'0402': '0402_1005Metric', '0603': '0603_1608Metric', '0805': '0805_2012Metric'}


def F(fp, lcsc, mpn, mfr='', desc=None, ds=None):
    d = {'Footprint': fp, 'LCSC': lcsc, 'MPN': mpn, 'Manufacturer': mfr}
    if desc:
        d['Description'] = desc
    if ds:
        d['Datasheet'] = ds
    return d


def R(sh, ref, x, y, n1, n2, val, size='0603', orient='v', **kw):
    lcsc, mpn = RES[(val, size)]
    return sh.two(ref, 'Device:R', x, y, n1, n2, val, F('Resistor_SMD:R_' + FPSZ[size], lcsc, mpn, 'UNI-ROYAL'),
                  orient, **kw)


def C(sh, ref, x, y, n1, n2, val, size='0603', orient='v', **kw):
    lcsc, mpn, spec = CAP[(val, size)]
    mfr = 'YAGEO' if mpn.startswith('CC') else ('FH' if mpn.startswith('0402CG') else 'Samsung')
    return sh.two(ref, 'Device:C', x, y, n1, n2, val, F('Capacitor_SMD:C_' + FPSZ[size], lcsc, mpn, mfr,
                                                      desc='%sF %s MLCC %s' % (val, spec, size)), orient, **kw)


def LED(sh, ref, x, y, colour, k_net, rot=90):
    lcsc, mpn = {'green': ('C12624', 'KT-0603G'), 'red': ('C2286', 'KT-0603R')}[colour]
    nets = {'1': k_net} if k_net else {}
    ra = (x + 2.6, y - 1.3, 'left') if rot in (90, 270) else (x, y - 3.2, None)
    va = (x + 2.6, y + 1.3, 'left') if rot in (90, 270) else (x, y + 3.4, None)
    return sh.sym(ref, 'Device:LED', x, y, rot, value=colour.upper(), nets=nets,
                  raw=['2'] if k_net else ['1', '2'],
                  fields=F('LED_SMD:LED_0603_1608Metric', lcsc, mpn, 'Hubei KENTO', desc='0603 %s LED' % colour),
                  ref_at=ra, val_at=va)


def rpack(sh, ref, x, y, val, left, right, text='above'):
    """4x0603 resistor array drawn rotated: pins 1-4 on the left (top->bottom), 8-5 on the right.
    left/right: lists of 4 nets; None = wired by hand; 'NC' = unused element."""
    lcsc, mpn, mfr = {'100k': ('C192933', 'YC164-JR-07100KL', 'YAGEO'), '10k': ('C29718', '4D03WGJ0103T5E', 'UNI-ROYAL')}[val]
    nets, nc, raw = {}, [], []
    for i in range(4):
        for num, n in ((str(i + 1), left[i]), (str(8 - i), right[i])):
            if n is None:
                raw.append(num)
            elif n == 'NC':
                nc.append(num)
            else:
                nets[num] = n
    if text == 'above':
        ra, va = (x - 3.2, y - 8.3, None), (x + 3.2, y - 8.3, None)
    else:
        ra, va = (x - 4.5, y + 5.9, None), (x + 1.2, y + 5.9, None)
    return sh.sym(ref, 'Device:R_Pack04', x, y, 270, value=val, nets=nets, nc=nc, raw=raw,
                  fields=F('Resistor_SMD:R_Array_Convex_4x0603', lcsc, mpn, mfr, desc='4x %s 5%% resistor array 0603x4' % val),
                  ref_at=ra, val_at=va)


def bus(sh, pts, net=None, d=None, at=None, stub=2.54):
    """Join collinear points with a wire (junction dots at interior points) and
    optionally attach `net` at point `at` (default: last point) in direction d."""
    pts = sorted(set(pts))
    sh.wire(pts)
    for p in pts[1:-1]:
        sh.junction(*p)
    if net:
        a = at or pts[-1]
        sh.net(a[0], a[1], d, net, stub)


def pin(pins, num):
    return pins[str(num)][0][:2]


# ===========================================================================
# Sheet: MCU + USB
# ===========================================================================
def sheet_mcu():
    sh = P.sheet('MCU_USB', 'mcu_usb.kicad_sch', 'RP2354A microcontroller, USB and 3.3 V supply')
    FP = 'Package_DFN_QFN:QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm'

    # --- USB connector, protection -----------------------------------------
    sh.box(12, 14, 182, 92, 'USB-B input, ESD protection, 3.3 V LDO   (USB / PC ground domain)')
    sh.sym('J2', 'Connector:USB_B', 30, 50, value='USB-B vertical',
           nets={'1': 'VBUS_CONN', '2': 'USB_D_N', '3': 'USB_D_P', '4': 'GND', 'SH': 'USB_SHLD'}, stubs={'SH': 2.54, '4': 2.54},
           fields=F('Connector_USB:USB_B_TE_5787834_Vertical', 'C592900', '5787834-1', 'TE Connectivity',
                    desc='USB 2.0 type B receptacle, vertical, THT',
                    ds='https://www.lcsc.com/datasheet/lcsc_datasheet_2409302231_TE-Connectivity-5787834-1_C592900.pdf'))
    R(sh, 'R1', 20, 78, 'USB_SHLD', 'GND', '1M')
    C(sh, 'C1', 44, 78, 'USB_SHLD', 'GND', '4.7n')
    sh.two('F1', 'Device:Polyfuse', 66, 34, 'VBUS_CONN', 'VBUS', '500mA',
           F('Fuse:Fuse_1206_3216Metric', 'C70075', 'nSMD050-16V', 'TECHFUSE', desc='PTC resettable fuse 0.5 A hold / 1 A trip, 16 V, 1206'), 'h')
    sh.flag(92, 30, (1, 0), 'VBUS')
    sh.sym('U3', 'Power_Protection:USBLC6-2SC6', 66, 58,
           nets={'1': 'USB_D_N', '6': 'USB_D_N', '3': 'USB_D_P', '4': 'USB_D_P', '5': 'VBUS', '2': 'GND'},
           fields=F('Package_TO_SOT_SMD:SOT-23-6', 'C7519', 'USBLC6-2SC6', 'STMicroelectronics'))
    R(sh, 'R2', 108, 52, 'USB_D_P', 'USB_DP', '27', '0402', 'h')
    R(sh, 'R3', 108, 62, 'USB_D_N', 'USB_DM', '27', '0402', 'h')
    C(sh, 'C2', 100, 78, 'VBUS', 'GND', '4.7u')
    # LDO
    u2 = sh.sym('U2', 'Regulator_Linear:AP2112K-3.3', 140, 40, value='AP2112K-3.3',
                nets={'2': 'GND', '5': '+3V3'}, nc=['4'], raw=['1', '3'],
                fields=F('Package_TO_SOT_SMD:SOT-23-5', 'C51118', 'AP2112K-3.3TRG1', 'Diodes Inc.'))
    v, e = pin(u2, 1), pin(u2, 3)
    sh.wire([e, (e[0] - 2.54, e[1]), (v[0] - 2.54, v[1]), v])
    sh.net(v[0] - 2.54, v[1], (-1, 0), 'VBUS')
    C(sh, 'C3', 160, 50, '+3V3', 'GND', '10u')
    # power LED on VBUS
    R(sh, 'R10', 172, 68, 'VBUS', None, '1k')
    LED(sh, 'D1', 172, 75.62, 'green', 'GND')
    sh.text('D1: USB power', 150, 86)

    # --- MCU ---------------------------------------------------------------
    sh.box(88, 96, 300, 270, 'RP2354A (2 MB flash in package)')
    X, Y = 215, 162
    nets = {'46': 'VREG_AVDD', '48': 'VREG_LX',
            '26': 'RUN', '51': 'USB_DM', '52': 'USB_DP', '60': 'QSPI_SS', '21': 'XIN', '22': 'XOUT',
            '24': 'SWCLK', '25': 'SWDIO',
            '2': 'UART_TX', '3': 'UART_RX', '4': 'MCU_SCK', '5': 'MCU_MOSI', '7': 'MCU_MISO',
            '8': 'MCU_LATCH', '9': 'MCU_OEn', '10': 'MCU_DRDY', '37': 'LED_ACT'}
    v33 = ['1', '11', '20', '30', '38', '45', '44', '53', '54', '49']
    v11 = ['6', '23', '39', '50']
    gnd = ['47', '61']
    used = set(nets) | set(v33) | set(v11) | set(gnd)
    nc = [str(n) for n in range(1, 62) if str(n) not in used]
    u1 = sh.sym('U1', 'MCU_RaspberryPi:RP2354A', X, Y, nets=nets, nc=nc, raw=v33 + v11 + gnd,
                stubs={'46': 5.08, '48': 2.54},
                fields=F(FP, 'C41378174', 'RP2354A', 'Raspberry Pi',
                         ds='https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf'))
    top = pin(u1, 1)[1]
    xs33 = sorted(set(pin(u1, n)[0] for n in v33))
    for x in xs33:
        sh.wire([(x, top), (x, top - 7.62)])
    bus(sh, [(x, top - 7.62) for x in xs33], '+3V3', (0, -1), at=(xs33[1], top - 7.62))
    xs11 = sorted(set(pin(u1, n)[0] for n in v11))
    for x in xs11:
        sh.wire([(x, top), (x, top - 3.81)])
    bus(sh, [(x, top - 3.81) for x in xs11], '+1V1', (1, 0), stub=5.08)
    g1, g2 = pin(u1, 47), pin(u1, 61)
    sh.wire([g1, (g1[0], g1[1] + 2.54)])
    sh.wire([g2, (g2[0], g2[1] + 2.54)])
    bus(sh, [(g1[0], g1[1] + 2.54), (g2[0], g2[1] + 2.54)], 'GND', (0, 1))

    # decoupling
    for i in range(8):
        C(sh, 'C%d' % (4 + i), 150 + i * 11, 252, '+3V3', 'GND', '100n', '0402')
    C(sh, 'C15', 238, 252, '+3V3', 'GND', '10u')
    for i in range(3):
        C(sh, 'C%d' % (12 + i), 262 + i * 11, 252, '+1V1', 'GND', '100n', '0402')
    sh.text('3V3 decoupling: 100n at IOVDD (x6) / QSPI_IOVDD / USB_OTP_VDD / ADC_AVDD pins + 10u bulk', 146, 264, 1.3)
    sh.text('DVDD (1.1 V) decoupling', 258, 264, 1.3)

    # core regulator (Raspberry Pi reference circuit)
    sh.box(304, 14, 408, 92, 'Core 1.1 V switching regulator (RP2350 reference circuit)')
    sh.two('L1', 'Device:L', 330, 40, 'VREG_LX', '+1V1', '3.3uH',
           F('Inductor_SMD:L_Abracon_AOTA-B201610S', 'C42411119', 'AOTA-B201610S3R3-101-T', 'Abracon',
             desc='3.3 uH 2.1 A polarised power inductor 2016 (dot = VREG_LX end, see RP2350 datasheet)'), 'h')
    C(sh, 'C17', 352, 56, '+1V1', 'GND', '4.7u', '0402')
    C(sh, 'C16', 372, 56, '+3V3', 'GND', '4.7u', '0402')
    R(sh, 'R5', 330, 62, '+3V3', 'VREG_AVDD', '33', '0402', 'h')
    C(sh, 'C18', 392, 56, 'VREG_AVDD', 'GND', '4.7u', '0402')
    sh.text('C16 at VREG_VIN, C17 at L1 output, C18 + R5 filter VREG_AVDD.\nL1 is polarised: follow the RP2350 datasheet layout.', 310, 78, 1.3)
    sh.flag(346, 30, (1, 0), '+1V1')
    sh.flag(376, 30, (1, 0), 'VREG_AVDD')

    # crystal
    sh.sym('Y1', 'Device:Crystal_GND24', 140, 196, value='12MHz', nets={'1': 'XIN', '3': 'XTAL_X', '2': 'GND', '4': 'GND'},
           fields=F('Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', 'C20625731', 'ABM8-272-T3', 'Abracon',
                    desc='12 MHz crystal, CL = 10 pF, 3225'), ref_at=(134, 190, None), val_at=(146, 190, None))
    C(sh, 'C19', 112, 212, 'XIN', 'GND', '15p', '0402')
    C(sh, 'C20', 168, 212, 'XTAL_X', 'GND', '15p', '0402')
    R(sh, 'R6', 140, 178, 'XTAL_X', 'XOUT', '1k', '0402', 'h')
    # reset / boot
    R(sh, 'R7', 100, 112, '+3V3', 'RUN', '10k', '0402')
    FSW = F('Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A', 'C318884', 'TS-1187A-B-A-B', 'XKB Connection', desc='Tactile switch 5.1x5.1 mm SMD')
    sh.sym('SW2', 'Switch:SW_Push', 140, 114, value='RESET', nets={'1': 'RUN', '2': 'GND'}, fields=FSW)
    sh.sym('SW1', 'Switch:SW_Push', 140, 134, value='BOOTSEL', nets={'1': 'BOOT_SW', '2': 'GND'}, fields=FSW)
    R(sh, 'R8', 140, 152, 'BOOT_SW', 'QSPI_SS', '1k', '0402', 'h')
    # SWD
    sh.sym('J3', 'Connector_Generic_MountingPin:Conn_01x03_MountingPin', 120, 238, value='SWD',
           nets={'1': 'SWCLK', '2': 'GND', '3': 'SWDIO', 'MP': 'GND'},
           fields=F('Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal', 'C160403', 'SM03B-SRSS-TB(LF)(SN)', 'JST',
                    desc='Raspberry Pi 3-pin debug connector (JST-SH): 1 SWCLK, 2 GND, 3 SWDIO'))
    # activity LED + UART test points
    R(sh, 'R9', 272, 214, 'LED_ACT', None, '1k', orient='h')
    LED(sh, 'D2', 279.62, 214, 'red', 'GND', rot=180)
    sh.text('D2: activity', 266, 219)
    FTP = F('TestPoint:TestPoint_Pad_D1.0mm', '', '', desc='test pad')
    sh.sym('TP1', 'Connector:TestPoint', 270, 110, value='TX', nets={'1': 'UART_TX'}, fields=FTP, stub=3.81)
    sh.sym('TP2', 'Connector:TestPoint', 284, 110, value='RX', nets={'1': 'UART_RX'}, fields=FTP, stub=3.81)

    # --- LED driver buffer ---------------------------------------------------
    sh.box(304, 96, 408, 250, 'Opto LED drivers (LED off = isolated line high)')
    FB = F('Package_SO:TSSOP-14_4.4x5mm_P0.65mm', 'C7813', 'SN74LVC125APWR', 'Texas Instruments')
    sigs = ['SCK', 'MOSI', 'LATCH', 'OEn']
    upins = [(1, 2, 3), (4, 5, 6), (10, 9, 8), (13, 12, 11)]
    for i, (sig, (oe, a, yv)) in enumerate(zip(sigs, upins)):
        sh.sym('U4', '74xx:74LVC125', 356, 116 + i * 24, unit=i + 1, value='74LVC125',
               nets={str(oe): 'GND', str(a): 'MCU_' + sig, str(yv): 'LEDK_' + sig}, fields=FB,
               ref_at=(356, 109 + i * 24, None), val_at=(366, 111 + i * 24, None))
    sh.sym('U4', '74xx:74LVC125', 392, 212, unit=5, value='74LVC125', nets={'14': '+3V3', '7': 'GND'}, fields=FB)
    C(sh, 'C21', 376, 212, '+3V3', 'GND', '100n', '0402')
    rn = rpack(sh, 'RN1', 326, 222, '10k', ['MCU_SCK', 'MCU_MOSI', 'MCU_LATCH', 'MCU_OEn'], [None] * 4)
    pts = [pin(rn, n) for n in (8, 7, 6, 5)]
    for p in pts:
        sh.wire([p, (p[0] + 2.54, p[1])])
    bus(sh, [(p[0] + 2.54, p[1]) for p in pts], '+3V3', (0, -1), at=(pts[0][0] + 2.54, min(q[1] for q in pts)))
    sh.text('RN1 pull-ups keep all four opto LEDs off\nwhile the MCU is in reset / unprogrammed.', 312, 236, 1.3)
    return sh


# ===========================================================================
# Sheet: isolation barrier + isolated supply
# ===========================================================================
def sheet_iso():
    sh = P.sheet('ISOLATION', 'isolation.kicad_sch', 'Opto-isolation barrier and isolated 5 V supply')
    FO = F('Package_DIP:SMDIP-8_W9.53mm', 'C188742', 'HCPL-2631-500E', 'Broadcom',
           desc='Dual 10 MBd logic-gate optocoupler, open-collector outputs, gull-wing SMD-8',
           ds='https://docs.broadcom.com/doc/AV02-0940EN')
    sh.text('USB / MCU ground domain  (GND, +3V3, VBUS)', 40, 20, 2.5, True)
    sh.text('Isolated multimeter domain  (GND_ISO, +5V_ISO)', 235, 20, 2.5, True)
    sh.items.append([S('polyline'), [S('pts'), [S('xy'), 210, 16], [S('xy'), 210, 196]],
                     [S('stroke'), [S('width'), 0.5], [S('type'), S('dash_dot')]], [S('fill'), [S('type'), S('none')]],
                     [S('uuid'), uid('iso', 'barrier')]])
    sh.text('ISOLATION BARRIER', 212, 28, 1.6, True)

    def down_opto(ref, y, s1, s2, r1, r2_, pu1, pu2, cref, pv1, pv2):
        u = sh.sym(ref, 'Isolator:HCPL-2631', 210, y, value='HCPL-2631',
                   nets={'2': 'LEDK_' + s1, '3': 'LEDK_' + s2, '8': '+5V_ISO', '5': 'GND_ISO'}, raw=['1', '4', '6', '7'], fields=FO)
        for rr, pn in ((r1, 1), (r2_, 4)):
            p = pin(u, pn)
            R(sh, rr, p[0] - 22, p[1], '+3V3', None, '180', orient='h')
            sh.wire([(p[0] - 22 + 3.81, p[1]), p])
        ytop = pin(u, 7)[1] - 10.16
        for pn, sname, pr, pv, dx in ((7, s1, pu1, pv1, 12.7), (6, s2, pu2, pv2, 27.94)):
            p = pin(u, pn)
            xr = p[0] + dx
            sh.wire([p, (xr, p[1]), (p[0] + 38.1, p[1])])
            sh.junction(xr, p[1])
            sh.net(p[0] + 38.1, p[1], (1, 0), sname + '_ISO')
            R(sh, pr, xr, ytop - 3.81, '+5V_ISO', None, pv)
            sh.wire([(xr, ytop), (xr, p[1])])
        C(sh, cref, 290, y, '+5V_ISO', 'GND_ISO', '100n')

    down_opto('U5', 56, 'SCK', 'MOSI', 'R11', 'R12', 'R15', 'R16', 'C22', '470', '470')
    down_opto('U6', 108, 'LATCH', 'OEn', 'R13', 'R14', 'R17', 'R18', 'C23', '470', '1k')
    sh.text('MCU -> multimeter side: SPI-style clock/data, register latch, output enable.\n'
            'LED off (MCU in reset, USB unplugged) = line high on the isolated side.', 228, 126, 1.3)
    sh.text('180R: IF = 9 mA typ from 3.3 V', 150, 76, 1.3)
    sh.text('390R: IF = 8.5 mA typ from +5V_ISO', 236, 196, 1.3)

    # uplink opto, mirrored so the barrier stays in the same place
    u7 = sh.sym('U7', 'Isolator:HCPL-2631', 210, 170, value='HCPL-2631', mirror=True,
                nets={'2': 'LEDK_MISO', '3': 'LEDK_DRDY', '8': 'VBUS', '5': 'GND'}, raw=['1', '4', '6', '7'], fields=FO)
    for rr, pn in (('R21', 1), ('R22', 4)):
        p = pin(u7, pn)
        R(sh, rr, p[0] + 22, p[1], None, '+5V_ISO', '390', orient='h')
        sh.wire([p, (p[0] + 22 - 3.81, p[1])])
    ytop = pin(u7, 7)[1] - 10.16
    for pn, sname, pr, dx in ((7, 'MCU_MISO', 'R19', 12.7), (6, 'MCU_DRDY', 'R20', 27.94)):
        p = pin(u7, pn)
        xr = p[0] - dx
        sh.wire([p, (xr, p[1]), (p[0] - 38.1, p[1])])
        sh.junction(xr, p[1])
        sh.net(p[0] - 38.1, p[1], (-1, 0), sname)
        R(sh, pr, xr, ytop - 3.81, '+3V3', None, '1k')
        sh.wire([(xr, ytop), (xr, p[1])])
    C(sh, 'C24', 130, 172, 'VBUS', 'GND', '100n')
    sh.text('Multimeter -> MCU: serial status data and PRINT (data ready) level.\n'
            'U7 output stage runs from VBUS (5 V); open collectors pull up to 3.3 V.', 30, 190, 1.3)

    # ISO-side LED driver
    sh.box(256, 136, 408, 200, 'Uplink LED drivers (TTL-level inputs)')
    FA = F('Package_SO:SOIC-14_3.9x8.7mm_P1.27mm', 'C155176', 'SN74AHCT125DR', 'Texas Instruments')
    for i, (oe, a, yv, na, ny, xx, yy) in enumerate([(1, 2, 3, 'MISO_ISO', 'LEDK_MISO', 296, 154),
                                                     (4, 5, 6, 'PRINT_LEVEL_S', 'LEDK_DRDY', 296, 180),
                                                     (10, 9, 8, 'GND_ISO', None, 346, 154),
                                                     (13, 12, 11, 'GND_ISO', None, 346, 180)]):
        nets = {str(oe): 'GND_ISO', str(a): na}
        if ny:
            nets[str(yv)] = ny
        sh.sym('U8', '74xx:74AHCT125', xx, yy, unit=i + 1, value='74AHCT125', nets=nets, nc=[] if ny else [str(yv)],
               fields=FA, ref_at=(xx, yy - 7, None), val_at=(xx + 10, yy - 5, None))
    sh.sym('U8', '74xx:74AHCT125', 396, 168, unit=5, value='74AHCT125', nets={'14': '+5V_ISO', '7': 'GND_ISO'}, fields=FA)
    C(sh, 'C25', 378, 168, '+5V_ISO', 'GND_ISO', '100n')

    # isolated supply
    sh.box(12, 204, 300, 268, 'Isolated supply: USB 5 V -> 9 V isolated DC-DC -> 5 V linear regulator')
    sh.two('FB1', 'Device:FerriteBead', 36, 226, 'VBUS', 'VBUS_DCDC', '120R@100MHz',
           F('Inductor_SMD:L_0603_1608Metric', 'C14709', 'BLM18PG121SN1D', 'Murata', desc='Ferrite bead 120 ohm @ 100 MHz, 2 A, 0603'), 'h')
    C(sh, 'C26', 60, 244, 'VBUS_DCDC', 'GND', '4.7u')
    sh.flag(74, 236, (0, 1), 'VBUS_DCDC')
    sh.sym('PS1', 'Converter_DCDC_Isolated:MEE1S0509SC', 100, 228.54, value='B0509S-1WR3',
           nets={'2': 'VBUS_DCDC', '1': 'GND', '4': '+9V_ISO', '3': 'GND_ISO'},
           fields=F('Converter_DCDC:Converter_DCDC_Murata_MEE1SxxxxSC_THT', 'C5369463', 'B0509S-1WR3', 'YLPTEC (Mornsun B0509S-1WR3 compatible)',
                    desc='Isolated 1 W DC-DC converter 5 V -> 9 V / 111 mA, 1.5 kV, SIP-4 (Murata MEE1S0509SC pin compatible)'))
    C(sh, 'C27', 132, 244, '+9V_ISO', 'GND_ISO', '10u', '0805')
    C(sh, 'C28', 148, 244, '+9V_ISO', 'GND_ISO', '100n')
    sh.sym('U9', 'Regulator_Linear:LM78M05_TO252', 180, 232, value='L78M05',
           nets={'1': '+9V_ISO', '2': 'GND_ISO', '3': '+5V_ISO'},
           fields=F('Package_TO_SOT_SMD:TO-252-2', 'C58069', 'L78M05ABDT-TR', 'STMicroelectronics', desc='5 V 500 mA linear regulator, DPAK'))
    C(sh, 'C29', 206, 244, '+5V_ISO', 'GND_ISO', '10u', '0805')
    C(sh, 'C30', 222, 244, '+5V_ISO', 'GND_ISO', '100n')
    R(sh, 'R23', 244, 236, '+5V_ISO', None, '1k')
    LED(sh, 'D3', 244, 243.62, 'green', 'GND_ISO')
    sh.text('D3: isolated\nsupply OK', 252, 250)
    return sh


# ===========================================================================
# Sheet: DVM connector + status inputs (parallel-in shift registers)
# ===========================================================================
PIN_NET = {}
for dec, base in ((5, 2), (4, 6), (3, 10), (2, 14), (1, 18), (0, 22)):
    for i, w in enumerate((8, 4, 2, 1)):
        PIN_NET[base + i] = 'DVM_D%d_%d' % (dec, w)
PIN_NET[1] = 'DVM_D6_1'
PIN_NET.update({26: 'DVM_POL_POS', 27: 'DVM_POL_NEG', 28: 'DVM_FN_OUT_A', 29: 'DVM_FN_OUT_B',
                30: 'DVM_RNG_OUT_4', 31: 'DVM_RNG_OUT_2', 32: 'DVM_RNG_OUT_1', 33: 'DVM_PRINT_PULSE',
                34: 'DVM_PRINT_LEVEL', 35: 'DVM_DATA_CAN_CHG', 36: 'DVM_OVERLOAD', 37: 'GND_ISO',
                38: 'DVM_FP_LOCKOUT', 39: 'DVM_SAMPLE_CONTACT', 40: 'DVM_SAMPLE_PULSE', 41: 'DVM_RATIO',
                42: 'DVM_FN_CMD_A', 43: 'DVM_FN_CMD_B', 44: 'DVM_INT_CMD_4', 45: 'DVM_INT_CMD_2',
                46: 'DVM_INT_CMD_1', 47: 'DVM_AUTORANGE', 48: 'DVM_RNG_CMD_1', 49: 'DVM_RNG_CMD_2',
                50: 'DVM_RNG_CMD_4'})


def sheet_inputs():
    sh = P.sheet('DVM_INPUTS', 'dvm_inputs.kicad_sch', 'Multimeter connector and status / BCD data inputs')
    nets = {str(n): PIN_NET[n] for n in range(1, 51)}
    j1 = sh.sym('J1', LIBNAME + ':DD50_Plug_MountingHoles', 46, 112, value='DD-50P (to 70754 SKB)', nets=nets, raw=['SH'],
                fields=F(LIBNAME + ':DSUB-50_Pins_Vertical_P2.76x2.84mm_MountingHoles', 'C5402574', 'DD50P364TXLF', 'Amphenol ICC'),
                val_at=(46, 74.5, None))
    shp = pin(j1, 'SH')
    R(sh, 'R24', shp[0], shp[1] + 3.81, None, 'GND_ISO', '0')
    sh.text('R24: connector shell / jackscrews to GND_ISO.\nSKB pin 37 = multimeter EARTH / logic 0.\nRemove R24 to float the shell.', 14, 172, 1.3)
    sh.text('J1 mounts on the BOTTOM side and plugs straight into\nthe "Systems Interface" socket SKB of the 70754 unit.\nPin numbers = SKB pin numbers (manual page 9.9).', 14, 52, 1.3)

    FU = F('Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', 'C456131', '74HCT165D,653', 'Nexperia',
           desc='8-bit parallel-in serial-out shift register, TTL-compatible inputs, SOIC-16',
           ds='https://assets.nexperia.com/documents/data-sheet/74HC_HCT165.pdf')
    # (ref, x0, y0, [net for D7..D0])  -- D7 is shifted out first
    groups = [
        ('U10', 195, 56, [PIN_NET[n] for n in range(1, 9)]),
        ('U11', 340, 56, [PIN_NET[n] for n in range(9, 17)]),
        ('U12', 195, 134, [PIN_NET[n] for n in range(17, 25)]),
        ('U13', 340, 134, [PIN_NET[n] for n in range(25, 33)]),
        ('U14', 195, 212, [PIN_NET[33], PIN_NET[34], PIN_NET[35], PIN_NET[36], 'DVM_FP_LOCKOUT', 'ID1', 'ID0', 'ID0']),
    ]
    strap = {'ID0': 'GND_ISO', 'ID1': '+5V_ISO'}
    dpins = [11, 12, 13, 14, 3, 4, 5, 6]
    chain = ['MISO_ISO', 'SR_Q1', 'SR_Q2', 'SR_Q3', 'SR_Q4']
    rn_i = 2
    for gi, (ref, x0, y0, sigs) in enumerate(groups):
        d = list(reversed(sigs))            # d[0] = D0 ... d[7] = D7
        un = {'16': '+5V_ISO', '8': 'GND_ISO', '1': 'LATCH_ISO', '2': 'SCK_ISO', '15': 'GND_ISO',
              '9': chain[gi], '10': chain[gi + 1] if gi < 4 else 'GND_ISO'}
        raw = []
        tie0 = []                               # pins strapped low, bussed to one GND_ISO symbol
        for k in range(8):
            if d[k] == 'ID0':
                tie0.append(str(dpins[k]))
            elif d[k] in strap:
                un[str(dpins[k])] = strap[d[k]]
            else:
                raw.append(str(dpins[k]))
        if tie0:
            tie0.append('10')
            del un['10']
        u = sh.sym(ref, '74xx:74HC165', x0, y0, value='74HCT165', nets=un, nc=['7'], raw=raw + tie0, fields=FU)
        if tie0:
            tp = [pin(u, n) for n in tie0]
            for q_ in tp:
                sh.wire([q_, (q_[0] - 2.54, q_[1])])
            bus(sh, [(q_[0] - 2.54, q_[1]) for q_ in tp], 'GND_ISO', (-1, 0), at=(tp[0][0] - 2.54, min(q_[1] for q_ in tp)))
        C(sh, 'C%d' % (31 + gi), x0 + 30, y0 + 8, '+5V_ISO', 'GND_ISO', '100n')
        xs, xp = x0 - 43.18, x0 - 86.36
        gpts = []
        for half in (0, 1):
            four = d[half * 4: half * 4 + 4]
            ys = y0 - 7.62 + half * 10.16
            lft = [s_ if s_ not in strap else 'NC' for s_ in four]
            rgt = [None if s_ not in strap else 'NC' for s_ in four]
            txt = 'above' if half == 0 else 'below'
            rs = rpack(sh, 'RN%d' % rn_i, xs, ys, '100k', lft, rgt, txt)
            for k in range(4):
                if rgt[k] is None:
                    a_, b_ = pin(rs, 8 - k), pin(u, dpins[half * 4 + k])
                    sh.wire([a_, b_])
                    if four[k] == 'DVM_PRINT_LEVEL':
                        # tap after the series resistor: feeds the direct data-ready opto channel
                        mx = a_[0] + 2.54
                        sh.junction(mx, a_[1])
                        sh.wire([(mx, a_[1]), (mx, y0 + 7.62)])
                        sh.net(mx, y0 + 7.62, (0, 1), 'PRINT_LEVEL_S', 0)
            rp = rpack(sh, 'RN%d' % (rn_i + 1), xp, ys, '100k', lft, rgt, txt)
            for k in range(4):
                if rgt[k] is None:
                    p_ = pin(rp, 8 - k)
                    sh.wire([p_, (p_[0] + 2.54, p_[1])])
                    gpts.append((p_[0] + 2.54, p_[1]))
            rn_i += 2
        bus(sh, gpts, 'GND_ISO', (0, 1))
        sh.text('100k pull-downs', xp - 8, y0 - 22.5, 1.3)
        sh.text('100k series', xs - 6, y0 - 22.5, 1.3)
    sh.text('Every multimeter output is read through 100k (series) into a 74HCT165 input, with a\n'
            '100k pull-down on the connector side:\n'
            ' - TTL-compatible thresholds for the 7404 outputs of the 70754 unit\n'
            ' - < 35 uA per line into the input clamp diodes when the isolated supply is off\n'
            '   (USB unplugged), so the multimeter cannot back-power this board\n'
            ' - defined (all-zero) data when the board is not plugged into the multimeter\n\n'
            'Serial stream at MISO after a LATCH pulse (first bit first):\n'
            '  bit 0..35  = SKB pin 1..36  (bit n = pin n+1)\n'
            '  bit 36     = SKB pin 38 read-back (FRONT PANEL LOCKOUT line; high = DVM powered)\n'
            '  bit 37..39 = 1,0,0  hard-wired marker (checks chain length / isolated supply present)', 240, 196, 1.4)
    return sh


# ===========================================================================
# Sheet: command outputs (open-drain shift registers)
# ===========================================================================
def sheet_outputs():
    sh = P.sheet('DVM_OUTPUTS', 'dvm_outputs.kicad_sch', 'Multimeter command outputs (open-drain)', paper='A4')
    FT = F('Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', 'C350572', 'TPIC6C595DR', 'Texas Instruments')
    d1 = ['DVM_FP_LOCKOUT', 'DVM_SAMPLE_CONTACT', 'PULSE_GATE', 'DVM_RATIO', 'DVM_FN_CMD_A', 'DVM_FN_CMD_B',
          'DVM_INT_CMD_4', 'DVM_INT_CMD_2']
    d2 = ['DVM_INT_CMD_1', 'DVM_AUTORANGE', 'DVM_RNG_CMD_1', 'DVM_RNG_CMD_2', 'DVM_RNG_CMD_4', None, None, None]
    dn = [3, 4, 5, 6, 11, 12, 13, 14]
    sh.box(12, 14, 142, 150, 'Open-drain command drivers')
    sh.text('output off = line released = logic 1 at the multimeter', 14, 21, 1.3)
    for ref, y, dd, sin, sout, cref in (('U15', 54, d1, 'MOSI_ISO', 'CMD_CHAIN', 'C36'), ('U16', 114, d2, 'CMD_CHAIN', None, 'C37')):
        nets = {'1': '+5V_ISO', '16': 'GND_ISO', '2': sin, '15': 'SCK_ISO', '10': 'LATCH_ISO', '7': '+5V_ISO', '8': 'OEn_ISO'}
        nc = []
        for k in range(8):
            if dd[k]:
                nets[str(dn[k])] = dd[k]
            else:
                nc.append(str(dn[k]))
        if sout:
            nets['9'] = sout
        else:
            nc.append('9')
        sh.sym(ref, LIBNAME + ':TPIC6C595', 84, y, nets=nets, nc=nc, fields=FT, stubs={'5': 33.02} if ref == 'U15' else None)
        C(sh, cref, 26, y, '+5V_ISO', 'GND_ISO', '100n')
    # sample pulse high-side driver
    sh.box(148, 14, 285, 78, 'SAMPLE pulse driver (SKB pin 40: positive pulse > 100 us)')
    q = sh.sym('Q1', 'Transistor_FET:AO3401A', 204, 42, value='AO3401A', nets={'1': 'PULSE_GATE', '2': '+5V_ISO'}, raw=['3'],
               fields=F('Package_TO_SOT_SMD:SOT-23', 'C15127', 'AO3401A', 'Alpha & Omega', desc='P-channel MOSFET -30 V -4 A SOT-23'),
               rot=180, ref_at=(193, 40, None), val_at=(193, 43, None))
    R(sh, 'R25', 170, 40, '+5V_ISO', 'PULSE_GATE', '10k')
    dp = pin(q, 3)
    R(sh, 'R26', dp[0] + 3.81, dp[1] + 12.7, None, 'DVM_SAMPLE_PULSE', '100', orient='h')
    sh.wire([dp, (dp[0], dp[1] + 12.7)])
    R(sh, 'R27', 262, 54, 'DVM_SAMPLE_PULSE', 'GND_ISO', '4.7k')
    sh.text('Command word = the last 16 bits clocked into MOSI before LATCH rises (MSB first):\n'
            '  bit 0  -> SKB 38 FRONT PANEL LOCKOUT      bit 7  -> SKB 45 INTEGRATION TIME (2)\n'
            '  bit 1  -> SKB 39 SAMPLE (contact to 0 V)   bit 8  -> SKB 46 INTEGRATION TIME (1)\n'
            '  bit 2  -> SKB 40 SAMPLE pulse (via Q1)     bit 9  -> SKB 47 AUTORANGE command\n'
            '  bit 3  -> SKB 41 RATIO                     bit 10 -> SKB 48 RANGE (1)\n'
            '  bit 4  -> SKB 42 FUNCTION                  bit 11 -> SKB 49 RANGE (2)\n'
            '  bit 5  -> SKB 43 FUNCTION                  bit 12 -> SKB 50 RANGE (4)\n'
            '  bit 6  -> SKB 44 INTEGRATION TIME (4)      bit 13..15 spare\n\n'
            'A 1 turns the open-drain output ON, i.e. pulls the SKB line to logic 0\n'
            '(bit 2: a 1 drives SKB 40 HIGH through Q1).  The multimeter has its own\n'
            '4.7k pull-ups to +5 V on every command line.\n\n'
            '~{G} (OEn_ISO) is pulled high until the MCU enables it, and all drains are\n'
            'off without isolated power, so an unpowered / unconfigured board leaves\n'
            'the multimeter exactly as if nothing were plugged in.', 150, 84, 1.3)
    return sh


# ===========================================================================
def root_sheet(sheets):
    R_ = [S('kicad_sch'), [S('version'), 20250114], [S('generator'), 'eeschema'], [S('generator_version'), '9.0'],
          [S('uuid'), P.root_uuid], [S('paper'), 'A4'],
          [S('title_block'), [S('title'), 'Solartron 7075 opto-isolated USB interface'], [S('date'), DATE], [S('rev'), REV],
           [S('company'), 'Solartron 7075 USB interface (RP2354A)'],
           [S('comment'), 1, 'Generated by scripts/gen_sch.py'],
           [S('comment'), 2, 'Plugs into SKB (50-way) of the 70754 Parallel BCD Interface Unit']],
          [S('lib_symbols')]]
    pos = {'MCU_USB': (30, 40), 'ISOLATION': (115, 40), 'DVM_INPUTS': (200, 28), 'DVM_OUTPUTS': (200, 62)}
    for sh in sheets:
        x, y = pos[sh.name]
        w, h = 55, 22
        R_.append([S('sheet'), [S('at'), x, y], [S('size'), w, h], [S('exclude_from_sim'), S('no')], [S('in_bom'), S('yes')],
                   [S('on_board'), S('yes')], [S('dnp'), S('no')],
                   [S('stroke'), [S('width'), 0.1524], [S('type'), S('solid')]],
                   [S('fill'), [S('color'), 0, 0, 0, 0.0]], [S('uuid'), sh.uuid],
                   [S('property'), 'Sheetname', sh.name, [S('at'), x, y - 0.7, 0],
                    [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S('left'), S('bottom')]]],
                   [S('property'), 'Sheetfile', sh.filename, [S('at'), x, y + h + 0.6, 0],
                    [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S('left'), S('top')]]],
                   [S('instances'), [S('project'), NAME, [S('path'), '/' + P.root_uuid, [S('page'), str(sh.page)]]]]])

    def text(s, x, y, size=1.6, bold=False):
        f = [S('font'), [S('size'), size, size]]
        if bold:
            f.append([S('bold'), S('yes')])
        R_.append([S('text'), s, [S('exclude_from_sim'), S('no')], [S('at'), x, y, 0],
                   [S('effects'), f, [S('justify'), S('left'), S('top')]], [S('uuid'), uid('root', 'text', s[:20], x, y)]])
    text('Solartron 7075 opto-isolated USB interface', 20, 14, 3.5, True)
    text('USB-B  ->  RP2354A  ->  6 opto channels  ->  shift registers  ->  50-way D (SKB of the 70754 BCD interface unit)', 20, 22, 1.8)
    text('Sheets are connected with global labels.', 20, 68, 1.3)
    text('Signals crossing the isolation barrier (3 x HCPL-2631 dual 10 MBd optocouplers):\n'
         '   SCK    MCU -> DVM side   shift clock for both register chains (rising edge shifts)\n'
         '   MOSI   MCU -> DVM side   command bits into 2 x TPIC6C595 (16 open-drain outputs)\n'
         '   LATCH  MCU -> DVM side   low = load 5 x 74HCT165 (40 inputs); rising edge = update command outputs\n'
         '   OEn    MCU -> DVM side   low = enable command outputs (high / LED off = all released)\n'
         '   MISO   DVM side -> MCU   status / BCD data out of the 74HCT165 chain\n'
         '   DRDY   DVM side -> MCU   PRINT command level (SKB pin 34): high = reading complete, data valid\n\n'
         'Power: USB VBUS -> AP2112K-3.3 (MCU side).  VBUS -> ferrite -> isolated 1 W DC-DC (9 V) -> L78M05 -> +5V_ISO\n'
         '(the 50-way connector has no supply pin, so the isolated logic is powered across the barrier).\n\n'
         'Mechanical: 104 x 48 mm, 4 layers.  J1 (DD-50 plug) is on the bottom side, everything else on the top side;\n'
         'the board is held by two 4-40 UNC screws through J1\'s flange holes into the jackposts of SKB.', 20, 96, 1.6)
    R_.append([S('sheet_instances'), [S('path'), '/', [S('page'), '1']]])
    open(os.path.join(OUT, NAME + '.kicad_sch'), 'w').write(dump(R_) + '\n')


def main():
    s1 = sheet_mcu()
    s2 = sheet_iso()
    s3 = sheet_inputs()
    s4 = sheet_outputs()
    P.finalize()
    for sh in P.sheets:
        sh.write(OUT, DATE, REV)
    root_sheet(P.sheets)
    for fn, kind in (('sym-lib-table', 'sym_lib_table'), ('fp-lib-table', 'fp_lib_table')):
        ext = '.kicad_sym' if kind == 'sym_lib_table' else '.pretty'
        open(os.path.join(OUT, fn), 'w').write(
            '(%s\n\t(version 7)\n\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/lib/%s%s")(options "")(descr "Project-local parts"))\n)\n'
            % (kind, LIBNAME, LIBNAME, ext))
    print('schematic written:', len(P.sheets) + 1, 'sheets')


if __name__ == '__main__':
    main()
