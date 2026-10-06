"""
Initial component placement for the Solartron 7075 USB interface board.

Run with atopile's Python after `ato build` has created the layout:

    ~/.local/share/uv/tools/atopile/bin/python scripts/place_components.py

Board: 78 x 60 mm, centred on the PCB origin (x right, y down).
  - y > 0 (south): isolated DVM side. The DD-50 plug is on the BOTTOM
    face (it plugs into the 7075's SKB socket); all other parts are on top.
  - y < 0 (north): USB side. The vertical USB-B is on the TOP face.
  - y = 0: isolation barrier, crossed only by the six TLP2361s and the
    IB0505LS DC-DC. Nothing else may come within BARRIER_HALF_GAP of it.

Footprints are matched by their `atopile_address` property, so re-running
after a design change keeps working.
"""

import math
import sys
from pathlib import Path

from faebryk.exporters.pcb.kicad.transformer import PCB_Transformer
from faebryk.libs.kicad.fileformats import kicad

LAYOUT = Path(__file__).resolve().parent.parent / "layouts/default/default.kicad_pcb"

BOARD_W, BOARD_H = 78.0, 60.0
BARRIER_HALF_GAP = 2.0

# --- DVM side --------------------------------------------------------------
DSUB_Y = 21.8
IC_ROW_Y = 11.5
IC_SLOTS_X = [25.8, 17.2, 8.6, 0.0, -8.6, -17.2, -25.8]

# address -> (x, y, rotation, layer)
P: dict[str, tuple[float, float, float, str]] = {
    "dvm.connector": (0.0, DSUB_Y, 0.0, "B.Cu"),
    # misc isolated-side parts, east end
    "drdy_buffer.package": (33.5, 6.5, 0.0, "F.Cu"),
    "drdy_buffer.decoupling": (33.5, 9.0, 0.0, "F.Cu"),
    "sample_fet": (34.0, 13.0, 0.0, "F.Cu"),
    "sample_fet_pulldown": (36.5, 13.0, 90.0, "F.Cu"),
    "oe_pullup": (-31.5, 3.8, 0.0, "F.Cu"),
    "iso_power_led.package": (36.0, 17.0, 90.0, "F.Cu"),
    "iso_power_led_resistor": (33.5, 17.0, 90.0, "F.Cu"),
    # isolated DC-DC on the west edge, straddling the barrier
    # (pins 1/2 at y = -5.08/-2.54, pins 4/6 at y = +2.54/+7.62)
    "iso_supply.converter": (-34.0, 1.27, 270.0, "F.Cu"),
    "iso_supply.input_capacitor": (-30.9, -6.0, 90.0, "F.Cu"),
    "iso_supply.output_capacitor": (-30.9, 7.5, 90.0, "F.Cu"),
    # --- USB side --------------------------------------------------------
    "usb_in.connector": (-26.0, -21.0, 0.0, "F.Cu"),
    "usb_in.esd": (-16.5, -17.5, 0.0, "F.Cu"),
    "usb_in.fuse": (-16.5, -13.0, 0.0, "F.Cu"),
    "usb_in.bulk": (-21.0, -12.0, 0.0, "F.Cu"),
    "ldo.package": (-12.0, -25.0, 0.0, "F.Cu"),
    "ldo.input_decoupling_capacitor": (-14.6, -25.0, 90.0, "F.Cu"),
    "ldo.output_decoupling_capacitor": (-9.4, -25.0, 90.0, "F.Cu"),
    "ldo.feedback_divider.chain.resistors[0]": (-12.5, -22.3, 0.0, "F.Cu"),
    "ldo.feedback_divider.chain.resistors[1]": (-12.5, -27.6, 0.0, "F.Cu"),
    # MCU (QFN-60, pins 46-60 face north, 16-30 south, 1-15 west, 31-45 east)
    "mcu.package": (4.0, -17.0, 0.0, "F.Cu"),
    "mcu.vreg_inductor": (7.5, -23.0, 0.0, "F.Cu"),
    "mcu.vreg_cin": (5.0, -23.0, 90.0, "F.Cu"),
    "mcu.vreg_cout": (10.0, -23.0, 90.0, "F.Cu"),
    "mcu.vreg_avdd_r": (7.5, -25.0, 0.0, "F.Cu"),
    "mcu.vreg_avdd_c": (10.0, -25.0, 0.0, "F.Cu"),
    "mcu.usb_series_r[0]": (2.6, -23.0, 90.0, "F.Cu"),
    "mcu.usb_series_r[1]": (1.4, -23.0, 90.0, "F.Cu"),
    "mcu.bulk": (-4.2, -23.0, 90.0, "F.Cu"),
    "mcu.io_decoupling[0]": (-1.5, -19.5, 90.0, "F.Cu"),
    "mcu.io_decoupling[1]": (-1.5, -17.0, 90.0, "F.Cu"),
    "mcu.io_decoupling[2]": (-1.5, -14.5, 90.0, "F.Cu"),
    "mcu.io_decoupling[3]": (1.5, -11.5, 0.0, "F.Cu"),
    "mcu.io_decoupling[4]": (6.5, -11.5, 0.0, "F.Cu"),
    "mcu.io_decoupling[5]": (9.5, -14.5, 90.0, "F.Cu"),
    "mcu.io_decoupling[6]": (9.5, -19.5, 90.0, "F.Cu"),
    "mcu.io_decoupling[7]": (-0.2, -23.0, 90.0, "F.Cu"),
    "mcu.io_decoupling[8]": (-1.6, -23.0, 90.0, "F.Cu"),
    "mcu.core_decoupling[0]": (-3.0, -17.0, 90.0, "F.Cu"),
    "mcu.core_decoupling[1]": (4.0, -11.5, 0.0, "F.Cu"),
    "mcu.core_decoupling[2]": (11.0, -17.0, 90.0, "F.Cu"),
    "mcu.crystal": (-5.5, -11.0, 0.0, "F.Cu"),
    "mcu.crystal_load[0]": (-8.5, -11.0, 90.0, "F.Cu"),
    "mcu.crystal_load[1]": (-2.5, -11.0, 90.0, "F.Cu"),
    "mcu.crystal_series_r": (-5.5, -7.8, 0.0, "F.Cu"),
    "mcu.bootsel_button.package": (21.0, -26.0, 0.0, "F.Cu"),
    "mcu.reset_button.package": (28.0, -26.0, 0.0, "F.Cu"),
    "mcu.bootsel_r": (16.5, -21.0, 90.0, "F.Cu"),
    "mcu.run_pullup": (15.0, -17.0, 90.0, "F.Cu"),
    "swd_header.connector": (21.0, -19.0, 0.0, "F.Cu"),
    "power_led.package": (33.0, -21.0, 90.0, "F.Cu"),
    "power_led_resistor": (33.0, -18.0, 90.0, "F.Cu"),
    "status_led.package": (35.5, -21.0, 90.0, "F.Cu"),
    "status_led_resistor": (35.5, -18.0, 90.0, "F.Cu"),
}

