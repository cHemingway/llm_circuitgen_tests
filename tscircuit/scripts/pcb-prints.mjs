// Renders the Gerbers in a zip to a multi-page vector PDF of PCB prints
// (A4 landscape: 1:1 board views, then 2:1 copper, assembly, stencil and
// drill sheets) and to top/bottom PNG renders. Everything is drawn from the
// Gerber and drill files, so the prints show exactly what the fab receives.
// Usage: node scripts/pcb-prints.mjs gerbers.zip out.pdf [pngPrefix]
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Resvg } from "@resvg/resvg-js"
import { unzipSync, strFromU8 } from "fflate"
import gerberToSvg from "gerber-to-svg"
import pcbStackup from "pcb-stackup"

const [zipPath, pdfPath, pngPrefix] = process.argv.slice(2)
if (!zipPath || !pdfPath) {
  console.error("usage: node scripts/pcb-prints.mjs gerbers.zip out.pdf [pngPrefix]")
  process.exit(2)
}

const PROJECT = "Solartron 7075 USB interface (RP2354A)"
const STACKUP = "2 layers, 1.6 mm FR-4"
const PAGE_W = 297
const PAGE_H = 210
const FONT = "DejaVu Sans, Liberation Sans, Arial, sans-serif"

const files = Object.fromEntries(
  Object.entries(unzipSync(readFileSync(zipPath))).map(([k, v]) => [k, strFromU8(v)]),
)
const need = (name) => {
  if (!(name in files)) throw new Error(`${name} missing from ${zipPath}`)
  return files[name]
}
const drillName = Object.keys(files).find((f) => f.endsWith(".drl"))

