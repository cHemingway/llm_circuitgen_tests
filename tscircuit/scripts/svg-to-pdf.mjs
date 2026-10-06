// Converts an SVG into a single-page vector PDF with headless Chromium.
// (`tsci export -f schematic-pdf` embeds a 144 dpi bitmap, which is blurry.)
// Usage: node scripts/svg-to-pdf.mjs in.svg out.pdf [pageWidthMm]
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

const [input, output, widthArg] = process.argv.slice(2)
if (!input || !output) {
  console.error("usage: node scripts/svg-to-pdf.mjs in.svg out.pdf [pageWidthMm]")
  process.exit(2)
}
const svg = readFileSync(input, "utf8")
const w = Number(svg.match(/<svg[^>]*\swidth="([\d.]+)"/)?.[1])
const h = Number(svg.match(/<svg[^>]*\sheight="([\d.]+)"/)?.[1])
if (!w || !h) throw new Error("SVG has no numeric width/height")

const pageW = Number(widthArg ?? 841) // default: A1 width
const pageH = (pageW * h) / w

// Without a viewBox the drawing would not scale to the page size
const scalable = /<svg[^>]*\sviewBox=/.test(svg)
  ? svg
  : svg.replace(/<svg\b/, `<svg viewBox="0 0 ${w} ${h}"`)

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: ${pageW}mm ${pageH}mm; margin: 0 }
html, body { margin: 0; padding: 0 }
svg { display: block; width: ${pageW}mm; height: ${pageH}mm }
</style></head><body>${scalable.replace(/^<\?xml[^>]*>/, "")}</body></html>`

const dir = mkdtempSync(join(tmpdir(), "svg2pdf-"))
const htmlPath = join(dir, "page.html")
writeFileSync(htmlPath, html)

const chrome =
  process.env.CHROME_PATH ??
  process.env.PLAYWRIGHT_CHROMIUM ??
  "/opt/pw-browsers/chromium"
execFileSync(
  chrome,
  [
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
    "--no-pdf-header-footer",
    `--print-to-pdf=${resolve(output)}`,
    `file://${htmlPath}`,
  ],
  { stdio: "ignore" },
)
console.log(`Wrote ${output} (${pageW} x ${pageH.toFixed(1)} mm, vector)`)