# Opto row on the barrier. TX: LED (pins 1/3) north; RX: LED south.
OPTOS = [
    ("opto_oe_n", -22.0, "tx"),
    ("opto_mosi", -14.0, "tx"),
    ("opto_latch", -6.0, "tx"),
    ("opto_sck", 2.0, "tx"),
    ("opto_miso", 10.0, "rx"),
    ("opto_drdy", 18.0, "rx"),
]
for name, x, kind in OPTOS:
    north, south = (-3.2, 3.2)
    if kind == "tx":
        P[f"{name}.opto"] = (x, 0.0, 90.0, "F.Cu")
        P[f"{name}.led_resistor"] = (x - 3.4, north, 90.0, "F.Cu")
        P[f"{name}.bypass"] = (x - 3.4, south, 90.0, "F.Cu")
    else:
        P[f"{name}.opto"] = (x, 0.0, 270.0, "F.Cu")
        P[f"{name}.led_resistor"] = (x - 3.4, south, 90.0, "F.Cu")
        P[f"{name}.bypass"] = (x - 3.4, north, 90.0, "F.Cu")


def props(fp) -> dict[str, str]:
    return {p.name: p.value for p in fp.propertys}


def pad_abs(fp, pad) -> tuple[float, float]:
    """Absolute pad centre (KiCad rotates footprints counter-clockwise)."""
    a = math.radians(fp.at.r or 0)
    x, y = pad.at.x, pad.at.y
    return (
        fp.at.x + x * math.cos(a) + y * math.sin(a),
        fp.at.y - x * math.sin(a) + y * math.cos(a),
    )


ZONE_NAMES = ("pour_GND", "pour_GND_ISO", "isolation_barrier")


