#!/usr/bin/env python3
"""Single-sheet KiCad 10 schematic generated from the SKiDL netlist.

SKiDL's own schematic generator mis-connects parts on this design (its
output exports a different netlist), so this script draws the schematic
itself: every part from output/solartron_7075_interface.net is placed in a
functional block, every pin gets a short wire stub ending in a net label
(power nets end in power symbols), unused pins get no-connect flags. Symbols
are copied from the stock KiCad libraries (plus lib/Solartron7075.kicad_sym).

The result is checked by exporting its netlist with kicad-cli and comparing
it, net by net, against the SKiDL netlist (--check).

    python3 scripts/gen_schematic.py [--check]
"""

import argparse
import copy
import math
import pathlib
import re
import subprocess
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
NETLIST = HERE / "output" / "solartron_7075_interface.net"
OUT = HERE / "pcb" / "solartron_7075_interface.kicad_sch"
SYMDIRS = [HERE / "lib", pathlib.Path("/usr/share/kicad/symbols")]
G = 1.27  # schematic grid


# ---------------------------------------------------------------------------
# Minimal S-expression reader / writer
# ---------------------------------------------------------------------------
class Q(str):
    """A quoted string atom."""


def sexp_parse(text):
    tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)
    pos, stack, cur = 0, [], []
    while True:
        m = tok.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        lp, rp, qs, atom = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done, cur = cur, stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(Q(qs.replace('\\"', '"').replace("\\\\", "\\")))
        else:
            cur.append(atom)
    return cur


def sexp_str(x, ind=0):
    if isinstance(x, list):
        if not any(isinstance(e, list) for e in x):
            return "(" + " ".join(sexp_str(e) for e in x) + ")"
        head = []
        rest = list(x)
        while rest and not isinstance(rest[0], list):
            head.append(sexp_str(rest.pop(0)))
        pad = "  " * (ind + 1)
        return "(" + " ".join(head) + "".join("\n" + pad + sexp_str(e, ind + 1) for e in rest) + ")"
    if isinstance(x, Q):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(x, float):
        return f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


# ---------------------------------------------------------------------------
# Symbol libraries
# ---------------------------------------------------------------------------
_libs = {}


def lib_tree(lib):
    if lib not in _libs:
        for d in SYMDIRS:
            p = d / f"{lib}.kicad_sym"
            if p.exists():
                _libs[lib] = sexp_parse(p.read_text())[0]
                break
        else:
            raise FileNotFoundError(lib)
    return _libs[lib]


def lib_symbol(lib, name):
    """Return a flattened copy of lib:name (with 'extends' resolved)."""
    tree = lib_tree(lib)
    sym = next(s for s in find(tree, "symbol") if s[1] == name)
    ext = first(sym, "extends")
    if not ext:
        return copy.deepcopy(sym)
    parent = lib_symbol(lib, ext[1])
    out = [e for e in parent if not (isinstance(e, list) and e[0] == "property")]
    out[1] = Q(name)
    for e in out:
        if isinstance(e, list) and e[0] == "symbol":  # sub-symbols Parent_u_b -> Child_u_b
            e[1] = Q(name + e[1][len(ext[1]):])
    props = [copy.deepcopy(e) for e in sym if isinstance(e, list) and e[0] == "property"]
    # child properties first, then any parent properties the child doesn't override
    names = {p[1] for p in props}
    props += [copy.deepcopy(e) for e in parent if isinstance(e, list) and e[0] == "property"
              and e[1] not in names]
    out = out[:2] + [e for e in out[2:] if not (isinstance(e, list) and e[0] == "symbol")] \
        + props + [e for e in out if isinstance(e, list) and e[0] == "symbol"]
    return out


class Pin:
    def __init__(self, num, name, x, y, ang, length, ptype, hidden):
        self.num, self.name, self.x, self.y = num, name, x, y
        self.ang, self.length, self.ptype, self.hidden = ang, length, ptype, hidden


