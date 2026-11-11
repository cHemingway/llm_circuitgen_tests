import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["QB"],
  pin2: ["QC"],
  pin3: ["QD"],
  pin4: ["QE"],
  pin5: ["QF"],
  pin6: ["QG"],
  pin7: ["QH"],
  pin8: ["GND"],
  pin9: ["QH_"],
  pin10: ["SRCLR_n"],
  pin11: ["SRCLK"],
  pin12: ["RCLK"],
  pin13: ["OE_n"],
  pin14: ["SER"],
  pin15: ["QA"],
  pin16: ["VCC"]
} as const

const pinAttributes = {
  pin8: {requiresGround: true},
  pin16: {requiresPower: true}
} as const

export const SN74LV595ADR = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C205940"
  ]
}}
      manufacturerPartNumber="SN74LV595ADR"
      footprint="soic16_pillpads_w7.44mm_pl1.97mm_pin1location(leftside,bottom)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C205940.obj?uuid=9adfdf34b7774b23880141fd3e8b4dbb",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C205940.step?uuid=9adfdf34b7774b23880141fd3e8b4dbb",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: -0.000012699999842880061, y: 0, z: 0.000575 },
      }}
      {...props}
    />
  )
}