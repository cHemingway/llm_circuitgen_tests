/**
 * Schematic layout helpers. Supply decoupling capacitors are drawn together
 * in the "decoupling" schematic section, one compact block per rail.
 */
export const DECOUPLING_SECTION = "decoupling"

const DECAP_BLOCKS = {
  V3V3: { x0: -20, y0: -12, cols: 4 },
  V1V1: { x0: -14.6, y0: -12, cols: 4 },
  V3V3_ISO: { x0: -9.8, y0: -12, cols: 4 },
  V5_ISO: { x0: -4.2, y0: -12, cols: 3 },
} as const

export type DecapRail = keyof typeof DECAP_BLOCKS

export const decapSch = (rail: DecapRail, index: number) => {
  const b = DECAP_BLOCKS[rail]
  return {
    schSectionName: DECOUPLING_SECTION,
    schX: b.x0 + (index % b.cols) * 1.15,
    schY: b.y0 - Math.floor(index / b.cols) * 1.25,
  }
}