def symbol_pins(sym):
    pins = []
    for sub in find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        unit, style = int(m.group(1)), int(m.group(2))
        if unit > 1 or style > 1:
            continue
        for p in find(sub, "pin"):
            at = first(p, "at")
            hidden = any(e == "hide" for e in p) or bool(first(p, "hide")) and first(p, "hide")[1] == "yes"
            pins.append(Pin(str(first(p, "number")[1]), str(first(p, "name")[1]),
                            float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0,
                            float(first(p, "length")[1]), p[1], hidden))
    return pins


def symbol_bbox(sym):
    """Lib-coordinate bounding box (x0, y0, x1, y1), y up, incl. pins."""
    xs, ys = [], []

    def walk(n):
        if not isinstance(n, list) or not n:
            return
        if n[0] in ("start", "end", "xy", "center") and len(n) >= 3:
            try:
                xs.append(float(n[1]))
                ys.append(float(n[2]))
            except ValueError:
                pass
        if n[0] == "circle":
            c, r = first(n, "center"), first(n, "radius")
            if c and r:
                xs.extend([float(c[1]) - float(r[1]), float(c[1]) + float(r[1])])
                ys.extend([float(c[2]) - float(r[1]), float(c[2]) + float(r[1])])
        if n[0] == "property":
            return
        for e in n:
            walk(e)
    for sub in find(sym, "symbol"):
        walk(sub)
    for p in symbol_pins(sym):
        xs.append(p.x)
        ys.append(p.y)
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------
# Geometry helpers (sheet coordinates: y down; symbol rotation CCW on screen)
# ---------------------------------------------------------------------------
def rot(dx, dy, r):
    r %= 360
    if r == 0:
        return dx, dy
    if r == 90:
        return dy, -dx
    if r == 180:
        return -dx, -dy
    return -dy, dx


def snap(v):
    return round(round(v / G) * G, 4)


# ---------------------------------------------------------------------------
# Netlist
# ---------------------------------------------------------------------------
def read_netlist(path):
    txt = path.read_text()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\(tstamps "([0-9a-f-]+)"\)\)', txt, re.S):
        ref, body, ts = m.group(1), m.group(2), m.group(3)
        val = re.search(r'\(value "([^"]*)"\)', body).group(1)
        fpm = re.search(r'\(footprint "([^"]*)"\)', body)
        lib = re.search(r'\(libsource\s+\(lib "([^"]+)"\)\s*\(part "([^"]+)"\)', body)
        fields = dict(re.findall(r'\(field\s+\(name "([^"]+)"\)\s*"([^"]*)"\)', body))
        sheet = re.search(r'\(sheetpath\s+\(names "([^"]*)"\)', body)
        comps[ref] = dict(ref=ref, value=val, footprint=fpm.group(1) if fpm else "",
                          lib=lib.group(1), part=lib.group(2), fields=fields, tstamp=ts,
                          sheet=sheet.group(1) if sheet else "/")
    nets = {}
    pinnet = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', txt, re.S):
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
        nets[m.group(1)] = nodes
        for r, p in nodes:
            pinnet[(r, p)] = m.group(1)
    return comps, nets, pinnet


def netlist_nets(path):
    """{net name: set((ref, pin))} for any KiCad netlist (SKiDL's or kicad-cli's)."""
    txt = path.read_text()
    out = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', txt, re.S):
        nodes = set(re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)))
        if nodes:
            out[m.group(1)] = nodes
    return out


# ---------------------------------------------------------------------------
# Drawing engine
# ---------------------------------------------------------------------------
# Power nets drawn with power symbols: net -> (lib symbol, shown value)
POWER = {
    "GND": "power:GND",
    "ISO_GND": "power:GNDREF",
    "+3V3": "power:+3V3",
    "+5V_USB": "power:+5V",
    "ISO_+5V": "power:+5V",
    "ISO_+9V": "power:+9V",
    "+1V1_DVDD": "power:+1V1",
}
STUB = 2.54


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "solartron7075-sch/" + "/".join(map(str, parts))))


