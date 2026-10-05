import { A_4D03WGJ0103T5E } from "../../imports/A_4D03WGJ0103T5E"
import { HT7533_1 } from "../../imports/HT7533_1"
import { SN74LV165ADR } from "../../imports/SN74LV165ADR"
import { SN74LV595ADR } from "../../imports/SN74LV595ADR"
import { SN74LVC07ADR } from "../../imports/SN74LVC07ADR"
import { CL10A106KP8NNNC } from "../common/CL10A106KP8NNNC"
import { DSub50MaleVertical } from "../DSub50MaleVertical"
import { C, R } from "../passives"
import { decapSch } from "../schLayout"
import { COMMAND_BITS, DVM_OUTPUT_PINS, dvmNet } from "../solartronSkb"

const secPower = "dvm_power"
const secIn = "dvm_inputs"
const secOut = "dvm_outputs"
const secConn = "dvm_connector"

/** D-sub centre (the connector is on the bottom side, facing the DVM) */
export const DSUB_X = 0
export const DSUB_Y = -14

// ---------------------------------------------------------------------------
// Input side: 5 x 74LV165A, 40 bits. Bit k of the MISO frame = SKB pin k+1.
// SR_IN1 is last in the chain and drives the MISO optocoupler.
// ---------------------------------------------------------------------------
const INPUT_LETTERS = ["H", "G", "F", "E", "D", "C", "B", "A"] as const
const SR_IN_ROW_Y = -3
const srIn = [
  { name: "U6", x: 11, cap: "C40" }, // SR_IN1: bits 0-7   (SKB 1-8)
  { name: "U7", x: -11, cap: "C41" }, // SR_IN2: bits 8-15  (SKB 9-16)
  { name: "U8", x: 22, cap: "C42" }, // SR_IN3: bits 16-23 (SKB 17-24)
  { name: "U9", x: 0, cap: "C43" }, // SR_IN4: bits 24-31 (SKB 25-32)
  { name: "U10", x: -22, cap: "C44" }, // SR_IN5: bits 32-39 (SKB 33-36, spare)
]

const srInConnections = (idx: number) => {
  const conns: Record<string, string> = {
    SH: "net.ISO_LATCH",
    CLK: "net.ISO_SCK",
    CLKINH: "net.GND_ISO",
    GND: "net.GND_ISO",
    VCC: "net.V3V3_ISO",
    SER: idx === srIn.length - 1 ? "net.GND_ISO" : `net.SR_IN_CHAIN${idx + 1}`,
    QH: idx === 0 ? "net.ISO_MISO" : `net.SR_IN_CHAIN${idx}`,
  }
  INPUT_LETTERS.forEach((letter, bit) => {
    const k = idx * 8 + bit
    conns[letter] =
      k < DVM_OUTPUT_PINS.length ? dvmNet(DVM_OUTPUT_PINS[k]) : "net.GND_ISO"
  })
  return conns
}

// ---------------------------------------------------------------------------
// Output side: 2 x 74LV595A -> 2 x 74LVC07A open-drain -> SKB inputs
// ---------------------------------------------------------------------------
const SR_OUT_ROW_Y = -26
const OUTPUT_LETTERS = ["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"] as const
const srOut = [
  { name: "U11", x: 10, cap: "C45" }, // SR_OUT1: command bits 0-7
  { name: "U12", x: 24, cap: "C46" }, // SR_OUT2: command bits 8-15
]
const odBuf = [
  { name: "U13", x: -4, cap: "C47" }, // bits 0-5
  { name: "U14", x: -18, cap: "C48" }, // bits 6-11
]
const OD_CHANNELS = [
  ["1A", "1Y"],
  ["2A", "2Y"],
  ["3A", "3Y"],
  ["4A", "4Y"],
  ["5A", "5Y"],
  ["6A", "6Y"],
] as const

const cmdNet = (bit: number) => `net.CMD_B${bit}`

const srOutConnections = (idx: number) => {
  const conns: Record<string, string> = {
    SER: idx === 0 ? "net.ISO_MOSI" : "net.SR_OUT_CHAIN",
    SRCLK: "net.ISO_SCK",
    RCLK: "net.ISO_LATCH",
    OE_n: "net.ISO_OE_N",
    SRCLR_n: "net.V3V3_ISO",
    GND: "net.GND_ISO",
    VCC: "net.V3V3_ISO",
  }
  if (idx === 0) conns.QH_ = "net.SR_OUT_CHAIN"
  OUTPUT_LETTERS.forEach((letter, i) => {
    const bit = idx * 8 + i
    if (COMMAND_BITS.some((c) => c.bit === bit)) conns[letter] = cmdNet(bit)
  })
  return conns
}

const odBits = COMMAND_BITS.filter((c) => c.openDrain)

const odConnections = (idx: number) => {
  const conns: Record<string, string> = {
    GND: "net.GND_ISO",
    VCC: "net.V3V3_ISO",
  }
  OD_CHANNELS.forEach(([a, y], ch) => {
    const cmd = odBits[idx * 6 + ch]
    conns[a] = cmdNet(cmd.bit)
    conns[y] = dvmNet(cmd.pin)
  })
  return conns
}

/** 10k pull-ups on the 74LVC07A inputs: outputs stay off while OE_N is high */
const pullupArrays = [
  { name: "RN2", x: -18, bits: [6, 7, 8, 9] },
  { name: "RN3", x: -10, bits: [10, 11, 0, 1] },
  { name: "RN4", x: -2, bits: [2, 3, 4, 5] },
]

