import type { CapacitorProps, ResistorProps } from "@tscircuit/props"

/**
 * Passive values used on the board, pinned to in-stock LCSC/JLCPCB parts
 * (basic parts where one exists).
 */
const RESISTORS = {
  "0402": {
    "27": "C25100",
    "33": "C25105",
    "1k": "C11702",
    "10k": "C25744",
  },
  "0603": {
    "100": "C22775",
    "390": "C23151",
    "1k": "C21190",
    "10k": "C25804",
  },
  "0805": {
    "470": "C17710",
  },
} as const

const CAPACITORS = {
  "0402": {
    "15pF": "C1548",
    "100nF": "C1525",
    "4.7uF": "C23733",
  },
  "0603": {
    "100nF": "C14663",
    "4.7uF": "C19666",
    "10uF": "C19702",
  },
} as const

type ResPkg = keyof typeof RESISTORS
type CapPkg = keyof typeof CAPACITORS

export const R = <P extends ResPkg>(
  props: Omit<ResistorProps, "resistance" | "footprint"> & {
    resistance: keyof (typeof RESISTORS)[P] & string
    footprint: P
  },
) => (
  <resistor
    {...props}
    supplierPartNumbers={{
      jlcpcb: [
        (RESISTORS[props.footprint] as Record<string, string>)[
          props.resistance
        ],
      ],
    }}
  />
)

export const C = <P extends CapPkg>(
  props: Omit<CapacitorProps, "capacitance" | "footprint"> & {
    capacitance: keyof (typeof CAPACITORS)[P] & string
    footprint: P
  },
) => (
  <capacitor
    {...props}
    supplierPartNumbers={{
      jlcpcb: [
        (CAPACITORS[props.footprint] as Record<string, string>)[
          props.capacitance
        ],
      ],
    }}
  />
)

/** 4 x 10k isolated resistor array, 0603x4 convex (UNI-ROYAL 4D03WGJ0103T5E) */
export const RES_ARRAY_10K_LCSC = "C29718"
