#!/usr/bin/env python3
"""
Export a PDF schematic of the atopile design.

atopile 0.15 has no schematic output (the .ato code *is* the schematic), so
this script builds a KiCad schematic from what `ato build` does produce:

  * netlist, references, footprints  layouts/default/default.kicad_pcb
  * values / part numbers            build/builds/default/default.bom.csv
  * symbols                          the .kicad_sym atopile stored next to
                                     each part (parts/ or .ato/modules/)

One sheet is generated per subsystem. Every pin gets a short wire and a
(global) net label - atopile net names are unique, and KiCad draws local
labels above the wire where they collide on 2.54 mm pin pitch - unused pins
get a no-connect flag, and each atopile module instance is boxed and titled
with its address. The schematic is then plotted with kicad-cli, and its
netlist is exported back out and compared against the PCB netlist so the
PDF is guaranteed to match the design.

Usage (from the atopile/ directory, after `ato build`):

    python3 scripts/export_schematic.py            # -> schematic/*.kicad_sch + PDF
    python3 scripts/export_schematic.py --no-pdf   # schematic files only

Requires Python 3.10+ and kicad-cli (KiCad 9 or 10).
"""

import argparse
import csv
import datetime
import math
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "layouts/default/default.kicad_pcb"
BOM = ROOT / "build/builds/default/default.bom.csv"
OUT_DIR = ROOT / "schematic"
PROJECT = "solartron_7075_usb"
TITLE = "Solartron 7075 USB interface"

# (file stem, sheet title, address prefixes, note)
SHEETS = [
    (
        "power_usb",
        "USB input and power",
        ("usb_in", "ldo", "iso_supply", "power_led", "iso_power_led"),
        "USB-B -> 500 mA PTC + USBLC6 ESD -> +5V.\n"
        "+5V -> TLV75901 (100k/20k feedback) -> +3V3.\n"
        "+5V -> IB0505LS-1WR3 isolated DC-DC -> +5V_ISO / GND_ISO (DVM side).",
    ),
    (
        "mcu",
        "RP2354A",
        ("mcu", "swd_header", "status_led"),
        "RP2354A (2 MB in-package flash). Core regulator per RP2350 datasheet:\n"
        "3.3 uH polarity-marked inductor, 4.7 uF CIN/COUT, 33R + 4.7 uF on VREG_AVDD.\n"
        "GPIO16 MISO, GPIO17 LATCH, GPIO18 SCK, GPIO19 MOSI, GPIO20 OE_N, GPIO21 DRDY, GPIO25 status LED.",
    ),
    (
        "isolation",
        "Isolation barrier",
        ("opto_",),
        "Six non-inverting TLP2361 channels. The LED cathode is driven by the source,\n"
        "the anode is fed through 330R (3.3 V side) or 680R (5 V side), ~4.5 mA.\n"
        "Undriven inputs leave the outputs HIGH (OE_N_ISO high = 595 outputs Hi-Z).",
    ),
    (
        "dvm",
        "Solartron SKB interface",
        ("dvm", "shift_in", "shift_out", "drdy_buffer", "sample_fet", "oe_pullup"),
        "SKB pins 1-36 -> 5x 74HCT165 (frame bit k = SKB pin k+1, then 1010 signature).\n"
        "2x 74HCT595 -> SKB 38, 40-50; 2N7002 contact-closure SAMPLE on SKB 39.\n"
        "SKB 37 = DVM earth / logic 0 = GND_ISO. See README.md for the bit map.",
    ),
]

