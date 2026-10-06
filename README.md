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

| Tool | Folder | Notes |
| --- | --- | --- |
| [tscircuit](https://tscircuit.com) | `tscircuit/` | Parts from tscircuit/common, then LCSC |
| [atopile](https://atopile.io) | `atopile/` | CLI version (`ato`, 0.15.x). This is the last open CLI line and is effectively end-of-life: [PyPI](https://pypi.org/project/atopile/) lists 0.15.9 (12 Sep 2026) as the latest release, and atopile has moved on to [0.16](https://atopile.io/enterprise). Parts from atopile's library, then LCSC |

## Layout

| Folder | Contents |
| --- | --- |
| `inputs/` | Source material: OCR'd Solartron 7075 service manual (interface in Section 9) |
| `tscircuit/` | [tscircuit](https://tscircuit.com) implementation; see its README |
| `atopile/` | [atopile](https://atopile.io) (CLI) implementation; see its README |
