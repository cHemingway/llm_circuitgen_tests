# llm_circuitgen_tests

A benchmark of "circuit as code" tools for LLM-aided circuit design. Every tool
gets the same design brief, and each implementation lives in its own top-level
folder.

## Brief

This repository is a benchmark of various "circuit as code" tools for LLM-aided
circuit design. Each tool is given the same prompt, with the tool name and branch
substituted where needed:

> Use `<tool>` to design me a RP2354A powered Solartron 7075 multimeter
> interface, using the 50 way D connector on the Solartron. Put it in the folder
> `<tool>`. Do these changes on a new branch.
>
> DO NOT LOOK AT OTHER BRANCHES FOR CODE, RELY ON THE TOOL, THE DATASHEET, AND
> WHAT YOU CAN FIND ONLINE ONLY, DON'T COPY THE OUTPUTS OF OTHER TOOLS USED IN
> THIS BENCHMARK.
>
> In the top level folder `inputs` is a datasheet for the multimeter. It
> describes how the interface works in section 9.
>
> Signals to/from the multimeter should be opto-isolated to prevent USB ground
> noise from affecting the system. I was thinking therefore they should be done
> through shift registers to minimise the number of signals across the isolation
> barrier.
>
> Select parts from `<tool>`'s library, then LCSC where possible.
>
> Have the board sit flat on the back of the multimeter, using a vertical PCB
> mount D-Sub connector on one side and a vertical USB-B connector on the other
> side of the board.
>
> The board will be rectangular, and mechanically fixed to the solartron using
> the jackscrews on the D-Sub connector, so doesn't need any other mounting
> holes.

## Results

