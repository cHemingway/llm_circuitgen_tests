# Konnect implementation

Solartron 7075 interface designed with [Konnect](https://github.com/mixelpixx/Konnect)
0.13.0, an MCP server that drives KiCad 10.0.6 (live IPC to the open editors,
with file-level tools for libraries and the schematic).

## Design

- 74 × 74 mm two-layer board. J1, a vertical DD-50 male (CAX DP-G-50P-ZC-YCLS,
  LCSC C54573066), sits on the bottom face, plugs into the meter's SKB socket
  and holds the board by its jackscrews. J2, a vertical USB-B (TE 5787834-1),
  sits on the top face.
- Meter side (GND_ISO): five SN74LVC165A shift registers read the 50-way
  interface's BCD and status lines through 100k pull-down networks. Two
  74LVC595A drive the command lines. An AMS1117-3.3 powers this side from a
  B0505S-1WR3 isolated DC-DC module.
- Isolation: six TLP2361 optocouplers carry the SPI-style links across a
  copper-free band about 4.8 mm wide. No net crosses the barrier.
- USB side (GND): RP2354A (internal flash), AP2112K-3.3, USBLC6-2SC6, BOOTSEL
  and RUN buttons, and an SWD header.
- Parts: KiCad's libraries, with LCSC numbers for every fitted part (the SWD
  header is optional and has none). KiCad has no DD-50, so its symbol and
  footprint are in the project library. The footprint follows the CAX
  part's drawing, checked against the DIN 41652 dimensions in Harting's
  catalogue. The project library also has a TLP2361 symbol with an
  inverting output.
- ERC: 0 errors, 0 warnings. DRC: 0 unconnected items and one cosmetic
  error: C17 pad 2 on the USB side, a ground pad with one thermal spoke
  where KiCad wants two, as in the first layout. The remaining items are
  warnings: footprints that differ from their library copies, silkscreen
  clipping, overlap and clearance, and a missing LCSC footprint field on the
  parity check.

## Review 1: pin swapping

The shift-register and resistor-array pins were re-assigned to untangle the
meter-side routing. The '165 inputs (D0–D7) are equivalent, as are the
'595 outputs (QA–QH) and the elements of the 100k arrays. The swaps were
therefore made both within each part and between identical parts.

- Each resistor array feeds one side of one '165. The 36 DVM outputs are
  taken in D-sub pin order, left to right. So the tracks run D-sub pin →
  array → '165 pin without crossing, almost all on the top layer.
- The '595 outputs follow the order of their D-sub pins. QA, the pin on the
  far side of the chip, takes the outermost signal.
- U16 D3..D0 keep the 0,0,1,1 signature. The SAMPLE line moved from U18
  QE/QD to QA/QC. The schematic's serial-link note now carries the full bit
  map that the firmware needs.
- The '165 LOAD and clock pins (1 and 2) escape to vias above each chip and
  join on two bottom-layer buses. Ground "pockets" (a bar and via over each
  array's ground pads, and vias for '165 pins 8 and 15) were placed before
  routing, so the input bus routes around them.
- The meter side was re-routed with Freerouting on top of those fixed
  pieces. The USB side was re-imported unchanged.

| Meter side | Before | After |
| --- | --- | --- |
| 36 '165 input nets | 1,343 mm, 53 vias | 781 mm, 7 vias |
| 13 '595 output nets | 157 mm, 7 vias | 118 mm, 1 via |
| 14 other nets (LOAD/SCK/MOSI/MISO, chain, +3V3_ISO) | 874 mm, 51 vias | 793 mm, 47 vias |
| All meter-side signals | 2,374 mm, 111 vias | 1,692 mm, 55 vias |
| GND_ISO stitching | 43 vias, 154 mm | 34 vias, 81 mm |

Whole board: 1,660 → 1,275 track segments and 201 → 136 vias.
`fab/routing_before_after.png` compares the meter-side routing before and after.

## Review 3: moving parts

The meter-side parts were moved, and the pins re-assigned again to suit.
This includes the swaps between parts offered in reply to review 2. The 36
DVM input tracks were laid out by a script, in one repeated pattern,
instead of by the autorouter.

- U16, the '165 with only four DVM inputs, moved from the middle of the row
  to the right-hand end. The nine '165 input sides that carry DVM lines now
  sit side by side, 11.08 mm per chip, which is twice the pitch of the
  D-sub's groups of four pins.
- Each array sits directly under its four D-sub pins, turned so that its
  signal pads face the connector. The tracks drop straight into the pads.
  On the way out, the outer two leave from the ends of the array, and the
  inner two run between its two rows of pads to the ends. Each '165 side
  takes two tracks from outside the chip and two from under the chip body.
