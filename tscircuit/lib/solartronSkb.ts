/**
 * Solartron 7075 + Parallel BCD Interface Unit 70754, socket SKB
 * (50 way Cannon/D-sub, standard density, 3 rows).
 *
 * Source: inputs/solartron_7075_service_manual.pdf, Section 9,
 * "Systems Interface 50-way Cannon Socket Connections" (p. 9.9) and the
 * input/output code tables on pp. 9.2 - 9.7.
 *
 * Logic levels (p. 9.1): TTL. Inputs read logic 1 when left open (the manual
 * notes an unconnected interface reverts to DC volts / 10 s integration), so
 * every command line is driven open-drain from this board.
 */

export type SkbDirection = "out" | "in" | "ground"

export interface SkbPin {
  pin: number
  /** Port label used on the connector and in net names (`net.DVM_<label>`) */
  label: string
  /** Direction as seen from the DVM ("out" = DVM drives it) */
  dir: SkbDirection
  description: string
}

export const SKB_PINS: SkbPin[] = [
  { pin: 1, label: "D6_1", dir: "out", description: "BCD 1 x 10^6 (half digit)" },
  { pin: 2, label: "D5_8", dir: "out", description: "BCD 8 x 10^5" },
  { pin: 3, label: "D5_4", dir: "out", description: "BCD 4 x 10^5" },
  { pin: 4, label: "D5_2", dir: "out", description: "BCD 2 x 10^5" },
  { pin: 5, label: "D5_1", dir: "out", description: "BCD 1 x 10^5" },
  { pin: 6, label: "D4_8", dir: "out", description: "BCD 8 x 10^4" },
  { pin: 7, label: "D4_4", dir: "out", description: "BCD 4 x 10^4" },
  { pin: 8, label: "D4_2", dir: "out", description: "BCD 2 x 10^4" },
  { pin: 9, label: "D4_1", dir: "out", description: "BCD 1 x 10^4" },
  { pin: 10, label: "D3_8", dir: "out", description: "BCD 8 x 10^3" },
  { pin: 11, label: "D3_4", dir: "out", description: "BCD 4 x 10^3" },
  { pin: 12, label: "D3_2", dir: "out", description: "BCD 2 x 10^3" },
  { pin: 13, label: "D3_1", dir: "out", description: "BCD 1 x 10^3" },
  { pin: 14, label: "D2_8", dir: "out", description: "BCD 8 x 10^2" },
  { pin: 15, label: "D2_4", dir: "out", description: "BCD 4 x 10^2" },
  { pin: 16, label: "D2_2", dir: "out", description: "BCD 2 x 10^2" },
  { pin: 17, label: "D2_1", dir: "out", description: "BCD 1 x 10^2" },
  { pin: 18, label: "D1_8", dir: "out", description: "BCD 8 x 10^1" },
  { pin: 19, label: "D1_4", dir: "out", description: "BCD 4 x 10^1" },
  { pin: 20, label: "D1_2", dir: "out", description: "BCD 2 x 10^1" },
  { pin: 21, label: "D1_1", dir: "out", description: "BCD 1 x 10^1" },
  { pin: 22, label: "D0_8", dir: "out", description: "BCD 8 x 10^0" },
  { pin: 23, label: "D0_4", dir: "out", description: "BCD 4 x 10^0" },
  { pin: 24, label: "D0_2", dir: "out", description: "BCD 2 x 10^0" },
  { pin: 25, label: "D0_1", dir: "out", description: "BCD 1 x 10^0" },
  { pin: 26, label: "POL_POS", dir: "out", description: "Polarity +ve (26,27: 10=+, 01=-, 00=AC/ohms)" },
  { pin: 27, label: "POL_NEG", dir: "out", description: "Polarity -ve" },
  { pin: 28, label: "FUNC_OUT_28", dir: "out", description: "Function output (28,29: 11=DC 01=AC 10=ohms 00=check)" },
  { pin: 29, label: "FUNC_OUT_29", dir: "out", description: "Function output" },
  { pin: 30, label: "RANGE_OUT_4", dir: "out", description: "Range output code (4)" },
  { pin: 31, label: "RANGE_OUT_2", dir: "out", description: "Range output code (2)" },
  { pin: 32, label: "RANGE_OUT_1", dir: "out", description: "Range output code (1)" },
  { pin: 33, label: "PRINT_PULSE", dir: "out", description: "PRINT command pulse, 10-30 us high at end of measurement" },
  { pin: 34, label: "PRINT_LEVEL", dir: "out", description: "PRINT command level, low during measurement, high when data valid" },
  { pin: 35, label: "DATA_CAN_CHANGE", dir: "out", description: "DATA CAN CHANGE, inverse of pin 34" },
  { pin: 36, label: "OVERLOAD", dir: "out", description: "Overload" },
  { pin: 37, label: "EARTH", dir: "ground", description: "Earth / logic 0 level" },
  { pin: 38, label: "LOCKOUT_N", dir: "in", description: "Front panel lockout, 0 = lockout" },
  { pin: 39, label: "SAMPLE_CONTACT", dir: "in", description: "Contact sample: closure to pin 37 (<2 ms bounce)" },
  { pin: 40, label: "SAMPLE_PULSE", dir: "in", description: "Pulse sample: +3..+8 V, >100 us" },
  { pin: 41, label: "RATIO_N", dir: "in", description: "Ratio, 0 = ratio commanded" },
  { pin: 42, label: "FUNC_CMD_42", dir: "in", description: "Function command (43,42: 11=DC 01=AC 10=ohms 00=check)" },
  { pin: 43, label: "FUNC_CMD_43", dir: "in", description: "Function command" },
  { pin: 44, label: "INT_CMD_4", dir: "in", description: "Integration time (4): 011=1ms 100=20ms 101=100ms 110=1s 111=10s" },
  { pin: 45, label: "INT_CMD_2", dir: "in", description: "Integration time (2)" },
  { pin: 46, label: "INT_CMD_1", dir: "in", description: "Integration time (1)" },
  { pin: 47, label: "AUTORANGE_INH", dir: "in", description: "1 = autorange inhibited (use range command)" },
  { pin: 48, label: "RANGE_CMD_1", dir: "in", description: "Range command (1)" },
  { pin: 49, label: "RANGE_CMD_2", dir: "in", description: "Range command (2)" },
  { pin: 50, label: "RANGE_CMD_4", dir: "in", description: "Range command (4)" },
]

export const skbPin = (pin: number): SkbPin => {
  const p = SKB_PINS.find((p) => p.pin === pin)
  if (!p) throw new Error(`No SKB pin ${pin}`)
  return p
}

/** Net name for an SKB signal, e.g. `net.DVM_D6_1` */
export const dvmNet = (pin: number) => `net.DVM_${skbPin(pin).label}`

// Which shift-register pin serves each signal, and the resulting firmware bit
// maps, are in ./dvmPinMap.ts.
