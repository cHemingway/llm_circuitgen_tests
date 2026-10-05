import type { ConnectorProps } from "@tscircuit/props"
import { SKB_PINS } from "./solartronSkb"

/**
 * DD-50 (standard density, 3 row) male D-sub, vertical through-hole PCB mount.
 *
 * Geometry follows the common straight-PCB DD-50 layout (Amphenol FCI
 * DD50P364TXLF drawing C-DSUB-0065, KiCad DSUB-xx_Pins_Vertical family):
 * 2.77 mm pitch, 2.84 mm row spacing, rows of 17/16/17 contacts and two
 * 3.1 mm holes on 61.11 mm centres for the 4-40 jackscrews.
 *
 * The footprint is drawn as seen looking at the mating face (pin 1 top left
 * on a plug). Place it on the bottom layer to face the instrument.
 */
const PITCH = 2.77
const ROW = 2.84
const MOUNT_HOLE_SPACING = 61.11

const pinPosition = (pin: number): { x: number; y: number } => {
  if (pin <= 17) return { x: (pin - 1 - 8) * PITCH, y: ROW }
  if (pin <= 33) return { x: (pin - 18 - 7.5) * PITCH, y: 0 }
  return { x: (pin - 34 - 8) * PITCH, y: -ROW }
}

const pinLabels = Object.fromEntries([
  ...SKB_PINS.map((p) => [`pin${p.pin}`, [p.label]]),
  ["pin51", ["SHELL1"]],
  ["pin52", ["SHELL2"]],
]) as Record<string, string[]>

// D-sub shell outline (DD size), mating-face view
const shellHalfWidthTop = 26.43
const shellHalfWidthBottom = 24.4
const shellHalfHeight = 5.0

export const DSub50MaleVertical = (
  props: Omit<ConnectorProps, "footprint" | "pinLabels">,
) => (
  <connector
    manufacturerPartNumber="DD50P364TXLF"
    supplierPartNumbers={{ jlcpcb: ["C5402574"] }}
    pinLabels={pinLabels}
    schPinArrangement={{
      leftSide: {
        direction: "top-to-bottom",
        pins: Array.from({ length: 25 }, (_, i) => `pin${i + 1}`),
      },
      rightSide: {
        direction: "top-to-bottom",
        pins: [
          ...Array.from({ length: 25 }, (_, i) => `pin${i + 26}`),
          "pin51",
          "pin52",
        ],
      },
    }}
    footprint={
      <footprint insertionDirection="from_above">
        {SKB_PINS.map((p) => {
          const { x, y } = pinPosition(p.pin)
          return (
            <platedhole
              key={p.pin}
              portHints={[`pin${p.pin}`]}
              pcbX={x}
              pcbY={y}
              shape="circle"
              holeDiameter="1mm"
              outerDiameter="1.6mm"
            />
          )
        })}
        <platedhole
          portHints={["pin51"]}
          pcbX={-MOUNT_HOLE_SPACING / 2}
          pcbY={0}
          shape="circle"
          holeDiameter="3.2mm"
          outerDiameter="5.6mm"
        />
        <platedhole
          portHints={["pin52"]}
          pcbX={MOUNT_HOLE_SPACING / 2}
          pcbY={0}
          shape="circle"
          holeDiameter="3.2mm"
          outerDiameter="5.6mm"
        />
        <silkscreenpath
          route={[
            { x: -shellHalfWidthTop, y: shellHalfHeight },
            { x: shellHalfWidthTop, y: shellHalfHeight },
            { x: shellHalfWidthBottom, y: -shellHalfHeight },
            { x: -shellHalfWidthBottom, y: -shellHalfHeight },
            { x: -shellHalfWidthTop, y: shellHalfHeight },
          ]}
        />
        <silkscreentext
          text="1"
          pcbX={pinPosition(1).x - 1.6}
          pcbY={pinPosition(1).y + 1.4}
          fontSize="1mm"
        />
        <courtyardrect pcbX={0} pcbY={0} width="67mm" height="12.6mm" />
      </footprint>
    }
    {...props}
  />
)
