import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["1A"],
  pin2: ["1Y"],
  pin3: ["2A"],
  pin4: ["2Y"],
  pin5: ["3A"],
  pin6: ["3Y"],
  pin7: ["GND"],
  pin8: ["4Y"],
  pin9: ["4A"],
  pin10: ["5Y"],
  pin11: ["5A"],
  pin12: ["6Y"],
  pin13: ["6A"],
  pin14: ["VCC"]
} as const

const pinAttributes = {
  pin7: {requiresGround: true},
  pin14: {requiresPower: true}
} as const

export const SN74LVC07ADR = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C7659"
  ]
}}
      manufacturerPartNumber="SN74LVC07ADR"
      footprint="soic14_pillpads_w7.28mm_pw0.57mm_pl2.04mm_pin1location(leftside,bottom)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C7659.obj?uuid=265efcdb862f47cf9eef6843d570fde7",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C7659.step?uuid=265efcdb862f47cf9eef6843d570fde7",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: -0.000025399999913133797, z: -0.099425 },
      }}
      {...props}
    />
  )
}