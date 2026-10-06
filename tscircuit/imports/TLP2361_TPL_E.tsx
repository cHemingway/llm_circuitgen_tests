import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["AN"],
  pin3: ["CAT"],
  pin4: ["GND"],
  pin5: ["VO"],
  pin6: ["VCC"]
} as const

const pinAttributes = {
  pin4: {requiresGround: true},
  pin6: {requiresPower: true}
} as const

export const TLP2361_TPL_E = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      symbol={
        <symbol>
          <schematicpath points={[{"x":-0.5,"y":0.4},{"x":-0.3,"y":0.4},{"x":-0.3,"y":-0.4},{"x":-0.5,"y":-0.4}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.38,"y":0.08},{"x":-0.22,"y":0.08},{"x":-0.3,"y":-0.04},{"x":-0.38,"y":0.08}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.38,"y":-0.04},{"x":-0.22,"y":-0.04}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.02,"y":0.16},{"x":-0.02,"y":-0.16},{"x":0.32,"y":-0.16}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.02,"y":0.16},{"x":0.32,"y":0.16}]} strokeColor="#880000" />
          <schematicpath svgPath="M 0.32 0.16 A 0.12 0.16 0 1 0 0.32 -0.16" strokeColor="#880000" />
          <schematicpath points={[{"x":0.4,"y":0.1},{"x":0.02,"y":0.1},{"x":0.02,"y":-0.1},{"x":0.06,"y":-0.02}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.02,"y":-0.1},{"x":-0.02,"y":-0.02}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0,"y":-0.12},{"x":0.38,"y":-0.12},{"x":0.38,"y":0.08},{"x":0.34,"y":0}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.38,"y":0.08},{"x":0.42,"y":0}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.1,"y":0.4},{"x":-0.1,"y":0.26}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.1,"y":0.2},{"x":-0.1,"y":0.04}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.1,"y":-0.04},{"x":-0.1,"y":-0.2}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.1,"y":-0.24},{"x":-0.1,"y":-0.4}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.1,"y":-0.4},{"x":0.5,"y":-0.4}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.44,"y":0},{"x":0.5,"y":0}]} strokeColor="#880000" />
          <schematicrect schX={0} schY={0} width={1} height={1.2} strokeWidth={0.02} color="#880000" />
          <port name="pin1" pinNumber={1} aliases={["AN"]} direction="left" schX={-0.9} schY={0.4} schStemLength={0.4} />
          <port name="pin3" pinNumber={3} aliases={["CAT"]} direction="left" schX={-0.9} schY={-0.4} schStemLength={0.4} />
          <port name="pin4" pinNumber={4} aliases={["GND"]} direction="right" schX={0.9} schY={-0.4} schStemLength={0.4} />
          <port name="pin5" pinNumber={5} aliases={["VO"]} direction="right" schX={0.9} schY={0} schStemLength={0.4} />
          <port name="pin6" pinNumber={6} aliases={["VCC"]} direction="right" schX={0.9} schY={0.4} schStemLength={0.4} />
          <schematictext schX={0} schY={0.806} text="{NAME}" fontSize={0.2} anchor="bottom_center" />
        </symbol>
      }
      supplierPartNumbers={{
  "jlcpcb": [
    "C107626"
  ]
}}
      manufacturerPartNumber="TLP2361(TPL,E"
      footprint={<footprint>
        <smtpad portHints={["pin6"]} pcbX="-3.149854mm" pcbY="-1.27mm" width="1.999996mm" height="0.6500114mm" radius="0.3250057mm" shape="pill" />
<smtpad portHints={["pin3"]} pcbX="3.175mm" pcbY="1.27mm" width="1.999996mm" height="0.6500114mm" radius="0.3250057mm" shape="pill" />
<smtpad portHints={["pin1"]} pcbX="3.149854mm" pcbY="-1.27mm" width="1.999996mm" height="0.6500114mm" radius="0.3250057mm" shape="pill" />
<smtpad portHints={["pin4"]} pcbX="-3.149854mm" pcbY="1.27mm" width="1.999996mm" height="0.6500114mm" radius="0.3250057mm" shape="pill" />
<smtpad portHints={["pin5"]} pcbX="-3.175mm" pcbY="0mm" width="1.999996mm" height="0.6500114mm" radius="0.3250057mm" shape="pill" />
<silkscreenpath route={[{"x":-2.299995399999716,"y":-1.797811999999908},{"x":-2.299995399999716,"y":-1.899869200000012}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":-0.518642600000021},{"x":-2.299995399999716,"y":-0.7421879999999419}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":0.7421879999999419},{"x":-2.299995399999716,"y":0.5188966000000619}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":1.900072399999999},{"x":2.2999700000002576,"y":1.900072399999999}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":-1.899869200000012},{"x":-0.508025399999724,"y":-1.899869200000012}]} />
<silkscreenpath route={[{"x":2.2999700000002576,"y":-1.899869200000012},{"x":0.5079746000002388,"y":-1.899869200000012}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":-1.899869200000012},{"x":-2.299995399999716,"y":-1.797685000000115}]} />
<silkscreenpath route={[{"x":-2.299995399999716,"y":1.7978881999999885},{"x":-2.299995399999716,"y":1.900072399999999}]} />
<silkscreenpath route={[{"x":2.2999700000002576,"y":-1.899869200000012},{"x":2.2999700000002576,"y":-1.797685000000115}]} />
<silkscreenpath route={[{"x":2.2999700000002576,"y":-0.7421118000000888},{"x":2.2999700000002576,"y":0.7421371999998883}]} />
<silkscreenpath route={[{"x":2.2999700000002576,"y":1.7980659999999489},{"x":2.2999700000002576,"y":1.900072399999999}]} />
<silkscreenpath route={[{"x":3.048000000000229,"y":-2.285898399999951},{"x":3.1967410559977907,"y":-2.1352563702960197},{"x":3.0467300000001387,"y":-1.9858789759853153},{"x":2.8967189440024868,"y":-2.135256370296247},{"x":3.0454600000002756,"y":-2.285898399999951}]} />
<silkscreenpath route={[{"x":-0.5079999999998108,"y":-1.899869200000012},{"x":0.5077460000002247,"y":-1.8998183999999583}]} />
<silkscreentext text="{NAME}" pcbX="0.11684mm" pcbY="2.893316mm" anchorAlignment="center" fontSize="1mm" />
<courtyardoutline outline={[{"x":-4.42499799999996,"y":2.10011059999988},{"x":4.424998000000073,"y":2.10011059999988},{"x":4.424998000000073,"y":-2.0998820000000933},{"x":-4.42499799999996,"y":-2.0998820000000933},{"x":-4.42499799999996,"y":2.10011059999988}]} />
      </footprint>}
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C107626.obj?uuid=2f86d20676d041f7afcf733787651bd9",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C107626.step?uuid=2f86d20676d041f7afcf733787651bd9",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: -0.000025400000367881148, y: -0.0001142999999501626, z: 0 },
      }}
      {...props}
    />
  )
}