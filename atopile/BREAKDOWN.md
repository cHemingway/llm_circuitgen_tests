# Token breakdown of the original design work: method and caveats

These notes go with the atopile table under "Breakdown" in the root README.

## Span

The span is the same as the atopile row in the root README's Results table
and [`CONVERSATION.md`](CONVERSATION.md):
* It starts at the first prompt (2026-10-06 10:38 UTC).
* It stops just before the request to export the conversation (19:34 UTC).
  The last call in the span is at 18:48.
* It covers 10 user turns, ending with "commit and merge into main" and
  "make a branch `start`".

The review comments and everything after them are left out. Those are in
[`REVIEW_CONVERSATION.md`](REVIEW_CONVERSATION.md).

## API calls by category

There are 370 API calls, counting each assistant `message.id` once. The
calls fall into these blocks, in order:

| Time (UTC) | Calls | Active | Category | What the calls did |
|---|---|---|---|---|
| 10:38–10:40 | 13 | 1.8 min | Schematic & research | read section 9 of the manual; install atopile |
| 10:40 | 1 | 0.1 min | Other | task list |
| 10:40–10:59 | 101 | 18.7 min | Schematic & research | atopile docs and sources; registry, LCSC and JLCPCB part searches; datasheets; part import; pinouts |
| 10:59 | 2 | 1.1 min | PCB | board-shape and auto-layout docs |
| 11:00–11:24 | 52 | 25.0 min | Schematic & research | writing the `.ato` modules; builds; LED and passive fixes; netlist checks; net names |
| 11:25–11:34 | 31 | 9.8 min | PCB | outline, placement script, layout checks, zones |
| 11:35–11:39 | 17 | 4.1 min | Other | choosing what to commit (unused parts, STEP sizes), README, commit, summary |
| 12:06–12:20 | 41 | 13.9 min | Schematic & research | KiCad install; schematic exporter; net labels |
| 12:20–12:21 | 8 | 0.7 min | Other | README, commit, summary |
| 12:29 | 1 | 0.7 min | Schematic & research | JLCPCB stock check |
| 12:29 | 3 | 0.6 min | Other | README open items, commit |
| 12:34–12:39 | 17 | 5.1 min | Schematic & research | ERC; manual section 9 (board 2 pull-ups) |
| 12:39 | 3 | 0.5 min | Other | README findings |
| 12:40 | 1 | 1.1 min | Schematic & research | rebuild, regenerate schematic |
| 12:41–18:18 | 5 | 0.6 min | Other | commit; sending the schematic PDF |
| 18:22–18:41 | 54 | 20.5 min | PCB | DRC, gerbers, prints, renders; LDO block placement; 3D-model offsets |
| 18:42–18:48 | 20 | 2.1 min | Other | README, commit, merge into `main`, `start` branch |

## How the figures were measured

* **Active time.** Each call is credited with the time until the next call in
  the same turn. The first call of a turn also gets the time from the
  prompt. The last call runs to the end of the turn. These are the same turn
  boundaries as the Results row, so the calls add up to its 1 h 46 min, and
  "Not attributable" time is 0.
* **Tokens.** Each call's logged usage, counted once per `message.id`:
  input + cache writes + cache reads + output.
* **Prices.** Per-token prices were fitted by least squares to the 9
  distinct `cost-state` snapshots of the main model in the session. Per
  million tokens they are:
  * input $3.95
  * cache write $7.99
  * cache read $0.20
  * output $20.03

  They reproduce every snapshot to within $0.005.
* **Not attributable.** This is the Results-row totals minus the three
  categories: 4.6 M tokens, $1.37. It is made of two parts:
  * the `/compact` summary at 18:36, which the transcript does not log as a
    call;
  * the helper model behind the web search and fetch tools: 61,797 tokens,
    $0.10.

## Caveats

* **"Other" has 0.80 M tokens excluding cache reads.** Most of that is one
  call, sending the schematic PDF at 18:18 after a 5½-hour pause. The prompt
  cache had expired, so the whole conversation, 679 k tokens, was written to
  the cache again.
* **The compaction's own time goes to PCB.** The compaction at 18:36 fell
  inside the PCB work, so its time is credited to the call before it. That
  call is a PCB call at 18:34, which got 126 s.
* **Calls that did several things are assigned by their main purpose.** For
  example:
  * Builds and netlist checks while writing the circuit are Schematic &
    research.
  * Inspecting candidate parts' footprints while choosing parts is Schematic
    & research.
  * Deleting unused part folders before the first commit is Other.