PAPERS = [("A4", 297.0, 210.0), ("A3", 420.0, 297.0), ("A2", 594.0, 420.0), ("A1", 841.0, 594.0)]
# Electrical pin types for ERC. atopile's EasyEDA-derived symbols type every
# pin "input" (passives) or "unspecified" (ICs), which makes KiCad's ERC
# meaningless; these follow the datasheets. Unlisted parts are all-passive.
PIN_TYPES = {
    "Raspberry_Pi_RP2354A": [
        (r"IOVDD|DVDD|ADC_AVDD|QSPI_IOVDD|USB_OTP_VDD|VREG_VIN|VREG_AVDD|VREG_PGND|EP", "power_in"),
        (r"VREG_LX", "power_out"),
        (r"VREG_FB|RUN|SWCLK|XIN", "input"),
        (r"XOUT", "output"),
        (r".*", "bidirectional"),  # GPIO, QSPI, USB_DP/DM, SWDIO
    ],
    "Texas_Instruments_TLV75901PDRVR": [
        (r"IN|GND|EP", "power_in"), (r"OUT", "power_out"), (r"EN|FB", "input"), (r"DNC", "no_connect"),
    ],
    # isolated DC-DC: both output terminals source the isolated domain
    "YLPTEC_IB0505LS_1WR3": [(r"VIN|GND", "power_in"), (r"\+Vo|0V", "power_out")],
    "TOSHIBA_TLP2361_TPL_E": [(r"VCC|GND", "power_in"), (r"VO", "output"), (r".*", "passive")],
    "Texas_Instruments_CD74HCT165M96": [(r"VCC|GND", "power_in"), (r"#?Q7", "output"), (r".*", "input")],
    "Nexperia_74HCT595D_118": [
        (r"VCC|GND", "power_in"), (r"Q7S", "output"), (r"Q\d", "tri_state"), (r".*", "input"),
    ],
    "Texas_Instruments_SN74AHCT1G125DBVR": [(r"VCC|GND", "power_in"), (r"Y", "tri_state"), (r".*", "input")],
}

# Nets that are powered through a passive part (connector, fuse, inductor,
# RC filter) get a PWR_FLAG so ERC knows they are driven. Any other power
# net without a power_out pin is reported as a real ERC error.
PWR_FLAGS = [
    ("GND", "power_usb"),        # USB connector ground
    ("+5V", "power_usb"),        # USB VBUS through the PTC fuse
    ("+1V1", "mcu"),             # RP2354A core regulator through L1
    ("VREG_AVDD", "mcu"),        # 33R / 4.7 uF filter from +3V3
]

PWR_FLAG_SYMBOL = """(symbol "power:PWR_FLAG" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))
  (exclude_from_sim no) (in_bom yes) (on_board yes)
  (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Description" "Special symbol for telling ERC where power comes from" (at 0 0 0)
    (effects (font (size 1.27 1.27)) (hide yes)))
  (symbol "PWR_FLAG_0_0"
    (pin power_out line (at 0 0 90) (length 0)
      (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
  (symbol "PWR_FLAG_0_1"
    (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27))
      (stroke (width 0) (type default)) (fill (type none)))))"""

GRID = 1.27
STUB = 2.54
FONT = 1.27
CHAR_W = 1.05  # approx. width of one label character at 1.27 mm
MARGIN = 16.0
TITLE_BLOCK_H = 40.0


# --------------------------------------------------------------------------
# S-expressions
# --------------------------------------------------------------------------
class Str(str):
    """A quoted string atom."""


_TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse(text: str):
    stack = [[]]
    for m in _TOK.finditer(text):
        if m.group(1):
            stack.append([])
        elif m.group(2):
            node = stack.pop()
            stack[-1].append(node)
        elif m.group(3) is not None:
            stack[-1].append(Str(m.group(3).replace('\\"', '"').replace("\\\\", "\\")))
        elif m.group(4) is not None:
            stack[-1].append(m.group(4))
    return stack[0][0]


def q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def dump(node, indent=0) -> str:
    if not isinstance(node, list):
        return q(node) if isinstance(node, Str) else str(node)
    if not any(isinstance(c, list) for c in node):
        return "(" + " ".join(dump(c) for c in node) + ")"
    pad = "\t" * (indent + 1)
    head = [dump(c) for c in node if not isinstance(c, list)]
    body = [pad + dump(c, indent + 1) for c in node if isinstance(c, list)]
    return "(" + " ".join(head) + "\n" + "\n".join(body) + "\n" + "\t" * indent + ")"


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


def walk(node):
    yield node
    for c in node:
        if isinstance(c, list):
            yield from walk(c)


def fmt(v: float) -> str:
    return f"{round(v, 4):g}"


_UUID_NS = uuid.UUID("6f1e6b52-6d3a-4f0e-9d5c-7a0c8a5e2b11")


