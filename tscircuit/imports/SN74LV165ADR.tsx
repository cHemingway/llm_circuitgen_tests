import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["SH","N_LD"],
  pin2: ["CLK"],
  pin3: ["E"],
  pin4: ["F"],
  pin5: ["G"],
  pin6: ["H"],
  pin7: ["N_QH"],
  pin8: ["GND"],
  pin9: ["QH"],
  pin10: ["SER"],
  pin11: ["A"],
  pin12: ["B"],
  pin13: ["C"],
  pin14: ["D"],
  pin15: ["CLKINH"],
  pin16: ["VCC"]
} as const

const pinAttributes = {
  pin8: {requiresGround: true},
  pin16: {requiresPower: true}
} as const

export const SN74LV165ADR = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C273656"
  ]
}}
      manufacturerPartNumber="SN74LV165ADR"
      footprint="soic16_pillpads_w7.44mm_pl1.97mm_pin1location(leftside,bottom)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C273656.obj?uuid=9adfdf34b7774b23880141fd3e8b4dbb",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C273656.step?uuid=9adfdf34b7774b23880141fd3e8b4dbb",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: -0.000012699999842880061, y: 0, z: 0.000575 },
      }}
      {...props}
    />
  )
}