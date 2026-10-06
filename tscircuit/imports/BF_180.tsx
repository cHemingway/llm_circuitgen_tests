import type { ConnectorProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["VCC"],
  pin2: ["D_NEG"],
  pin3: ["D_POS"],
  pin4: ["GND1"],
  pin5: ["GND3"],
  pin6: ["GND2"]
} as const

const pinAttributes = {
  pin1: {requiresPower: true},
  pin4: {requiresGround: true},
  pin5: {requiresGround: true},
  pin6: {requiresGround: true}
} as const

export const BF_180 = (props: ConnectorProps) => {
  return (
    <connector
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C6081376"
  ]
}}
      manufacturerPartNumber="BF 180"
      footprint={<footprint insertionDirection="from_above">
        <platedhole  portHints={["pin1"]} pcbX="1.249807mm" pcbY="1.599946mm" holeWidth="0.999998mm" holeHeight="0.999998mm" outerWidth="1.7999964mm" outerHeight="1.7999964mm" rectPad={true} pcbRotation="0deg" shape="pill" />
<platedhole  portHints={["pin2"]} pcbX="-1.250061mm" pcbY="1.599946mm" outerDiameter="1.7999964mm" holeDiameter="0.999998mm" shape="circle" />
<platedhole  portHints={["pin3"]} pcbX="-1.250061mm" pcbY="-1.599946mm" outerDiameter="1.7999964mm" holeDiameter="0.999998mm" shape="circle" />
<platedhole  portHints={["pin4"]} pcbX="1.250061mm" pcbY="-1.599946mm" outerDiameter="1.7999964mm" holeDiameter="0.999998mm" shape="circle" />
<platedhole  portHints={["pin6"]} pcbX="6.019927mm" pcbY="-0.900176mm" outerDiameter="2.999994mm" holeDiameter="2.3000208mm" shape="circle" />
<platedhole  portHints={["pin5"]} pcbX="-6.019927mm" pcbY="-0.900176mm" outerDiameter="2.999994mm" holeDiameter="2.3000208mm" shape="circle" />
<silkscreenpath route={[{"x":-3.8103810000000067,"y":-3.937253999999939},{"x":-3.8103810000000067,"y":1.5339060000001155},{"x":-3.8103810000000067,"y":2.5397460000000365},{"x":-2.540381000000025,"y":3.8097460000000183},{"x":2.539619000000016,"y":3.8097460000000183},{"x":3.809618999999998,"y":2.5397460000000365},{"x":3.809618999999998,"y":-3.937253999999939},{"x":-3.437001000000123,"y":-3.937253999999939},{"x":-3.8103810000000067,"y":-3.937253999999939}]} />
<silkscreenpath route={[{"x":-6.000038800000084,"y":5.229936200000111},{"x":-6.000038800000084,"y":0.8309610000000021}]} />
<silkscreenpath route={[{"x":5.999937199999977,"y":5.229936200000111},{"x":-6.000038800000084,"y":5.229936200000111}]} />
<silkscreenpath route={[{"x":5.999937199999977,"y":-2.631058999999823},{"x":5.999937199999977,"y":-5.7700417999999445}]} />
<silkscreenpath route={[{"x":5.999937199999977,"y":5.229936200000111},{"x":5.999937199999977,"y":0.8309610000000021}]} />
<silkscreenpath route={[{"x":-6.000038800000084,"y":-2.631058999999823},{"x":-6.000038800000084,"y":-5.7700417999999445}]} />
<silkscreenpath route={[{"x":5.999937199999977,"y":-5.7700417999999445},{"x":-6.000038800000084,"y":-5.7700417999999445}]} />
<silkscreentext text="{NAME}" pcbX="-0.005461mm" pcbY="6.257546mm" anchorAlignment="center" fontSize="1mm" />
<fabricationnotepath route={[{"x":-3.937381000000073,"y":-3.937253999999939},{"x":-3.937381000000073,"y":1.5339060000000018},{"x":-3.937381000000073,"y":2.5397460000000365},{"x":-3.927721434902651,"y":2.5883518017809592},{"x":-3.900195399999916,"y":2.6295604000000594},{"x":-2.630195399999934,"y":3.8995604000000412},{"x":-2.5889868017809476,"y":3.9270864349026624},{"x":-2.5403810000001386,"y":3.9367460000000847},{"x":2.5396189999999024,"y":3.9367460000000847},{"x":2.588224801780939,"y":3.9270864349026624},{"x":2.6294333999999253,"y":3.8995604000000412},{"x":3.899433399999907,"y":2.6295604000000594},{"x":3.9269594349025283,"y":2.5883518017809592},{"x":3.936618999999837,"y":2.5397460000000365},{"x":3.936618999999837,"y":-3.937253999999939},{"x":3.8994215612107155,"y":-4.027056561210657},{"x":3.809618999999884,"y":-4.064253999999892},{"x":-3.4290000000000873,"y":-4.063999999999851},{"x":-3.3020000000001346,"y":-3.936999999999898},{"x":-3.4290000000000873,"y":-3.8099999999998317},{"x":3.6826189999999315,"y":-3.8102539999998726},{"x":3.6826189999999315,"y":2.4871426000001975},{"x":2.4870155999999497,"y":3.6827460000000656},{"x":-2.487777600000072,"y":3.6827460000000656},{"x":-3.6833810000001677,"y":2.4871426000001975},{"x":-3.6833810000001677,"y":1.5339060000000018},{"x":-3.6833810000001677,"y":-3.937253999999939},{"x":-3.8103810000001204,"y":-3.8102539999998726},{"x":-3.937381000000073,"y":-3.937253999999939}]} strokeWidth="0.254mm" />
<courtyardoutline outline={[{"x":-7.76992400000006,"y":5.479936200000111},{"x":7.769923999999946,"y":5.479936200000111},{"x":7.769923999999946,"y":-6.0200417999999445},{"x":-7.76992400000006,"y":-6.0200417999999445},{"x":-7.76992400000006,"y":5.479936200000111}]} />
      </footprint>}
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C6081376.obj?uuid=431f072ee54e4797a0d238808c7fea5a",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C6081376.step?uuid=431f072ee54e4797a0d238808c7fea5a",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0.00005080000005364127, y: 0.2700527999999167, z: -16.1000126 },
      }}
      {...props}
    />
  )
}