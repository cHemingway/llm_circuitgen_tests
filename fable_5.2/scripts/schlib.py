"""Small KiCad schematic writer used by gen_sch.py.

Connectivity is expressed mostly with net labels / power symbols placed on
short wire stubs at each pin, which keeps the generated sheets unambiguous
and easy to verify with ERC.
"""
import math
import os
import uuid
from sx import parse, dump, find, first, Sym

KSYM = '/usr/share/kicad/symbols/'
NS = uuid.UUID('7f0c5a52-7075-4a11-9c11-5e1a27f07075')
G = 1.27


def S(x):
    return Sym(x)


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


def r2(v):
    """Snap to the 1.27 mm (50 mil) connection grid."""
    return round(round(v / G) * G + 0.0, 4)


class SymLib:
    """Loads (and flattens 'extends') symbols from .kicad_sym libraries."""

    def __init__(self, project_libs):
        self.paths = dict(project_libs)
        self.trees = {}
        self.cache = {}

    def tree(self, lib):
        if lib not in self.trees:
            path = self.paths.get(lib, KSYM + lib + '.kicad_sym')
            self.trees[lib] = parse(open(path).read())
        return self.trees[lib]

    def raw(self, lib, name):
        for s in find(self.tree(lib), 'symbol'):
            if s[1] == name:
                return s
        raise KeyError(lib + ':' + name)

    def flat(self, lib_id):
        if lib_id in self.cache:
            return self.cache[lib_id]
        lib, name = lib_id.split(':')
        s = self.raw(lib, name)
        chain = [s]
        while first(chain[-1], 'extends'):
            chain.append(self.raw(lib, first(chain[-1], 'extends')[1]))
        base = chain[-1]
        out = [S('symbol'), lib_id]
        props = {}
        order = []
        for c in reversed(chain):
            for p in find(c, 'property'):
                if p[1] not in props:
                    order.append(p[1])
                props[p[1]] = p
        for item in base[2:]:
            if isinstance(item, list) and item[0] in ('property', 'symbol', 'extends'):
                continue
            out.append(item)
        for k in order:
            out.append(props[k])
        for sub in find(base, 'symbol'):
            sub2 = parse(dump(sub))
            sub2[1] = name + sub[1][len(base[1]):]
            out.append(sub2)
        self.cache[lib_id] = out
        return out

    def pins(self, lib_id, unit):
        """-> list of (number, name, x, y, angle) in library coordinates."""
        name = lib_id.split(':')[1]
        res = []
        for sub in find(self.flat(lib_id), 'symbol'):
            u, style = sub[1][len(name) + 1:].split('_')
            if int(u) not in (0, unit) or int(style) not in (0, 1):
                continue
            for p in find(sub, 'pin'):
                at = first(p, 'at')
                res.append((first(p, 'number')[1], first(p, 'name')[1],
                            float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
        return res

    def prop(self, lib_id, key):
        for p in find(self.flat(lib_id), 'property'):
            if p[1] == key:
                return p
        return None

    def is_power(self, lib_id):
        return first(self.flat(lib_id), 'power') is not None


def rot_vec(dx, dy, rot):
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    return (dx * c + dy * s, -dx * s + dy * c)


# power net name -> (lib_id, 'up' | 'down')
POWER = {
    'GND': ('power:GND', 'down'),
    '+3V3': ('power:+3V3', 'up'),
    '+1V1': ('power:+1V1', 'up'),
    'VBUS': ('power:VBUS', 'up'),
    'GND_ISO': ('solartron7075:GND_ISO', 'down'),
    '+5V_ISO': ('solartron7075:+5V_ISO', 'up'),
    '+9V_ISO': ('solartron7075:+9V_ISO', 'up'),
}


class Project:
    def __init__(self, name, libs):
        self.name = name
        self.lib = SymLib(libs)
        self.root_uuid = uid('root')
        self.sheets = []
        self.pwr_count = 0
        self.net_sheets = {}

    def sheet(self, name, filename, title, paper='A3'):
        sh = Sheet(self, name, filename, title, paper, page=len(self.sheets) + 2)
        self.sheets.append(sh)
        return sh

    def finalize(self):
        for sh in self.sheets:
            for (_, _, _, net) in sh.attach:
                self.net_sheets.setdefault(net, set()).add(sh.name)

    def is_global(self, net):
        return len(self.net_sheets.get(net, ())) > 1


class Sheet:
    def __init__(self, proj, name, filename, title, paper, page):
        self.p = proj
        self.name = name
        self.filename = filename
        self.title = title
        self.paper = paper
        self.page = page
        self.uuid = uid('sheet', name)          # uuid of the sheet symbol in the root sheet
        self.file_uuid = uid('sheetfile', name)
        self.items = []
        self.used = []
        self.attach = []      # (x, y, direction, net)
        self.attach_seen = set()
        self.n = 0
        self.refs = {}

    # ---- low-level items -------------------------------------------------
    def _id(self, kind):
        self.n += 1
        return uid(self.name, kind, self.n)

    def path(self):
        return '/%s/%s' % (self.p.root_uuid, self.uuid)

    def wire(self, pts):
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            self.items.append([S('wire'), [S('pts'), [S('xy'), r2(a[0]), r2(a[1])], [S('xy'), r2(b[0]), r2(b[1])]],
                               [S('stroke'), [S('width'), 0], [S('type'), S('default')]],
                               [S('uuid'), self._id('wire')]])

    def junction(self, x, y):
        self.items.append([S('junction'), [S('at'), r2(x), r2(y)], [S('diameter'), 0], [S('color'), 0, 0, 0, 0],
                           [S('uuid'), self._id('junction')]])

    def nc(self, x, y):
        self.items.append([S('no_connect'), [S('at'), r2(x), r2(y)], [S('uuid'), self._id('nc')]])

    def text(self, s, x, y, size=1.5, bold=False):
        f = [S('font'), [S('size'), size, size]]
        if bold:
            f.append([S('bold'), S('yes')])
        self.items.append([S('text'), s, [S('exclude_from_sim'), S('no')], [S('at'), round(x, 3), round(y, 3), 0],
                           [S('effects'), f, [S('justify'), S('left'), S('top')]],
                           [S('uuid'), self._id('text')]])

    def box(self, x1, y1, x2, y2, title=None):
        self.items.append([S('rectangle'), [S('start'), r2(x1), r2(y1)], [S('end'), r2(x2), r2(y2)],
                           [S('stroke'), [S('width'), 0.15], [S('type'), S('dash')]],
                           [S('fill'), [S('type'), S('none')]], [S('uuid'), self._id('rect')]])
        if title:
            self.text(title, x1 + 1.5, y1 + 1.5, size=2.2, bold=True)

    # ---- nets --------------------------------------------------------------
    def net(self, x, y, d, net, stub=2.54):
        """Attach `net` at point (x, y) with a stub in direction d=(dx, dy)."""
        key = (r2(x), r2(y), net)
        if key in self.attach_seen:
            return
        self.attach_seen.add(key)
        ex, ey = x + d[0] * stub, y + d[1] * stub
        if stub:
            self.wire([(x, y), (ex, ey)])
        self.attach.append((ex, ey, d, net))

    def _emit_attach(self):
        for (x, y, d, net) in self.attach:
            if net in POWER:
                self._power(x, y, d, net)
            else:
                self._label(x, y, d, net)

    def _label(self, x, y, d, net):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        if self.p.is_global(net):
            just = 'left' if ang in (0, 90) else 'right'
            self.items.append([S('global_label'), net, [S('shape'), S('passive')], [S('at'), r2(x), r2(y), ang],
                               [S('fields_autoplaced'), S('yes')],
                               [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S(just)]],
                               [S('uuid'), self._id('glabel')],
                               [S('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [S('at'), 0, 0, 0],
                                [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('hide'), S('yes')]]]])
        else:
            just = [S('left'), S('bottom')] if ang in (0, 90) else [S('right'), S('bottom')]
            self.items.append([S('label'), net, [S('at'), r2(x), r2(y), ang],
                               [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify')] + just],
                               [S('uuid'), self._id('label')]])

    def _power(self, x, y, d, net):
        lib_id, kind = POWER[net]
        if kind == 'down':
            rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]
            dist = 5.2
        else:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]
            dist = 3.7
        self.p.pwr_count += 1
        ref = '#PWR%03d' % self.p.pwr_count
        vx, vy = x + d[0] * dist, y + d[1] * dist
        just = None
        if d == (1, 0):
            vx, just = x + 3.3, 'left'
        elif d == (-1, 0):
            vx, just = x - 3.3, 'right'
        self._symbol(ref, lib_id, x, y, rot, 1, net, fields={}, ref_at=None, val_at=(vx, vy, just), hide_ref=True)

    def flag(self, x, y, d, net, stub=2.54):
        """PWR_FLAG on a net (placed on its own labelled/powered stub)."""
        self.p.pwr_count += 1
        ref = '#FLG%03d' % self.p.pwr_count
        self._symbol(ref, 'power:PWR_FLAG', x, y, 0, 1, 'PWR_FLAG', fields={}, ref_at=None,
                     val_at=(x, y - 4.6, None), hide_ref=True)
        self.net(x, y, d, net, stub)

    # ---- symbols -----------------------------------------------------------
    def pin_xy(self, lib_id, unit, x, y, rot, mirror=False):
        out = {}
        m = -1 if mirror else 1
        for (num, name, px, py, ang) in self.p.lib.pins(lib_id, unit):
            dx, dy = rot_vec(m * px, -py, rot)
            a = math.radians(ang)
            ox, oy = -round(math.cos(a)), round(math.sin(a))   # outward dir, screen coords at rot 0
            ddx, ddy = rot_vec(m * ox, oy, rot)
            out.setdefault(num, []).append((x + dx, y + dy, (int(ddx), int(ddy)), name))
        return out

    def _symbol(self, ref, lib_id, x, y, rot, unit, value, fields, ref_at, val_at, hide_ref=False,
                hide_val=False, dnp=False, mirror=False):
        lib = self.p.lib
        if lib_id not in self.used:
            self.used.append(lib_id)
        fa = 90 if rot in (90, 270) else 0

        def P(name, val, at, hide=False):
            px, py, just = at
            if just and rot in (90, 180):      # KiCad flips justification for these orientations
                just = {'left': 'right', 'right': 'left'}[just]
            e = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]
            if just:
                e.append([S('justify'), S(just)])
            if hide:
                e.append([S('hide'), S('yes')])
            return [S('property'), name, val, [S('at'), round(px - x + r2(x), 3), round(py - y + r2(y), 3), fa], e]

        def lib_at(key, default):
            p = lib.prop(lib_id, key)
            if p is None:
                return default
            at = first(p, 'at')
            dx, dy = rot_vec((-1 if mirror else 1) * float(at[1]), -float(at[2]), rot)
            j = first(first(p, 'effects'), 'justify')
            just = None
            if j is not None and rot == 0:
                for t in j[1:]:
                    if t in ('left', 'right'):
                        just = str(t)
                if mirror and just:
                    just = {'left': 'right', 'right': 'left'}[just]
            return (x + dx, y + dy, just)

        if ref_at is None:
            ref_at = lib_at('Reference', (x, y - 5, None))
        if val_at is None:
            val_at = lib_at('Value', (x, y + 5, None))
        sym = [S('symbol'), [S('lib_id'), lib_id], [S('at'), r2(x), r2(y), rot]] + \
              ([[S('mirror'), S('y')]] if mirror else []) + [[S('unit'), unit],
               [S('exclude_from_sim'), S('no')], [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
               [S('dnp'), S('yes' if dnp else 'no')],
               [S('uuid'), uid(self.name, 'sym', ref, unit)],
               P('Reference', ref, ref_at, hide_ref),
               P('Value', value, val_at, hide_val)]
        std = {'Footprint': '', 'Datasheet': '', 'Description': ''}
        for k in std:
            p = lib.prop(lib_id, k)
            v = fields.get(k, p[2] if p is not None else '')
            sym.append(P(k, v, (x, y, None), True))
        for k, v in fields.items():
            if k not in std:
                sym.append(P(k, v, (x, y, None), True))
        nums = []
        for (num, _, _, _, _) in lib.pins(lib_id, unit):
            if num not in nums:
                nums.append(num)
        for num in nums:
            sym.append([S('pin'), num, [S('uuid'), uid(self.name, 'pin', ref, unit, num)]])
        sym.append([S('instances'), [S('project'), self.p.name,
                                     [S('path'), self.path(), [S('reference'), ref], [S('unit'), unit]]]])
        self.items.append(sym)

    def sym(self, ref, lib_id, x, y, rot=0, unit=1, value=None, nets=None, nc=(), fields=None, stub=2.54,
            stubs=None, ref_at=None, val_at=None, hide_val=False, raw=(), mirror=False):
        """Place a symbol.  nets: {pin number: net}; nc: pins flagged no-connect;
        raw: pins that are wired by hand (no automatic stub)."""
        fields = dict(fields or {})
        if value is None:
            value = lib_id.split(':')[1]
        self._symbol(ref, lib_id, x, y, rot, unit, value, fields, ref_at, val_at, hide_val=hide_val, mirror=mirror)
        pins = self.pin_xy(lib_id, unit, x, y, rot, mirror)
        nets = {str(k): v for k, v in (nets or {}).items()}
        ncs = [str(k) for k in nc]
        raws = [str(k) for k in raw]
        for num, plist in pins.items():
            for (px, py, d, name) in plist:
                if num in nets:
                    L = (stubs or {}).get(num, (stubs or {}).get(int(num) if num.isdigit() else num, stub))
                    self.net(px, py, d, nets[num], L)
                elif num in ncs:
                    if (r2(px), r2(py), 'NC') not in self.attach_seen:
                        self.attach_seen.add((r2(px), r2(py), 'NC'))
                        self.nc(px, py)
                elif num in raws:
                    pass
                else:
                    raise ValueError('%s pin %s (%s) not assigned' % (ref, num, name))
        for k in list(nets) + ncs + raws:
            if k not in pins:
                raise ValueError('%s has no pin %s' % (ref, k))
        self.refs[(ref, unit)] = pins
        return pins

    def two(self, ref, lib_id, x, y, n1, n2, value, fields, orient='v', stub=2.54, flip=False):
        """2-pin part. orient 'v': pin 1 on top; 'h': pin 1 on the left (flip swaps)."""
        if orient == 'v':
            rot = 180 if flip else 0
            ref_at, val_at = (x + 2.2, y - 1.3, 'left'), (x + 2.2, y + 1.3, 'left')
        else:
            rot = 270 if flip else 90
            ref_at, val_at = (x, y - 2.4, None), (x, y + 2.6, None)
        nets = {k: v for k, v in (('1', n1), ('2', n2)) if v is not None}
        raw = [k for k, v in (('1', n1), ('2', n2)) if v is None]
        return self.sym(ref, lib_id, x, y, rot, value=value, nets=nets, raw=raw, fields=fields,
                        stub=stub, ref_at=ref_at, val_at=val_at)

    # ---- output ------------------------------------------------------------
    def write(self, outdir, date, rev):
        self._emit_attach()
        lib_syms = [S('lib_symbols')] + [self.p.lib.flat(l) for l in self.used]
        doc = [S('kicad_sch'), [S('version'), 20250114], [S('generator'), 'eeschema'], [S('generator_version'), '9.0'],
               [S('uuid'), self.file_uuid], [S('paper'), self.paper],
               [S('title_block'), [S('title'), self.title], [S('date'), date], [S('rev'), rev],
                [S('company'), 'Solartron 7075 USB interface (RP2354A)'],
                [S('comment'), 1, 'Generated by scripts/gen_sch.py']],
               lib_syms] + self.items
        open(os.path.join(outdir, self.filename), 'w').write(dump(doc) + '\n')