| Tool | Folder | Active time | of which tool time | Total tokens | API calls | API-price estimate | Schematic | PCB prints | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [tscircuit](https://tscircuit.com) | `tscircuit/` | 3 h 11 min | 2 h 06 min | 156.3 M | 376 | $59.32 | [PDF](tscircuit/outputs/schematic.pdf) | [PDF](tscircuit/outputs/pcb-prints.pdf) | Parts from tscircuit/common, then LCSC. Session log and statistics: [`tscircuit/CONVERSATION.md`](tscircuit/CONVERSATION.md) |
| [atopile](https://atopile.io) | `atopile/` | 1 h 46 min | 38 min | 149.5 M | 370 | $49.34 | [PDF](atopile/schematic/solartron_7075_usb.pdf) | [PDF](atopile/fab/solartron_7075_usb_prints.pdf) | CLI version (`ato`, 0.15.x). This is the last open CLI line and is effectively end-of-life: [PyPI](https://pypi.org/project/atopile/) lists 0.15.9 (12 Sep 2026) as the latest release, and atopile has moved on to [0.16](https://atopile.io/enterprise). Parts from atopile's library, then LCSC. Session log and statistics: [`atopile/CONVERSATION.md`](atopile/CONVERSATION.md) |
| [SKiDL](https://github.com/devbisme/skidl) | `skidl/` | 2 h 29 min | 59 min | 124.5 M | 347 | $46.64 | [PDF](skidl/pcb/render/schematic.pdf) | [PDF](skidl/pcb/print/pcb_prints.pdf) | SKiDL 2.3.0 on KiCad 10 (the brief added "use KiCad 10"). SKiDL has no part library of its own, so parts come from KiCad's libraries, then LCSC. Board built with kinet2pcb and routed with Freerouting 2.5. SKiDL's schematic generator mis-connects nets on this design, so the schematic is drawn by a script and checked against the netlist. Statistics run to the conversation export, and exclude the merge into `main` that came after it. Session log and statistics: [`skidl/CONVERSATION.md`](skidl/CONVERSATION.md) |
| [Manta](https://github.com/Derrick-Derrickson/Manta) | `manta/` | 46 min | – | 62.9 M | 191 | – | [HTML](manta/output/solartron7075.html) | – | Manta 2.0.1 (language revision 2.0). Manta is a schematic and netlist language with no layout, so the result is a checked netlist, a KiCad netlist (with a footprint map and two generated footprints), an LCSC BOM and an HTML schematic. No PCB was made, so there are no prints. Manta's only part library is its `blinky` example; 8 part types came from it, the rest from LCSC. The session transcript kept no cost-state record, so tool time and the price estimate were not recorded; tokens and API calls are summed from the transcript's per-response usage. Statistics run to the conversation export, and exclude the merge into `main` that came after it. Notes on the tool: [`manta/README.md`](manta/README.md#notes-on-the-tool-benchmark-observations). Session log and statistics: [`manta/CONVERSATION.md`](manta/CONVERSATION.md) |

Statistics cover the Claude Code session from the first prompt to the merge into
`main`.

- **Active time:** Claude working, including tool runs such as autorouting. It
  excludes time spent waiting for the user.
- **Of which tool time:** the part of the active time spent running tools
  (builds, exports, autorouting, searches) rather than in model calls.
- **Total tokens:** these include prompt-cache reads, which dominate the total
  because every API call re-sends the conversation.
- **API-price estimate:** Claude Code's estimate at API list prices, not a bill.

A dash means the figure was not recorded.

## Breakdown

The Results figures for each tool, split by the kind of work. Every API call in
the session is put in one category according to what it was doing:

- **Schematic & research:** reading the manual, choosing parts and looking them
  up, datasheets and tool documentation, writing the circuit, and netlist and
  schematic work.
- **PCB:** footprints, placement, routing, DRC and other board checks, Gerbers,
  fabrication fixes and PCB prints.
- **Other:** commits, pushes, README writing, status checks and final
  summaries.
- **Not attributable:** calls the session's counters include but the transcript
  doesn't log, such as the `/compact` summary.

How the figures are measured:

- **Tokens:** summed from each call's logged usage.
- **Active time:** each call is credited with the time until the next call,
  including the tool runs it started.
- **API-price estimate:** per-token prices fitted to the session's cost counter
  are applied to each category's tokens.

Calls that did both kinds of work are assigned by their main purpose.

### tscircuit

| | Schematic & research | PCB | Other | Not attributable | Total |
| --- | --- | --- | --- | --- | --- |
| Active time | 1 h 08 min | 1 h 57 min | 4 min | 1 min | 3 h 11 min |
| API calls | 171 | 174 | 31 | – | 376 |
| Total tokens | 61.6 M | 75.2 M | 16.0 M | 3.5 M | 156.3 M |
| Tokens excl. cache reads | 1.33 M | 0.57 M | 0.74 M | 0.74 M | 3.38 M |
| Output tokens | 169 k | 178 k | 26 k | 9 k | 382 k |
| API-price estimate | $24.69 | $21.64 | $9.32 | $3.67 | $59.32 |

### atopile

| | Schematic & research | PCB | Other | Not attributable | Total |
| --- | --- | --- | --- | --- | --- |
| Active time | 1 h 06 min | 31 min | 9 min | 0 min | 1 h 46 min |
| API calls | 226 | 87 | 57 | – | 370 |
| Total tokens | 78.2 M | 42.0 M | 24.7 M | 4.6 M | 149.5 M |
| Tokens excl. cache reads | 0.75 M | 0.32 M | 0.80 M | 0.09 M | 1.97 M |
| Output tokens | 217 k | 104 k | 42 k | 16 k | 378 k |
| API-price estimate | $24.10 | $12.17 | $11.70 | $1.37 | $49.34 |

## Review feedback

After the design is finished, each tool's session gets the same review comments,
in this order:

> 1. Can you tidy up the routing through pin swapping the shift registers /
>    resistor arrays?
> 2. Did you try swapping pins between parts as well or just within the same
>    part?
> 3. Try moving parts too

Statistics are measured as above, from the first review comment to the last
reply.

| Tool | Active time | of which tool time | Total tokens | API calls | API-price estimate | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| [tscircuit](https://tscircuit.com) | 1 h 35 min | 1 h 12 min | 48.9 M | 97 | $16.38 | Review log and statistics: [`tscircuit/REVIEW_CONVERSATION.md`](tscircuit/REVIEW_CONVERSATION.md) |
| [atopile](https://atopile.io) | 2 h 28 min | 2 h 03 min | 53.1 M | 141 | $16.94 | Review log and statistics: [`atopile/REVIEW_CONVERSATION.md`](atopile/REVIEW_CONVERSATION.md) |
| [SKiDL](https://github.com/devbisme/skidl) | – | – | – | – | – | |
| [Manta](https://github.com/Derrick-Derrickson/Manta) | – | – | – | – | – | |

## Layout

| Folder | Contents |
| --- | --- |
| `inputs/` | Source material: OCR'd Solartron 7075 service manual (interface in Section 9) |
| `tscircuit/` | [tscircuit](https://tscircuit.com) implementation; see its README |
| `atopile/` | [atopile](https://atopile.io) (CLI) implementation; see its README |
| `skidl/` | [SKiDL](https://github.com/devbisme/skidl) implementation, with a KiCad 10 board; see its README |
| `manta/` | [Manta](https://github.com/Derrick-Derrickson/Manta) implementation, schematic and netlist only (no board); see its README |
