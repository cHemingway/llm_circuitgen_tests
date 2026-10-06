import { A_4D03WGJ0103T5E } from "../../imports/A_4D03WGJ0103T5E"
import { B0505S_1WR3 } from "../../imports/B0505S_1WR3"
import { TLP2361_TPL_E } from "../../imports/TLP2361_TPL_E"
import { CL10A106KP8NNNC } from "../common/CL10A106KP8NNNC"
import { C, R } from "../passives"
import { decapSch } from "../schLayout"

const sec = "isolation"

/** Isolation barrier centre line (board y coordinate) */
export const BARRIER_Y = 9

/**
 * Forward channels (MCU -> DVM side). Each LED is driven from its cathode, so
 * GPIO low = LED on = TLP2361 output low: the link is non-inverting, and an
 * undriven GPIO (held high by the pull-up array) leaves the far side high,
 * which keeps the 74LV595A outputs disabled through OE_N.
 */
const forward = [
  { oc: "OC1", r: "R10", c: "C30", sig: "SCK", x: -24 },
  { oc: "OC2", r: "R11", c: "C31", sig: "MOSI", x: -15 },
  { oc: "OC3", r: "R12", c: "C32", sig: "LATCH", x: -6 },
  { oc: "OC4", r: "R13", c: "C33", sig: "OE_N", x: 3 },
]

/**
 * TLP2361 optocoupler barrier (4 forward + 1 return channel) and the
 * isolated 1 W DC-DC converter. All five links are 15 Mbit/s capable; the
 * SPI clock is limited mainly by the round trip MISO delay (~200 ns).
 */
export const Isolation = () => (
  <>
    <schematicsection name={sec} displayName="Isolation barrier" />

    {forward.flatMap((ch, i) => [
        <TLP2361_TPL_E
          key={ch.oc}
          name={ch.oc}
          pcbX={ch.x}
          pcbY={BARRIER_Y}
          pcbRotation={90}
          schSectionName={sec}
          schX={20}
          schY={5 - i * 2.2}
          connections={{
            AN: `net.OC_${ch.sig}_AN`,
            CAT: `net.ISO_${ch.sig}_TX`,
            VCC: "net.V3V3_ISO",
            GND: "net.GND_ISO",
            VO: `net.ISO_${ch.sig}`,
          }}
        />,
        <R
          key={ch.r}
          name={ch.r}
          resistance="390"
          footprint="0603"
          pcbX={ch.x + 3.6}
          pcbY={BARRIER_Y + 5}
          pcbRotation={-90}
          schSectionName={sec}
          schX={17.4}
          schY={5.4 - i * 2.2}
          schRotation={-90}
          connections={{ pin1: "net.V3V3", pin2: `net.OC_${ch.sig}_AN` }}
        />,
        <C
          key={ch.c}
          name={ch.c}
          capacitance="100nF"
          footprint="0603"
          pcbX={ch.x + 3.6}
          pcbY={BARRIER_Y - 3.4}
          pcbRotation={90}
          schOrientation="vertical"
          {...decapSch("V3V3_ISO", i)}
          connections={{ pin1: "net.V3V3_ISO", pin2: "net.GND_ISO" }}
        />,
    ])}

    {/* Pull-ups keep the forward LEDs off while the RP2354A is in reset */}
    <A_4D03WGJ0103T5E
      name="RN1"
      pcbX={-9}
      pcbY={BARRIER_Y + 8.4}
      schSectionName={sec}
      schX={15.4}
      schY={2.4}
      connections={{
        pin1: "net.ISO_SCK_TX",
        pin2: "net.ISO_MOSI_TX",
        pin3: "net.ISO_LATCH_TX",
        pin4: "net.ISO_OE_N_TX",
        pin5: "net.V3V3",
        pin6: "net.V3V3",
        pin7: "net.V3V3",
        pin8: "net.V3V3",
      }}
    />

    {/* Return channel (DVM -> MCU): MISO */}
    <TLP2361_TPL_E
      name="OC5"
      pcbX={12}
      pcbY={BARRIER_Y}
      pcbRotation={-90}
      schSectionName={sec}
      schX={20}
      schY={-3.8}
      connections={{
        AN: "net.OC_MISO_AN",
        CAT: "net.ISO_MISO",
        VCC: "net.V3V3",
        GND: "net.GND",
        VO: "net.ISO_MISO_RX",
      }}
    />
    <R
      name="R14"
      schRotation={-90}
      resistance="390"
      footprint="0603"
      pcbX={12}
      pcbY={BARRIER_Y - 5.8}
      schSectionName={sec}
      schX={17.4}
      schY={-3.4}
      connections={{ pin1: "net.V3V3_ISO", pin2: "net.OC_MISO_AN" }}
    />
    <C
      name="C34"
      {...decapSch("V3V3", 11)}
      capacitance="100nF"
      footprint="0603"
      pcbX={8.4}
      pcbY={BARRIER_Y + 4.4}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V3V3", pin2: "net.GND" }}
    />

    {/* Isolated 5 V -> 5 V 1 W converter, unregulated (needs >=10 % load) */}
    <B0505S_1WR3
      name="U4"
      pcbX={-32}
      pcbY={BARRIER_Y}
      pcbRotation={-90}
      schSectionName={sec}
      schX={20}
      schY={-7.4}
      connections={{
        GND: "net.GND",
        Vin_POS: "net.V5_DCDC",
        VO_NEG: "net.GND_ISO",
        VO_POS: "net.V5_ISO",
      }}
    />
    <CL10A106KP8NNNC
      name="C35"
      {...decapSch("V5_ISO", 0)}
      pcbX={-36.4}
      pcbY={4.4}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V5_ISO", pin2: "net.GND_ISO" }}
    />
    <R
      name="R15"
      {...decapSch("V5_ISO", 2)}
      resistance="470"
      footprint="0805"
      pcbX={-36.4}
      pcbY={0.4}
      pcbRotation={90}
      schRotation={-90}
      connections={{ pin1: "net.V5_ISO", pin2: "net.GND_ISO" }}
    />
  </>
)
