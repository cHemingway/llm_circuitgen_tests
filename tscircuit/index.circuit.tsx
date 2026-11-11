import { DvmInterface } from "./lib/sections/DvmInterface"
import { BARRIER_Y, Isolation } from "./lib/sections/Isolation"
import { Mcu } from "./lib/sections/Mcu"
import { UsbPower } from "./lib/sections/UsbPower"
import { DECOUPLING_SECTION } from "./lib/schLayout"

/**
 * Solartron 7075 USB interface.
 *
 * An RP2354A talks over USB-B and drives the 70754 Parallel BCD Interface
 * (socket SKB, 50 way D) through five TLP2361 optocouplers and a chain of
 * shift registers on the isolated side: 5 x 74LV165A read the 36 DVM outputs,
 * 2 x 74LV595A + 2 x 74LVC07A drive the 13 DVM inputs.
 *
 * Mechanics: the board sits flat against the back of the instrument. The
 * DD-50 plug is on the bottom side and is held by its jackscrews; the vertical
 * USB-B socket is on the top side, so the cable leaves straight out the back.
 */
const BOARD_W = 80
const BOARD_H = 70
const POUR_GAP = 1.6 // half width of the copper-free strip at the barrier

const EDGE = 0.6 // keep pours back from the board edge

const usbSideOutline = [
  { x: -BOARD_W / 2 + EDGE, y: BARRIER_Y + POUR_GAP },
  { x: BOARD_W / 2 - EDGE, y: BARRIER_Y + POUR_GAP },
  { x: BOARD_W / 2 - EDGE, y: BOARD_H / 2 - EDGE },
  { x: -BOARD_W / 2 + EDGE, y: BOARD_H / 2 - EDGE },
]
const isoSideOutline = [
  { x: -BOARD_W / 2 + EDGE, y: -BOARD_H / 2 + EDGE },
  { x: BOARD_W / 2 - EDGE, y: -BOARD_H / 2 + EDGE },
  { x: BOARD_W / 2 - EDGE, y: BARRIER_Y - POUR_GAP },
  { x: -BOARD_W / 2 + EDGE, y: BARRIER_Y - POUR_GAP },
]

export default () => (
  <board
    width={`${BOARD_W}mm`}
    height={`${BOARD_H}mm`}
    layers={2}
    borderRadius="2mm"
    title="Solartron 7075 USB interface"
    minViaHoleDiameter="0.2mm"
    minViaPadDiameter="0.45mm"
    schMaxTraceDistance={4}
    schTraceAutoLabelEnabled
  >
    <schematicsection name={DECOUPLING_SECTION} displayName="Supply decoupling" />
    <UsbPower />
    <Mcu />
    <Isolation />
    <DvmInterface />

    <copperpour connectsTo="net.GND" layer="top" outline={usbSideOutline} clearance="0.25mm" />
    <copperpour connectsTo="net.GND" layer="bottom" outline={usbSideOutline} clearance="0.25mm" />
    <copperpour connectsTo="net.GND_ISO" layer="top" outline={isoSideOutline} clearance="0.25mm" />
    <copperpour connectsTo="net.GND_ISO" layer="bottom" outline={isoSideOutline} clearance="0.25mm" />

    {/* Copper keepout along the barrier: no trace or via may cross it */}
    <keepout
      shape="rect"
      pcbX={0}
      pcbY={BARRIER_Y}
      width={`${BOARD_W}mm`}
      height="1.8mm"
      layers={["top", "bottom"]}
      allowPlacements
    />

    {/* Isolation barrier marking */}
    <silkscreenline
      x1={-BOARD_W / 2 + 1}
      y1={BARRIER_Y}
      x2={BOARD_W / 2 - 1}
      y2={BARRIER_Y}
      strokeWidth={0.15}
    />
    <silkscreentext text="USB SIDE" pcbX={33} pcbY={BARRIER_Y + 1.6} fontSize="0.9mm" />
    <silkscreentext text="ISOLATED (DVM)" pcbX={31} pcbY={BARRIER_Y - 1.6} fontSize="0.9mm" />
    <silkscreentext
      text="SOLARTRON 7075 USB IF"
      pcbX={-28}
      pcbY={-33.6}
      fontSize="0.8mm"
    />
  </board>
)