def uid(*parts) -> str:
    """Deterministic UUIDs so regenerated files diff cleanly."""
    return str(uuid.uuid5(_UUID_NS, "/".join(map(str, parts))))


def snap(v: float) -> float:
    return round(v / GRID) * GRID


# --------------------------------------------------------------------------
# Design data
# --------------------------------------------------------------------------
def load_pcb():
    pcb = parse(PCB.read_text(encoding="utf-8"))
    parts = []
    for fp in find(pcb, "footprint"):
        props = {p[1]: p[2] for p in find(fp, "property")}
        lib, fpname = fp[1].split(":", 1)
        pads = {}
        for pad in find(fp, "pad"):
            net = first(pad, "net")
            if pad[1]:
                pads.setdefault(str(pad[1]), net[-1] if net else None)
        parts.append(
            {
                "ref": props["Reference"],
                "addr": props.get("atopile_address", ""),
                "lib": lib,
                "footprint": fp[1],
                "lcsc": props.get("LCSC", ""),
                "mpn": props.get("Partnumber", ""),
                "pads": pads,
            }
        )
    return parts


def load_bom_values():
    values = {}
    if not BOM.exists():
        return values
    with BOM.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for ref in row["Designator"].split(","):
                values[ref.strip()] = row["Value"] or row["Partnumber"]
    return values


def part_dir(lib: str) -> Path:
    """Where atopile keeps a part's symbol/footprint (project or library)."""
    for base in [ROOT / "parts", *sorted((ROOT / ".ato/modules").glob("*/*/parts"))]:
        if sorted((base / lib).glob("*.kicad_sym")):
            return base / lib
    raise FileNotFoundError(f"no symbol for {lib} (run `ato build` / `ato sync` first)")


def find_symbol_file(lib: str) -> Path:
    return sorted(part_dir(lib).glob("*.kicad_sym"))[0]


def pin_type(lib: str, pin_name: str) -> str:
    for pattern, ptype in PIN_TYPES.get(lib, [(r".*", "passive")]):
        if re.fullmatch(pattern, pin_name):
            return ptype
    raise ValueError(f"no pin type for {lib} pin {pin_name}")