class Schematic:
    def __init__(self, comps, pinnet, title, paper="A2"):
        self.comps, self.pinnet = comps, pinnet
        self.title, self.paper = title, paper
        self.root = uid("root")
        self.libsyms = {}          # lib_id -> flattened symbol
        self.placed = {}           # ref -> (x, y, rot, mirror)
        self.items = []            # schematic body items (sexp lists)
        self.npwr = 0
        self.nflg = 0
        self.drawn_pins = set()
        self.joined = set()
        self.joins = []
        self.flags = []

    # -- library symbols ------------------------------------------------------
    def libsym(self, lib_id):
        if lib_id not in self.libsyms:
            lib, name = lib_id.split(":")
            sym = lib_symbol(lib, name)
            sym[1] = Q(lib_id)
            self.libsyms[lib_id] = sym
        return self.libsyms[lib_id]

    # -- transforms -------------------------------------------------------------
    @staticmethod
    def xf(x, y, rot_, mirror, lx, ly):
        dx, dy = lx, -ly
        if mirror == "y":
            dx = -dx
        dx, dy = rot(dx, dy, rot_)
        return snap(x + dx), snap(y + dy)

    def pin_geom(self, ref):
        """[(pin, (px, py), (sx, sy) stub direction)] for a placed part."""
        c = self.comps[ref]
        x, y, r, m = self.placed[ref]
        sym = self.libsym(f"{c['lib']}:{c['part']}")
        out = []
        for p in symbol_pins(sym):
            px, py = self.xf(x, y, r, m, p.x, p.y)
            a = math.radians(p.ang)
            dx, dy = -math.cos(a), math.sin(a)       # outward, in lib-y-flipped coords
            if m == "y":
                dx = -dx
            dx, dy = rot(round(dx), round(dy), r)
            out.append((p, (px, py), (dx, dy)))
        return out

    def bbox(self, ref):
        c = self.comps[ref]
        x, y, r, m = self.placed[ref]
        x0, y0, x1, y1 = symbol_bbox(self.libsym(f"{c['lib']}:{c['part']}"))
        pts = [self.xf(x, y, r, m, a, b) for a in (x0, x1) for b in (y0, y1)]
        return (min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts))

    # -- placement ----------------------------------------------------------------
    def place(self, ref, x, y, rot_=0, mirror=None):
        assert ref in self.comps, ref
        assert ref not in self.placed, f"{ref} placed twice"
        self.placed[ref] = (snap(x), snap(y), rot_, mirror)

    # -- primitives -----------------------------------------------------------------
    def wire(self, a, b):
        self.items.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                           ["stroke", ["width", 0], ["type", "default"]],
                           ["uuid", Q(uid("w", a, b))]])

    def label(self, name, at, d):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        just = "left" if ang in (0, 90) else "right"
        self.items.append(["label", Q(name), ["at", at[0], at[1], ang],
                           ["effects", ["font", ["size", 1.27, 1.27]], ["justify", just]],
                           ["uuid", Q(uid("l", name, at))]])

    def global_label(self, name, at, d):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        just = "left" if ang in (0, 90) else "right"
        self.items.append(["global_label", Q(name), ["shape", "passive"], ["at", at[0], at[1], ang],
                           ["effects", ["font", ["size", 1.27, 1.27]], ["justify", just]],
                           ["uuid", Q(uid("gl", name, at))]])

    def no_connect(self, at):
        self.items.append(["no_connect", ["at", at[0], at[1]], ["uuid", Q(uid("nc", at))]])

    def text(self, s, x, y, size=2.54, bold=False, valign="bottom"):
        eff = ["effects", ["font", ["size", size, size]] + ([["bold", "yes"]] if bold else []),
               ["justify", "left", valign]]
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", snap(x), snap(y), 0], eff,
                           ["uuid", Q(uid("t", s, x, y))]])

    def rect(self, x0, y0, x1, y1, dashed=True):
        self.items.append(["rectangle", ["start", snap(x0), snap(y0)], ["end", snap(x1), snap(y1)],
                           ["stroke", ["width", 0.254], ["type", "dash" if dashed else "default"]],
                           ["fill", ["type", "none"]], ["uuid", Q(uid("r", x0, y0, x1, y1))]])

    def polyline(self, pts, dashed=True, width=0.508):
        self.items.append(["polyline", ["pts"] + [["xy", snap(a), snap(b)] for a, b in pts],
                           ["stroke", ["width", width], ["type", "dash_dot" if dashed else "default"]],
                           ["uuid", Q(uid("pl", *pts))]])

    def _props(self, sym, ref, value, x, y, r, m, extra):
        """Property list for a symbol instance, positioned like KiCad would."""
        out = []
        lib_props = {p[1]: p for p in find(sym, "property")}
        for key, val in [("Reference", ref), ("Value", value)] + extra:
            lp = lib_props.get(key)
            at = first(lp, "at") if lp else None
            if at is not None and key in ("Reference", "Value"):
                px, py = self.xf(x, y, r, m, float(at[1]), float(at[2]))
                ang = (float(at[3]) + r) % 180 if len(at) > 3 else r % 180
            else:
                px, py, ang = x, y, 0
            hide = key not in ("Reference", "Value") or (lp is not None and _hidden(lp))
            eff = ["effects", ["font", ["size", 1.27, 1.27]]]
            if lp is not None:
                je = first(first(lp, "effects") or [], "justify")
                if je and key in ("Reference", "Value"):
                    eff.append(copy.deepcopy(je))
            if hide:
                eff.append(["hide", "yes"])
            out.append(["property", Q(key), Q(val), ["at", px, py, ang], eff])
        return out

    def _instance(self, lib_id, ref, value, x, y, r, m, extra, sym_uuid, pins, in_bom=True, power=False):
        sym = self.libsym(lib_id)
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, r]]
        if m:
            node.append(["mirror", m])
        node += [["unit", 1], ["exclude_from_sim", "yes" if power else "no"],
                 ["in_bom", "yes" if in_bom else "no"], ["on_board", "no" if power else "yes"],
                 ["dnp", "no"], ["uuid", Q(sym_uuid)]]
        node += self._props(sym, ref, value, x, y, r, m, extra)
        for pn in pins:
            node.append(["pin", Q(pn), ["uuid", Q(uid("pin", sym_uuid, pn))]])
        node.append(["instances", ["project", Q("solartron_7075_interface"),
                                   ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]])
        self.items.append(node)

    def power_symbol(self, net, at, d):
        lib_id = POWER[net]
        sym = self.libsym(lib_id)
        x0, y0, x1, y1 = symbol_bbox(sym)
        up = y1 > -y0                          # graphic above the pin?
        r = 0
        if up and d == (0, 1):
            r = 180
        if not up and d == (0, -1):
            r = 180
        self.npwr += 1
        ref = f"#PWR{self.npwr:03d}"
        self._instance(lib_id, ref, net, at[0], at[1], r, None,
                       [("Footprint", ""), ("Datasheet", "")], uid("pwr", net, at),
                       [str(p.num) for p in symbol_pins(sym)], in_bom=False, power=True)

    def pwr_flag(self, net, at):
        """PWR_FLAG on a supply that is only fed through passives (keeps ERC quiet)."""
        self.nflg += 1
        self._instance("power:PWR_FLAG", f"#FLG{self.nflg:02d}", "PWR_FLAG", at[0], at[1], 0, None,
                       [("Footprint", ""), ("Datasheet", "")], uid("flg", net, at), ["1"],
                       in_bom=False, power=True)
        end = (at[0], snap(at[1] + STUB))
        self.wire(at, end)
        if net in POWER:
            self.power_symbol(net, end, (0, 1))
        else:
            self.label(net, end, (0, 1))

    def join(self, ref_a, pin_a, ref_b, pin_b, keep_a=False):
        """Wire two pins directly (L-shaped if not aligned) instead of labelling both.

        keep_a: pin_a still gets its label / power symbol (for nets with more members)."""
        pa = next(at for p, at, d in self.pin_geom(ref_a) if p.num == str(pin_a))
        pb = next(at for p, at, d in self.pin_geom(ref_b) if p.num == str(pin_b))
        na, nb = self.pinnet.get((ref_a, str(pin_a))), self.pinnet.get((ref_b, str(pin_b)))
        assert na and na == nb, f"join {ref_a}.{pin_a}-{ref_b}.{pin_b}: nets {na} / {nb}"
        if pa[0] == pb[0] or pa[1] == pb[1]:
            self.wire(pa, pb)
            seg = (pa, pb)
        else:
            mid = (pa[0], pb[1])
            self.wire(pa, mid)
            self.wire(mid, pb)
            seg = (pa, mid) if abs(pa[1] - mid[1]) >= abs(pb[0] - mid[0]) else (mid, pb)
        if not keep_a and na not in POWER:
            # Name the wire so the net keeps its SKiDL name (else KiCad calls it Net-(...))
            (x0, y0), (x1, y1) = seg
            vertical = x0 == x1
            at = (x0, snap((y0 + y1) / 2)) if vertical else (snap((x0 + x1) / 2), y0)
            self.label(na, at, (0, -1) if vertical else (1, 0))
        self.joined.add((ref_b, str(pin_b)))
        if not keep_a:
            self.joined.add((ref_a, str(pin_a)))

    # -- connecting a placed part -----------------------------------------------------
    def connect(self, ref, stub=None, label_side=None):
        stub = stub or {}
        groups = {}
        for p, at, d in self.pin_geom(ref):
            groups.setdefault(at, []).append((p, d))
        for at, plist in groups.items():
            if all((ref, p.num) in self.joined for p, _ in plist):
                continue
            nets = {self.pinnet.get((ref, p.num)) for p, _ in plist}
            nets.discard(None)
            assert len(nets) <= 1, f"{ref} stacked pins on different nets {nets}"
            d = plist[0][1]
            if not nets:
                self.no_connect(at)
                continue
            net = nets.pop()
            length = stub.get(plist[0][0].num, STUB)
            end = (snap(at[0] + d[0] * length), snap(at[1] + d[1] * length))
            self.wire(at, end)
            if net in POWER and len(groups) > 6:
                self.global_label(net, end, d)   # dense IC supply pins: global label = same net
            elif net in POWER:
                self.power_symbol(net, end, d)
            else:
                self.label(net, end, d)
            for p, _ in plist:
                self.drawn_pins.add((ref, p.num))

    # -- output -----------------------------------------------------------------------
    def write(self, path):
        for ref in self.placed:
            c = self.comps[ref]
            lib_id = f"{c['lib']}:{c['part']}"
            x, y, r, m = self.placed[ref]
            f = c["fields"]
            extra = [("Footprint", c["footprint"]), ("Datasheet", "")]
            extra += [(k, f[k]) for k in ("LCSC", "MPN", "Manufacturer") if k in f]
            pins = sorted({p.num for p in symbol_pins(self.libsym(lib_id))}, key=lambda s: (len(s), s))
            # Keep the SKiDL time stamp as the symbol UUID: it is what the PCB footprints refer to.
            self._instance(lib_id, ref, c["value"], x, y, r, m, extra, c["tstamp"],
                           pins)
        doc = ["kicad_sch", ["version", "20250114"], ["generator", Q("solartron_gen_schematic")],
               ["generator_version", Q("10.0")], ["uuid", Q(self.root)], ["paper", Q(self.paper)],
               ["title_block", ["title", Q(self.title)], ["company", Q("")],
                ["comment", 1, Q("Generated from the SKiDL netlist by scripts/gen_schematic.py")],
                ["comment", 2, Q("Net labels with the same name are connected")]],
               ["lib_symbols"] + list(self.libsyms.values())]
        doc += self.items
        doc.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        path.write_text(sexp_str(doc) + "\n")


