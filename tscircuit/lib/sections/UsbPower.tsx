import { BF_180 } from "../../imports/BF_180"
import { USBLC6_2SC6 } from "../../imports/USBLC6_2SC6"
import { AP2112K_3_3TRG1 } from "../common/AP2112K_3_3TRG1"
import { BLM18PG121SN1D } from "../common/BLM18PG121SN1D"
import { CL10A106KP8NNNC } from "../common/CL10A106KP8NNNC"
import { C, R } from "../passives"
import { decapSch } from "../schLayout"

const sec = "usb_power"

/**
 * USB-B (vertical, top side), ESD protection, 3.3 V LDO for the MCU side and
 * the filtered 5 V feed for the isolated DC-DC converter.
 */
export const UsbPower = () => (
  <>
    <schematicsection name={sec} displayName="USB-B & 3.3 V supply" />

    <BF_180
      name="J1"
      pcbX={-31}
      pcbY={26}
      schSectionName={sec}
      schX={-18}
      schY={4}
      connections={{
        VCC: "net.VBUS",
        D_NEG: "net.USB_DM_CONN",
        D_POS: "net.USB_DP_CONN",
        GND1: "net.GND",
        GND2: "net.GND",
        GND3: "net.GND",
      }}
    />

    {/* USBLC6-2SC6: 1/6 = I/O1, 3/4 = I/O2, 2 = GND, 5 = VBUS */}
    <USBLC6_2SC6
      name="U3"
      pcbX={-19}
      pcbY={28.5}
      schSectionName={sec}
      schX={-14}
      schY={5}
      connections={{
        pin1: "net.USB_DM_CONN",
        pin6: "net.USB_DM_CONN",
        pin3: "net.USB_DP_CONN",
        pin4: "net.USB_DP_CONN",
        pin2: "net.GND",
        pin5: "net.VBUS",
      }}
    />
    <R
      name="R1"
      resistance="27"
      footprint="0402"
      pcbX={-14.5}
      pcbY={29.6}
      schSectionName={sec}
      schX={-11}
      schY={5.6}
      connections={{ pin1: "net.USB_DM_CONN", pin2: "net.USB_DM" }}
    />
    <R
      name="R2"
      resistance="27"
      footprint="0402"
      pcbX={-14.5}
      pcbY={28.2}
      schSectionName={sec}
      schX={-11}
      schY={4.4}
      connections={{ pin1: "net.USB_DP_CONN", pin2: "net.USB_DP" }}
    />

    <CL10A106KP8NNNC
      name="C1"
      pcbX={-21}
      pcbY={23.4}
      schSectionName={sec}
      schX={-15.6}
      schY={1.2}
      schOrientation="vertical"
      connections={{ pin1: "net.VBUS", pin2: "net.GND" }}
    />

    {/* MCU 3.3 V rail */}
    <AP2112K_3_3TRG1
      name="U2"
      pcbX={-17.5}
      pcbY={20}
      schSectionName={sec}
      schX={-12.6}
      schY={1.4}
      connections={{
        VIN: "net.VBUS",
        EN: "net.VBUS",
        GND: "net.GND",
        VOUT: "net.V3V3",
      }}
    />
    <CL10A106KP8NNNC
      name="C2"
      {...decapSch("V3V3", 0)}
      pcbX={-13.6}
      pcbY={20}
      pcbRotation={90}
      schOrientation="vertical"
      connections={{ pin1: "net.V3V3", pin2: "net.GND" }}
    />

    {/* Filtered 5 V feed to the isolated DC-DC converter */}
    <BLM18PG121SN1D
      name="FB1"
      schRotation={-90}
      pcbX={-26}
      pcbY={17.2}
      pcbRotation={-90}
      schSectionName={sec}
      schX={-15.6}
      schY={-1.6}
      connections={{ pin1: "net.VBUS", pin2: "net.V5_DCDC" }}
    />
    <C
      name="C3"
      capacitance="4.7uF"
      footprint="0603"
      pcbX={-27.6}
      pcbY={13.6}
      pcbRotation={90}
      schSectionName={sec}
      schX={-14.2}
      schY={-2.4}
      schOrientation="vertical"
      connections={{ pin1: "net.V5_DCDC", pin2: "net.GND" }}
    />
  </>
)
