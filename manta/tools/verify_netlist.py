#!/usr/bin/env python3
"""Checks on the linked netlist that manta's ERC cannot make, because they are
about this board's intent rather than the language's rules.

1. Isolation. Every net is assigned to the USB side or the meter side by
   flooding outwards from GND and from ISO-GND through every component. The
   barrier parts are split into their two halves first, so the flood cannot
   cross them. The check fails if any net is reached from both grounds, if any
   net is reached from neither, or if a barrier half lands on the wrong side.

2. Bit order. The '165 and '595 chains are simulated from the netlist's own
   connectivity, starting at the RP2354 pins, so the firmware bit map printed
   here is what the copper does, not what a comment says.

Usage: python3 tools/verify_netlist.py output/solartron7075.mantaNets
Exits non-zero on any failure.
"""

import json
import re
import sys

# Pins on each side of each barrier part. Anything listed under "usb" must
# land on GND's side, "meter" on ISO-GND's.
BARRIER = {
    "TLP2361":     {"in": {"1", "3"}, "out": {"4", "5", "6"}},
    "B0509S-1WR3": {"in": {"1", "2"}, "out": {"3", "4"}},
}
FORWARD_OPTOS = {"U10", "U11", "U12", "U13"}   # LED on the USB side
RETURN_OPTOS = {"U14"}                         # LED on the meter side


def load(path):
    d = json.load(open(path))
    comps = {c["designator"]: c for c in d["components"]}
    nets = {n["name"]: n for n in d["nets"]}
    pin_net = {}
    for n in d["nets"]:
        for p in n["pins"]:
            pin_net[(p["designator"], p["pin"])] = n["name"]
    return comps, nets, pin_net


def node_of(comps, des, pin):
    """The graph node a component pin belongs to: barrier parts are two nodes."""
    part = comps[des]["part"]
    if part in BARRIER:
        half = "in" if pin in BARRIER[part]["in"] else "out"
        return f"{des}/{half}"
    return des