// ---- Gerber layers -------------------------------------------------------
// gerber-to-svg draws clear-polarity features (the pour cut-outs) as SVG
// masks, which Chromium prints as thousands of bitmap tiles. Every layer here
// is drawn straight onto white paper, so each masked group is flattened into
// its content followed by the cleared shapes painted in the paper colour.
const PAPER = "#fff"
const h = (tag, attrs = {}, children = []) => ({ tag, attrs, children })
const flattenMasks = (defs, layer) => {
  const masks = new Map()
  for (const d of defs) {
    if (d.tag !== "mask") continue
    const shapes = d.children.flatMap((c) => (c.tag === "g" ? c.children : [c]))
    masks.set(d.attrs.id, shapes.filter((c) => !(c.tag === "rect" && c.attrs.fill === "#fff")))
  }
  const walk = (node) => {
    if (typeof node === "string") return [node]
    const children = node.children.flatMap(walk)
    const id = node.attrs.mask?.match(/url\(#(.+)\)/)?.[1]
    if (node.tag === "g" && id && masks.has(id)) {
      const { mask, ...attrs } = node.attrs
      return [h("g", attrs, children), h("g", { fill: PAPER, stroke: PAPER, "data-paper": 1 }, masks.get(id))]
    }
    return [{ ...node, children }]
  }
  return { defs: defs.filter((d) => d.tag !== "mask"), layer: layer.flatMap(walk) }
}
const serialize = (node, paper = false) => {
  if (typeof node === "string") return node
  paper ||= Boolean(node.attrs["data-paper"])
  const attrs = Object.entries(node.attrs)
    .filter(([k]) => k !== "data-paper")
    .map(([k, v]) => `${k}="${paper && (k === "fill" || k === "stroke") && v !== "none" ? PAPER : v}"`)
    .join(" ")
  const inner = node.children.map((c) => serialize(c, paper)).join("")
  return `<${node.tag}${attrs ? ` ${attrs}` : ""}${inner ? `>${inner}</${node.tag}>` : "/>"}`
}
const convert = (name, id) =>
  new Promise((ok, fail) => {
    const conv = gerberToSvg(need(name), { id, objectMode: true, createElement: h }, (err) => {
      if (err) return fail(err)
      const flat = flattenMasks(conv.defs, conv.layer)
      ok({ defs: flat.defs.map((n) => serialize(n)).join(""), layer: flat.layer.map((n) => serialize(n)).join(""), viewBox: conv.viewBox, id })
    })
  })
const L = {}
for (const [key, name] of Object.entries({
  fcu: "F_Cu.gbr",
  bcu: "B_Cu.gbr",
  fmask: "F_Mask.gbr",
  bmask: "B_Mask.gbr",
  fsilk: "F_SilkScreen.gbr",
  bsilk: "B_SilkScreen.gbr",
  fpaste: "F_Paste.gbr",
  bpaste: "B_Paste.gbr",
  ffab: "F_Fab.gbr",
  edge: "Edge_Cuts.gbr",
})) {
  L[key] = await convert(name, `g${key}`)
}

// Board extent from the outline (Gerber units, mm)
const [ex, ey, ew, eh] = L.edge.viewBox.map((v) => v / 1000)
const board = { cx: ex + ew / 2, cy: ey + eh / 2, w: ew, h: eh }

// ---- Drill file (Excellon, metric decimal) -------------------------------
const holes = []
{
  const tools = {}
  let tool = null
  for (const line of need(drillName).split(/\r?\n/)) {
    let m = line.match(/^T(\d+)C([\d.]+)/)
    if (m) {
      tools[m[1]] = Number(m[2])
      continue
    }
    m = line.match(/^T(\d+)$/)
    if (m) {
      tool = tools[m[1]]
      continue
    }
    m = line.match(/^X(-?[\d.]+)Y(-?[\d.]+)/)
    if (m && tool) holes.push({ x: Number(m[1]), y: Number(m[2]), d: Math.round(tool * 100) / 100 })
  }
}
const plated = /TF\.FileFunction,Plated/.test(need(drillName))
const drillSizes = [...new Set(holes.map((h) => h.d))].sort((a, b) => a - b)

// ---- Drawing helpers (page units: mm) ------------------------------------
let uid = 0
const xmlText = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
const text = (x, y, s, { size = 3, anchor = "start", weight = "normal", fill = "#000" } = {}) =>
  `<text x="${x}" y="${y}" font-size="${size}" font-family="${FONT}" font-weight="${weight}" text-anchor="${anchor}" fill="${fill}">${xmlText(s)}</text>`

// Places a view so the board centre lands on (px, py); bottom views are mirrored in x
const view = ({ px, py, scale, mirror }) => ({ px, py, sx: (mirror ? -1 : 1) * scale, sy: -scale })
// One Gerber layer in a view. IDs are made unique per use.
const layer = (v, Lr, color) => {
  const tag = `${Lr.id}u${uid++}`
  const body = (Lr.defs ? `<defs>${Lr.defs}</defs>` : "") + Lr.layer
  return `<g transform="translate(${v.px} ${v.py}) scale(${v.sx / 1000} ${v.sy / 1000}) translate(${-board.cx * 1000} ${-board.cy * 1000})" fill="currentColor" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="0" fill-rule="evenodd" color="${color}">${body.replaceAll(`${Lr.id}_`, `${tag}_`)}</g>`
}
// Arbitrary board-coordinate content (mm) in a view
const boardGroup = (v, inner) =>
  `<g transform="translate(${v.px} ${v.py}) scale(${v.sx} ${v.sy}) translate(${-board.cx} ${-board.cy})">${inner}</g>`
const drillHoles = (v, fill = "#fff") =>
  boardGroup(v, holes.map((h) => `<circle cx="${h.x}" cy="${h.y}" r="${h.d / 2}" fill="${fill}"/>`).join(""))
const boardBox = (v) => ({
  x0: v.px - (board.w * Math.abs(v.sx)) / 2,
  x1: v.px + (board.w * Math.abs(v.sx)) / 2,
  y0: v.py - (board.h * Math.abs(v.sy)) / 2,
  y1: v.py + (board.h * Math.abs(v.sy)) / 2,
})

const scaleBar = (x, y, scale, lengthMm = 20, step = 5) => {
  let s = `<g stroke="#000" stroke-width="0.25">`
  s += `<line x1="${x}" y1="${y}" x2="${x + lengthMm * scale}" y2="${y}"/>`
  for (let d = 0; d <= lengthMm; d += step) {
    const xx = x + d * scale
    s += `<line x1="${xx}" y1="${y - 1.5}" x2="${xx}" y2="${y}"/>`
  }
  for (let d = 0; d < lengthMm; d += step) {
    if ((d / step) % 2 === 0) s += `<rect x="${x + d * scale}" y="${y - 0.8}" width="${step * scale}" height="0.8" fill="#000" stroke="none"/>`
  }
  s += `</g>`
  for (let d = 0; d <= lengthMm; d += step) s += text(x + d * scale, y + 3.2, d, { size: 2.4, anchor: "middle" })
  s += text(x + lengthMm * scale + 3, y + 0.8, "mm", { size: 2.4 })
  return s
}

// Dimension line with arrows; horizontal if y1 === y2
const dimension = (x1, y1, x2, y2, label) => {
  const horiz = y1 === y2
  const a = 1.2
  const arrows = horiz
    ? `<path d="M${x1} ${y1} l${a} ${-a / 2.5} v${(2 * a) / 2.5} z M${x2} ${y2} l${-a} ${-a / 2.5} v${(2 * a) / 2.5} z"/>`
    : `<path d="M${x1} ${y1} l${-a / 2.5} ${a} h${(2 * a) / 2.5} z M${x2} ${y2} l${-a / 2.5} ${-a} h${(2 * a) / 2.5} z"/>`
  const t = horiz
    ? text((x1 + x2) / 2, y1 - 1.2, label, { size: 2.6, anchor: "middle" })
    : `<g transform="translate(${x1 - 1.2} ${(y1 + y2) / 2}) rotate(-90)">${text(0, 0, label, { size: 2.6, anchor: "middle" })}</g>`
  return `<g fill="#000" stroke="#000" stroke-width="0.2"><line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>${arrows}</g>${t}`
}

// Frame, title block and the notes panel on the right
const frame = (n, total, { title, viewNote, scaleNote, notes = [], legend = [] }) => {
  const tx = 200
  const tw = PAGE_W - 8 - tx
  let s = `<rect x="8" y="8" width="${PAGE_W - 16}" height="${PAGE_H - 16}" fill="none" stroke="#000" stroke-width="0.35"/>`
  s += `<line x1="${tx - 4}" y1="8" x2="${tx - 4}" y2="${PAGE_H - 8}" stroke="#000" stroke-width="0.25"/>`
  // notes
  let ny = 18
  for (const [i, note] of notes.entries()) {
    if (i === 0) {
      s += text(tx, ny, note, { size: 3.4, weight: "bold" })
      ny += 7
    } else if (note === "") ny += 2.5
    else {
      s += text(tx, ny, note, { size: 2.7 })
      ny += 4.2
    }
  }
  ny += 4
  for (const [color, label] of legend) {
    s += legendSwatch(tx, ny, color, label)
    ny += 5.5
  }
  // title block
  const rows = [
    ["Project", PROJECT],
    ["Sheet", title],
    ["View", viewNote],
    ["Scale", scaleNote],
    ["Board", `${board.w.toFixed(0)} x ${board.h.toFixed(0)} mm, ${STACKUP}`],
    ["Source", "tscircuit/outputs/gerbers.zip"],
  ]
  const rh = 6.5
  const ty = PAGE_H - 8 - rh * (rows.length + 1)
  s += `<g stroke="#000" stroke-width="0.25" fill="none"><rect x="${tx - 4}" y="${ty}" width="${tw + 4}" height="${rh * (rows.length + 1)}"/>`
  for (let i = 1; i <= rows.length; i++) s += `<line x1="${tx - 4}" y1="${ty + rh * i}" x2="${PAGE_W - 8}" y2="${ty + rh * i}"/>`
  s += `<line x1="${tx + 12}" y1="${ty}" x2="${tx + 12}" y2="${ty + rh * rows.length}"/></g>`
  rows.forEach(([k, v], i) => {
    s += text(tx - 2, ty + rh * i + 4.4, k, { size: 2.3, fill: "#444" })
    s += text(tx + 14, ty + rh * i + 4.4, v, { size: k === "Sheet" ? 3 : 2.4, weight: k === "Sheet" ? "bold" : "normal" })
  })
  s += text(tx - 2, ty + rh * rows.length + 4.4, `Print at 100 % (actual size)`, { size: 2.3, fill: "#444" })
  s += text(PAGE_W - 10, ty + rh * rows.length + 4.4, `${n} / ${total}`, { size: 2.8, anchor: "end", weight: "bold" })
  return s
}

const legendSwatch = (x, y, color, label) =>
  `<rect x="${x}" y="${y - 2.6}" width="5" height="3.2" fill="${color}" stroke="#000" stroke-width="0.15"/>` +
  text(x + 7, y, label, { size: 2.6 })

// Reference designators at part centres, from the pick-and-place file
const placements = need("pick_and_place.csv")
  .trim()
  .split(/\r?\n/)
  .slice(1)
  .map((line) => line.split(",").map((f) => f.replace(/^"|"$/g, "")))
  .map(([ref, x, y, side]) => ({ ref, x: Number(x), y: Number(y), side }))
const REFDES = "#1f4fbf"
const refdes = (v, side) =>
  placements
    .filter((p) => p.side === side)
    .map((p) => {
      const x = v.px + (p.x - board.cx) * v.sx
      const y = v.py + (p.y - board.cy) * v.sy
      return `<text x="${x}" y="${y}" font-size="${side === "top" ? 1.6 : 2.6}" font-family="${FONT}" font-weight="bold" text-anchor="middle" dominant-baseline="central" fill="${REFDES}" stroke="#fff" stroke-width="0.4" paint-order="stroke">${xmlText(p.ref)}</text>`
    })
    .join("")

// ---- Realistic renders ---------------------------------------------------
const stack = await pcbStackup(
  ["F_Cu.gbr", "B_Cu.gbr", "F_Mask.gbr", "B_Mask.gbr", "F_SilkScreen.gbr", "B_SilkScreen.gbr", "F_Paste.gbr", "B_Paste.gbr", "Edge_Cuts.gbr", drillName].map(
    (filename) => ({ filename, gerber: need(filename) }),
  ),
  { useOutline: true, id: "stackup" },
)
// The renders rely on masks too, so they go into the PDF as 500 dpi images
const renderPng = (side, widthPx) =>
  new Resvg(stack[side].svg, { fitTo: { mode: "width", value: widthPx }, background: "#ffffff" }).render().asPng()
const embedRender = (side, x, y, w, hgt) =>
  `<image x="${x}" y="${y}" width="${w}" height="${hgt}" href="data:image/png;base64,${renderPng(side, Math.round((w / 25.4) * 500)).toString("base64")}"/>`

if (pngPrefix) {
  for (const side of ["top", "bottom"]) writeFileSync(`${pngPrefix}-${side}.png`, renderPng(side, 2000))
}

// ---- Pages ---------------------------------------------------------------
const pages = []
const DRAW_CX = 102
const DRAW_CY = 102
const S2 = 2

// 1: 1:1 top and bottom views
{
  const top = view({ px: 57, py: 98, scale: 1 })
  const bot = view({ px: 147, py: 98, scale: 1, mirror: true })
  const bt = boardBox(top)
  const bb = boardBox(bot)
  let s = ""
  s += embedRender("top", bt.x0, bt.y0, board.w, board.h)
  s += embedRender("bottom", bb.x0, bb.y0, board.w, board.h)
  s += text(top.px, bt.y0 - 9, "TOP (component side)", { size: 3.2, anchor: "middle", weight: "bold" })
  s += text(bot.px, bb.y0 - 9, "BOTTOM (D-sub side, viewed from below)", { size: 3.2, anchor: "middle", weight: "bold" })
  s += dimension(bt.x0, bt.y0 - 3, bt.x1, bt.y0 - 3, `${board.w.toFixed(1)} mm`)
  s += dimension(bt.x0 - 3, bt.y0, bt.x0 - 3, bt.y1, `${board.h.toFixed(1)} mm`)
  s += dimension(bb.x0, bb.y0 - 3, bb.x1, bb.y0 - 3, `${board.w.toFixed(1)} mm`)
  s += scaleBar(20, 158, 1, 50, 10)
  s += text(20, 172, "Check the print: this bar must measure 50 mm and the board outlines 80 x 70 mm.", { size: 2.6 })
  s += text(20, 177, "Cut out the bottom view to check the DD-50 against the 70754's SKB socket.", { size: 2.6 })
  pages.push({
    body: s,
    title: "Board views, actual size",
    viewNote: "top from above; bottom from below (mirrored)",
    scaleNote: "1:1",
    notes: [
      "Board views",
      "Rendered from the Gerbers with",
      "pcb-stackup (tracespace).",
      "",
      "Top: all SMD parts, USB-B (J1),",
      "B0505S-1WR3 (U4).",
      "Bottom: DD-50 plug (J2) only.",
      "",
      "Isolation barrier: the silkscreen",
      "line across the optocouplers.",
      "USB side above, DVM side below.",
    ],
  })
}

// 2/3: copper
for (const side of ["top", "bottom"]) {
  const v = view({ px: DRAW_CX, py: DRAW_CY, scale: S2 })
  const cu = side === "top" ? L.fcu : L.bcu
  const color = side === "top" ? "#b8322a" : "#2457a6"
  let s = layer(v, cu, color) + drillHoles(v) + layer(v, L.edge, "#000")
  s += scaleBar(22, 190, S2)
  pages.push({
    body: s,
    title: side === "top" ? "Top copper (F.Cu)" : "Bottom copper (B.Cu)",
    viewNote: side === "top" ? "from top" : "from top (seen through the board)",
    scaleNote: "2:1",
    notes: [
      side === "top" ? "Top copper" : "Bottom copper",
      "Tracks 0.15 mm min, vias",
      "0.2 mm drill / 0.45 mm pad.",
      "Pours: GND (USB side) and",
      "GND_ISO (DVM side), stopping",
      "1.6 mm each side of the barrier.",
      "",
      "Drilled holes shown white.",
    ],
  })
}

// 4/5: assembly (silkscreen over pads)
for (const side of ["top", "bottom"]) {
  const v = view({ px: DRAW_CX, py: DRAW_CY, scale: S2, mirror: side === "bottom" })
  const mask = side === "top" ? L.fmask : L.bmask
  const silk = side === "top" ? L.fsilk : L.bsilk
  let s = layer(v, mask, "#b9b9b9")
  if (side === "top") s += layer(v, L.ffab, "#8fa8cf")
  s += drillHoles(v) + layer(v, silk, "#000") + layer(v, L.edge, "#000") + refdes(v, side)
  s += scaleBar(22, 190, S2)
  const notes =
    side === "top"
      ? [
          "Top assembly",
          "All SMD parts are on this side.",
          "J1 (USB-B) and U4 (B0505S)",
          "are through-hole, fitted from",
          "this side.",
          "",
          "Designators in blue are at the",
          "part centres in pick_and_place.csv.",
        ]
      : [
          "Bottom assembly",
          "J2 (DD-50 plug) is the only part",
          "on this side; solder it from the",
          "top. Trim J1/U4 leads flush: this",
          "face sits a few mm from the",
          "70754 housing.",
        ]
  pages.push({
    body: s,
    title: side === "top" ? "Top assembly" : "Bottom assembly",
    viewNote: side === "top" ? "from top" : "from below (mirrored)",
    scaleNote: "2:1",
    notes,
    legend: [
      [REFDES, "Reference designator"],
      ["#000", "Silkscreen"],
      ["#b9b9b9", "Pads (solder-mask openings)"],
      ...(side === "top" ? [["#8fa8cf", "Fabrication outlines (F.Fab)"]] : []),
    ],
  })
}

// 6: top stencil
{
  const v = view({ px: DRAW_CX, py: DRAW_CY, scale: S2 })
  let s = layer(v, L.fmask, "#cfcfcf") + layer(v, L.fpaste, "#333") + layer(v, L.edge, "#000")
  s += scaleBar(22, 190, S2)
  pages.push({
    body: s,
    title: "Top stencil (F.Paste)",
    viewNote: "from top",
    scaleNote: "2:1",
    notes: [
      "Top stencil",
      "Apertures 1:1 with the pads;",
      "RP2354A exposed pad: 2 x 2",
      "windowpane, about 60 %.",
      "No paste on through-holes.",
      "No bottom stencil needed.",
      "",
      "Made by scripts/prepare-fab.mjs",
      "(tscircuit omits paste on pill",
      "pads: every SOIC and TLP2361).",
    ],
    legend: [
      ["#333", "Paste apertures"],
      ["#cfcfcf", "Pads (mask openings)"],
    ],
  })
}

// 7: drill drawing
{
  const v = view({ px: DRAW_CX, py: DRAW_CY, scale: S2 })
  const shapes = [
    (r) => `<circle r="${r}" fill="none"/><line x1="${-r}" x2="${r}"/><line y1="${-r}" y2="${r}"/>`,
    (r) => `<rect x="${-r}" y="${-r}" width="${2 * r}" height="${2 * r}" fill="none"/>`,
    (r) => `<path d="M0 ${-r} L${r * 0.87} ${r / 2} L${-r * 0.87} ${r / 2} Z" fill="none"/>`,
    (r) => `<path d="M0 ${-r} L${r} 0 L0 ${r} L${-r} 0 Z" fill="none"/>`,
    (r) => `<line x1="${-r}" y1="${-r}" x2="${r}" y2="${r}"/><line x1="${-r}" y1="${r}" x2="${r}" y2="${-r}"/>`,
    (r) => `<circle r="${r}" fill="none"/><circle r="${r / 3}" fill="#000"/>`,
  ]
  const symbolAt = (i, x, y, r) => `<g transform="translate(${x} ${y})" stroke="#000" stroke-width="0.18">${shapes[i % shapes.length](r)}</g>`
  let s = layer(v, L.edge, "#000")
  s += boardGroup(v, holes.map((h) => `<circle cx="${h.x}" cy="${h.y}" r="${h.d / 2}" fill="none" stroke="#999" stroke-width="0.04"/>`).join(""))
  // symbols in page space so they keep their size
  for (const h of holes) {
    const x = v.px + (h.x - board.cx) * v.sx
    const y = v.py + (h.y - board.cy) * v.sy
    s += symbolAt(drillSizes.indexOf(h.d), x, y, h.d < 0.5 ? 0.45 : 0.9)
  }
  s += scaleBar(22, 190, S2)
  // drill table in the notes panel
  const tx = 200
  let ty = 30
  s += text(tx, 18, "Drill drawing", { size: 3.4, weight: "bold" })
  s += text(tx, ty, "Sym", { size: 2.5, weight: "bold" })
  s += text(tx + 10, ty, "Finished dia.", { size: 2.5, weight: "bold" })
  s += text(tx + 36, ty, "Qty", { size: 2.5, weight: "bold" })
  s += text(tx + 47, ty, "Plating", { size: 2.5, weight: "bold" })
  s += text(tx + 64, ty, "Use", { size: 2.5, weight: "bold" })
  s += `<line x1="${tx}" y1="${ty + 1.5}" x2="${PAGE_W - 10}" y2="${ty + 1.5}" stroke="#000" stroke-width="0.2"/>`
  const use = { 0.2: "vias", 1: "J1, J2, U4 pins", 2.3: "J1 shell", 3.2: "J2 flange (4-40)" }
  for (const [i, d] of drillSizes.entries()) {
    ty += 6
    s += symbolAt(i, tx + 3, ty - 1, 1.1)
    s += text(tx + 10, ty, `${d.toFixed(2)} mm`, { size: 2.5 })
    s += text(tx + 36, ty, holes.filter((h) => h.d === d).length, { size: 2.5 })
    s += text(tx + 47, ty, plated ? "PTH" : "NPTH", { size: 2.5 })
    s += text(tx + 64, ty, use[d] ?? "", { size: 2.5 })
  }
  ty += 4
  s += `<line x1="${tx}" y1="${ty}" x2="${PAGE_W - 10}" y2="${ty}" stroke="#000" stroke-width="0.2"/>`
  s += text(tx + 10, ty + 4.5, "Total", { size: 2.5, weight: "bold" })
  s += text(tx + 36, ty + 4.5, holes.length, { size: 2.5, weight: "bold" })
  const notes = [
    "All holes plated through.",
    "Sizes are finished hole diameters.",
    `File: ${drillName} (Excellon, mm).`,
  ]
  notes.forEach((n, i) => (s += text(tx, ty + 14 + i * 4.2, n, { size: 2.6 })))
  pages.push({ body: s, title: "Drill drawing", viewNote: "from top", scaleNote: "2:1", notes: [] })
}

// ---- Assemble and print --------------------------------------------------
const svgPages = pages.map(
  (p, i) => `<div class="page"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${PAGE_W} ${PAGE_H}" width="${PAGE_W}mm" height="${PAGE_H}mm">
<rect width="${PAGE_W}" height="${PAGE_H}" fill="#fff"/>${p.body}${frame(i + 1, pages.length, p)}</svg></div>`,
)
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: ${PAGE_W}mm ${PAGE_H}mm; margin: 0 }
html, body { margin: 0; padding: 0 }
.page { width: ${PAGE_W}mm; height: ${PAGE_H}mm; overflow: hidden; page-break-after: always }
.page:last-child { page-break-after: auto }
svg { display: block }
</style></head><body>${svgPages.join("\n")}</body></html>`

const dir = mkdtempSync(join(tmpdir(), "pcb-prints-"))
const htmlPath = join(dir, "prints.html")
writeFileSync(htmlPath, html)
const chrome = process.env.CHROME_PATH ?? process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium"
execFileSync(
  chrome,
  ["--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", `--print-to-pdf=${resolve(pdfPath)}`, `file://${htmlPath}`],
  { stdio: "ignore" },
)
console.log(`Wrote ${pdfPath} (${pages.length} pages, A4 landscape)${pngPrefix ? ` and ${pngPrefix}-{top,bottom}.png` : ""}`)
