import { ABM8_272_T3 } from "../../imports/ABM8_272_T3"
import { AOTA_B201610S3R3_101_T } from "../../imports/AOTA_B201610S3R3_101_T"
import { RP2354A } from "../../imports/RP2354A"
import { SKRPACE010 } from "../common/SKRPACE010"
import { XL_1608SURC_06 } from "../common/XL_1608SURC_06"
import { C, R } from "../passives"
import { decapSch } from "../schLayout"

const sec = "mcu"

// RP2354A placement; the passives below are positioned relative to it
const U1X = 0
const U1Y = 25

/** 100 nF supply decoupling capacitors, one per supply pin */
const decouplers: {
  name: string
  net: string
  x: number
  y: number
  rot?: number
}[] = [
  { name: "C10", net: "V3V3", x: -5.6, y: 29.2, rot: 90 }, // IOVDD pin 1
  { name: "C11", net: "V1V1", x: -5.6, y: 25.8, rot: 90 }, // DVDD pin 6
  { name: "C12", net: "V3V3", x: -5.6, y: 22.4, rot: 90 }, // IOVDD pin 11
  { name: "C13", net: "V3V3", x: -2.6, y: 20.14, rot: 180 }, // IOVDD pin 20
  { name: "C14", net: "V1V1", x: 2.6, y: 20.0 }, // DVDD pin 23
  { name: "C15", net: "V3V3", x: 5.6, y: 21.6, rot: 90 }, // IOVDD pin 30
  { name: "C16", net: "V3V3", x: 5.6, y: 24.6, rot: 90 }, // IOVDD pin 38
  { name: "C17", net: "V1V1", x: 7.0, y: 24.6, rot: 90 }, // DVDD pin 39
  { name: "C18", net: "V3V3", x: 5.6, y: 27.6, rot: 90 }, // ADC_AVDD pin 44
  { name: "C19", net: "V3V3", x: 7.0, y: 27.6, rot: 90 }, // IOVDD pin 45
  { name: "C20", net: "V3V3", x: -1.2, y: 30.6, rot: 90 }, // USB_OTP_VDD pin 53
  { name: "C21", net: "V3V3", x: -2.6, y: 30.6, rot: 90 }, // QSPI_IOVDD pin 54
]

/**
 * RP2354A (RP2350A + 2 MB in-package flash) with the core regulator,
 * 12 MHz crystal, BOOTSEL/RUN buttons, SWD pads and status LEDs.
 * Follows "Hardware design with RP2350" / the Pico 2 regulator layout.
 */
