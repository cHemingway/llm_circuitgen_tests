import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["IOVDD6"],
  pin2: ["GPIO0"],
  pin3: ["GPIO1"],
  pin4: ["GPIO2"],
  pin5: ["GPIO3"],
  pin6: ["DVDD3"],
  pin7: ["GPIO4"],
  pin8: ["GPIO5"],
  pin9: ["GPIO6"],
  pin10: ["GPIO7"],
  pin11: ["IOVDD5"],
  pin12: ["GPIO8"],
  pin13: ["GPIO9"],
  pin14: ["GPIO10"],
  pin15: ["GPIO11"],
  pin16: ["GPIO12"],
  pin17: ["GPIO13"],
  pin18: ["GPIO14"],
  pin19: ["GPIO15"],
  pin20: ["IOVDD4"],
  pin21: ["XIN"],
  pin22: ["XOUT"],
  pin23: ["DVDD2"],
  pin24: ["SWCLK"],
  pin25: ["SWDIO"],
  pin26: ["RUN"],
  pin27: ["GPIO16"],
  pin28: ["GPIO17"],
  pin29: ["GPIO18"],
  pin30: ["IOVDD3"],
  pin31: ["GPIO19"],
  pin32: ["GPIO20"],
  pin33: ["GPIO21"],
  pin34: ["GPIO22"],
  pin35: ["GPIO23"],
  pin36: ["GPIO24"],
  pin37: ["GPIO25"],
  pin38: ["IOVDD2"],
  pin39: ["DVDD1"],
  pin40: ["GPIO26_ADC0"],
  pin41: ["GPIO27_ADC1"],
  pin42: ["GPIO28_ADC2"],
  pin43: ["GPIO29_ADC3"],
  pin44: ["ADC_AVDD"],
  pin45: ["IOVDD1"],
  pin46: ["VREG_AVDD"],
  pin47: ["VREG_PGND"],
  pin48: ["VREG_LX"],
  pin49: ["VREG_VIN"],
  pin50: ["VREG_FB"],
  pin51: ["USB_DM"],
  pin52: ["USB_DP"],
  pin53: ["USB_OTP_VDD"],
  pin54: ["QSPI_IOVDD"],
  pin55: ["QSPI_SD3"],
  pin56: ["QSPI_SCLK"],
  pin57: ["QSPI_SD0"],
  pin58: ["QSPI_SD2"],
  pin59: ["QSPI_SD1"],
  pin60: ["QSPI_SS"],
  pin61: ["EP"]
} as const

const pinAttributes = {
  pin61: {isPassive: true, capabilities: [], requiresGround: true, includeInBoardPinout: false, mustBeConnected: true},
  pin60: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin59: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin58: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin57: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin56: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin55: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin54: {isInput: true, capabilities: [], requiresPower: true, requiresVoltage: 3.3, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin53: {isInput: true, capabilities: [], requiresPower: true, requiresVoltage: 3.3, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin52: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["uart_tx","i2c_sda"], canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin51: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["uart_rx","i2c_scl"], canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin50: {isInput: true, capabilities: [], mustBeConnected: true},
  pin49: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "4.7uF"},
  pin48: {isOutput: true, canUseTriState: true, capabilities: [], providesPower: true},
  pin47: {isPassive: true, capabilities: [], requiresGround: true, mustBeConnected: true},
  pin46: {isInput: true, capabilities: [], requiresPower: true, requiresVoltage: 3.3, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "4.7uF"},
  pin45: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin44: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin43: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin42: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin41: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin40: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin39: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin38: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin37: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin36: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin35: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin34: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin33: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin32: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin31: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin30: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin29: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin28: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin27: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin26: {isInput: true, capabilities: [], canUseInternalPullup: true},
  pin25: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: [], canUseInternalPullup: true, canUseInternalPulldown: true, canUsePushPull: true},
  pin24: {isInput: true, capabilities: [], canUseInternalPullup: true, canUseInternalPulldown: true},
  pin23: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "4.7uF"},
  pin22: {isOutput: true, capabilities: []},
  pin21: {isInput: true, capabilities: []},
  pin20: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin19: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin18: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin17: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin16: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin15: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin14: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin13: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin12: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin11: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin10: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin9: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin8: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin7: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin6: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"},
  pin5: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_mosi","i2c_scl","uart_rx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin4: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_sck","i2c_sda","uart_tx"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin3: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_cs","uart_rx","i2c_scl"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin2: {isInput: true, isOutput: true, isBidirectional: true, canUseTriState: true, capabilities: ["spi_miso","uart_tx","i2c_sda"], canUseInternalPullup: true, canUseInternalPulldown: true, canUseOpenDrain: true, canUsePushPull: true, isGpio: true},
  pin1: {isInput: true, capabilities: [], requiresPower: true, mustBeConnected: true, shouldHaveDecouplingCapacitor: true, recommendedDecouplingCapacitorCapacitance: "100nF"}
} satisfies NonNullable<ChipProps["pinAttributes"]>

const footprinterPinLabels = {
  ...pinLabels,
  "pin61": [...pinLabels["pin61"], "thermalpad"],
} as const

export const RP2354A = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={footprinterPinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C41378174"
  ]
}}
      manufacturerPartNumber="RP2354A"
      footprint="qfn60_thermalpad3.4mmx3.4mm_p0.4mm_h8.23mm_pw0.2mm_pl0.88mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C41378174.obj?uuid=6af829ad488a4e1689b27543b3583581",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C41378174.step?uuid=6af829ad488a4e1689b27543b3583581",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: 0, z: 0 },
      }}
      {...props}
    />
  )
}