#!/usr/bin/env python3
"""
Solartron 7075 DVM -> USB interface, described with SKiDL.

The 7075's Parallel BCD Interface Unit (70754, manual section 9) presents a
50-way Cannon D socket (SKB) carrying TTL-level BCD display data, status
outputs and remote-control command inputs. This board plugs straight into
that socket, captures the 36 meter outputs with 74HCT165 shift registers,
drives the 13 command inputs from 74HC595 shift registers, and talks to an
RP2354A over just five optocoupled lines (SCLK, MOSI, LATCH, /OE -> meter
side; MISO <- meter side). The meter side is powered from USB through an
isolated DC/DC converter, so the USB host's ground never touches the meter.

Run:  python3 solartron_7075_interface.py   (or ./build.sh for the whole flow)
Outputs go to ./output: KiCad netlist, ERC log and the unplaced .kicad_pcb
that scripts/layout_pcb.py and scripts/route_pcb.py turn into the board.
"""

import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

# Point SKiDL at the KiCad 10 libraries before importing it.
os.environ.setdefault("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD_SYMBOL_DIR", os.environ["KICAD10_SYMBOL_DIR"])

from skidl import (  # noqa: E402
    KICAD10,
    POWER,
    TEMPLATE,
    Net,
    Part,
    ERC,
    generate_netlist,
    generate_pcb,
    generate_schematic,
    lib_search_paths,
    set_default_tool,
    subcircuit,
)

import builtins  # noqa: E402

NC = builtins.NC  # SKiDL keeps its no-connect net and default circuit in builtins
set_default_tool(KICAD10)
lib_search_paths[KICAD10].append(str(HERE / "lib"))

LOCAL_LIB = "Solartron7075"

# ---------------------------------------------------------------------------
# Footprints and part helpers
# ---------------------------------------------------------------------------
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_RN = "Resistor_SMD:R_Array_Convex_4x0603"
FP_SO16 = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
FP_OPTO = "Package_SO:Toshiba_SOIC-5-6_4.4x3.6mm_P1.27mm"


def tag(part, lcsc, mpn, mfr):
    """Attach sourcing fields (exported to the netlist / BOM)."""
    part.fields["LCSC"] = lcsc
    part.fields["MPN"] = mpn
    part.fields["Manufacturer"] = mfr
    return part


# Basic-library passives (JLCPCB "basic" parts where available).
# 0603 by default; 0402 for the parts packed around the RP2354A.
R_LCSC = {
    "0603": {
        "27": ("C25190", "0603WAF270JT5E"),
        "390": ("C23151", "0603WAF3900T5E"),
        "820": ("C23253", "0603WAF8200T5E"),
        "1k": ("C21190", "0603WAF1001T5E"),
        "2.2k": ("C4190", "0603WAF2201T5E"),
        "10k": ("C25804", "0603WAF1002T5E"),
        "100k": ("C25803", "0603WAF1003T5E"),
        "1M": ("C22935", "0603WAF1004T5E"),
    },
    "0402": {
        "27": ("C25100", "0402WGF270JTCE"),
        "33": ("C25105", "0402WGF330JTCE"),
        "1k": ("C11702", "0402WGF1001TCE"),
        "10k": ("C25744", "0402WGF1002TCE"),
    },
}
C_LCSC = {
    "0603": {
        "4.7n": ("C53987", "0603B472K500NT", "FH"),
        "100n": ("C14663", "CC0603KRX7R9BB104", "YAGEO"),
        "1u": ("C15849", "CL10A105KB8NNNC", "Samsung"),
        "2.2u": ("C23630", "CL10A225KO8NNNC", "Samsung"),
        "4.7u": ("C19666", "CL10A475KO8NNNC", "Samsung"),
        "10u": ("C19702", "CL10A106KP8NNNC", "Samsung"),
    },
    "0402": {
        "15p": ("C1548", "0402CG150J500NT", "FH"),
        "100n": ("C1525", "CL05B104KO5NNNC", "Samsung"),
        "1u": ("C52923", "CL05A105KA5NQNC", "Samsung"),
        "4.7u": ("C23733", "CL05A475MP5NRNC", "Samsung"),
    },
}
FP_SIZE = {"0603": "1608Metric", "0402": "1005Metric"}

