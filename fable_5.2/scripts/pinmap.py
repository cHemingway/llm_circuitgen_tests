"""Pin assignment shared by the schematic generator, the optimiser and the docs.

Everything on the multimeter side that can be exchanged without changing what the
circuit does is described here instead of being hard-wired in gen_sch.py:

* which 74HCT165 input reads which SKB pin (any of the 40 inputs will do, the
  firmware just reads a different bit of the 40-bit status stream);
* which element of which 100k pull-down array hangs on which SKB pin;
* which TPIC6C595 output drives which command line;
* the order of the registers in the two serial chains.

scripts/pinmap.json holds the assignment chosen by scripts/optimise.py.  Without
that file the original "bit n = SKB pin n+1" assignment is used.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, 'pinmap.json')

# SKB pin -> net (service manual page 9.9)
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
NET_PIN = {v: k for k, v in PIN_NET.items() if k != 37}

DESCR = {1: '1 x 10^6'}
for dec, base in ((5, 2), (4, 6), (3, 10), (2, 14), (1, 18), (0, 22)):
    for i, w in enumerate((8, 4, 2, 1)):
        DESCR[base + i] = '%d x 10^%d' % (w, dec)
DESCR.update({26: 'polarity +', 27: 'polarity -', 28: 'function out', 29: 'function out', 30: 'range out (4)',
              31: 'range out (2)', 32: 'range out (1)', 33: 'PRINT pulse', 34: 'PRINT level', 35: 'DATA CAN CHANGE',
              36: 'OVERLOAD', 38: 'FRONT PANEL LOCKOUT', 39: 'SAMPLE (contact to 0 V)', 40: 'SAMPLE pulse (via Q1)',
              41: 'RATIO', 42: 'FUNCTION', 43: 'FUNCTION', 44: 'INTEGRATION TIME (4)', 45: 'INTEGRATION TIME (2)',
              46: 'INTEGRATION TIME (1)', 47: 'AUTORANGE', 48: 'RANGE (1)', 49: 'RANGE (2)', 50: 'RANGE (4)'})

# status inputs: SKB 1..36 and the read-back of SKB 38
INPUT_NETS = [PIN_NET[n] for n in range(1, 37)] + ['DVM_FP_LOCKOUT']
# command outputs; PULSE_GATE drives SKB 40 through Q1
OUTPUT_NETS = ['DVM_FP_LOCKOUT', 'DVM_SAMPLE_CONTACT', 'PULSE_GATE', 'DVM_RATIO', 'DVM_FN_CMD_A', 'DVM_FN_CMD_B',
               'DVM_INT_CMD_4', 'DVM_INT_CMD_2', 'DVM_INT_CMD_1', 'DVM_AUTORANGE', 'DVM_RNG_CMD_1', 'DVM_RNG_CMD_2',
               'DVM_RNG_CMD_4']

U165 = ['U10', 'U11', 'U12', 'U13', 'U14']
U595 = ['U15', 'U16']
D165 = [11, 12, 13, 14, 3, 4, 5, 6]            # package pins of D0..D7
D595 = [3, 4, 5, 6, 11, 12, 13, 14]            # package pins of DRAIN0..DRAIN7
# series arrays: (D0..D3, D4..D7) of each register; element k of the array sits next to input k of its half
SER = {'U10': ('RN2', 'RN4'), 'U11': ('RN6', 'RN8'), 'U12': ('RN10', 'RN12'), 'U13': ('RN14', 'RN16'),
       'U14': ('RN18', 'RN20')}
PD = ['RN3', 'RN5', 'RN7', 'RN9', 'RN11', 'RN13', 'RN15', 'RN17', 'RN19', 'RN21']


def default():
    """The original assignment: status bit n = SKB pin n+1, command bit k = SKB pin 38+k."""
    groups = {'U10': [PIN_NET[n] for n in range(1, 9)], 'U11': [PIN_NET[n] for n in range(9, 17)],
              'U12': [PIN_NET[n] for n in range(17, 25)], 'U13': [PIN_NET[n] for n in range(25, 33)],
              'U14': [PIN_NET[33], PIN_NET[34], PIN_NET[35], PIN_NET[36], 'DVM_FP_LOCKOUT', 'ID1', 'ID0', 'ID0']}
    pm = {'chain165': list(U165), 'chain595': list(U595), 'inputs': {}, 'pulldown': {}, 'outputs': {}}
    for i, u in enumerate(U165):
        d = list(reversed(groups[u]))           # D0..D7 (D7 is shifted out first)
        pm['inputs'][u] = d
        for half in (0, 1):
            pm['pulldown'][PD[2 * i + half]] = {str(k + 1): d[half * 4 + k] for k in range(4)
                                                if not d[half * 4 + k].startswith('ID')}
    pm['outputs']['U15'] = OUTPUT_NETS[:8]
    pm['outputs']['U16'] = OUTPUT_NETS[8:] + [None] * 3
    return pm


def load():
    if os.path.exists(PATH):
        pm = json.load(open(PATH))
    else:
        pm = default()
    check(pm)
    return pm


def check(pm):
    ins = [s for u in U165 for s in pm['inputs'][u]]
    assert sorted(s for s in ins if not s.startswith('ID')) == sorted(INPUT_NETS), 'status inputs'
    assert sorted(s for s in ins if s.startswith('ID')) == ['ID0', 'ID0', 'ID1'], 'marker bits'
    pds = [s for rn in PD for s in pm['pulldown'].get(rn, {}).values()]
    assert sorted(pds) == sorted(INPUT_NETS), 'pull-downs'
    for rn in PD:
        pads = [int(p) for p in pm['pulldown'].get(rn, {})]
        assert len(set(min(p, 9 - p) for p in pads)) == len(pads), 'two nets on one resistor of ' + rn
    outs = [s for u in U595 for s in pm['outputs'][u] if s]
    assert sorted(outs) == sorted(OUTPUT_NETS), 'command outputs'
    assert sorted(pm['chain165']) == U165 and sorted(pm['chain595']) == U595


def verify_netlist(pm, nets):
    """Check the netlist exported from the schematic against the pin map: every SKB line must
    reach exactly its series resistor, its pull-down and (commands) its driver, and nothing else.
    nets: {net name: [(ref, pad), ...]}.  Raises AssertionError with the first mismatch."""
    def short(n):
        return n.rsplit('/', 1)[-1] if n.startswith('/') else n
    by = {short(n): set(map(tuple, v)) for n, v in nets.items()}
    of = {node: n for n, v in by.items() for node in v}
    for n in range(1, 51):
        assert of[('J1', str(n))] == PIN_NET[n], 'SKB %d is on net %s' % (n, of[('J1', str(n))])
    exp = {net: {('J1', str(NET_PIN[net]))} for net in set(INPUT_NETS) | set(OUTPUT_NETS) - {'PULSE_GATE'}}
    exp['DVM_SAMPLE_PULSE'] = {('J1', '40'), ('R26', '2'), ('R27', '1')}
    exp['PULSE_GATE'] = {('Q1', '1'), ('R25', '2')}
    for u in U165:
        for d, net in enumerate(pm['inputs'][u]):
            upin = (u, str(D165[d]))
            if net.startswith('ID'):
                assert of[upin] == ('+5V_ISO' if net == 'ID1' else 'GND_ISO'), 'marker bit at %s %s' % upin
                continue
            arr, k = SER[u][d // 4], d % 4
            exp[net].add((arr, str(k + 1)))
            link = {upin, (arr, str(8 - k))} | ({('U8', '5')} if net == 'DVM_PRINT_LEVEL' else set())
            assert by[of[upin]] == link, 'series resistor of %s: %s' % (net, sorted(by[of[upin]]))
    for rn, m in pm['pulldown'].items():
        for pad, net in m.items():
            exp[net].add((rn, pad))
            assert of[(rn, str(9 - int(pad)))] == 'GND_ISO', 'pull-down of %s not grounded' % net
    for u in U595:
        for d, net in enumerate(pm['outputs'][u]):
            if net:
                exp[net].add((u, str(D595[d])))
    for net, nodes in exp.items():
        assert by.get(net) == nodes, 'net %s: expected %s, schematic has %s' % (net, sorted(nodes), sorted(by.get(net, [])))
    ch = pm['chain165']
    assert ('U8', '2') in by['MISO_ISO'] and (ch[0], '9') in by['MISO_ISO']
    for a, b in zip(ch, ch[1:]):
        assert of[(a, '10')] == of[(b, '9')], 'register chain %s <- %s' % (a, b)
    assert of[(ch[-1], '10')] == 'GND_ISO'
    a, b = pm['chain595']
    assert of[(a, '2')] == 'MOSI_ISO' and of[(a, '9')] == of[(b, '2')], 'driver chain'


def status_bits(pm):
    """[(register, input name, net)] in the order the bits appear at MISO."""
    out = []
    for u in pm['chain165']:
        for d in range(7, -1, -1):
            out.append((u, 'D%d' % d, pm['inputs'][u][d]))
    return out


def command_bits(pm):
    """[(register, output name, net or None)]; index = bit number of the 16-bit command word."""
    out = []
    for u in pm['chain595']:
        for d in range(8):
            out.append((u, 'DRAIN%d' % d, pm['outputs'][u][d]))
    return out


def marker(pm):
    """Value of the three hard-wired bits as (bit number, value)."""
    return [(i, 1 if s == 'ID1' else 0) for i, (_, _, s) in enumerate(status_bits(pm)) if s.startswith('ID')]


def skb(net):
    return 40 if net == 'PULSE_GATE' else NET_PIN[net]


def sch_text_status(pm):
    lines = ['Serial stream at MISO after a LATCH pulse; bit 0 is shifted out first.',
             'Numbers are SKB pins, "=1" / "=0" are hard-wired marker bits (chain length check).']
    bits = status_bits(pm)
    for i, u in enumerate(pm['chain165']):
        cells = []
        for (_, _, s) in bits[8 * i: 8 * i + 8]:
            cells.append('=1' if s == 'ID1' else '=0' if s == 'ID0' else '%d' % skb(s))
        lines.append('  bit %2d..%2d  %s D7..D0 :  %s' % (8 * i, 8 * i + 7, u, '  '.join('%2s' % c for c in cells)))
    lines.append('SKB 38 is the read-back of the FRONT PANEL LOCKOUT line (high = DVM powered).')
    return '\n'.join(lines)


def sch_text_command(pm):
    bits = command_bits(pm)
    lines = ['Command word = the last 16 bits clocked into MOSI before LATCH rises (MSB first):']
    for k in range(8):
        cells = []
        for i in (k, k + 8):
            s = bits[i][2]
            cells.append('bit %-2d -> %-34s' % (i, 'spare' if s is None else 'SKB %d %s' % (skb(s), DESCR[skb(s)])))
        lines.append('  ' + ''.join(cells).rstrip())
    return '\n'.join(lines)


def markdown(pm):
    """Bit tables for the README."""
    out = ['**Status stream** (40 bits, bit 0 is shifted out first):', '',
           '| Bit | Register input | SKB pin | Signal |', '|---|---|---|---|']
    for i, (u, d, s) in enumerate(status_bits(pm)):
        if s.startswith('ID'):
            out.append('| %d | %s %s | - | hard-wired %s |' % (i, u, d, s[2]))
        else:
            n = skb(s)
            out.append('| %d | %s %s | %d | %s |' % (i, u, d, n, DESCR[n] + (' (read-back)' if n == 38 else '')))
    out += ['', '**Command word** (16 bits, sent MSB first, so bit 15 goes out first):', '',
            '| Bit | Register output | SKB pin | Signal |', '|---|---|---|---|']
    for i, (u, d, s) in enumerate(command_bits(pm)):
        if s is None:
            out.append('| %d | %s %s | - | spare |' % (i, u, d))
        else:
            out.append('| %d | %s %s | %d | %s |' % (i, u, d, skb(s), DESCR[skb(s)]))
    return '\n'.join(out)


def c_header(pm):
    """Bit numbers as C macros for the firmware."""
    out = ['/* Generated by scripts/pinmap.py from scripts/pinmap.json - do not edit.',
           ' * Bit positions in the 40-bit status stream (bit 0 = first bit shifted out of MISO)',
           ' * and in the 16-bit command word (bit 15 is sent first). */', '#pragma once', '']
    bits = status_bits(pm)
    for n in range(1, 37):
        i = [k for k, b in enumerate(bits) if b[2] == PIN_NET[n]][0]
        out.append('#define ST_SKB%-2d %2d   /* %s */' % (n, i, DESCR[n]))
    i = [k for k, b in enumerate(bits) if b[2] == 'DVM_FP_LOCKOUT'][0]
    out.append('#define ST_SKB38 %2d   /* FRONT PANEL LOCKOUT line read-back */' % i)
    for (i, v) in marker(pm):
        out.append('#define ST_MARKER_BIT_%d %d   /* always reads %d */' % (i, i, v))
    out.append('')
    for i, (u, d, s) in enumerate(command_bits(pm)):
        if s is not None:
            out.append('#define CMD_SKB%-2d %2d   /* %s */' % (skb(s), i, DESCR[skb(s)]))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    print(markdown(load()))