export const Mcu = () => (
  <>
    <schematicsection name={sec} displayName="RP2354A microcontroller" />

    <RP2354A
      name="U1"
      pcbX={U1X}
      pcbY={U1Y}
      schSectionName={sec}
      schX={2}
      schY={1.6}
      schWidth={2.8}
      connections={{
        IOVDD1: "net.V3V3",
        IOVDD2: "net.V3V3",
        IOVDD3: "net.V3V3",
        IOVDD4: "net.V3V3",
        IOVDD5: "net.V3V3",
        IOVDD6: "net.V3V3",
        QSPI_IOVDD: "net.V3V3",
        USB_OTP_VDD: "net.V3V3",
        ADC_AVDD: "net.V3V3",
        VREG_VIN: "net.V3V3",
        VREG_AVDD: "net.VREG_AVDD",
        VREG_LX: "net.VREG_LX",
        VREG_FB: "net.V1V1",
        VREG_PGND: "net.GND",
        DVDD1: "net.V1V1",
        DVDD2: "net.V1V1",
        DVDD3: "net.V1V1",
        EP: "net.GND",
        USB_DP: "net.USB_DP",
        USB_DM: "net.USB_DM",
        XIN: "net.XIN",
        XOUT: "net.XOUT",
        RUN: "net.RUN",
        SWCLK: "net.SWCLK",
        SWDIO: "net.SWDIO",
        QSPI_SS: "net.QSPI_SS",
        // Isolated SPI link (SPI0 pins; LATCH and OE_N are plain GPIO)
        GPIO2: "net.ISO_SCK_TX",
        GPIO3: "net.ISO_MOSI_TX",
        GPIO4: "net.ISO_MISO_RX",
        GPIO5: "net.ISO_LATCH_TX",
        GPIO6: "net.ISO_OE_N_TX",
        GPIO25: "net.LED_STATUS",
      }}
    />

    {decouplers.map((d) => (
      <C
        key={d.name}
        name={d.name}
        capacitance="100nF"
        footprint="0402"
        pcbX={d.x}
        pcbY={d.y}
        pcbRotation={d.rot ?? 0}
        schOrientation="vertical"
        {...decapSch(
          d.net === "V1V1" ? "V1V1" : "V3V3",
          decouplers.filter((o) => o.net === d.net).indexOf(d) +
            (d.net === "V1V1" ? 0 : 1),
        )}
        connections={{ pin1: `net.${d.net}`, pin2: "net.GND" }}
      />
    ))}

    {/* Core regulator: Cin on VREG_VIN, L + Cout on DVDD, RC filter on VREG_AVDD */}
    <C
      name="C22"
      {...decapSch("V3V3", 10)}
      capacitance="4.7uF"
      footprint="0402"
      pcbX={1.4}
      pcbY={30.8}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V3V3", pin2: "net.GND" }}
    />
    <AOTA_B201610S3R3_101_T
      name="L1"
      pcbX={4.4}
      pcbY={31.4}
      schSectionName={sec}
      schX={6.6}
      schY={5.4}
      connections={{ pin1: "net.VREG_LX", pin2: "net.V1V1" }}
    />
    <C
      name="C23"
      {...decapSch("V1V1", 3)}
      capacitance="4.7uF"
      footprint="0402"
      pcbX={7.4}
      pcbY={31.4}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V1V1", pin2: "net.GND" }}
    />
    <R
      name="R3"
      schRotation={-90}
      resistance="33"
      footprint="0402"
      pcbX={4.6}
      pcbY={33.3}
      schSectionName={sec}
      schX={5.6}
      schY={3.4}
      connections={{ pin1: "net.V3V3", pin2: "net.VREG_AVDD" }}
    />
    <C
      name="C24"
      capacitance="4.7uF"
      footprint="0402"
      pcbX={1.8}
      pcbY={33.3}
      pcbRotation={180}
      schSectionName={sec}
      schOrientation="vertical"
      schX={6.8}
      schY={2.4}
      connections={{ pin1: "net.VREG_AVDD", pin2: "net.GND" }}
    />

    {/* 12 MHz crystal (RP2350 reference: ABM8-272-T3, 15 pF, 1k on XOUT) */}
    <ABM8_272_T3
      name="Y1"
      pcbX={-1.8}
      pcbY={17.6}
      pcbRotation={-90}
      schSectionName={sec}
      schX={-2}
      schY={-5}
      connections={{
        pin1: "net.XIN",
        pin3: "net.XOUT_R",
        GND1: "net.GND",
        GND2: "net.GND",
      }}
    />
    <R
      name="R4"
      schRotation={180}
      resistance="1k"
      footprint="0402"
      pcbX={0.6}
      pcbY={18}
      pcbRotation={-90}
      schSectionName={sec}
      schX={0.4}
      schY={-4.4}
      connections={{ pin1: "net.XOUT", pin2: "net.XOUT_R" }}
    />
    <C
      name="C25"
      capacitance="15pF"
      footprint="0402"
      pcbX={-4.6}
      pcbY={18.4}
      pcbRotation={90}
      schSectionName={sec}
      schOrientation="vertical"
      schX={-3.4}
      schY={-6.6}
      connections={{ pin1: "net.XIN", pin2: "net.GND" }}
    />
    <C
      name="C26"
      capacitance="15pF"
      footprint="0402"
      pcbX={0.6}
      pcbY={15.8}
      pcbRotation={90}
      schSectionName={sec}
      schOrientation="vertical"
      schX={-0.6}
      schY={-6.6}
      connections={{ pin1: "net.XOUT_R", pin2: "net.GND" }}
    />

    {/* BOOTSEL: QSPI_SS pulled low through 1k at reset */}
    <SKRPACE010
      name="SW1"
      pcbX={-10}
      pcbY={32.4}
      schSectionName={sec}
      schX={-3.45}
      schY={5.4}
      connections={{ pin1: "net.BOOT_SW", pin3: "net.GND" }}
    />
    <R
      name="R5"
      resistance="1k"
      footprint="0402"
      pcbX={-5.8}
      pcbY={32.6}
      pcbRotation={180}
      schSectionName={sec}
      schX={-0.95}
      schY={5.4}
      connections={{ pin1: "net.QSPI_SS", pin2: "net.BOOT_SW" }}
    />

    {/* RUN (reset) */}
    <R
      name="R6"
      resistance="10k"
      footprint="0402"
      pcbX={4.6}
      pcbY={18.2}
      pcbRotation={90}
      schSectionName={sec}
      schX={7.4}
      schY={-4.4}
      schRotation={90}
      connections={{ pin1: "net.RUN", pin2: "net.V3V3" }}
    />
    <SKRPACE010
      name="SW2"
      pcbX={14}
      pcbY={32.4}
      schSectionName={sec}
      schX={9}
      schY={-5.4}
      connections={{ pin1: "net.RUN", pin3: "net.GND" }}
    />

    {/* SWD debug pads */}
    {[
      { name: "TP1", net: "SWCLK", x: 8 },
      { name: "TP2", net: "SWDIO", x: 10.5 },
      { name: "TP3", net: "GND", x: 13 },
      { name: "TP4", net: "V3V3", x: 15.5 },
    ].map((tp, i) => (
      <testpoint
        key={tp.name}
        name={tp.name}
        footprintVariant="pad"
        padShape="circle"
        padDiameter="1.5mm"
        pcbX={tp.x}
        pcbY={19.4}
        schSectionName={sec}
        schX={2.4 + i * 1.2}
        schY={-6.6}
        connections={{ pin1: `net.${tp.net}` }}
      />
    ))}

    {/* Status LED on GPIO25, power LED on 3.3 V */}
    <R
      name="R7"
      schRotation={-90}
      resistance="1k"
      footprint="0603"
      pcbX={20}
      pcbY={32.4}
      schSectionName={sec}
      schX={8.4}
      schY={1.6}
      connections={{ pin1: "net.LED_STATUS", pin2: "net.LED_STATUS_A" }}
    />
    <XL_1608SURC_06
      name="D1"
      schRotation={-90}
      color="red"
      pcbX={23}
      pcbY={32.4}
      schSectionName={sec}
      schX={8.4}
      schY={-0.2}
      connections={{ anode: "net.LED_STATUS_A", cathode: "net.GND" }}
    />
    <R
      name="R8"
      schRotation={-90}
      resistance="1k"
      footprint="0603"
      pcbX={27}
      pcbY={32.4}
      schSectionName={sec}
      schX={9.9}
      schY={1.6}
      connections={{ pin1: "net.V3V3", pin2: "net.LED_PWR_A" }}
    />
    <XL_1608SURC_06
      name="D2"
      schRotation={-90}
      color="red"
      pcbX={30}
      pcbY={32.4}
      schSectionName={sec}
      schX={9.9}
      schY={-0.2}
      connections={{ anode: "net.LED_PWR_A", cathode: "net.GND" }}
    />

    <silkscreentext text="BOOT" pcbX={-10} pcbY={29.6} fontSize="0.8mm" />
    <silkscreentext text="RUN" pcbX={14} pcbY={29.6} fontSize="0.8mm" />
    <silkscreentext text="SWCLK SWDIO GND 3V3" pcbX={11.8} pcbY={17.4} fontSize="0.6mm" />
    <silkscreentext text="ACT" pcbX={23} pcbY={34.2} fontSize="0.7mm" />
    <silkscreentext text="PWR" pcbX={30} pcbY={34.2} fontSize="0.7mm" />
  </>
)