def check_isolation(comps, nets, pin_net):
    # Bipartite graph of nets and component nodes, flooded from each ground.
    adj = {}
    for (des, pin), net in pin_net.items():
        a, b = "net:" + net, "cmp:" + node_of(comps, des, pin)
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    def flood(start):
        seen, todo = {start}, [start]
        while todo:
            for nxt in adj.get(todo.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    usb, meter = flood("net:GND"), flood("net:ISO-GND")
    errors = []
    both = sorted(x[4:] for x in usb & meter if x.startswith("net:"))
    if both:
        errors.append("nets reached from both grounds: " + ", ".join(both))
    # A harness declaration is listed as a net with no pins of its own.
    orphan = sorted(n for n in nets if nets[n]["pins"] and "net:" + n not in usb | meter)
    if orphan:
        errors.append("nets reached from neither ground: " + ", ".join(orphan))
    for des, c in comps.items():
        if c["part"] not in BARRIER:
            continue
        led_usb = des in FORWARD_OPTOS or c["part"] == "B0509S-1WR3"
        want_in, want_out = (usb, meter) if led_usb else (meter, usb)
        if "cmp:" + des + "/in" not in want_in or "cmp:" + des + "/out" not in want_out:
            errors.append(f"{des} does not straddle the barrier the right way round")
    usb_nets = sorted(x[4:] for x in usb if x.startswith("net:"))
    meter_nets = sorted(x[4:] for x in meter if x.startswith("net:"))
    return errors, usb_nets, meter_nets


def driver_of(nets, net, want_logical):
    for p in nets[net]["pins"]:
        if re.fullmatch(want_logical, p["logical"]):
            return p
    return None


def pins_named(comps, des):
    return {p["name"]: p["pin"] for p in comps[des]["pins"]}


def trace_to_skb(nets, pin_net, net):
    """Follow a '165 input net back through the series network to a J1 position,
    or report what the input is tied to instead."""
    if net in ("ISO-5V", "ISO-GND", "nSR-OE", "CMD-LOOP"):
        return net
    for p in nets[net]["pins"]:
        if p["designator"].startswith("RN"):
            # Element n joins pad n to pad 9-n.
            other = str(9 - int(p["pin"]))
            far = pin_net[(p["designator"], other)]
            for q in nets[far]["pins"]:
                if q["designator"] == "J1":
                    return "SKB " + q["pin"]
    return "?" + net


def simulate_165(comps, nets, pin_net):
    # From the RP2354's MISO pin back across U14 to the first '165.
    opto = driver_of(nets, "MCU-MISO", "VO")["designator"]
    led_net = pin_net[(opto, "1")]
    src = [p for p in nets[led_net]["pins"] if p["designator"] != opto]
    res = pin_net[(src[0]["designator"], "1" if src[0]["pin"] == "2" else "2")]
    first = driver_of(nets, res, r"nQ7")
    chain, des = [], first["designator"]
    # nQ7 then the opto each invert, so MISO reads Q7 true.
    while des:
        chain.append(des)
        ds_net = pin_net[(des, pins_named(comps, des)["DS"])]
        nxt = driver_of(nets, ds_net, "Q7")
        des = nxt["designator"] if nxt else None
    order = []
    for des in chain:
        names = pins_named(comps, des)
        for bit in range(7, -1, -1):
            net = pin_net[(des, names[f"D[{bit}]"])]
            order.append((des, f"D{bit}", trace_to_skb(nets, pin_net, net)))
    return chain, order


def simulate_595(comps, nets, pin_net):
    # From the RP2354's MOSI pin across U11 to the first '595.
    opto = [p for p in nets["SR-DIN"]["pins"] if p["logical"] == "VO"][0]["designator"]
    first = driver_of(nets, "SR-DIN", "DS")["designator"]
    chain, des = [], first
    while des:
        chain.append(des)
        q7s_net = pin_net[(des, pins_named(comps, des)["Q7S"])]
        nxt = driver_of(nets, q7s_net, "DS")
        des = nxt["designator"] if nxt and nxt["designator"] in comps and \
            comps[nxt["designator"]]["part"] == "74HCT595" else None
    # Clock in 16 marked bits; the first one in ends deepest in the chain.
    regs = {d: [None] * 8 for d in chain}
    for k in range(16):
        carry = k + 1
        for d in chain:
            out = regs[d][7]
            regs[d] = [carry] + regs[d][:7]
            carry = out
    result = []
    for d in chain:
        names = pins_named(comps, d)
        for q in range(8):
            net = pin_net.get((d, names[f"Q[{q}]"]))
            skb = None
            if net:
                for p in nets[net]["pins"]:
                    if p["designator"] == "J1":
                        skb = p["pin"]
            result.append((regs[d][q], d, f"Q{q}", skb))
    result.sort()
    return opto, chain, result


def main():
    comps, nets, pin_net = load(sys.argv[1])
    errors, usb_nets, meter_nets = check_isolation(comps, nets, pin_net)
    print(f"isolation: {len(usb_nets)} nets on the USB side, {len(meter_nets)} on the meter side")

    chain, order = simulate_165(comps, nets, pin_net)
    print("\n'165 chain, nearest the barrier first:", " -> ".join(chain))
    print("MISO bit (first after the latch = 1) : register input : source")
    for i, (des, d, src) in enumerate(order, 1):
        print(f"  bit {i:2d} : {des}.{d} : {src}")
        if i <= 36 and src != f"SKB {i}":
            errors.append(f"MISO bit {i} reads {src}, expected SKB {i}")

    opto, chain, result = simulate_595(comps, nets, pin_net)
    print(f"\n'595 chain from {opto}:", " -> ".join(chain))
    print("Of the last 16 bits clocked in (1 = first of them):")
    for k, des, q, skb in result:
        print(f"  bit {k:2d} : {des}.{q} : " + (f"SKB {skb}" if skb else "spare"))
        if skb and int(skb) != 37 + k:
            errors.append(f"command bit {k} drives SKB {skb}, expected SKB {37 + k}")

    for e in errors:
        print("ERROR:", e)
    print("\nOK" if not errors else f"\n{len(errors)} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
