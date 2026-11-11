// Prepares a routed circuit.json for Gerber export. Copper geometry is not
// changed; this works around two tscircuit 0.0.2745 export problems.
//
// 1. Rotated rectangular pads (U2, U3) are written as an aperture plus a
//    Gerber %LR (load rotation) command. Viewers and CAM tools that predate
//    the 2016 spec ignore %LR and draw those pads unrotated, which merges
//    U3's pads into shorts. Pads rotated by a multiple of 90 degrees are
//    rewritten as plain rectangles with the same outline.
// 2. The solder paste layer is wrong in three ways:
//    - pill and polygon pads get no paste (every SOIC, TLP2361 and the
//      SOT-89 tab);
//    - every plated through hole gets paste on both sides;
//    - other pads get 70 % linear apertures, which on the RP2354A's 0.2 mm
//      pins gives an area ratio below the 0.66 needed for clean release.
//    Paste is rebuilt with 1:1 apertures on every SMD pad, a 2 x 2 windowpane
//    (about 60 % coverage) on exposed pads over 4 mm^2, and none on THT holes.
// Usage: node scripts/prepare-fab.mjs dist/index/circuit.json dist/fab/circuit.json
import { readFileSync, writeFileSync } from "node:fs"

const [input, output] = process.argv.slice(2)
if (!input || !output) {
  console.error("usage: node scripts/prepare-fab.mjs in.json out.json")
  process.exit(2)
}
const cj = JSON.parse(readFileSync(input, "utf8"))

let unrotated = 0
for (const pad of cj) {
  if (pad.type !== "pcb_smtpad" || pad.shape !== "rotated_rect") continue
  const quarter = (((pad.ccw_rotation ?? 0) % 360) + 360) % 360 / 90
  if (Math.abs(quarter - Math.round(quarter)) > 1e-6) continue
  const swap = Math.round(quarter) % 2 === 1
  ;[pad.width, pad.height] = swap ? [pad.height, pad.width] : [pad.width, pad.height]
  pad.shape = "rect"
  delete pad.ccw_rotation
  unrotated++
}

const LARGE_PAD_MM2 = 4
const WINDOW_GAP = 0.5 // mm between windowpane apertures
const ARC_SEGMENTS = 12 // per pill end

const rotate = (x, y, deg) => {
  const a = (deg * Math.PI) / 180
  return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)]
}

// Stadium outline for a (rotated) pill pad, long axis along the larger side
const pillPoints = (p) => {
  const long = Math.max(p.width, p.height)
  const r = Math.min(p.radius ?? Infinity, Math.min(p.width, p.height) / 2)
  const half = long / 2 - r
  const axisDeg = (p.ccw_rotation ?? 0) + (p.width >= p.height ? 0 : 90)
  const pts = []
  for (const [cx, start] of [
    [half, -90],
    [-half, 90],
  ]) {
    for (let i = 0; i <= ARC_SEGMENTS; i++) {
      const a = ((start + (180 * i) / ARC_SEGMENTS) * Math.PI) / 180
      const [x, y] = rotate(cx + r * Math.cos(a), r * Math.sin(a), axisDeg)
      pts.push({ x: p.x + x, y: p.y + y })
    }
  }
  return pts
}

const pasteFor = (pad) => {
  const base = {
    type: "pcb_solder_paste",
    layer: pad.layer,
    pcb_component_id: pad.pcb_component_id,
    pcb_smtpad_id: pad.pcb_smtpad_id,
    subcircuit_id: pad.subcircuit_id,
    pcb_group_id: pad.pcb_group_id,
  }
  switch (pad.shape) {
    case "circle":
      return [{ ...base, shape: "circle", x: pad.x, y: pad.y, radius: pad.radius }]
    case "rect":
    case "rotated_rect": {
      const rot = pad.shape === "rotated_rect" ? pad.ccw_rotation ?? 0 : 0
      if (pad.width * pad.height <= LARGE_PAD_MM2) {
        return [
          rot
            ? { ...base, shape: "rotated_rect", x: pad.x, y: pad.y, width: pad.width, height: pad.height, ccw_rotation: rot }
            : { ...base, shape: "rect", x: pad.x, y: pad.y, width: pad.width, height: pad.height },
        ]
      }
      // Windowpane for exposed/thermal pads
      const w = (pad.width - WINDOW_GAP) / 2 - 0.1
      const h = (pad.height - WINDOW_GAP) / 2 - 0.1
      const dx = (w + WINDOW_GAP) / 2
      const dy = (h + WINDOW_GAP) / 2
      return [
        [-dx, -dy],
        [dx, -dy],
        [-dx, dy],
        [dx, dy],
      ].map(([ox, oy]) => {
        const [x, y] = rotate(ox, oy, rot)
        return { ...base, shape: "rect", x: pad.x + x, y: pad.y + y, width: w, height: h }
      })
    }
    case "pill":
    case "rotated_pill":
      return [{ ...base, shape: "polygon", points: pillPoints(pad) }]
    case "polygon":
      return [{ ...base, shape: "polygon", points: pad.points }]
    default:
      throw new Error(`no paste rule for pad shape ${pad.shape}`)
  }
}

const out = cj.filter((e) => e.type !== "pcb_solder_paste")
let n = 0
let pads = 0
for (const pad of cj.filter((e) => e.type === "pcb_smtpad")) {
  if (pad.is_covered_with_solder_mask) continue
  pads++
  for (const paste of pasteFor(pad)) {
    out.push({ ...paste, pcb_solder_paste_id: `pcb_solder_paste_fab_${n++}` })
  }
}
const before = cj.filter((e) => e.type === "pcb_solder_paste").length
writeFileSync(output, JSON.stringify(out))
console.log(`Pads: ${unrotated} rotated rectangles rewritten without %LR`)
console.log(`Paste: ${before} tscircuit apertures replaced by ${n} for ${pads} SMD pads (no paste on THT holes)`)
