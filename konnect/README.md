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
  starved-thermal error on C17 pad 2, which is connected by a track. The
  remaining items are warnings: footprints that differ from their library
  copies, silkscreen clipping and clearance, and a missing LCSC footprint
  field on the parity check.

| Path | Contents |
| --- | --- |
| `solartron_7075_interface_konnect.kicad_sch` / `.kicad_pcb` / `.kicad_pro` | KiCad project |
| `solartron.kicad_sym`, `solartron.pretty/` | Project symbols and footprints, including rect-pad copies of the stock footprints |
| `fab/` | Gerbers and drill files, JLCPCB BOM and positions, `schematic.pdf`, `pcb_layers.pdf`, DRC report, render |
| `CONVERSATION.md` | Session log and statistics |
| `stats.py`, `calls.csv` | Script for the statistics, and every API call with its category |

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
- Konnect has no tool to delete or move a via. KiCad's save rewrites the
  project's design rules and net classes, so the rules were re-applied before
  each DRC.
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
