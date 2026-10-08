/**
 * Which shift-register, buffer and resistor-array pin serves each SKB signal.
 * Chosen together with the command-side placement (dvmPlacement.ts) to
 * untangle the routing, so the bit order is not the SKB pin order: firmware
 * should use MISO_BITS and COMMAND_BITS.
 */
import { SKB_PINS } from "./solartronSkb"

export type InputLetter = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H"
export type OutputLetter = "QA" | "QB" | "QC" | "QD" | "QE" | "QF" | "QG" | "QH"

/**
 * 74LV165A chain, in shift order: entry 0 drives MISO, the last entry has
 * SER tied low. Input -> SKB pin; unlisted inputs are spare and tied low.
 * Each chip reads the SKB pins nearest it; within a pad column the outer
 * pins go to the upper pads so the fan-in from the D-sub doesn't cross.
 */
export const READ_CHAIN: { ref: string; inputs: Partial<Record<InputLetter, number>> }[] = [
  { ref: "U8", inputs: { A: 35, B: 18, C: 1, D: 34, E: 3, F: 36, G: 19, H: 2 } }, // drives MISO
  { ref: "U6", inputs: { A: 5, B: 21, C: 4, D: 20, E: 7, F: 23, G: 6, H: 22 } },
  { ref: "U9", inputs: { A: 9, B: 25, C: 8, D: 24, E: 11, F: 27, G: 10, H: 26 } },
  { ref: "U7", inputs: { A: 13, B: 29, C: 12, D: 28, E: 15, F: 31, G: 14, H: 30 } },
  { ref: "U10", inputs: { A: 16, B: 32, G: 17, H: 33 } }, // SER tied low
]

/**
 * 74LV595A chain: entry 0 takes MOSI. Output -> SKB pin. This, the buffer
 * channels, the pull-up elements and the command-side placement were chosen
 * together by minimising ratsnest crossings (simulated annealing).
 */
export const COMMAND_CHAIN: { ref: string; outputs: Partial<Record<OutputLetter, number>> }[] = [
  { ref: "U11", outputs: { QA: 40, QB: 47, QC: 44, QD: 46, QE: 42, QF: 45, QG: 48, QH: 49 } },
  { ref: "U12", outputs: { QA: 39, QB: 50, QC: 43, QF: 38, QG: 41 } },
]

/** 74LVC07A open-drain buffers: channel n (nA in, nY out) -> SKB pin. */
export const OD_BUFFERS: { ref: string; channels: Record<1 | 2 | 3 | 4 | 5 | 6, number> }[] = [
  { ref: "U13", channels: { 1: 42, 2: 38, 3: 39, 4: 41, 5: 43, 6: 45 } },
  { ref: "U14", channels: { 1: 47, 2: 44, 3: 46, 4: 48, 5: 49, 6: 50 } },
]

/**
 * 10k pull-up arrays on the 74LVC07A inputs. Element n (pins n and 9 - n)
 * pulls up the command line for the SKB pin listed at position n - 1.
 */
export const PULLUP_ARRAYS: { ref: string; elements: [number, number, number, number] }[] = [
  { ref: "RN2", elements: [47, 48, 49, 50] },
  { ref: "RN3", elements: [45, 42, 46, 44] },
  { ref: "RN4", elements: [39, 41, 38, 43] },
]

// ---------------------------------------------------------------------------
// Firmware view
// ---------------------------------------------------------------------------

/** Shift order of a 74LV165A: H comes out first after the load */
const SHIFT_ORDER: InputLetter[] = ["H", "G", "F", "E", "D", "C", "B", "A"]

/**
 * MISO_BITS[k] is the SKB pin read in bit k of the 40-bit MISO frame
 * (k = 0 is the first bit received); null bits are spare and read 0.
 */
export const MISO_BITS: (number | null)[] = READ_CHAIN.flatMap((sr) =>
  SHIFT_ORDER.map((l) => sr.inputs[l] ?? null),
)

const OUTPUT_ORDER: OutputLetter[] = ["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]

/**
 * Command word bit b (b0 = last bit clocked out) drives this SKB pin. Every
 * command except pulse sample (pin 40) goes through a 74LVC07A, so writing a 1
 * leaves the DVM input at its idle logic 1 and the manual's codes apply as is.
 */
export const COMMAND_BITS: { bit: number; pin: number; openDrain: boolean }[] =
  COMMAND_CHAIN.flatMap((sr, idx) =>
    OUTPUT_ORDER.flatMap((q, i) => {
      const pin = sr.outputs[q]
      return pin === undefined ? [] : [{ bit: idx * 8 + i, pin, openDrain: pin !== 40 }]
    }),
  ).sort((a, b) => a.pin - b.pin)

// Every SKB signal must be served exactly once
const served = [...MISO_BITS.filter((p): p is number => p !== null), ...COMMAND_BITS.map((c) => c.pin)]
const signals = SKB_PINS.filter((p) => p.dir !== "ground").map((p) => p.pin)
if (served.length !== signals.length || signals.some((p) => !served.includes(p)))
  throw new Error("dvmPinMap: every SKB signal must be served exactly once")
const odPins = OD_BUFFERS.flatMap((b) => Object.values(b.channels)).sort((a, b) => a - b)
const puPins = PULLUP_ARRAYS.flatMap((a) => a.elements).sort((a, b) => a - b)
const odCmds = COMMAND_BITS.filter((c) => c.openDrain).map((c) => c.pin)
if (odPins.join() !== odCmds.join() || puPins.join() !== odCmds.join())
  throw new Error("dvmPinMap: buffers and pull-ups must match the open-drain commands")
