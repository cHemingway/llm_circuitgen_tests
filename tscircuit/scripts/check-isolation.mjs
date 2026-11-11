// Checks a routed circuit.json for copper of USB-side nets below the
// isolation strip or isolated-side nets above it (traces and vias), i.e.
// anything bridging the barrier. DRC errors recorded by the build are listed
// for information but do not fail the check.
// Usage: node scripts/check-isolation.mjs [dist/index/circuit.json]
import { readFileSync } from "node:fs"

const BARRIER_Y = 9 // keep in sync with lib/sections/Isolation.tsx
const STRIP = 1.0 // copper may approach the centre line to within this distance

const file = process.argv[2] ?? "dist/index/circuit.json"
const cj = JSON.parse(readFileSync(file, "utf8"))

// Nets that live on the isolated (DVM) side. Everything else is USB side.
const ISO_PREFIXES = [
  "GND_ISO",
  "V3V3_ISO",
  "V5_ISO",
  "ISO_SCK",
  "ISO_MOSI",
  "ISO_LATCH",
  "ISO_OE_N",
  "ISO_MISO",
  "SR_",
  "CMD_",
  "DVM_",
  "OC_MISO_AN",
]
const USB_SIDE_EXCEPTIONS = new Set([
  "ISO_SCK_TX",
  "ISO_MOSI_TX",
  "ISO_LATCH_TX",
  "ISO_OE_N_TX",
  "ISO_MISO_RX",
])
const sideOf = (net) =>
  !USB_SIDE_EXCEPTIONS.has(net) && ISO_PREFIXES.some((p) => net.startsWith(p))
    ? "iso"
    : "usb"

const keyToNet = new Map(
  cj
    .filter((e) => e.type === "source_net" && e.subcircuit_connectivity_map_key)
    .map((e) => [e.subcircuit_connectivity_map_key, e.name]),
)
const sourceTraces = new Map(
  cj
    .filter((e) => e.type === "source_trace")
    .map((e) => [e.source_trace_id, e]),
)
const netOfTrace = (t) => {
  const st = sourceTraces.get(t.source_trace_id)
  return keyToNet.get(
    st?.subcircuit_connectivity_map_key ?? t.subcircuit_connectivity_map_key,
  )
}

let problems = 0
const errors = cj.filter((e) => e.type.endsWith("_error"))
for (const e of errors) console.log(`DRC ${e.type}: ${e.message ?? ""}`)

let traces = 0
let unresolved = 0
for (const t of cj.filter((e) => e.type === "pcb_trace")) {
  const net = netOfTrace(t)
  if (!net) {
    unresolved++
    continue
  }
  traces++
  const side = sideOf(net)
  const bad = t.route.find((p) =>
    side === "usb" ? p.y < BARRIER_Y - STRIP : p.y > BARRIER_Y + STRIP,
  )
  if (bad) {
    console.log(`BARRIER ${net} (${side}) reaches (${bad.x}, ${bad.y})`)
    problems++
  }
}
for (const v of cj.filter((e) => e.type === "pcb_via")) {
  if (Math.abs(v.y - BARRIER_Y) < STRIP) {
    console.log(`BARRIER via at (${v.x}, ${v.y}) inside the isolation strip`)
    problems++
  }
}

console.log(
  `${traces} traces checked, ${unresolved} without a net, ${problems} barrier violations (${errors.length} DRC errors listed above)`,
)
process.exit(problems === 0 && unresolved === 0 ? 0 : 1)