export const DvmInterface = () => (
  <>
    <schematicsection name={secPower} displayName="Isolated 3.3 V" />
    <schematicsection name={secIn} displayName="DVM outputs -> 74LV165A" />
    <schematicsection
      name={secOut}
      displayName="Commands: 74LV595A -> 74LVC07A open drain"
    />
    <schematicsection name={secConn} displayName="SKB 50-way D (to 70754)" />

    {/* ---------------- isolated 3.3 V ---------------- */}
    <CL10A106KP8NNNC
      name="C36"
      {...decapSch("V5_ISO", 1)}
      pcbX={-36.6}
      pcbY={-4.6}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V5_ISO", pin2: "net.GND_ISO" }}
    />
    <HT7533_1
      name="U5"
      pcbX={-31.6}
      pcbY={-4.6}
      schSectionName={secPower}
      schX={21}
      schY={-7.4}
      connections={{ Vin: "net.V5_ISO", Vout: "net.V3V3_ISO", GND: "net.GND_ISO" }}
    />
    <CL10A106KP8NNNC
      name="C37"
      {...decapSch("V3V3_ISO", 4)}
      pcbX={-27.6}
      pcbY={-9.2}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V3V3_ISO", pin2: "net.GND_ISO" }}
    />

    {/* ---------------- 74LV165A input chain ---------------- */}
    {srIn.flatMap((u, idx) => [
      <SN74LV165ADR
        key={u.name}
        name={u.name}
        pcbX={u.x}
        pcbY={SR_IN_ROW_Y}
        pcbRotation={-90}
        schSectionName={secIn}
        schX={2 + idx * 6}
        schY={-14}
        connections={srInConnections(idx)}
      />,
      <C
        key={u.cap}
        name={u.cap}
        capacitance="100nF"
        footprint="0603"
        pcbX={u.x + 4.2}
        pcbY={SR_IN_ROW_Y + 6.4}
        schOrientation="vertical"
        {...decapSch("V3V3_ISO", 5 + idx)}
        connections={{ pin1: "net.V3V3_ISO", pin2: "net.GND_ISO" }}
      />,
    ])}

    {/* ---------------- 74LV595A command register ---------------- */}
    {srOut.flatMap((u, idx) => [
      <SN74LV595ADR
        key={u.name}
        name={u.name}
        pcbX={u.x}
        pcbY={SR_OUT_ROW_Y}
        pcbRotation={-90}
        schSectionName={secOut}
        schX={2 + idx * 5}
        schY={-24}
        connections={srOutConnections(idx)}
      />,
      <C
        key={u.cap}
        name={u.cap}
        capacitance="100nF"
        footprint="0603"
        pcbX={u.x + 4.2}
        pcbY={SR_OUT_ROW_Y + 6.3}
        schOrientation="vertical"
        {...decapSch("V3V3_ISO", 10 + idx)}
        connections={{ pin1: "net.V3V3_ISO", pin2: "net.GND_ISO" }}
      />,
    ])}
    <R
      name="R20"
      resistance="10k"
      footprint="0603"
      pcbX={17}
      pcbY={-32.6}
      schSectionName={secOut}
      schX={0}
      schY={-21}
      schRotation={90}
      connections={{ pin1: "net.ISO_OE_N", pin2: "net.V3V3_ISO" }}
    />

    {/* ---------------- 74LVC07A open-drain drivers ---------------- */}
    {odBuf.flatMap((u, idx) => [
      <SN74LVC07ADR
        key={u.name}
        name={u.name}
        pcbX={u.x}
        pcbY={SR_OUT_ROW_Y}
        pcbRotation={-90}
        schSectionName={secOut}
        schX={13 + idx * 5}
        schY={-24}
        connections={odConnections(idx)}
      />,
      <C
        key={u.cap}
        name={u.cap}
        capacitance="100nF"
        footprint="0603"
        pcbX={u.x + 4.2}
        pcbY={SR_OUT_ROW_Y + 6.3}
        schOrientation="vertical"
        {...decapSch("V3V3_ISO", 12 + idx)}
        connections={{ pin1: "net.V3V3_ISO", pin2: "net.GND_ISO" }}
      />,
    ])}
    {pullupArrays.map((rn, idx) => (
      <A_4D03WGJ0103T5E
        key={rn.name}
        name={rn.name}
        pcbX={rn.x}
        pcbY={-32.6}
        schSectionName={secOut}
        schX={12.1 + idx * 2.6}
        schY={-28}
        connections={{
          pin1: cmdNet(rn.bits[0]),
          pin2: cmdNet(rn.bits[1]),
          pin3: cmdNet(rn.bits[2]),
          pin4: cmdNet(rn.bits[3]),
          pin5: "net.V3V3_ISO",
          pin6: "net.V3V3_ISO",
          pin7: "net.V3V3_ISO",
          pin8: "net.V3V3_ISO",
        }}
      />
    ))}

    {/* Pulse SAMPLE (pin 40) is the only push-pull command: 3.3 V > +3 V min */}
    <R
      name="R21"
      resistance="100"
      footprint="0603"
      pcbX={6.4}
      pcbY={-19.7}
      pcbRotation={180}
      schSectionName={secOut}
      schX={7.9}
      schY={-28}
      connections={{ pin1: cmdNet(12), pin2: dvmNet(40) }}
    />

    {/* ---------------- SKB connector ---------------- */}
    <DSub50MaleVertical
      name="J2"
      layer="bottom"
      pcbX={DSUB_X}
      pcbY={DSUB_Y}
      schSectionName={secConn}
      schX={36}
      schY={-18}
      connections={Object.fromEntries([
        ...DVM_OUTPUT_PINS.map((p) => [`pin${p}`, dvmNet(p)]),
        ...COMMAND_BITS.map((c) => [`pin${c.pin}`, dvmNet(c.pin)]),
        ["pin37", "net.GND_ISO"],
        ["pin51", "net.GND_ISO"],
        ["pin52", "net.GND_ISO"],
      ])}
    />
  </>
)