r_tmpl = Part("Device", "R", dest=TEMPLATE, footprint=FP_R)
c_tmpl = Part("Device", "C", dest=TEMPLATE, footprint=FP_C)
led_tmpl = Part("Device", "LED", dest=TEMPLATE, footprint=FP_LED)
rn_tmpl = Part("Device", "R_Pack04", dest=TEMPLATE, footprint=FP_RN)


def R(value, size="0603"):
    r = r_tmpl(value=value, footprint=f"Resistor_SMD:R_{size}_{FP_SIZE[size]}")
    lcsc, mpn = R_LCSC[size][value]
    return tag(r, lcsc, mpn, "UNI-ROYAL")


def C(value, size="0603"):
    c = c_tmpl(value=value, footprint=f"Capacitor_SMD:C_{size}_{FP_SIZE[size]}")
    lcsc, mpn, mfr = C_LCSC[size][value]
    return tag(c, lcsc, mpn, mfr)


def decouple(pos, neg, value="100n", size="0603"):
    c = C(value, size)
    c[1] += pos
    c[2] += neg
    return c


def LED(colour):
    led = led_tmpl(value=colour)
    if colour == "green":  # AlInGaP yellow-green, ~2.0 V: bright enough from 3.3 V
        return tag(led, "C125094", "LTST-C190KGKT", "Lite-On")
    return tag(led, "C2286", "KT-0603R", "Hubei KENTO")


# ---------------------------------------------------------------------------
# Global nets
# ---------------------------------------------------------------------------
def power_net(name):
    n = Net(name)
    n.drive = POWER
    return n


# USB / host side
vbus_raw = Net("VBUS_RAW")
vbus = power_net("+5V_USB")
v3v3 = power_net("+3V3")
gnd = power_net("GND")

# Isolated / meter side
iso_9v = power_net("ISO_+9V")
iso_5v = power_net("ISO_+5V")
iso_gnd = power_net("ISO_GND")  # = Solartron pin 37 "EARTH / Logic 0"

# MCU <-> optocoupler (host side)
mcu_sclk, mcu_mosi, mcu_miso, mcu_latch, mcu_oe_n = (
    Net("MCU_SCLK"), Net("MCU_MOSI"), Net("MCU_MISO"), Net("MCU_LATCH"), Net("MCU_OE_N"))

# Optocoupler -> shift registers (meter side)
iso_sclk, iso_mosi, iso_latch, iso_oe_n = (
    Net("ISO_SCLK"), Net("ISO_MOSI"), Net("ISO_LATCH"), Net("ISO_OE_N"))

# ---------------------------------------------------------------------------
# Solartron 7075 / 70754 SKB pin map (manual section 9, connection table).
# ---------------------------------------------------------------------------
# Outputs from the meter (TTL, '1' = +2.4..+6 V from 6 kOhm, '0' sinks 10 mA)
BCD_PINS = {}  # (decade, weight) -> pin
BCD_PINS[(6, 1)] = 1  # the "half" digit: 1 x 10^6
for decade, first_pin in zip((5, 4, 3, 2, 1, 0), (2, 6, 10, 14, 18, 22)):
    for i, weight in enumerate((8, 4, 2, 1)):
        BCD_PINS[(decade, weight)] = first_pin + i

METER_OUT = {f"BCD_1E{d}_{w}": p for (d, w), p in BCD_PINS.items()}
METER_OUT.update({
    "POL_POS": 26,        # +ve polarity
    "POL_NEG": 27,        # -ve polarity (both 0 = AC / ohms)
    "FUNC_OUT_A": 28,     # function output code (28,29): 11 DC, 01 AC, 10 ohm, 00 check
    "FUNC_OUT_B": 29,
    "RANGE_OUT_4": 30,    # range output code
    "RANGE_OUT_2": 31,
    "RANGE_OUT_1": 32,
    "PRINT_PULSE": 33,    # 10-30 us high at end of measurement
    "PRINT_LEVEL": 34,    # high when the output data is valid
    "DATA_CAN_CHANGE": 35,
    "OVERLOAD": 36,
})
METER_GND_PIN = 37
# Inputs to the meter (TTL, '1' = +2.4..+5 V, '0' must sink 5 mA)
METER_IN = {
    "LOCKOUT_N": 38,      # 0 = front panel lockout (forces REMOTE)
    "SAMPLE_CONTACT": 39,  # contact closure to pin 37 starts a reading
    "SAMPLE_PULSE": 40,   # +3..+8 V pulse > 100 us starts a reading
    "RATIO_N": 41,        # 0 = ratio
    "FUNC_CMD_42": 42,    # function command (43,42): 11 DC, 01 AC, 10 ohm, 00 check
    "FUNC_CMD_43": 43,
    "INTEG_4": 44,        # integration time code (4,2,1)
    "INTEG_2": 45,
    "INTEG_1": 46,
    "AUTORANGE_INH": 47,  # 1 = commanded range, 0 = autorange
    "RANGE_CMD_1": 48,    # range command code (4,2,1 on 50,49,48)
    "RANGE_CMD_2": 49,
    "RANGE_CMD_4": 50,
}