- All 36 input tracks are on the top layer except DD-50 pin 36, which sits
  directly above pin 3. It uses one bottom-layer track and a via.
- The '165 decoupling caps moved to the top of each chip, between its two
  sets of input tracks, with a via to a bottom-layer +3V3_ISO spine. C29
  moved above the regulator to make room for U16. U19 turned round so that
  PRINT_LEVEL reaches its input directly.
- Both shift-register chains now run in board order. MOSI enters U18, U18
  feeds U17, and U17 loops back into U16. The '165 chain runs U16 → U15 →
  U14 → U12 → U13 → MISO. CMD_RATIO_N moved to U18 QD, next to the other
  U18 outputs. The serial-link note in the schematic has the new bit map.
- The script also placed:
  - the LOAD, SCK and OE buses on the bottom layer under both '595s, with a
    riser down the left of the D-sub;
  - SCK down a free channel under U15;
  - SIPO_CH1 under the '595 bodies;
  - a +3V3_ISO rail along the top edge and another along the opto row;
  - SIPO_LOOP down the right-hand side;
  - the '165 chain and MISO in a channel under the chips.
- Freerouting routed the rest: MOSI, the '595 outputs and the opto links.
  The USB side is unchanged.

| Meter side | Review 1 | Review 3 |
| --- | --- | --- |
| 36 '165 input nets | 781 mm, 7 vias | 655 mm, 1 via |
| 13 '595 output nets | 118 mm, 1 via | 96 mm, 0 vias |
| 14 other nets (LOAD/SCK/MOSI/MISO, chain, +3V3_ISO) | 793 mm, 47 vias | 807 mm, 35 vias |
| All meter-side signals | 1,692 mm, 55 vias | 1,558 mm, 36 vias |
| GND_ISO stitching | 34 vias, 81 mm | 27 vias, 65 mm |

Whole board: 1,275 → 958 track segments and 136 → 110 vias. DRC lost
Review 1's three starved thermals on the meter side (C24, C30 and C31). It
gained eight silkscreen overlap warnings, where the moved caps' reference
text overlaps the '165 outlines and C37's overlaps U19. Konnect has no tool
to move reference text. The positions file was regenerated; the BOM is
unchanged. `fab/routing_review3.png` compares the meter-side routing after
Review 1 and now.

| Path | Contents |
| --- | --- |
| `solartron_7075_interface_konnect.kicad_sch` / `.kicad_pcb` / `.kicad_pro` | KiCad project |
| `solartron.kicad_sym`, `solartron.pretty/` | Project symbols and footprints, including rect-pad copies of the stock footprints |
| `fab/` | Gerbers and drill files, JLCPCB BOM and positions, `schematic.pdf`, `pcb_layers.pdf`, DRC report, render, routing comparisons for reviews 1 and 3 |
| `CONVERSATION.md` | Session log and statistics |
| `stats.py`, `calls.csv` | Script for the statistics, and every API call with its category |
| `REVIEW_CONVERSATION.md` | Review log and statistics |
| `review_stats.py`, `review_calls.csv` | Script for the review statistics and log, and every review API call with its category |

## Notes on the tool

- Konnect's Specctra (Freerouting) export refuses roundrect pads, duplicate
  pad numbers and bottom-side footprints. Nearly every KiCad SMD footprint
  has roundrect pads. 15 stock footprints were therefore copied into the
  project library with rectangular pads. Routing-only variants were swapped
  in for the export and swapped back after the import: renumbered duplicate
  pads, and a front-side mirror of the bottom-mounted DD-50.
- The DSN export wrote each pin's rotation as an absolute angle, not relative
  to the footprint, so rotated parts had their pads turned twice and
  Freerouting reported 226 violations. The pin rotations were corrected in
  the scratch copy of the DSN. The session import then refused one part
  because the angles were written as 270 and −90, so those angles were
  normalised.
- Konnect has no tool to delete or move a via, or to delete a copper zone,
  and it deletes tracks one segment at a time. Its SES import also needs a
  board with no tracks, vias or zones. So re-routing after the pin swaps
  needed KiCad's own Edit ▸ Global Deletions, run in the GUI by screen
  control with the user's agreement. In Review 3 the same dialog was driven
  through the menu bar in the background. Each time, the whole board's
  copper was then re-imported through Konnect: the USB side unchanged, the
  meter side new.
- Konnect can move and rotate footprints but not their reference text, so
  silkscreen overlaps from moved parts stay as DRC warnings.
- KiCad's save rewrites the project's design rules and net classes, so the
  rules were re-applied before each DRC.
