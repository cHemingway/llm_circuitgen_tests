# Solartron 7075 USB interface

An RP2354A-based, opto-isolated USB interface for the Solartron 7075 digital
multimeter, described in [Manta](https://github.com/Derrick-Derrickson/Manta).
It plugs straight onto the meter's 50-way D socket and lies flat against the
back of the instrument.

```
 USB-B ── ESD ── RP2354A ──┬─ 4 × TLP2361 ──▶ SCLK, DIN, LATCH, nOE ─┬─ 5 × 74HCT165 ◀── SKB 1-36 (meter outputs)
   │                       └─ 1 × TLP2361 ◀── serial data back ─────┘   2 × 74HCT595 ──▶ SKB 38-50 (meter commands)
   └── FB ── B0509S (isolated 1 W) ── HT7550 5 V ─────────────────────── meter-side logic, referenced to SKB 37
        USB ground (GND)        ║ isolation barrier ║        meter earth / logic 0 (ISO-GND)
```

Only five logic signals cross the barrier. Every meter-side part is powered
from the isolated converter and referenced to SKB pin 37, so the USB host's
ground never touches the meter.

## The interface it targets

The 50-way connector is **SKB of the Parallel BCD Interface Unit 70754**, the
interface documented in section 9 of the service manual (connection table on
page 9.9). That is the socket this board's pinout follows. A 7075 *without*
the 70754 fitted has only SK1 on its rear panel, which carries the meter's
internal word-serial bus instead and is **not** compatible with this board.

| SKB pins | Direction | Signals |
|---|---|---|
| 1–25 | meter → board | Staticised BCD: 1×10⁶, then 8/4/2/1 × 10⁵ … 10⁰ |
| 26, 27 | meter → board | Polarity: 10 = +, 01 = −, 00 = AC/Ω |
| 28, 29 | meter → board | Function: 11 DC, 01 AC, 10 Ω, 00 CHECK |
| 30–32 | meter → board | Range output (4, 2, 1) |
| 33, 34, 35, 36 | meter → board | PRINT pulse, PRINT level, DATA CAN CHANGE, OVERLOAD |
| 37 | — | Earth / logic 0 → ISO-GND |
| 38–50 | board → meter | Lockout, contact SAMPLE, pulse SAMPLE, RATIO, function, integration time, AUTORANGE, range |

Levels (manual p. 9.1): meter outputs high 2.4–6 V from 6 kΩ, low < 0.5 V at
10 mA; meter inputs high 2.4–5 V at 100 µA, low < 0.5 V at a 5 mA sink. The
input circuits (Diag 9.2) are TTL gates with 4.7 kΩ pull-ups, so an
undriven input reads 1.

## Layout of this folder

| Path | What |
|---|---|
| `src/board.manta` | The board, top block `solartron-7075-usb`, one `--- SECTION` per functional group |
| `src/*.manta` | One part per file with its datasheet excerpt after `---`; commodity passives share `passives.manta` |
| `solartron7075.mantaRules` | Project checks: logic levels, footprints present, every fitted part has an LCSC code |
| `solartron7075.fpmap` | Package → KiCad footprint translation |
| `footprints/Solartron7075.pretty` | Two generated footprints KiCad lacks (DD-50 vertical plug, polarised AOTA inductor land) |
| `tools/` | Footprint generator, LCSC BOM grouper, netlist verifier |
| `output/` | Netlist, KiCad netlist, HTML schematic, BOMs, verification report |
| `build.sh` | The whole build |

```sh
./build.sh
```

runs `fmt --check`, `compile`, `check -Werror` with the project rules, `link`
with the BOM, the KiCad `export` and `render` (both `-Werror`), then the
footprint generator, the LCSC BOM and the netlist verifier. Every stage was
silent on the committed sources. To use the KiCad netlist, add
`footprints/Solartron7075.pretty` to the project footprint table as
`Solartron7075`.

## Parts

From **manta's own part library** (`examples/blinky`), unchanged apart from an
added `#lcsc` code and, where the library left it open, an `#~mpn`:
AP2112K-3.3 LDO, USBLC6-2SC6 ESD array, 1 kΩ and 10 kΩ RC0603 resistors,
100 nF / 1 µF / 10 µF capacitors, the 0603 green LED, and the `usb2` harness.

Everything else was chosen from **LCSC**; `output/solartron7075-bom-lcsc.csv`
has one line per part with its LCSC code. All 98 placements have one.

| Ref | Part | LCSC | Why |
|---|---|---|---|
| U1 | RP2354A | C41378174 | As requested; 2 MB flash in package |
| U10–U14 | Toshiba TLP2361 | C107626 | 15 MBd optocoupler, 2.7–5.5 V output side, 1.3 mA threshold |
| U20–U24 | TI CD74HCT165M96 | C352828 | TTL-level inputs for the meter's 2.4 V highs |
| U30, U31 | Nexperia 74HCT595D | C282339 | 3-state outputs, 0.33 V at 6 mA for the meter's 0.5 V / 5 mA lows |
| PS1 | YLPTEC B0509S-1WR3 | C5369463 | 1 W isolated, 1.5 kV DC |
| U4 | UMW HT7550-1 | C347189 | 30 V-input 5 V LDO behind the unregulated 9 V |
| L1 | Abracon AOTA-B201610S3R3-101-T | C42411119 | The polarity-marked inductor the RP2350 datasheet requires |
| Y1 | Abracon ABM8-272-T3 | C20625731 | The crystal the RP2350 design guide specifies |
| J1 | Amphenol DD50P364TXLF | C5402574 | Vertical DD-50 plug with plain flange holes for jackscrews |
| J2 | TE 5787834-1 | C592900 | Vertical USB-B |
| J3 | JST SM03B-SRSS-TB | C160403 | Raspberry Pi debug-probe connector |
| RN1–RN18 | Uniroyal 4D03 10 k / 100 k | C29718 / C1996 | Series protection and pull-ups on the 36 meter outputs |

**Stock at design time (2026-10-10):** DD50P364TXLF showed 0 at LCSC (RS and
other distributors list it). LCSC's only stocked vertical DD-50 plug, CAX
DP-G-50P-ZC-YCLS (C54573066), has riveted board locks and female 4-40
screwlocks, which jackscrews cannot pass through, so it is not a drop-in
substitute. The AOTA inductor (109) and the JST header (15) were also low.

## Firmware interface

### Pins

| RP2354A | Net | Notes |
|---|---|---|
| GPIO2 | MCU-SCLK | SPI0 SCK. Inverted by the optocoupler |
| GPIO3 | MCU-MOSI | SPI0 TX. Inverted |
| GPIO4 | MCU-MISO | SPI0 RX. **True** polarity (inverted twice) |
| GPIO5 | MCU-LATCH | SPI0 CSn. Inverted |
| GPIO6 | MCU-OE | High enables the command outputs |
| GPIO25 | MCU-LED | Status LED, active high |

Use the RP2354's per-pin output inversion (or a PIO program) so the meter
side sees the intended levels. At reset the pins are high-impedance and
pulled low, every opto LED is dark and the '595 outputs are disabled, so the
meter sees no command until firmware enables them.

### One transfer

On the meter side this is SPI mode 0: SR-CLK idles low, both chains shift on
its rising edge, and the '165 presents bit 1 as soon as it is loaded.

1. Hold **MCU-SCLK high** (meter-side clock low). The 74HCT165 datasheet
   requires CP low when PL rises.
2. Pulse **MCU-LATCH high, then low**: the '165s capture all 40 inputs, and
   the rising edge of SR-LATCH copies the command shifted in last time onto
   the '595 outputs.
3. Clock 40 bits. For each bit: put the *complement* of the command bit on
   MCU-MOSI, read MCU-MISO, then take MCU-SCLK low and back high.

Keep the clock at or below about 1 MHz: each optocoupler adds up to 80 ns and
MISO comes back through two of them plus the '165.

Before the first `MCU-OE` high, run one transfer and one latch so the '595s
hold a known command (all ones is "no command").

### Bits read on MISO (1 = first after the latch)

| Bits | Content |
|---|---|
| 1–36 | SKB pins 1–36, in order: bit *n* is SKB pin *n* |
| 37 | Always 1 |
| 38 | Always 0 |
| 39 | nSR-OE as the meter side sees it: 1 = commands disabled |
| 40 | The SKB 38 command bit from the previous transfer, read back from the end of the '595 chain |

With the board unplugged from the meter, bits 1–36 read 1 through the
pull-ups, so every BCD digit reads 0xF.

### Command bits (the last 16 shifted in; 1 = first of them)

| Bit | SKB | Meaning (manual pp. 9.2–9.4) |
|---|---|---|
| 1 | 38 | FRONT PANEL LOCKOUT, 0 = locked out (puts the meter in REMOTE) |
| 2 | 39 | CONTACT SAMPLE, 0 = contact closed |
| 3 | 40 | PULSE SAMPLE: 1 for > 10 µs, then 0, takes a reading |
| 4 | 41 | RATIO, 0 = ratio (DC and AC only) |
| 5, 6 | 42, 43 | Function (43, 42): 11 DC, 01 AC, 10 Ω, 00 CHECK |
| 7–9 | 44–46 | Integration time (4, 2, 1): 011 1 ms, 100 20 ms, 101 100 ms, 110 1 s, 111 10 s |
| 10 | 47 | AUTORANGE: 1 = use the commanded range, 0 = autorange |
| 11–13 | 48–50 | Range (1, 2, 4), table on p. 9.3; 111 = autorange |
| 14–16 | — | Spare |

A reading is ready when bit 34 (PRINT level) is 1; bit 35 (DATA CAN CHANGE)
is its complement. The manual's timing is on p. 9.8.

`output/verify.txt` is these two maps derived from the netlist itself rather
than from this text.

## Layout notes

- **J1 on the bottom side, J2 on the top.** J1 is a through-hole part placed
  on the bottom (KiCad mirrors it); its two `SH` pads are the 3.2 mm
  jackscrew holes and the board's only fixing. All SMD parts go on the top.
- **Isolation gap.** Keep a continuous copper-free gap between the GND and
  ISO-GND domains, crossed only by U10–U14 and PS1. No pour, plane or trace
  may span it. PS1 is rated 1500 V DC for 1 minute and the TLP2361 3750 Vrms;
  the gap width is a layout decision this schematic does not make.
- **RP2354A core regulator.** Copy the RP2350 datasheet's Figure 26: C21, C22,
  L1, C24/R3 on the top side, tight loops, copper cut away under L1. L1's
  pad 1 (silkscreen dot) is the dotted end and goes to 1V1.
- **TLP2361 bypass** capacitors within 1 cm of pins 4 and 6.
- **USB pair** at 90 Ω differential through U2 and R1/R2.

## What has and has not been verified

Verified, by running it:

- `manta check -Werror` with the project rules: no findings. The rules were
  mutation-tested: a '595 VOL of 0.6 V, a 1.9 V opto VOH and a missing LCSC
  code are each reported.
- `link`, KiCad `export` and `render`, all under `-Werror`.
- `tools/verify_netlist.py`: the two ground domains (33 USB-side and 102
  meter-side nets) meet only through the five optocouplers and PS1, each
  oriented correctly; and the bit order above is simulated from the netlist.
  Rewiring one opto's LED to the wrong ground makes it fail, which manta's own
  checks do not catch.

Not verified:

- No PCB has been laid out, so there is no DRC and no 3D check of J1 against
  the meter's socket.
- The two generated footprints were drawn from the manufacturers' drawings
  but have not been opened in KiCad or checked against a physical part.
- The rendered schematic passed `render -Werror` but was not inspected by eye.
- No firmware has been written.
- Current draws are estimates (about 15–20 mA on the meter side, under
  150 mA from USB); the RP2350 datasheet gives no single active-current
  figure to put on the budget, so the design carries no `#DRAW` rule.
- That the meter has a 70754 fitted, as discussed above.