meter = {name: Net(name) for name in list(METER_OUT) + list(METER_IN)}


# ---------------------------------------------------------------------------
# Sub-circuits
# ---------------------------------------------------------------------------
@subcircuit
def usb_input():
    """Vertical USB-B, polyfuse, ESD clamp, 3.3 V LDO."""
    j = Part("Connector", "USB_B", ref="J2", footprint="Connector_USB:USB_B_TE_5787834_Vertical")
    tag(j, "C592900", "5787834-1", "TE Connectivity")
    usb_dp, usb_dm = Net("USB_D+"), Net("USB_D-")
    shield = Net("USB_SHIELD")
    j["VBUS"] += vbus_raw
    j["D+"] += usb_dp
    j["D-"] += usb_dm
    j["GND"] += gnd
    j["Shield"] += shield

    # Shield to ground through 1M || 4.7 nF (keeps chassis/shield currents out of GND)
    r_sh, c_sh = R("1M"), C("4.7n")
    r_sh[1, 2] += shield, gnd
    c_sh[1, 2] += shield, gnd

    f = Part("Device", "Polyfuse", ref="F1", value="500mA", footprint="Fuse:Fuse_1206_3216Metric")
    tag(f, "C20799", "SMD1206P050TF", "RUILON")
    f[1, 2] += vbus_raw, vbus

    esd = Part("Power_Protection", "USBLC6-2SC6", ref="U3", footprint="Package_TO_SOT_SMD:SOT-23-6")
    tag(esd, "C7519", "USBLC6-2SC6", "STMicroelectronics")
    esd[1] += usb_dp
    esd[6] += usb_dp
    esd[3] += usb_dm
    esd[4] += usb_dm
    esd["VBUS"] += vbus
    esd["GND"] += gnd

    decouple(vbus, gnd, "10u")

    ldo = Part("Regulator_Linear", "AP2112K-3.3", ref="U2", footprint="Package_TO_SOT_SMD:SOT-23-5")
    tag(ldo, "C51118", "AP2112K-3.3TRG1", "Diodes Incorporated")
    ldo["VIN"] += vbus
    ldo["EN"] += vbus
    ldo["GND"] += gnd
    ldo["VOUT"] += v3v3
    ldo["NC"] += NC
    decouple(vbus, gnd, "1u")
    decouple(v3v3, gnd, "10u")

    # Host-side power LED
    led, r = LED("green"), R("1k")
    v3v3 & r & Net("LED_PWR_A") & led["A,K"] & gnd
    return usb_dp, usb_dm


