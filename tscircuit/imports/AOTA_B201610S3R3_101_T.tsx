import type { InductorProps } from "@tscircuit/props"

export const AOTA_B201610S3R3_101_T = (props: Omit<InductorProps, "inductance">) => {
  return (
    <inductor
      inductance="3.3uH"
      supplierPartNumbers={{
  "jlcpcb": [
    "C42411119"
  ]
}}
      manufacturerPartNumber="AOTA-B201610S3R3-101-T"
      footprint="smdpads2_p2mm_pw1mm_ph1.6mm_cyw3.5mm_cyh2.11mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C42411119.obj?uuid=1fea8f9ef5b64dc68dc98052e0860c3b",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C42411119.step?uuid=1fea8f9ef5b64dc68dc98052e0860c3b",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: -0.0050000000000000044, z: -0.05 },
      }}
      {...props}
    />
  )
}