def _hidden(prop):
    h = first(prop, "hide")
    if h is not None and (len(h) == 1 or h[1] == "yes"):
        return True
    eff = first(prop, "effects")
    if not eff:
        return False
    h = first(eff, "hide")
    return (h is not None and (len(h) == 1 or h[1] == "yes")) or "hide" in eff


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
NOTES = """\
Isolated serial link (RP2354A SPI0 / PIO): SPI mode 0, MSB first, <= 1 MHz, 40 clocks per transfer.
Pulse LATCH low >= 1 us, then clock 5 bytes. LATCH low: the 74HCT165s sample the meter outputs.
LATCH rising edge: the 74HC595 outputs take the last two bytes clocked in.
/OE (GPIO24) high = command outputs off (the default while the MCU is unpowered or in reset).

MISO  byte0 U10: POL+  POL-  FUNC_A  FUNC_B  RANGE_4  RANGE_2  RANGE_1  PRINT_PULSE
      byte1 U11: 10^3 digit (8 4 2 1), 10^2 digit (8 4 2 1)
      byte2 U12: 10^5 digit, 10^4 digit
      byte3 U13: 10^1 digit, 10^0 digit
      byte4 U14: PRINT_LEVEL  DATA_CAN_CHANGE  OVERLOAD  1x10^6  1 0 1 0 (link check)
MOSI  byte3 U16: -  -  REMOTE LED  CONTACT_SAMPLE  PULSE_SAMPLE  RANGE_4  RANGE_2  RANGE_1
      byte4 U15: AUTORANGE_INH  INTEG_4  INTEG_2  INTEG_1  FUNC_43  FUNC_42  RATIO_N  LOCKOUT_N

Meter levels (7075 manual sect. 9): outputs '1' = 2.4..6 V from 6k, '0' sinks 10 mA;
inputs '1' = 2.4..5 V, '0' < 0.5 V at 5 mA. Series 10k on every meter output.
ISO_GND = SKB pin 37 (meter earth / logic 0). Net labels of the same name are connected."""


