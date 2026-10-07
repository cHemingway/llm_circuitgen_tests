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

## Tools

| Tool | Folder | Active time | of which tool time | Total tokens | API calls | API-price estimate | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [tscircuit](https://tscircuit.com) | `tscircuit/` | 3 h 11 min | 2 h 06 min | 156.3 M | 376 | $59.32 | Parts from tscircuit/common, then LCSC. Session log and statistics: [`tscircuit/CONVERSATION.md`](tscircuit/CONVERSATION.md) |
| [atopile](https://atopile.io) | `atopile/` | 1 h 46 min | 38 min | 149.5 M | 370 | $49.34 | CLI version (`ato`, 0.15.x). This is the last open CLI line and is effectively end-of-life: [PyPI](https://pypi.org/project/atopile/) lists 0.15.9 (12 Sep 2026) as the latest release, and atopile has moved on to [0.16](https://atopile.io/enterprise). Parts from atopile's library, then LCSC. Session log and statistics: [`atopile/CONVERSATION.md`](atopile/CONVERSATION.md) |

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

## Review feedback

This table covers follow-up work requested after the initial design, carried
out in the same session as that design.

| Tool | Feedback handled | Active time | of which tool time | Total tokens | Tokens excl. cache reads | API calls | API-price estimate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [tscircuit](https://tscircuit.com) | Tidy the routing: pin swapping within and between parts, then moving the command-side parts (3 prompts) | 1 h 35 min | 1 h 12 min | 48.9 M | 0.64 M | 97 | $16.38 |
| [atopile](https://atopile.io) | – | – | – | – | – | – | – |

- **Measured span:** for tscircuit, from the first review prompt ("Can you tidy
  up the routing through pin swapping…") to the last reply before this README
  update. It excludes the conversation export and README updates that came
  before it.
- **Tool time:** this includes the background autorouter runs, which routed up
  to four candidate layouts in parallel.
- **Total tokens:** the total includes 48.2 M prompt-cache reads. Output was
  135 k tokens, of which 68 k were thinking.

## Layout

| Folder | Contents |
| --- | --- |
| `inputs/` | Source material: OCR'd Solartron 7075 service manual (interface in Section 9) |
| `tscircuit/` | [tscircuit](https://tscircuit.com) implementation; see its README |
| `atopile/` | [atopile](https://atopile.io) (CLI) implementation; see its README |