class Symbol:
    """A library symbol, its pins and its graphical extent (schematic coords)."""

    def __init__(self, lib: str, tree=None):
        if tree is None:
            sym = find(parse(find_symbol_file(lib).read_text(encoding="utf-8")), "symbol")[0]
        else:
            sym = tree
        # atopile's EasyEDA converter writes circles as (center ..)(end ..),
        # which KiCad rejects; KiCad wants (center ..)(radius ..).
        for node in walk(sym):
            if node[0] == "circle" and first(node, "end") and not first(node, "radius"):
                c, e = first(node, "center"), first(node, "end")
                r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
                node[node.index(e)] = ["radius", fmt(r)]
        if tree is None:
            for node in walk(sym):
                if node[0] == "pin" and first(node, "name"):
                    node[1] = pin_type(lib, str(first(node, "name")[1]))
        self.lib = lib
        self.name = str(sym[1]).split(":")[-1]
        self.lib_id = f"{lib}:{self.name}"
        sym[1] = Str(self.lib_id)
        self.tree = sym
        self.reference_prefix = next(
            (p[2] for p in find(sym, "property") if p[1] == "Reference"), "U"
        )
        self.datasheet = next(
            (p[2] for p in find(sym, "property") if p[1] == "Datasheet"), ""
        )
        self.pins = []  # (number, name, x, y, dx, dy) schematic offsets / outward dir
        pts = []
        for node in walk(sym):
            if node[0] == "pin" and first(node, "at"):
                at = first(node, "at")
                x, y = float(at[1]), float(at[2])
                a = math.radians(float(at[3]) if len(at) > 3 else 0.0)
                length = float(first(node, "length")[1])
                num = str(first(node, "number")[1])
                nm = str(first(node, "name")[1])
                dx, dy = -round(math.cos(a)), round(math.sin(a))
                self.pins.append((num, nm, x, -y, dx, dy))
                pts += [(x, -y), (x - dx * length, -y - dy * length)]
            elif node[0] in ("rectangle",):
                for k in ("start", "end"):
                    p = first(node, k)
                    pts.append((float(p[1]), -float(p[2])))
            elif node[0] in ("polyline", "bezier"):
                for xy in find(first(node, "pts"), "xy"):
                    pts.append((float(xy[1]), -float(xy[2])))
            elif node[0] == "arc":
                for k in ("start", "mid", "end"):
                    p = first(node, k)
                    if p:
                        pts.append((float(p[1]), -float(p[2])))
            elif node[0] == "circle":
                c = first(node, "center")
                cx, cy = float(c[1]), -float(c[2])
                if first(node, "radius"):
                    r = float(first(node, "radius")[1])
                else:  # (circle (center ..) (end ..)) form
                    e = first(node, "end")
                    r = math.hypot(float(e[1]) - cx, -float(e[2]) - cy)
                pts += [(cx - r, cy - r), (cx + r, cy + r)]
        xs, ys = zip(*pts)
        self.bbox = (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def label_len(text: str) -> float:
    return len(text) * CHAR_W + 3.0  # text + global-label outline


def component_extent(c):
    """Box (relative to symbol origin) covering symbol, stubs, labels, fields."""
    x0, y0, x1, y1 = c["sym"].bbox
    for num, _, px, py, dx, dy in c["sym"].pins:
        net = c["pin_nets"].get(num)
        if not net:
            continue
        ln = STUB + label_len(net)
        ex, ey = px + dx * ln, py + dy * ln
        x0, y0, x1, y1 = min(x0, ex, px), min(y0, ey - 1, py), max(x1, ex, px), max(y1, ey + 1, py)
    fields_w = max(len(c["ref"]) + 2, len(c["value"]), len(c["addr"]) * 0.8) * CHAR_W
    x1 = max(x1, x0 + fields_w)
    return x0, y0 - 4.0, x1, y1 + 7.5


def pack(items, max_w, gap):
    """Shelf-pack (w, h) items; returns positions and the used size."""
    x = y = row_h = used_w = 0.0
    pos = []
    for w, h in items:
        if x > 0 and x + w > max_w:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        pos.append((x, y))
        x += w + gap
        row_h = max(row_h, h)
        used_w = max(used_w, x - gap)
    return pos, used_w, y + row_h


def pack_blocks(sizes, max_w, gap):
    """Pack group blocks: plain shelves, or the tallest block in a left column
    with the rest shelf-packed beside it - whichever is shorter."""
    pos, _, h = pack(sizes, max_w, gap)
    best = (h, pos)
    w0, h0 = sizes[0]
    if len(sizes) > 1 and w0 + gap < max_w:
        rest, _, rest_h = pack(sizes[1:], max_w - w0 - gap, gap)
        if all(w <= max_w - w0 - gap for w, _ in sizes[1:]):
            col_h = max(h0, rest_h)
            if col_h < best[0]:
                best = (col_h, [(0.0, 0.0)] + [(x + w0 + gap, y) for x, y in rest])
    return best[1], best[0]


def group_key(addr: str) -> str:
    head = addr.split(".")[0]
    # keep the MCU's helpers together by their own sub-block
    if head == "mcu":
        sub = addr.split(".")[1] if "." in addr else ""
        for key, members in (
            ("mcu (core regulator)", ("vreg_",)),
            ("mcu (decoupling)", ("io_decoupling", "core_decoupling", "bulk")),
            ("mcu (crystal)", ("crystal",)),
            ("mcu (USB)", ("usb_series",)),
            ("mcu (boot / reset)", ("bootsel", "reset", "run_")),
        ):
            if sub.startswith(members):
                return key
        return "mcu"
    if head.startswith(("power_led", "status_led", "iso_power_led", "sample_fet")):
        return head.replace("_resistor", "").replace("_pulldown", "")
    return head


# --------------------------------------------------------------------------
# Schematic writer
# --------------------------------------------------------------------------
def effects(size=FONT, justify=None, hide=False):
    e = ["effects", ["font", ["size", fmt(size), fmt(size)]]]
    if justify:
        e.append(["justify", *justify.split()])
    if hide:
        e.append(["hide", "yes"])
    return e


def prop(name, value, x, y, size=FONT, justify="left", hide=False, angle=0):
    return [
        "property", Str(name), Str(value), ["at", fmt(x), fmt(y), fmt(angle)],
        effects(size, justify, hide),
    ]


def title_block(sheet_title: str):
    return [
        "title_block",
        ["title", Str(f"{TITLE} - {sheet_title}")],
        ["date", Str(datetime.date.today().isoformat())],
        ["rev", Str("A")],
        ["company", Str("atopile design (../*.ato)")],
        ["comment", "1", Str("Auto-generated from the atopile netlist by scripts/export_schematic.py")],
        ["comment", "2", Str("The .ato files are the source of truth - do not edit this schematic")],
    ]


def build_sheet(stem, title, note, comps, root_uuid, sheet_uuid):
    comps = sorted(comps, key=lambda c: (group_key(c["addr"]), -len(c["sym"].pins), c["addr"]))
    groups = defaultdict(list)
    for c in comps:
        c["extent"] = component_extent(c)
        groups[group_key(c["addr"])].append(c)

    def group_order(item):
        name, members = item
        return (-max(len(m["sym"].pins) for m in members), name)

    group_list = sorted(groups.items(), key=group_order)

    for paper, pw, ph in PAPERS:
        usable_w = pw - 2 * MARGIN
        blocks = []
        for name, members in group_list:
            sizes = [(m["extent"][2] - m["extent"][0], m["extent"][3] - m["extent"][1]) for m in members]
            area = sum(w * h for w, h in sizes)
            inner_w = min(usable_w - 6, max(max(w for w, _ in sizes), math.sqrt(area) * 1.7))
            pos, w, h = pack(sizes, inner_w, 5.0)
            blocks.append((name, members, pos, w + 6, h + 10))
        blocks.sort(key=lambda b: -b[4])  # tallest first packs shelves tighter
        note_h = 3.0 * (note.count("\n") + 1) + 8
        bpos, bh = pack_blocks([(w, h) for *_, w, h in blocks], usable_w, 6.0)
        if MARGIN + note_h + bh <= ph - MARGIN - TITLE_BLOCK_H:
            break

    items = []
    ox, oy = MARGIN, MARGIN + note_h
    items.append([
        "text", Str(note), ["exclude_from_sim", "no"],
        ["at", fmt(MARGIN), fmt(MARGIN), "0"], effects(2.0, "left top"), ["uuid", Str(uid(stem, "note"))],
    ])
    symbols, lib_symbols = [], {}
    for (name, members, pos, w, h), (bx, by) in zip(blocks, bpos):
        gx, gy = ox + bx, oy + by
        items.append([
            "rectangle", ["start", fmt(gx), fmt(gy)], ["end", fmt(gx + w), fmt(gy + h)],
            ["stroke", ["width", "0"], ["type", "dash"]], ["fill", ["type", "none"]],
            ["uuid", Str(uid(stem, "box", name))],
        ])
        items.append([
            "text", Str(name), ["exclude_from_sim", "no"], ["at", fmt(gx + 1.5), fmt(gy + 1.5), "0"],
            effects(1.8, "left top"), ["uuid", Str(uid(stem, "boxlabel", name))],
        ])
        for m, (mx, my) in zip(members, pos):
            ex0, ey0, ex1, ey1 = m["extent"]
            X = snap(gx + 3 + mx - ex0)
            Y = snap(gy + 7 + my - ey0)
            sym = m["sym"]
            lib_symbols[sym.lib_id] = sym.tree
            sx0, sy0, sx1, sy1 = sym.bbox
            ref, addr = m["ref"], m["addr"]
            inst = [
                "symbol", ["lib_id", Str(sym.lib_id)], ["at", fmt(X), fmt(Y), "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if m["in_bom"] else "no"],
                ["on_board", "yes"], ["dnp", "no"], ["uuid", Str(uid(stem, "sym", ref))],
                prop("Reference", ref, X + sx0, Y + sy0 - 1.5, 1.4),
                prop("Value", m["value"], X + sx0, Y + sy1 + 2.5),
                prop("Footprint", m["footprint"], X, Y, hide=True),
                prop("Datasheet", sym.datasheet, X, Y, hide=True),
                prop("Description", "", X, Y, hide=True),
                prop("LCSC", m["lcsc"], X, Y, hide=True),
                prop("ato_address", addr, X + sx0, Y + sy1 + 5.0, 1.0),
            ]
            for num, *_ in sym.pins:
                inst.append(["pin", Str(num), ["uuid", Str(uid(stem, "pin", ref, num))]])
            inst.append([
                "instances",
                ["project", Str(PROJECT),
                 ["path", Str(f"/{root_uuid}/{sheet_uuid}"), ["reference", Str(ref)], ["unit", "1"]]],
            ])
            symbols.append(inst)

            for num, _, px, py, dx, dy in sym.pins:
                cx, cy = X + px, Y + py
                net = m["pin_nets"].get(num)
                key = (ref, num, cx, cy)
                if not net:
                    items.append(["no_connect", ["at", fmt(cx), fmt(cy)], ["uuid", Str(uid(stem, "nc", *key))]])
                    continue
                lx, ly = cx + dx * STUB, cy + dy * STUB
                items.append([
                    "wire", ["pts", ["xy", fmt(cx), fmt(cy)], ["xy", fmt(lx), fmt(ly)]],
                    ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Str(uid(stem, "w", *key))],
                ])
                angle, just = {(1, 0): (0, "left"), (-1, 0): (180, "right"),
                               (0, -1): (90, "left"), (0, 1): (270, "right")}[(dx, dy)]
                items.append([
                    "global_label", Str(net), ["shape", "passive"], ["at", fmt(lx), fmt(ly), str(angle)],
                    ["fields_autoplaced", "yes"], effects(FONT, just), ["uuid", Str(uid(stem, "gl", *key))],
                    prop("Intersheetrefs", "${INTERSHEET_REFS}", lx, ly, hide=True),
                ])

    sch = [
        "kicad_sch", ["version", "20250114"], ["generator", Str("export_schematic.py")],
        ["generator_version", Str("9.0")], ["uuid", Str(uid(stem, "file"))], ["paper", Str(paper)],
        title_block(title), ["lib_symbols", *lib_symbols.values()], *items, *symbols,
    ]
    return sch, paper


def build_root(root_uuid, sheet_uuids):
    items = []
    y = 40.0
    for i, (stem, title, _, note) in enumerate(SHEETS):
        x0 = 30.0
        items.append([
            "sheet", ["at", fmt(x0), fmt(y)], ["size", "90", "22"], ["exclude_from_sim", "no"],
            ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["fields_autoplaced", "yes"],
            ["stroke", ["width", "0.1524"], ["type", "solid"]], ["fill", ["color", "0", "0", "0", "0.0000"]],
            ["uuid", Str(sheet_uuids[stem])],
            prop("Sheetname", f"{i + 2}. {title}", x0, y - 0.7, 1.8, "left bottom"),
            prop("Sheetfile", f"{stem}.kicad_sch", x0, y + 22.6, FONT, "left top"),
            ["instances", ["project", Str(PROJECT), ["path", Str(f"/{root_uuid}"), ["page", Str(str(i + 2))]]]],
        ])
        items.append([
            "text", Str(note), ["exclude_from_sim", "no"], ["at", "130", fmt(y + 2), "0"],
            effects(1.6, "left top"), ["uuid", Str(uid("root", "note", stem))],
        ])
        y += 45.0
    overview = (
        f"{TITLE}\n"
        "RP2354A USB interface for the Solartron 7075 DVM + 70754 Parallel BCD Interface (SKB, 50-way Cannon).\n"
        "Everything to/from the meter is opto-isolated: only SCK, MOSI, LATCH, OE_N, MISO and DRDY cross the barrier.\n"
        "Nets are joined by name (global labels). GND (USB side) and GND_ISO (DVM side) are never joined."
    )
    items.append([
        "text", Str(overview), ["exclude_from_sim", "no"], ["at", "30", "15", "0"],
        effects(2.0, "left top"), ["uuid", Str(uid("root", "overview"))],
    ])
    return [
        "kicad_sch", ["version", "20250114"], ["generator", Str("export_schematic.py")],
        ["generator_version", Str("9.0")], ["uuid", Str(root_uuid)], ["paper", Str("A3")],
        title_block("overview"), ["lib_symbols"], *items,
        ["sheet_instances", ["path", Str("/"), ["page", Str("1")]]],
    ]


def write_library_tables(symbols) -> None:
    """Per-part symbol libraries (with the fixes applied) plus sym/fp tables,
    so ERC can check the schematic against its libraries."""
    sym_dir = OUT_DIR / "symbols"
    sym_dir.mkdir(exist_ok=True)
    for old in sym_dir.glob("*.kicad_sym"):
        old.unlink()
    sym_rows, fp_rows = [], []
    for lib, sym in sorted(symbols.items()):
        bare = [sym.tree[0], Str(sym.name), *sym.tree[2:]]
        lib_file = ["kicad_symbol_lib", ["version", "20241209"], ["generator", Str("export_schematic.py")], bare]
        (sym_dir / f"{lib}.kicad_sym").write_text(dump(lib_file) + "\n", encoding="utf-8")
        sym_rows.append((lib, f"${{KIPRJMOD}}/symbols/{lib}.kicad_sym"))
        if lib != "power":
            rel = Path("..") / part_dir(lib).relative_to(ROOT)
            fp_rows.append((lib, f"${{KIPRJMOD}}/{rel.as_posix()}"))

    def table(kind, rows):
        libs = [["lib", ["name", Str(n)], ["type", Str("KiCad")], ["uri", Str(u)], ["options", Str("")],
                 ["descr", Str("")]] for n, u in rows]
        return dump([kind, ["version", "7"], *libs]) + "\n"

    (OUT_DIR / "sym-lib-table").write_text(table("sym_lib_table", sym_rows), encoding="utf-8")
    (OUT_DIR / "fp-lib-table").write_text(table("fp_lib_table", fp_rows), encoding="utf-8")
    pro = OUT_DIR / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text('{"meta": {"filename": "%s.kicad_pro", "version": 3}}\n' % PROJECT, encoding="utf-8")


def run_erc(root_sch: Path):
    """Run KiCad's ERC; returns (errors, warnings) and writes erc_report.rpt."""
    import json

    report = OUT_DIR / "erc_report.rpt"
    subprocess.run(["kicad-cli", "sch", "erc", "--severity-all", "-o", str(report), str(root_sch)],
                   check=True, capture_output=True, text=True)
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "erc.json"
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", str(js),
                        str(root_sch)], check=True, capture_output=True, text=True)
        data = json.loads(js.read_text(encoding="utf-8"))
    found = [(sh["path"], v) for sh in data["sheets"] for v in sh["violations"]]
    errors = [f for f in found if f[1]["severity"] == "error"]
    warnings = [f for f in found if f[1]["severity"] == "warning"]
    for path, v in errors + warnings:
        items = " / ".join(i["description"] for i in v["items"])
        print(f"  ERC {v['severity']}: {path} {v['description']} | {items}")
    return errors, warnings


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------
def multi_nets_from_pcb(parts):
    nets = defaultdict(set)
    for p in parts:
        for pad, net in p["pads"].items():
            if net:
                nets[net].add((p["ref"], pad))
    return {frozenset(v) for v in nets.values() if len(v) > 1}


