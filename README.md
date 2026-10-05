# llm_circuitgen_tests

A benchmark of "circuit as code" tools for LLM-aided circuit design. Every tool
gets the same design brief, and each implementation lives in its own top-level
folder.

## Brief

Build a USB interface for the Solartron 7075 multimeter around an RP2354A. It
connects through the instrument's 50-way D connector (the 70754 Parallel BCD
Interface, socket SKB) and must meet these requirements:

- DVM signals are opto-isolated from USB ground, using shift registers to keep
  the number of isolated channels low.
- Parts come from tscircuit/common first, then from LCSC.
- The board is rectangular and sits flat on the back of the meter, with a
  vertical PCB-mount D-sub on one side and a vertical USB-B on the other.
- The D-sub jackscrews are the only mechanical fixing.

## Layout

| Folder | Contents |
| --- | --- |
| `inputs/` | Source material: OCR'd Solartron 7075 service manual (interface in Section 9) |
| `tscircuit/` | [tscircuit](https://tscircuit.com) implementation; see its README |
