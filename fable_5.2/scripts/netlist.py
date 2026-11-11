"""Read a KiCad s-expression netlist (kicad-cli sch export netlist --format kicadsexpr)."""
from sx import parse, find, first


def load(path):
    t = parse(open(path).read())
    comps = {}
    for c in find(first(t, 'components'), 'comp'):
        ref = first(c, 'ref')[1]
        fields = {}
        for f in find(first(c, 'fields') or [], 'field'):
            fields[first(f, 'name')[1]] = f[2] if len(f) > 2 else ''
        sp = first(c, 'sheetpath')
        comps[ref] = {
            'value': first(c, 'value')[1],
            'footprint': first(c, 'footprint')[1],
            'fields': fields,
            'sheet_names': first(sp, 'names')[1],
            'sheet_tstamps': first(sp, 'tstamps')[1],
            'tstamps': first(c, 'tstamps')[1:],
            'lib': first(first(c, 'libsource'), 'lib')[1] + ':' + first(first(c, 'libsource'), 'part')[1],
            'description': (first(c, 'description') or [None, ''])[1],
        }
    nets = {}
    for n in find(first(t, 'nets'), 'net'):
        name = first(n, 'name')[1]
        nets[name] = [(first(nd, 'ref')[1], first(nd, 'pin')[1]) for nd in find(n, 'node')]
    return comps, nets
