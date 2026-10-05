import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["GND"],
  pin2: ["Vin_POS"],
  pin3: ["VO_NEG"],
  pin4: ["VO_POS"]
} as const

const pinAttributes = {
  pin1: {requiresGround: true}
} as const

export const B0505S_1WR3 = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C5183119"
  ]
}}
      manufacturerPartNumber="B0505S-1WR3"
      footprint="pinrow4_nosquareplating_od1.8mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C5183119.obj?uuid=5a5bfc4de03a417ea9a8c415a9619e86",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C5183119.step?uuid=5a5bfc4de03a417ea9a8c415a9619e86",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: -2.104995799999874, z: -0.10000799999999987 },
      }}
      {...props}
    />
  )
}