def _zone(net_number, net_name, name, rect, keepout=False):
    x0, y0, x1, y1 = rect
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    na = kicad.pcb.E_zone_keepout.NOT_ALLOWED
    ok = kicad.pcb.E_zone_keepout.ALLOWED
    return kicad.pcb.Zone(
        net=net_number,
        net_name=net_name,
        layers=["F.Cu", "B.Cu"],
        layer=None,
        uuid=kicad.gen_uuid(""),
        name=name,
        polygon=kicad.pcb.Polygon(
            pts=kicad.pcb.Pts(xys=[kicad.pcb.Xy(x=x, y=y) for x, y in pts]),
            layers=[],
            layer=None,
            solder_mask_margin=None,
            stroke=None,
            fill=None,
            locked=None,
            uuid=kicad.gen_uuid(""),
        ),
        min_thickness=0.2,
        filled_areas_thickness=False,
        fill=kicad.pcb.ZoneFill(
            enable=kicad.pcb.E_zone_fill_enable.YES,
            mode=None,
            hatch_thickness=0.0,
            hatch_gap=0.5,
            hatch_orientation=0,
            hatch_smoothing_level=0,
            hatch_smoothing_value=0,
            hatch_border_algorithm=kicad.pcb.E_zone_hatch_border_algorithm.HATCH_THICKNESS,
            hatch_min_hole_area=0.3,
            thermal_gap=0.3,
            thermal_bridge_width=0.3,
            smoothing=None,
            radius=1,
            island_area_min=10.0,
            arc_segments=None,
            island_removal_mode=None,
        ),
        hatch=kicad.pcb.Hatch(mode=kicad.pcb.E_zone_hatch_mode.EDGE, pitch=0.5),
        priority=0,
        keepout=kicad.pcb.ZoneKeepout(
            tracks=na, vias=na, pads=ok, copperpour=na, footprints=ok
        )
        if keepout
        else None,
        connect_pads=kicad.pcb.ConnectPads(mode=None, clearance=0.3),
        filled_polygon=[],
        placement=None,
        attr=None,
    )


def add_zones(pcb) -> None:
    """GND pour on the USB half, GND_ISO pour on the DVM half (both layers),
    and a no-copper keep-out strip along the isolation barrier."""
    kicad.filter(pcb, "zones", pcb.zones, lambda z: z.name not in ZONE_NAMES)
    nets = {n.name: n.number for n in pcb.nets}
    e = 0.5  # pull-back from the board edge
    w, h = BOARD_W / 2 - e, BOARD_H / 2 - e
    pour_gap = BARRIER_HALF_GAP + 0.5
    for z in (
        _zone(nets["GND"], "GND", "pour_GND", (-w, -h, w, -pour_gap)),
        _zone(nets["GND_ISO"], "GND_ISO", "pour_GND_ISO", (-w, pour_gap, w, h)),
        _zone(
            0, "", "isolation_barrier",
            (-BOARD_W / 2, -BARRIER_HALF_GAP + 0.4, BOARD_W / 2, BARRIER_HALF_GAP - 0.4),
            keepout=True,
        ),
    ):
        kicad.insert(pcb, "zones", pcb.zones, z)


def main() -> int:
    pcb_file = kicad.loads(kicad.pcb.PcbFile, LAYOUT)
    pcb = pcb_file.kicad_pcb
    by_addr = {props(fp).get("atopile_address", ""): fp for fp in pcb.footprints}

    # Shift registers: order the IC slots by where their SKB pins land so the
    # traces to the DD-50 stay short. (Pins are mirrored: DD-50 is on B.Cu.)
    dsub_local_x = {
        p.name: p.at.x for p in by_addr["dvm.connector"].pads if p.name.isdigit()
    }
    ic_pins = {f"shift_in[{c}].package": range(8 * c + 1, min(8 * c + 9, 37)) for c in range(5)}
    ic_pins["shift_out[0].package"] = [38, 39, 40, 41, 42, 43, 44, 45]
    ic_pins["shift_out[1].package"] = [46, 47, 48, 49, 50]
    centroid = {
        ic: sum(-dsub_local_x[str(n)] for n in pins) / len(pins)
        for ic, pins in ic_pins.items()
    }
    for ic, slot_x in zip(sorted(centroid, key=centroid.get, reverse=True), IC_SLOTS_X):
        P[ic] = (slot_x, IC_ROW_Y, 90.0, "F.Cu")
        P[ic.replace(".package", ".decoupling")] = (slot_x, IC_ROW_Y - 6.4, 0.0, "F.Cu")

    missing = [a for a in P if a not in by_addr]
    unplaced = [a for a in by_addr if a and a not in P]
    if missing or unplaced:
        print("missing footprints:", missing, "\nunplaced footprints:", unplaced)
        return 1

    for addr, (x, y, r, layer) in P.items():
        PCB_Transformer.move_fp(by_addr[addr], kicad.pcb.Xyr(x=x, y=y, r=r), layer)

    add_zones(pcb)

    kicad.dumps(pcb_file, LAYOUT)
    print(f"placed {len(P)} footprints -> {LAYOUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