def layout(S):
    P = S.place

    def block(title, x0, y0, x1, y1):
        S.rect(x0, y0, x1, y1)
        S.text(title, x0 + 2.54, y0 + 5.08, size=2.54, bold=True)

    def caps(refs, x, y, pitch=7.62):
        for i, r in enumerate(refs):
            P(r, x + i * pitch, y)

    # ---- USB input and 3.3 V ------------------------------------------------
    block("USB INPUT, PROTECTION, 3.3 V", 12.7, 12.7, 152.4, 111.76)
    P("J2", 27.94, 50.8)
    P("F1", 58.42, 33.02, 90)                  # VBUS_RAW -> +5V_USB
    P("U3", 78.74, 81.28)                       # USBLC6 ESD clamp
    P("R1", 30.48, 91.44)
    P("C1", 43.18, 91.44)                       # shield RC
    caps(["C2", "C3"], 91.44, 40.64, 12.7)
    P("U2", 124.46, 43.18)                      # AP2112K-3.3
    P("C4", 144.78, 40.64)
    P("R2", 124.46, 71.12)                      # 3V3 power LED
    P("D1", 124.46, 86.36, 90)
    S.flags.append(("+5V_USB", (66.04, 50.8)))

    # ---- Notes ------------------------------------------------------------------
    block("NOTES", 12.7, 116.84, 152.4, 271.78)
    S.text(NOTES, 15.24, 124.46, size=1.524, valign="top")

    # ---- RP2354A ------------------------------------------------------------
    block("RP2354A (2 MB IN-PACKAGE FLASH)", 157.48, 12.7, 312.42, 251.46)
    P("U1", 238.76, 137.16)
    caps(["C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14"], 170.18, 33.02)
    caps(["C17", "C18", "C19", "C16"], 251.46, 33.02, 12.7)
    P("L1", 302.26, 33.02)                      # VREG_LX -> DVDD
    S.flags.append(("+1V1_DVDD", (302.26, 63.5)))
    P("R3", 172.72, 63.5)                       # 3V3 -> VREG_AVDD
    P("C15", 185.42, 63.5)
    S.flags.append(("VREG_AVDD", (195.58, 63.5)))
    P("Y1", 180.34, 160.02)
    P("R4", 198.12, 182.88)
    P("C20", 172.72, 193.04)
    P("C21", 187.96, 193.04)
    P("R5", 180.34, 109.22, 90)                 # USB 27R series
    P("R6", 180.34, 99.06, 90)
    P("R7", 205.74, 205.74)                     # RUN pull-up
    P("SW2", 220.98, 226.06)                    # RESET
    P("R8", 246.38, 205.74)                     # BOOTSEL series
    P("SW1", 261.62, 226.06)
    P("J3", 294.64, 228.6)                      # SWD
    P("R9", 294.64, 81.28)                      # status LED
    P("D2", 294.64, 96.52, 90)

    # ---- Isolation barrier ----------------------------------------------------
    block("ISOLATION: 5 x TLP2361 + B0509S", 317.5, 12.7, 401.32, 271.78)
    bx = 359.41
    for i, (u, r, c) in enumerate((("U5", "R14", "C33"), ("U6", "R15", "C34"), ("U7", "R16", "C35"),
                                   ("U8", "R17", "C36"))):
        y = 43.18 + i * 43.18
        P(u, bx, y)
        P(r, 332.74, y - 10.16)
        P(c, 388.62, y - 7.62)
        S.joins.append((r, 2, u, 1))           # LED resistor straight to the anode
    y = 43.18 + 4 * 43.18
    P("U9", bx, y, 0, "y")                      # return channel: LED on the meter side
    P("R18", 386.08, y - 10.16)
    P("C37", 330.2, y - 7.62)
    S.joins.append(("R18", 2, "U9", 1))
    P("PS1", bx, 251.46)
    P("C22", 330.2, 241.3)
    S.barrier_x = bx
    S.text("HOST SIDE (GND)", 320.04, 269.24, size=1.778)
    S.text("METER SIDE (ISO_GND)", 363.22, 269.24, size=1.778)

    # ---- Meter-side supply -----------------------------------------------------
    block("METER-SIDE 5 V", 406.4, 205.74, 500.38, 271.78)
    P("C23", 416.56, 228.6)
    P("R10", 429.26, 228.6)
    P("C24", 441.96, 228.6)
    P("U4", 464.82, 233.68)                     # 78L05
    P("C25", 485.14, 228.6)
    P("R11", 495.3, 226.06)
    P("D3", 495.3, 243.84, 90)

    # ---- Command outputs -------------------------------------------------------
    block("COMMAND OUTPUTS: 2 x 74HC595", 406.4, 12.7, 500.38, 200.66)
    P("U15", 449.58, 55.88)
    P("C31", 485.14, 30.48)
    P("U16", 449.58, 132.08)
    P("C32", 485.14, 106.68)
    P("Q1", 439.42, 180.34)                     # CONTACT SAMPLE closure
    P("R12", 421.64, 185.42)
    P("R13", 477.52, 167.64)                    # REMOTE LED
    P("D4", 477.52, 182.88, 90)

    # ---- Meter connector -----------------------------------------------------------
    block("J1: DD-50 PLUG TO 7075 SKB", 505.46, 12.7, 579.12, 271.78)
    P("J1", 541.02, 129.54)

    # ---- Input shift registers ---------------------------------------------------------
    block("DISPLAY DATA / STATUS INPUTS: 5 x 74HCT165 (MISO = U10.Q7; chain U10 <- U11 <- U12 <- U13 <- U14)",
          12.7, 276.86, 579.12, 381.0)
    groups = [("U10", "RN1", "RN2", "C26"), ("U11", "RN3", "RN4", "C27"), ("U12", "RN5", "RN6", "C28"),
              ("U13", "RN7", "RN8", "C29"), ("U14", "RN9", None, "C30")]
    for i, (u, ra, rb, c) in enumerate(groups):
        x = 48.26 + i * 111.76
        P(ra, x - 22.86, 304.8)
        if rb:
            P(rb, x - 22.86 + 25.4, 304.8)
        P(u, x + 33.02, 341.63)
        P(c, x + 63.5, 320.04)

    for pair in [("R2", 2, "D1", 2), ("R9", 2, "D2", 2), ("R11", 2, "D3", 2), ("R13", 2, "D4", 2)]:
        S.joins.append(pair)
    S.joins.append(("U2", 1, "U2", 3, True))   # EN tied to VIN