def multi_nets_from_schematic(root_sch: Path):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sch.net"
        subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(root_sch)],
            check=True, capture_output=True, text=True,
        )
        tree = parse(out.read_text(encoding="utf-8"))
    nets = set()
    for net in find(first(tree, "nets"), "net"):
        nodes = {(str(first(n, "ref")[1]), str(first(n, "pin")[1])) for n in find(net, "node")
                 if not str(first(n, "ref")[1]).startswith("#")}
        if len(nodes) > 1:
            nets.add(frozenset(nodes))
    return nets


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-pdf", action="store_true", help="only write the .kicad_sch files")
    args = ap.parse_args()

    if not PCB.exists():
        sys.exit(f"{PCB} not found - run `ato build` first")
    parts = load_pcb()
    values = load_bom_values()

    # net -> how many pads in the whole design; single-pad nets are no-connects
    pad_count = defaultdict(int)
    for p in parts:
        for net in p["pads"].values():
            if net:
                pad_count[net] += 1

    comps_by_sheet = defaultdict(list)
    symbols = {}
    for p in parts:
        stem = next((s for s, _, prefixes, _ in SHEETS if p["addr"].startswith(prefixes)), None)
        if stem is None:
            sys.exit(f"{p['ref']} ({p['addr']}) does not belong to any sheet - update SHEETS")
        sym = symbols.setdefault(p["lib"], Symbol(p["lib"]))
        pin_nets = {}
        for num, *_ in sym.pins:
            net = p["pads"].get(num)
            pin_nets[num] = net if net and pad_count[net] > 1 else None
        missing = [pad for pad, net in p["pads"].items() if net and pad_count[net] > 1
                   and pad not in {n for n, *_ in sym.pins}]
        if missing:
            print(f"warning: {p['ref']} pads {missing} have no symbol pin", file=sys.stderr)
        comp = {
            **p,
            "sym": sym,
            "pin_nets": pin_nets,
            "value": values.get(p["ref"]) or p["mpn"] or p["lib"],
            "in_bom": p["ref"] in values,
        }
        if not comp["in_bom"]:
            comp["value"] += " (footprint only)"
        comps_by_sheet[stem].append(comp)

    flag_sym = Symbol("power", parse(PWR_FLAG_SYMBOL))
    symbols["power"] = flag_sym
    for i, (net, stem) in enumerate(PWR_FLAGS, 1):
        if pad_count.get(net, 0) < 2:
            sys.exit(f"PWR_FLAG net {net} not found in the design")
        comps_by_sheet[stem].append({
            "ref": f"#FLG{i:02d}", "addr": "erc_power_flags", "lib": "power", "footprint": "",
            "lcsc": "", "mpn": "", "pads": {}, "sym": flag_sym, "pin_nets": {"1": net},
            "value": "PWR_FLAG", "in_bom": False,
        })

    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("*.kicad_sch"):
        old.unlink()
    root_uuid = uid("root")
    sheet_uuids = {stem: uid("sheet", stem) for stem, *_ in SHEETS}
    for stem, title, _, note in SHEETS:
        sch, paper = build_sheet(stem, title, note, comps_by_sheet[stem], root_uuid, sheet_uuids[stem])
        (OUT_DIR / f"{stem}.kicad_sch").write_text(dump(sch) + "\n", encoding="utf-8")
        print(f"  {stem}.kicad_sch: {len(comps_by_sheet[stem])} parts on {paper}")
    root_sch = OUT_DIR / f"{PROJECT}.kicad_sch"
    root_sch.write_text(dump(build_root(root_uuid, sheet_uuids)) + "\n", encoding="utf-8")
    write_library_tables(symbols)
    print(f"wrote {root_sch.relative_to(ROOT)}")

    if args.no_pdf:
        return 0
    if not shutil.which("kicad-cli"):
        sys.exit("kicad-cli not found - install KiCad 9/10 or use --no-pdf")

    # Prove the schematic is electrically identical to the atopile netlist
    pcb_nets = multi_nets_from_pcb(parts)
    sch_nets = multi_nets_from_schematic(root_sch)
    if pcb_nets != sch_nets:
        for n in sorted(pcb_nets - sch_nets, key=sorted)[:20]:
            print("  missing from schematic:", sorted(n), file=sys.stderr)
        for n in sorted(sch_nets - pcb_nets, key=sorted)[:20]:
            print("  extra in schematic:   ", sorted(n), file=sys.stderr)
        sys.exit("schematic netlist does NOT match the atopile netlist")
    print(f"netlist check: {len(sch_nets)} nets match the atopile PCB netlist")

    pdf = OUT_DIR / f"{PROJECT}.pdf"
    subprocess.run(
        ["kicad-cli", "sch", "export", "pdf", "-o", str(pdf), str(root_sch)],
        check=True, capture_output=True, text=True,
    )
    print(f"wrote {pdf.relative_to(ROOT)}")

    errors, warnings = run_erc(root_sch)
    print(f"ERC: {len(errors)} errors, {len(warnings)} warnings (schematic/erc_report.rpt)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