- The ground pours needed a lot of manual work: stitching vias, a
  ground-only Freerouting pass, a small grid router written in the
  scratchpad, and hand-placed thermal spokes.
- Freerouting 2.4.1 was downloaded with the user's permission and run both
  through Konnect and from the command line.

## Session statistics

`stats.py` reads the session transcript,
`~/.claude/projects/-Users-chris-repos-llm-circuitgen-tests/47e5c69c-808f-4cd7-8f0d-34a4d53529bd.jsonl`.
It takes everything before the export request (2026-10-15 18:44:30 UTC),
prints the tables in `CONVERSATION.md` and writes `calls.csv`. The export
itself ran in a resumed session, `3539381d-…`, whose file starts with a copy
of the original's later records. The original file is the complete record.

The review that followed ran in the same resumed session. `review_stats.py`
reads that session's transcript from the first review comment to the review
export request. It prints the review tables, writes `review_calls.csv` and,
with `--write-md`, writes `REVIEW_CONVERSATION.md`. The resumed session
writes no cost-state records, so the review figures come from the
transcript's per-response usage and tool timings, priced at the published
Opus 5.5 prices. `REVIEW_CONVERSATION.md` explains how each figure was
measured.

- **Totals** (tokens, API time, tool time and cost) come from the last
  `cost-state` record before the export request. API calls are the 520
  distinct assistant message ids; the usage-limit error message is not a
  call.
- **Active time** is measured from each typed message until the reply
  finished, giving four stretches.
  - Waiting for the user's answers to the two AskUserQuestion prompts (27 s
    and 2 min 14 s) is left out.
  - The 4 min stall between 20:52 and 20:57 on 2026-10-14 is left out. The
    session stopped after a tool result with no reply, and nothing ran
    until the user's "keep going".
  - Time waiting on background autorouter runs counts as active.
  - Each call is credited from its request (the record that triggered it)
    to the next call's request in the same stretch. The last call runs to
    the end of the stretch.
  - The 80 s compaction goes under Not attributable.
- **Categories** are set by call number in `stats.py`. Judgement calls:
  - The DD-50 footprint work (calls 43 and 68–71) is PCB. The search for a
    DD-50 drawing that came before it is Schematic & research, as part
    selection.
  - Everything from the schematic-to-PCB update (call 153) to the
    fabrication outputs (call 515) is PCB. That includes:
    - the rect-pad footprint copies, and pointing the schematic symbols at
      them;
    - the short replies to autorouter progress notifications;
    - the BOM export with the Gerbers.
  - Other covers:
    - creating the branch (call 1);
    - the two commits, the file send and the two summaries;
    - the connector status checks after "Continue" (calls 195–196).
- **Prices.** There are only two distinct cost-state snapshots, too few for
  a least-squares fit, so the published prices are used. They come from
  <https://platform.claude.com/docs/en/about-claude/pricing>, read on
  2026-10-15.
  - Claude Opus 5.5, per million tokens: $4 input, $5 for 5-minute cache
    writes, $8 for 1-hour cache writes, $0.20 for cache reads and $20 for
    output. The full 1M context is at standard prices.
  - Claude Haiku 5.5 (the web-tool helper): $0.10 input and $0.50 output for
    prompts up to 100k tokens, plus $10 per 1,000 web searches.

  Every cache write the transcript logs is a 1-hour write, and the 5-minute
  and 1-hour writes are priced separately per call. Checked against the
  snapshots:

  | Snapshot | Model | Reported | Published prices |
  | --- | --- | --- | --- |
  | 2026-10-14 21:05 | Opus 5.5 | $35.5377 | $35.5377 |
  | 2026-10-14 21:05 | Haiku 5.5 | $0.0777 | $0.0777 |
  | 2026-10-15 12:31 | Opus 5.5 | $112.1028 | $112.1034 |
  | 2026-10-15 12:31 | Haiku 5.5 | $0.0777 | $0.0777 |

  The $0.0006 gap in the second Opus snapshot is in usage the transcript
  doesn't log. Pricing that usage's cache writes as 1-hour writes slightly
  overstates it, which implies about 200 tokens of 5-minute writes.
- **Not attributable** is the counters minus the logged calls:
  - Opus: 6,153 input, 905,282 cache-write, 4,026,769 cache-read and 8,379
    output tokens, or $8.24.
  - Haiku: 143,884 tokens from web search and fetch, or $0.08.

  The first snapshot matches the logged calls exactly, so all of the
  unlogged Opus usage comes after it. That is more than one compaction
  summary of a 969k-token context would use. The counters also show 52 s of
  API time on retried requests, which the transcript doesn't log either.
  These retries are the likely remainder.
- **Thinking tokens** are part of the output tokens, as in the API's usage
  fields.