STUBS = {"U3": {"5": 7.62},
         "PS1": {"1": 7.62, "2": 7.62, "3": 10.16, "4": 10.16},
         "U4": {"1": 5.08, "3": 5.08}}


def build_schematic():
    comps, nets, pinnet = read_netlist(NETLIST)
    S = Schematic(comps, pinnet, "Solartron 7075 USB interface (SKiDL)")
    layout(S)
    missing = sorted(set(comps) - set(S.placed))
    assert not missing, f"unplaced parts: {missing}"
    for j in S.joins:
        S.join(*j)
    for ref in S.placed:
        S.connect(ref, STUBS.get(ref))
    # Supplies fed only through passives need a PWR_FLAG for KiCad's ERC
    for net, at in S.flags:
        S.pwr_flag(net, at)
    # Isolation barrier: dashed line through the gaps between the optocouplers
    spans = sorted((S.bbox(u)[1] - 7.62, S.bbox(u)[3] + 7.62) for u in ("U5", "U6", "U7", "U8", "U9"))
    y = 17.78
    for top, bot in spans:
        S.polyline([(S.barrier_x, y), (S.barrier_x, top)])
        y = bot
    S.polyline([(S.barrier_x, y), (S.barrier_x, 266.7)])
    S.write(OUT)
    return comps, nets


