import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["pin1"],
  pin2: ["pin2"],
  pin3: ["pin3"],
  pin4: ["pin4"],
  pin5: ["pin5"],
  pin6: ["pin6"],
  pin7: ["pin7"],
  pin8: ["pin8"]
} as const

export const A_4D03WGJ0103T5E = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      symbol={
        <symbol>
          <port name="pin1" pinNumber={1} aliases={["1"]} direction="left" schX={-0.7} schY={0.3} schStemLength={0.4} />
          <port name="pin2" pinNumber={2} aliases={["2"]} direction="left" schX={-0.7} schY={0.1} schStemLength={0.4} />
          <port name="pin3" pinNumber={3} aliases={["3"]} direction="left" schX={-0.7} schY={-0.1} schStemLength={0.4} />
          <port name="pin4" pinNumber={4} aliases={["4"]} direction="left" schX={-0.7} schY={-0.3} schStemLength={0.4} />
          <port name="pin5" pinNumber={5} aliases={["5"]} direction="right" schX={0.7} schY={-0.3} schStemLength={0.4} />
          <port name="pin6" pinNumber={6} aliases={["6"]} direction="right" schX={0.7} schY={-0.1} schStemLength={0.4} />
          <port name="pin7" pinNumber={7} aliases={["7"]} direction="right" schX={0.7} schY={0.1} schStemLength={0.4} />
          <port name="pin8" pinNumber={8} aliases={["8"]} direction="right" schX={0.7} schY={0.3} schStemLength={0.4} />
          <schematicpath points={[{"x":-0.3,"y":-0.3},{"x":-0.18,"y":-0.3}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":0.5},{"x":-0.3,"y":-0.5}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.3,"y":0.5},{"x":0.3,"y":-0.5}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":0.3},{"x":-0.18,"y":0.3}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":-0.1},{"x":-0.18,"y":-0.1}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":0.5},{"x":0.3,"y":0.5}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":0.1},{"x":-0.18,"y":0.1}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":0.34},{"x":0.18,"y":0.34}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":0.34},{"x":-0.18,"y":0.26},{"x":0.18,"y":0.26},{"x":0.18,"y":0.34}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":0.14},{"x":0.18,"y":0.14}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":0.14},{"x":-0.18,"y":0.06},{"x":0.18,"y":0.06},{"x":0.18,"y":0.14}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":-0.06},{"x":0.18,"y":-0.06}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":-0.06},{"x":-0.18,"y":-0.14},{"x":0.18,"y":-0.14},{"x":0.18,"y":-0.06}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":-0.26},{"x":0.18,"y":-0.26}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.18,"y":-0.26},{"x":-0.18,"y":-0.34},{"x":0.18,"y":-0.34},{"x":0.18,"y":-0.26}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.18,"y":0.3},{"x":0.3,"y":0.3}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.18,"y":0.1},{"x":0.3,"y":0.1}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.18,"y":-0.1},{"x":0.3,"y":-0.1}]} strokeColor="#880000" />
          <schematicpath points={[{"x":0.18,"y":-0.3},{"x":0.3,"y":-0.3}]} strokeColor="#880000" />
          <schematicpath points={[{"x":-0.3,"y":-0.5},{"x":0.3,"y":-0.5}]} strokeColor="#880000" />
          <schematictext schX={0} schY={0.7} text="{NAME}" fontSize={0.2} anchor="bottom_center" />
        </symbol>
      }
      supplierPartNumbers={{
  "jlcpcb": [
    "C29718"
  ]
}}
      manufacturerPartNumber="4D03WGJ0103T5E"
      footprint={<footprint>
        <smtpad portHints={["pin5"]} pcbX="1.199896mm" pcbY="0.7999984mm" width="0.6500114mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin4"]} pcbX="1.199896mm" pcbY="-0.7999984mm" width="0.6500114mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin6"]} pcbX="0.40005mm" pcbY="0.7999984mm" width="0.499999mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin3"]} pcbX="0.40005mm" pcbY="-0.7999984mm" width="0.499999mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin7"]} pcbX="-0.40005mm" pcbY="0.7999984mm" width="0.499999mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin2"]} pcbX="-0.40005mm" pcbY="-0.7999984mm" width="0.499999mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin8"]} pcbX="-1.199896mm" pcbY="0.7999984mm" width="0.6500114mm" height="0.7999984mm" shape="rect" />
<smtpad portHints={["pin1"]} pcbX="-1.199896mm" pcbY="-0.7999984mm" width="0.6500114mm" height="0.7999984mm" shape="rect" />
<silkscreenpath route={[{"x":1.8695670000000035,"y":-0.45001179999999863},{"x":1.8695670000000035,"y":-1.4497811999999897},{"x":-1.870328999999991,"y":-1.450035200000002},{"x":-1.870328999999991,"y":-0.409905199999983}]} />
<silkscreenpath route={[{"x":-1.8699480000000008,"y":0.44996100000000183},{"x":-1.8699480000000008,"y":1.4697710000000086},{"x":1.8699480000000008,"y":1.4700250000000068},{"x":1.8699480000000008,"y":0.4297171999999989}]} />
<silkscreentext text="{NAME}" pcbX="-0.0127mm" pcbY="2.473073mm" anchorAlignment="center" fontSize="1mm" />
<courtyardoutline outline={[{"x":-1.8499968000000067,"y":1.4499976000000032},{"x":1.8499968000000067,"y":1.4499976000000032},{"x":1.8499968000000067,"y":-1.449997599999989},{"x":-1.8499968000000067,"y":-1.449997599999989},{"x":-1.8499968000000067,"y":1.4499976000000032}]} />
      </footprint>}
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C29718.obj?uuid=551b3dd0a237409fa823f51b33d3f6d1",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C29718.step?uuid=551b3dd0a237409fa823f51b33d3f6d1",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: 0, z: 0 },
      }}
      {...props}
    />
  )
}