@subcircuit
def mcu(usb_dp, usb_dm):
    """RP2354A (2 MB in-package flash) with crystal, core SMPS, USB, SWD, buttons."""
    u = Part("MCU_RaspberryPi", "RP2354A", ref="U1",
             footprint="Package_DFN_QFN:QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm_ThermalVias")
    tag(u, "C41378174", "RP2354A", "Raspberry Pi")

    dvdd = power_net("+1V1_DVDD")
    vreg_avdd = power_net("VREG_AVDD")  # 3V3 through a 33R / 4.7 uF filter

    # 3.3 V rails, one 100 nF per pin
    for p in u["IOVDD"]:
        p += v3v3
        decouple(v3v3, gnd, size="0402")
    for name in ("USB_OTP_VDD", "ADC_AVDD", "QSPI_IOVDD"):
        u[name] += v3v3
        decouple(v3v3, gnd, size="0402")
    u["GND"] += gnd

    # On-chip switching regulator: VREG_VIN -> VREG_LX -> 3.3 uH -> DVDD (1.1 V)
    u["VREG_VIN"] += v3v3
    decouple(v3v3, gnd, "4.7u", "0402")
    r_av = R("33", "0402")
    r_av[1, 2] += v3v3, vreg_avdd
    u["VREG_AVDD"] += vreg_avdd
    decouple(vreg_avdd, gnd, "4.7u", "0402")
    u["VREG_PGND"] += gnd
    l1 = Part("Device", "L", ref="L1", value="3.3uH", footprint="Inductor_SMD:L_Murata_DFE201610P")
    tag(l1, "C42411119", "AOTA-B201610S3R3-101-T", "Abracon")
    vreg_lx = Net("VREG_LX")
    u["VREG_LX"] += vreg_lx
    l1[1, 2] += vreg_lx, dvdd
    u["VREG_FB"] += dvdd
    decouple(dvdd, gnd, "4.7u", "0402")
    for p in u["DVDD"]:
        p += dvdd
        decouple(dvdd, gnd, size="0402")

    # 12 MHz crystal (RP2350 hardware design guide values: 15 pF loads, 1k series)
    y = Part("Device", "Crystal_GND24", ref="Y1", value="12MHz",
             footprint="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm")
    tag(y, "C20625731", "ABM8-272-T3", "Abracon")
    xin, xout, xout_r = Net("XIN"), Net("XOUT"), Net("XOUT_R")
    u["XIN"] += xin
    u["XOUT"] += xout
    r_x = R("1k", "0402")
    r_x[1, 2] += xout, xout_r
    y[1] += xin
    y[3] += xout_r
    y[2] += gnd
    y[4] += gnd
    for n in (xin, xout_r):
        c = C("15p", "0402")
        c[1, 2] += n, gnd

    # USB with 27R series resistors (RP2350 has the D+ pull-up on chip)
    for pin, net in (("USB_DP", usb_dp), ("USB_DM", usb_dm)):
        r = R("27", "0402")
        mcu_side = Net(f"MCU_{pin}")
        r[1, 2] += net, mcu_side
        u[pin] += mcu_side

    # RUN (reset) with pull-up and button; BOOTSEL on QSPI_SS
    run = Net("RUN")
    u["RUN"] += run
    r_run = R("10k", "0402")
    r_run[1, 2] += v3v3, run
    sw_run = Part("Switch", "SW_Push", ref="SW2", value="RESET",
                  footprint="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A")
    tag(sw_run, "C318884", "TS-1187A-B-A-B", "XKB Connection")
    sw_run[1, 2] += run, gnd

    qspi_ss, boot = Net("QSPI_SS"), Net("BOOTSEL")
    u[60] += qspi_ss  # ~QSPI_SS
    r_boot = R("1k", "0402")
    r_boot[1, 2] += qspi_ss, boot
    sw_boot = Part("Switch", "SW_Push", ref="SW1", value="BOOTSEL",
                   footprint="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A")
    tag(sw_boot, "C318884", "TS-1187A-B-A-B", "XKB Connection")
    sw_boot[1, 2] += boot, gnd
    # Flash is inside the RP2354A package: the QSPI data/clock pins stay unconnected.
    for name in ("QSPI_SD0", "QSPI_SD1", "QSPI_SD2", "QSPI_SD3", "QSPI_SCLK"):
        u[name] += NC

    # SWD debug header (Raspberry Pi 3-pin debug order: SWCLK, GND, SWDIO)
    swd = Part("Connector_Generic", "Conn_01x03", ref="J3", value="SWD",
               footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    tag(swd, "C2937625", "PZ254V-11-03P", "XFCN")
    swclk, swdio = Net("SWCLK"), Net("SWDIO")
    u["SWCLK"] += swclk
    u["SWDIO"] += swdio
    swd[1, 2, 3] += swclk, gnd, swdio

    # Isolated link on GPIO20-24 (one contiguous run of pins facing the
    # optocouplers): GPIO20/22/23 = SPI0 RX/SCK/TX, GPIO21 = LATCH, GPIO24 = /OE.
    # PIO can drive the same pins if hardware SPI timing is not wanted.
    u["GPIO20"] += mcu_miso
    u["GPIO21"] += mcu_latch
    u["GPIO22"] += mcu_sclk
    u["GPIO23"] += mcu_mosi
    u["GPIO24"] += mcu_oe_n

    # Status LED on GPIO5 (active high)
    led_net = Net("LED_STATUS")
    u["GPIO5"] += led_net
    led, r = LED("green"), R("1k", "0402")
    led_net & r & Net("LED_STATUS_A") & led["A,K"] & gnd

    used = {5, 20, 21, 22, 23, 24}
    for p in u.pins:
        if p.name.startswith("GPIO") and int(p.name[4:].split("/")[0]) not in used:
            p += NC


@subcircuit
def opto(ref, led_supply, led_r, led_drive, out_vdd, out_gnd, out_net):
    """TLP2361 15 MBd logic optocoupler (inverting, totem-pole output).

    The LED anode goes to its supply through led_r and the cathode is pulled
    low by the driving logic, so the overall path is non-inverting and an
    undriven input (MCU in reset) gives a HIGH output.
    """
    # KiCad has no TLP2361 symbol; the TLP2310 symbol has the identical SO6
    # (5-lead) pinout: 1 A, 3 K, 4 GND, 5 VO, 6 VCC.
    u = Part("Isolator", "TLP2310", ref=ref, value="TLP2361", footprint=FP_OPTO)
    tag(u, "C107626", "TLP2361(TPL,E", "Toshiba")
    anode = Net(f"{ref}_A")
    r = R(led_r)
    r[1, 2] += led_supply, anode
    u["A"] += anode
    u["K"] += led_drive
    u["VDD"] += out_vdd
    u["GND"] += out_gnd
    u["VO"] += out_net
    decouple(out_vdd, out_gnd)


@subcircuit
def isolated_power():
    """USB 5 V -> isolated 9 V (B0509S) -> 78L05 -> ISO_+5V for the meter side."""
    ps = Part("Converter_DCDC_Isolated", "MEE1S0509SC", ref="PS1", value="B0509S-1WR3",
              footprint="Converter_DCDC:Converter_DCDC_Murata_MEE1SxxxxSC_THT")
    tag(ps, "C7500906", "B0509S-1WR3", "EVISUN")
    ps["+Vin"] += vbus
    ps["-Vin"] += gnd
    ps["+Vout"] += iso_9v
    ps["-Vout"] += iso_gnd
    decouple(vbus, gnd, "4.7u")      # module datasheet: Cin 4.7 uF
    decouple(iso_9v, iso_gnd, "2.2u")  # module datasheet: Cout 2.2 uF (9 V)
    # Bleed resistor so the unregulated module sees roughly its 10 % minimum load
    r_min = R("2.2k")
    r_min[1, 2] += iso_9v, iso_gnd

    reg = Part("Regulator_Linear", "L78L05_SOT89", ref="U4", value="78L05",
               footprint="Package_TO_SOT_SMD:SOT-89-3")
    tag(reg, "C347258", "78L05 (SOT-89)", "UMW")
    reg["IN"] += iso_9v
    reg["GND"] += iso_gnd
    reg["OUT"] += iso_5v
    decouple(iso_9v, iso_gnd, "1u")
    decouple(iso_5v, iso_gnd, "10u")

    led, r = LED("green"), R("1k")
    iso_5v & r & Net("LED_ISO_PWR_A") & led["A,K"] & iso_gnd


@subcircuit
def input_shift_registers():
    """5 x 74HCT165 capturing the 36 meter outputs (plus 4 fixed check bits).

    Each register serves a group of physically adjacent connector pins (keeps
    the routing around the DD-50 short). Bit order on MISO after a LATCH pulse,
    MSB of each byte first (byte0 = U10, whose Q7 drives the MISO opto):
      byte0 U10: POL_POS POL_NEG FUNC_OUT_A FUNC_OUT_B RANGE_OUT_4 RANGE_OUT_2 RANGE_OUT_1 PRINT_PULSE
      byte1 U11: 10^3 digit (8 4 2 1), 10^2 digit (8 4 2 1)
      byte2 U12: 10^5 digit, 10^4 digit
      byte3 U13: 10^1 digit, 10^0 digit
      byte4 U14: PRINT_LEVEL DATA_CAN_CHANGE OVERLOAD BCD_1E6_1  1 0 1 0 (fixed check pattern)
    """
    one, zero = iso_5v, iso_gnd

    def digits(hi, lo):
        return [f"BCD_1E{hi}_{w}" for w in (8, 4, 2, 1)] + [f"BCD_1E{lo}_{w}" for w in (8, 4, 2, 1)]

    bytes_ = [
        ["POL_POS", "POL_NEG", "FUNC_OUT_A", "FUNC_OUT_B",
         "RANGE_OUT_4", "RANGE_OUT_2", "RANGE_OUT_1", "PRINT_PULSE"],
        digits(3, 2),
        digits(5, 4),
        digits(1, 0),
        ["PRINT_LEVEL", "DATA_CAN_CHANGE", "OVERLOAD", "BCD_1E6_1", one, zero, one, zero],
    ]

    # Series resistors (4-element arrays) between the connector and the 165 inputs:
    # ESD current limiting and limits back-feeding when only one side is powered.
    signals = [s for b in bytes_ for s in b if isinstance(s, str)]
    filtered = {}
    for i in range(0, len(signals), 4):
        rn = rn_tmpl(value="10k")
        tag(rn, "C29718", "4D03WGJ0103T5E", "UNI-ROYAL")
        for k, sig in enumerate(signals[i:i + 4]):
            filtered[sig] = Net(f"{sig}_R")
            rn[k + 1] += meter[sig]          # Rn.1
            rn[8 - k] += filtered[sig]       # Rn.2

    q7_prev = iso_miso_drive = Net("ISO_MISO_K")  # first register's Q7 sinks the MISO opto LED
    for idx, bits in enumerate(bytes_):
        u = Part("74xx", "74HC165", ref=f"U{10 + idx}", value="74HCT165", footprint=FP_SO16)
        tag(u, "C456131", "74HCT165D,653", "Nexperia")
        u["VCC"] += iso_5v
        u["GND"] += iso_gnd
        decouple(iso_5v, iso_gnd)
        u[1] += iso_latch  # ~PL
        u["CP"] += iso_sclk
        u[15] += iso_gnd  # ~CE
        u[7] += NC  # ~Q7
        u[9] += q7_prev  # Q7
        for k, sig in enumerate(bits):  # bits[0] -> D7 (shifted out first)
            u[f"D{7 - k}"] += filtered[sig] if isinstance(sig, str) else sig
        if idx == len(bytes_) - 1:
            u["DS"] += iso_gnd
        else:
            q7_prev = Net(f"SR165_CHAIN{idx + 1}")
            u["DS"] += q7_prev
    return iso_miso_drive


@subcircuit
def output_shift_registers():
    """2 x 74HC595 driving the 13 meter command inputs.

    Outputs are high-impedance until the MCU pulls /OE low; the meter's TTL
    inputs then float to '1', which is the meter's "nothing commanded" state.
    The last two bytes clocked in (of the 5 per transfer) land here:
      byte4 -> U15: QH..QA = AUTORANGE_INH INTEG_4 INTEG_2 INTEG_1 FUNC_CMD_43 FUNC_CMD_42 RATIO_N LOCKOUT_N
      byte3 -> U16: QH..QA = - - LED_REMOTE SAMPLE_CONTACT SAMPLE_PULSE RANGE_CMD_4 RANGE_CMD_2 RANGE_CMD_1
    """
    u15 = Part("74xx", "74HC595", ref="U15", footprint=FP_SO16)
    u16 = Part("74xx", "74HC595", ref="U16", footprint=FP_SO16)
    chain = Net("SR595_CHAIN")
    for u in (u15, u16):
        tag(u, "C5947", "74HC595D,118", "Nexperia")
        u["VCC"] += iso_5v
        u["GND"] += iso_gnd
        decouple(iso_5v, iso_gnd)
        u["SRCLK"] += iso_sclk
        u["RCLK"] += iso_latch
        u[13] += iso_oe_n  # ~OE
        u[10] += iso_5v  # ~SRCLR
    u15["SER"] += iso_mosi
    u15[9] += chain  # QH' (pin names with ' are mangled by SKiDL, so use the number)
    u16["SER"] += chain
    u16[9] += NC  # QH'

    u15["QA"] += meter["LOCKOUT_N"]
    u15["QB"] += meter["RATIO_N"]
    u15["QC"] += meter["FUNC_CMD_42"]
    u15["QD"] += meter["FUNC_CMD_43"]
    u15["QE"] += meter["INTEG_1"]
    u15["QF"] += meter["INTEG_2"]
    u15["QG"] += meter["INTEG_4"]
    u15["QH"] += meter["AUTORANGE_INH"]

    u16["QA"] += meter["RANGE_CMD_1"]
    u16["QB"] += meter["RANGE_CMD_2"]
    u16["QC"] += meter["RANGE_CMD_4"]
    u16["QD"] += meter["SAMPLE_PULSE"]

    # CONTACT SAMPLE needs a real closure to pin 37: small N-MOSFET, gate held
    # low by 100k while the 595 outputs are disabled.
    gate = Net("SAMPLE_CONTACT_DRV")
    u16["QE"] += gate
    q = Part("Transistor_FET", "2N7002", ref="Q1", footprint="Package_TO_SOT_SMD:SOT-23")
    tag(q, "C8545", "2N7002", "CJ")
    q["G"] += gate
    q["D"] += meter["SAMPLE_CONTACT"]
    q["S"] += iso_gnd
    r_g = R("100k")
    r_g[1, 2] += gate, iso_gnd

    # "Remote active" indicator on the meter side
    led_net = Net("LED_REMOTE")
    u16["QF"] += led_net
    led, r = LED("red"), R("1k")
    led_net & r & Net("LED_REMOTE_A") & led["A,K"] & iso_gnd
    u16["QG"] += NC
    u16["QH"] += NC


@subcircuit
def meter_connector():
    """DD-50 male, vertical, mounted on the underside so it plugs into SKB."""
    j = Part(LOCAL_LIB, "DD50_Pins_MountingHoles", ref="J1", value="DD-50 plug")
    tag(j, "C17502305", "D50P24A4PA00LF", "Amphenol ICC")
    for name, pin in list(METER_OUT.items()) + list(METER_IN.items()):
        j[pin] += meter[name]
    j[METER_GND_PIN] += iso_gnd
    j["SH"] += iso_gnd  # shell / jackscrew holes: meter earth


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------
def build():
    usb_dp, usb_dm = usb_input(tag="usb")
    mcu(usb_dp, usb_dm, tag="mcu")
    isolated_power(tag="iso_pwr")
    meter_connector(tag="meter")
    miso_drive = input_shift_registers(tag="sr_in")
    output_shift_registers(tag="sr_out")

    # Host -> meter: LED driven from 3.3 V by the RP2354A, detector on ISO_+5V.
    for ref, src, dst in (("U5", mcu_sclk, iso_sclk), ("U6", mcu_mosi, iso_mosi),
                          ("U7", mcu_latch, iso_latch), ("U8", mcu_oe_n, iso_oe_n)):
        opto(ref, v3v3, "390", src, iso_5v, iso_gnd, dst, tag=f"opto_{ref}")
    # Meter -> host: LED driven from ISO_+5V by the first 74HCT165, detector on +3V3.
    opto("U9", iso_5v, "820", miso_drive, v3v3, gnd, mcu_miso, tag="opto_U9")

    # Stable tags (=> stable timestamps/UUIDs when the netlist is re-imported).
    for part in builtins.default_circuit.parts:
        part.tag = part.ref


if __name__ == "__main__":
    build()
    ERC()
    generate_netlist(file_=str(OUT / "solartron_7075_interface.net"))
    # SKiDL drops its logs next to the script; keep them with the other outputs.
    for ext in (".erc", ".log"):
        log = HERE / f"solartron_7075_interface{ext}"
        if log.exists():
            log.replace(OUT / log.name)
    (HERE / "solartron_7075_interface_sklib.py").unlink(missing_ok=True)
    # SKiDL's KiCad 10 schematic generator is experimental: on this design it
    # draws some power symbols/labels touching other nets (KiCad ERC flags e.g.
    # +3V3 joined to +1V1_DVDD), so it is off by default. The netlist is the
    # source of truth for the PCB.
    if os.environ.get("SKIDL_SCH", "0") == "1":
        sch_dir = OUT / "schematic"
        sch_dir.mkdir(exist_ok=True)
        generate_schematic(filepath=str(sch_dir), top_name="solartron_7075_interface",
                           title="Solartron 7075 USB interface (SKiDL)", auto_stub=True)
        rpt = HERE / "solartron_7075_interface-erc.rpt"  # KiCad ERC log from the generator
        if rpt.exists():
            rpt.replace(sch_dir / rpt.name)
    if os.environ.get("SKIDL_PCB", "1") == "1":
        # kinet2pcb (used by generate_pcb) can't parse KiCad 10's quoted
        # fp-lib-table entries, so hand it the .pretty directories directly.
        generate_pcb(file_=str(OUT / "solartron_7075_interface_unplaced.kicad_pcb"), do_backup=False,
                     fp_libs=[str(HERE / "lib"), os.environ["KICAD10_FOOTPRINT_DIR"]])