def check(nets_skidl):
    """Export the schematic's netlist with kicad-cli and compare connectivity."""
    tmp = OUT.with_suffix(".check.net")
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(tmp), str(OUT)],
                   check=True, capture_output=True)
    sch = netlist_nets(tmp)
    tmp.unlink()
    a = {frozenset(v) for v in nets_skidl.values() if len(v) > 1}
    b = {frozenset(v) for v in sch.values() if len(v) > 1}
    if a == b:
        # Names must survive too (KiCad prefixes local-label nets with the sheet path "/")
        name = {frozenset(v): k for k, v in sch.items()}
        bad = [(k, name[frozenset(v)]) for k, v in nets_skidl.items()
               if len(v) > 1 and name[frozenset(v)] not in (k, "/" + k)]
        for k, n in bad[:15]:
            print(f"  net {k} is named {n} in the schematic")
        if not bad:
            print(f"schematic connectivity and net names match the SKiDL netlist ({len(a)} nets)")
        return not bad
    for v in sorted(a - b, key=len)[:15]:
        print("  SKiDL net missing/split in schematic:", sorted(v)[:6], len(v))
    for v in sorted(b - a, key=len)[:15]:
        print("  schematic-only net:", sorted(v)[:6], len(v))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify against the SKiDL netlist")
    args = ap.parse_args()
    _, nets = build_schematic()
    print("wrote", OUT)
    if args.check:
        nets_skidl = {k: set(v) for k, v in nets.items()}
        sys.exit(0 if check(nets_skidl) else 1)


if __name__ == "__main__":
    main()
