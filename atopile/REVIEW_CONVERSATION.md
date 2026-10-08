# Review conversation: Solartron 7075 USB interface in atopile

Review feedback on the finished atopile design, in Claude Code session `53615df1-8373-55e4-9ed6-294aee33d6b5`, 07 Oct 2026. It continues [`CONVERSATION.md`](CONVERSATION.md) in the same session.

This file contains:

- User prompts and Claude's replies, verbatim.
- Tool calls as one-line entries under each reply.
- Notes where a stop hook or a finished background job prompted Claude.
- No thinking, tool output or system reminders.

## Statistics

| Measure | Value |
| --- | --- |
| **Active time** (Claude working, excluding waits for the user) | **2 h 28 min** |
| &nbsp;&nbsp;model time (API calls) | 25 min |
| &nbsp;&nbsp;tool time (builds, optimiser runs, Freerouting runs, exports) | 2 h 03 min |
| Wall-clock span, first prompt to last reply | 3 h 01 min |
| User prompts | 3 |
| API calls / tool calls | 141 / 150 |
| **Total tokens** | **53.12 M** |
| &nbsp;&nbsp;input read from prompt cache | 52.54 M |
| &nbsp;&nbsp;input written to prompt cache | 428 k |
| &nbsp;&nbsp;input, uncached | 4 k |
| &nbsp;&nbsp;output (of which thinking) | 149 k (75 k) |
| Tokens excluding cache reads | 581 k |
| API-equivalent cost (Claude Code's estimate) | $16.94 |

How these figures were measured:

- **Active time:** each turn runs from the user's prompt to Claude's last action before the next prompt; the turns are summed.
  - This excludes time spent waiting for the user.
  - It includes time spent on background jobs: the placement search and the 40-minute Freerouting comparison runs.
  - Tool time is active time minus model time.
- **Tokens, model time and cost:** these are the change in Claude Code's session counters (the `cost-state` records in the session transcript) from just before the first review prompt to just after the last reply.
- **API calls:** the number of model responses logged in the transcript for this span. The token counters are slightly higher than the sum over those responses (about 2.9 M more cache reads, with almost no extra output), so a few calls that the transcript does not log may be missing from this count.
- **Cost:** an API list-price estimate, not a bill.

| # | Prompt | Started (UTC) | Active | API calls | Output tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | Can you tidy up the routing through pin swapping the shif... | 07 Oct 18:38 | 1 h 05 min | 83 | 79 k |
| 2 | Did you try swapping pins between parts as well or just w... | 07 Oct 20:15 | 28 s | 2 | 2 k |
| 3 | Try moving parts too | 07 Oct 20:17 | 1 h 22 min | 56 | 68 k |

---

## Conversation

### User (1), 07 Oct 2026 18:38 UTC

> Can you tidy up the routing through pin swapping the shift registers / resistor arrays?

### Claude

<details><summary>5 tool calls</summary>

- Bash: Check for upstream changes and routing state
- Bash: Read main's README tools and review sections
- Bash: Show shift register wiring in main.ato
- Bash: List IC and connector placements
- Bash: Map IC references to atopile addresses and pad nets

</details>

Mapping the current shift-register pins against the DD-50 to measure the ratsnest before swapping.

<details><summary>6 tool calls</summary>

- Bash: Map IC references to atopile addresses and pad nets
- Bash: Get DD-50 pad rows and check for Java
- Bash: Find IC slot assignment logic
- Bash: Read slot assignment code
- Bash: Read firmware interface docs and related ato code
- Bash: Find the latest Freerouting release jar

</details>

Checking whether I can fetch the Freerouting autorouter, so I can compare routing before and after the pin swaps.

<details><summary>11 tool calls</summary>

- Bash: Check GitHub API and release redirect
- add_repo: freerouting/freerouting (read)
- ToolSearch: select:TaskCreate,TaskUpdate
- Bash: Look for a Freerouting jar on Maven Central
- TaskCreate: Pin-swap optimiser for 165 inputs / 595 outputs / 165 chain order
- TaskCreate: Rebuild and verify after pin swap
- TaskCreate: Autorouter comparison before/after (if Freerouting builds)
- TaskCreate: Update README firmware bit maps and docs, commit, push
- Bash: Clone Freerouting source
- Bash: Check Freerouting build setup and Gradle reachability
- Bash: Build the Freerouting executable jar

</details>

While Freerouting builds in the background, I'm writing the pin-swap optimiser.

<details><summary>3 tool calls</summary>

- TaskUpdate: task #5 -> in_progress
- Bash: List pads of chain, opto and control nets
- Write: atopile/scripts/pin_swap.py

</details>

*Background command "Build the Freerouting executable jar" failed with exit code 2.*

### Claude

<details><summary>4 tool calls</summary>

- Bash: Show Freerouting build failure
- Bash: Inspect Freerouting Gradle plugins
- Bash: List Freerouting release tags
- Bash: Clone Freerouting v2.1.0 and check its build requirements

</details>

Freerouting 2.5 needs Java 25; building 2.1.0 (Java 21) in the background instead, and running the pin-swap optimiser meanwhile.

<details><summary>3 tool calls</summary>

- Bash: Build Freerouting 2.1.0 executable jar
- Bash: Run the pin-swap optimiser in report mode
- Bash: Fix field lookup and rerun optimiser

</details>

*Background command "Build Freerouting 2.1.0 executable jar" failed with exit code 2.*

### Claude

<details><summary>4 tool calls</summary>

- Bash: Show Freerouting 2.1.0 build error
- Bash: Check plugin usage and plugin portal access
- Bash: Follow the Gradle plugin portal redirect
- Bash: Check Maven Central mirror reachability and repo config

</details>

Freerouting's Gradle plugin lookup fails through the proxy; pointing it at Maven Central directly and retrying.

<details><summary>2 tool calls</summary>

- Bash: Retry Freerouting build resolving plugins from Maven Central
- Bash: Retry Freerouting build with one worker

</details>

Optimiser result: ratsnest crossings 839 → 154, length 1544 → 860 mm. Now wiring it into `main.ato` and fixing the placement script so it won't shuffle the ICs after the swap.

<details><summary>5 tool calls</summary>

- Read: atopile/main.ato
- Bash: Restructure main.ato with a generated pin-map block
- Bash: Check main.ato tail and newline
- Bash: Add bit-map markers to README and fix bit references
- Bash: Find other bit-map references

</details>

Now updating the placement script to pin each IC to its current slot (the old centroid sort would move parts after the swap).

<details><summary>5 tool calls</summary>

- Edit: atopile/scripts/place_components.py
- Edit: atopile/scripts/place_components.py
- Bash: Check matplotlib availability
- Bash: Add SVG plot and save options to pin_swap.py
- Bash: Save the old map and write the optimised pin map

</details>

*Background command "Retry Freerouting build with one worker" completed (exit code 0).*

### Claude

<details><summary>1 tool call</summary>

- Bash: Check Freerouting jar and generated README tables

</details>

Generated tables look right. Rebuilding with atopile so the layout picks up the new nets.

<details><summary>3 tool calls</summary>

- Bash: Rebuild with atopile and check verify tool assumptions
- Bash: Read the connectivity verify tool
- Bash: Verify layout nets match the new pin map

</details>

Layout nets match the new map (109 checks, 0 errors), isolation and placement checks pass. Confirming the rebuilt layout scores as optimised and drawing before/after.

<details><summary>8 tool calls</summary>

- Bash: Confirm optimised score and render the before/after SVG
- Bash: Rasterise the SVG for a visual check
- Bash: Screenshot the SVG with headless Chromium
- Read: $SCRATCH/pin_swap.png
- Bash: Re-screenshot the SVG at full size
- Read: $SCRATCH/pin_swap.png
- Bash: Render SVG via HTML wrapper at higher resolution
- Read: $SCRATCH/pin_swap.png

</details>

The pin swap visibly untangles the ratsnest. Now the autorouter check: export both layouts to Specctra DSN and route them with Freerouting.

<details><summary>5 tool calls</summary>

- TaskUpdate: task #5 -> completed
- TaskUpdate: task #7 -> in_progress
- Bash: Show Freerouting CLI options
- Bash: Export before/after layouts to Specctra DSN
- Bash: Autoroute before and after boards with Freerouting

</details>

While the autorouter runs, regenerating the schematic (nets changed) and re-running ERC.

<details><summary>7 tool calls</summary>

- TaskUpdate: task #6 -> in_progress
- Bash: Regenerate schematic PDF, netlist check and ERC
- Bash: Regenerate gerbers, prints and renders
- Bash: Outline README sections
- Bash: Read README architecture, board and open items
- Bash: Check autorouter progress
- Bash: Inspect autorouter errors and resources

</details>

Autorouting both versions in parallel (≈20–40 min). Meanwhile updating the README.

<details><summary>9 tool calls</summary>

- Bash: Update architecture notes for the new chain map
- Bash: Break down ratsnest length before and after
- Edit: atopile/README.md
- Edit: atopile/README.md
- Edit: atopile/README.md
- TaskUpdate: task #6 -> completed
- Bash: Check autorouter progress
- Bash: Confirm no footprints moved in the layout
- Bash: Check the placement script is idempotent

</details>

Placement script now re-runs without moving anything (only zone UUIDs differ, so I restored the built copy). Waiting on the autorouter comparison.

<details><summary>5 tool calls</summary>

- Bash: Restore built layout and revert parts churn
- ToolSearch: select:Monitor
- Monitor: Freerouting before/after progress milestones
- Bash: Write SES import and stats tool
- Bash: Show current time and main.ato diff head

</details>

The pin swap is done and verified. I'm now waiting on the autorouter comparison: Freerouting is routing the old and new boards side by side, at about pass 12 of 40 so far. Once it finishes I'll add the result to the README, then commit and push.

*Stop hook: There are uncommitted changes in the repository. Please commit and push these changes to the remote branch.*

### Claude

<details><summary>3 tool calls</summary>

- Bash: Commit and push the pin-swap work
- ToolSearch: select:TaskStop
- TaskStop: b15prcvgc

</details>

I committed and pushed the pin-swap work to `claude/dazzling-mendel-wb2g7k`. The board is still unrouted, so this tidies the ratsnest (the unrouted connection lines), not existing tracks.

| DVM-side ratsnest | Before | After |
|---|---|---|
| Total length | 1544 mm | 860 mm |
| Crossings | 839 | 154 |
| 74HCT165 chain | 124 mm | 56 mm |

**What I swapped:**
- **SKB outputs:** any of the 36 can go on any 74HCT165 input, the four link-check constants take the spare inputs, and the order of the five 165s in their chain is free.
- **SKB command inputs:** any of these, plus the gate of the SAMPLE transistor (the 2N7002 for SKB pin 39), can go on any 74HCT595 output, and the order of the two 595s is free.
- **Scope:** swaps happen within a part and between parts. No parts moved.
- **Resistor arrays:** this design has none, so there was nothing to swap there.

**How it works:** the new `scripts/pin_swap.py` searches for the best assignment. It then rewrites the generated pin-map section of `main.ato` and the firmware bit-map tables in the README, so the firmware tables always match the board. `docs/pin_swap.svg` shows the ratsnest before and after.

**Firmware impact:** the read-frame and command-word bit maps have changed. Firmware should use the new README tables, not the old "frame bit k = SKB pin k+1" rule.

**Checks run:**
- After `ato build`, the layout's nets match the new pin map (109 checks, no errors).
- The isolation and placement checks pass.
- The regenerated schematic's netlist matches the board, and the electrical rules check reports 0 errors and 0 warnings.
- I regenerated the gerbers and prints; they are still the unrouted fit-check set.

**Problem found:** the shift-register row was placed in reverse order relative to the DD-50. The placement script got the sign wrong once the connector moved to the bottom face, and re-running it reversed the row. I've fixed the register slots in that script so it can't undo the new pin map.

That reversal, plus the DRDY buffer and SAMPLE transistor sitting at the opposite end from SKB 34 and 39, are the main reasons 154 crossings remain. Those two nets are still the longest, at about 64 mm and 60 mm. Moving parts would fix them, and I've added this to the README's open items.

**Still running:** Freerouting is autorouting the old and new boards side by side as an independent check. Early passes favour the new map: about 45 connections left unrouted after 15 passes, against about 72 after 7 for the old board. Once both finish I'll add the comparison to the README and push it.

*Background command "Autoroute before and after boards with Freerouting" completed (exit code 0).*

### Claude

<details><summary>3 tool calls</summary>

- Bash: Summarise both autorouting runs
- Bash: Compare unrouted counts at equal pass numbers
- Bash: Compare unrouted counts at equal pass numbers

</details>

Both runs hit the 40-minute limit without finishing, but the comparison is clear. Adding it to the README.

<details><summary>4 tool calls</summary>

- Edit: atopile/README.md
- Bash: Commit and push the routing comparison
- TaskUpdate: task #7 -> completed
- TaskUpdate: task #8 -> completed

</details>

The autorouter comparison finished. Neither version of the board routed fully in 40 minutes, but the pin-swapped one got noticeably further.

| Freerouting 2.1, 40 min each, run side by side | Before | After |
|---|---|---|
| Passes completed | 55 | 456 |
| Best unrouted connections after 20 passes | 59 | 39 |
| Best unrouted connections after 55 passes | 55 | 35 |
| Best unrouted connections within 40 min | 55 | 30 |

- **Freerouting version:** I built 2.1 from source, because the current 2.5 needs Java 25 and this machine has Java 21. It logged internal errors on both boards.
- **Routing not kept:** both runs hit the time limit before saving a result, so this was a measurement only. The board in the repo is still unrouted.

The table is in the README's pin-swapping section, committed and pushed to `claude/dazzling-mendel-wb2g7k` as `ff4f470`. That is not merged into `main`.

### User (2), 07 Oct 2026 20:15 UTC

> Did you try swapping pins between parts as well or just within the same part?

### Claude

<details><summary>1 tool call</summary>

- Bash: Count signals moved between parts by the pin swap

</details>

Yes, it swapped between parts as well as within them. The optimiser treated all five 74HCT165s as one pool of 40 inputs and both 74HCT595s as one pool of 16 outputs. It could also change the order of each shift chain.

Compared with the original wiring, the result uses that freedom heavily:
- **74HCT165 inputs:** 35 of the 36 SKB outputs now land on a different 165 than before.
- **74HCT595 outputs:** 10 of the 13 command lines (SKB 38, 40–42, 46–50 and the SAMPLE transistor gate) moved to the other 595.
- **165 chain order:** changed from 0→1→2→3→4 to 0→4→2→3→1, so the chain now follows the physical row. That cut the chain ratsnest from 124 mm to 56 mm.
- **595 order:** MOSI now feeds the west 595 first.

Swaps were only between parts of the same type, since a 165 input and a 595 output aren't interchangeable.

Two other kinds of swap were not tried:
- **Optocouplers:** the four MCU→meter channels (SCK, MOSI, LATCH, OE_N) use identical TLP2361 optocouplers, so which channel carries which signal could be swapped too.
- **RP2354A GPIOs:** LATCH, OE_N, DRDY and the status LED are plain GPIOs and could move to other pins. SCK, MOSI and MISO must stay on SPI-capable pins.

These would mainly tidy the USB side and the isolation barrier, not the DD-50 area. I can add them to the script if you want.

### User (3), 07 Oct 2026 20:17 UTC

> Try moving parts too

### Claude

Plan: let the parts move, then re-run the pin swap on the new positions. Before writing the placement search, I'll speed up the pin-swap crossing count, since the search will call it many times.

<details><summary>2 tool calls</summary>

- Read: atopile/scripts/pin_swap.py
- Bash: Speed up crossing counts and time a short anneal

</details>

Crossing count is now ~10× faster with identical results. Next, the placement search script.

<details><summary>2 tool calls</summary>

- Bash: Review placement tables to restructure
- Bash: Restructure placement script with a generated DVM block

</details>

Refactor reproduces the existing layout exactly. Now the placement search.

<details><summary>1 tool call</summary>

- Write: atopile/scripts/optimise_placement.py

</details>

Validating the candidate spots with the real placement and layout checks before running the search.

<details><summary>1 tool call</summary>

- Bash: Check geometry round trip and spot legality

</details>

All candidate spots pass the layout checks, and the geometry model reproduces the layout exactly. Running the placement search (≈8 min).

<details><summary>1 tool call</summary>

- Bash: Run the placement search in report mode

</details>

While the search runs: once it finishes I'll apply the placement, redo the full pin swap for it, rebuild and verify, then repeat the Freerouting comparison against the pin-swap-only board.

<details><summary>3 tool calls</summary>

- Bash: Check placement search progress
- Bash: Prepare the three-panel figure tool
- Bash: Commit the placement-search groundwork

</details>

I've committed and pushed the groundwork, but no parts have moved yet:
- **Placement search script:** the new `scripts/optimise_placement.py`.
- **Placement table:** the DVM-side positions in `scripts/place_components.py` now sit in a generated block; re-running it reproduces the current layout exactly.
- **Faster pin swap:** `scripts/pin_swap.py` now counts ratsnest crossings about 10× faster, with the same results.

The search is running now (about 8 minutes). It tries:
- **Shift-register row:** every arrangement of the five 165s and two 595s across the seven slots, and both orientations of each type.
- **DRDY buffer and SAMPLE transistor:** three candidate spots each. All of them pass the layout checks.
- **Optocouplers:** every order of the six along the isolation barrier.

Each candidate gets its own short pin-swap search, scored on ratsnest length and crossings, including the control buses and the MCU-to-opto nets. Once the search finishes I'll apply the best placement, re-run the full pin swap and verification, and repeat the Freerouting comparison.

*Background command "Run the placement search in report mode" completed (exit code 0).*

### Claude

Search finished, but reviewing the winner (SAMPLE MOSFET south of the connector) I found a gap in the scoring: the MOSFET's drain net to SKB 39 wasn't counted, which unfairly favours that spot. Fixing and re-running.

<details><summary>5 tool calls</summary>

- Bash: Add the SKB 39 drain net to the placement scoring
- Bash: Reflow docstring and rerun the placement search
- Bash: Check the search is running
- Bash: Wait for the placement search to finish
- Bash: Commit the scoring fix

</details>

The first search run finished, but its winner put the SAMPLE transistor south of the DD-50. That looked good only because the transistor's drain net to SKB 39 wasn't being scored. The fix is committed and pushed, and the search is running again (about 8 minutes).

What the first run found, for reference:

| | Before moving parts | First run's best placement |
|---|---|---|
| Ratsnest score (length + 5 mm per crossing, including control buses) | 2454 | 1542 |
| Crossings | 258 | 114 |

- **Shift-register row:** 595s moved into the middle (east to west: 165, 165, 595, 165, 595, 165, 165). The 165s are rotated so their control pins face away from the connector.
- **DRDY buffer:** moved to the west end, next to SKB 34.
- **Optocouplers:** reordered so DRDY is at the west end and MISO at the east end.

Once the corrected run finishes I'll apply the best placement and redo the full pin swap. Then I'll re-run the layout, connectivity and schematic checks and the Freerouting comparison, and push.

*Background command "Wait for the placement search to finish" completed (exit code 0).*

### Claude

<details><summary>1 tool call</summary>

- Bash: Show placement search results

</details>

With the drain net scored, the transistor still belongs south of the connector (drain to SKB 39 drops to about 9 mm). Applying the winning placement.

<details><summary>1 tool call</summary>

- Bash: Write and apply the best placement, then check it

</details>

Placement passes the layout checks. Before re-running the full pin swap, I'm making `pin_swap.py` score the same fixed control nets as the placement search, so the two use one consistent model.

<details><summary>4 tool calls</summary>

- Bash: Locate State construction sites in pin_swap.py
- Bash: Read current_state, report and main
- Bash: Move fixed nets into pin_swap and share with the placement search
- Bash: Run the full pin swap on the new placement

</details>

The full pin swap scores 1613, worse than the 1540 the placement search reached for this same placement, so the annealer isn't converging from a bad starting map. Trying longer runs.

<details><summary>1 tool call</summary>

- Bash: Test longer annealing runs on the new placement

</details>

Longer annealing reaches ~1540. Raising the iteration count and re-running the swap.

<details><summary>2 tool calls</summary>

- Bash: Rerun full pin swap with longer annealing
- Bash: Add a chain-reversal move and rerun the pin swap

</details>

All restarts now converge (1540.5; longest swapped net 19 mm). Rebuilding and verifying.

<details><summary>1 tool call</summary>

- Bash: Rebuild and verify nets, layout and pin-map score

</details>

Nets, pin map, isolation and placement checks all pass. Starting the 40-minute Freerouting comparison (pin swap only vs pin swap + moved parts) in the background.

<details><summary>2 tool calls</summary>

- Bash: Export DSN for pin-swap-only and moved boards
- Bash: Autoroute pin-swap-only and moved boards side by side

</details>

While the routers run: regenerating schematic, fab outputs and figures.

<details><summary>5 tool calls</summary>

- Bash: Find how docs/placement.png was generated
- Bash: Show render.py output handling
- Bash: Regenerate placement image and schematic
- Read: atopile/docs/placement.png
- Bash: Regenerate fab outputs for the moved placement

</details>

Two new DRC items appeared (more starved thermals, one silk-to-edge). Checking them.

<details><summary>1 tool call</summary>

- Bash: Show the starved-thermal and silk-edge DRC items

</details>

Both are minor: the starved thermal is the same opto pad as before (now reported three times), and R18's reference text is clipped by the board edge. Rotating R18 180° moves the text inboard.

<details><summary>1 tool call</summary>

- Bash: Rotate R18 so its silk stays on the board

</details>

Now the three-panel before/after figure (original, pin swap, pin swap + moved parts).

<details><summary>10 tool calls</summary>

- Bash: Build and render the three-panel ratsnest figure
- Bash: Fix the figure tool and render it
- Read: $SCRATCH/fig.png
- Bash: Extend the figure panel to include the south strip
- Read: $SCRATCH/fig.png
- Bash: Re-render with a taller viewport
- Read: $SCRATCH/fig_bottom.png
- Bash: Find README text affected by the part moves
- Bash: Read the pin-swapping section and open items
- Bash: Check routing progress

</details>

Early routing numbers favour the moved layout (33 unrouted at pass 24 vs 47 at pass 13). Updating the README while it finishes.

<details><summary>6 tool calls</summary>

- Bash: Rewrite the README pin-swap section for the part moves
- Bash: Tighten two README statements
- Bash: Regenerate fab outputs after the R18 rotation
- Bash: Check starved-thermal items and README counts
- Bash: Read README DRC bullet list
- Bash: Update README DRC counts

</details>

Parts moved, pin swap redone, everything rebuilt and verified. Committing this now (with the earlier Freerouting result in place) while the second routing comparison runs.

<details><summary>1 tool call</summary>

- Bash: Commit and push the part moves

</details>

I moved the DVM-side parts, re-ran the pin swap for the new positions, and pushed it as `e860a76`. The board is still unrouted.

**What moved:**
- **Shift-register row, east to west:** 165, 595, 165, 595, 165, 165, 165. The two 595s now sit above SKB 38–50, the command pins they drive.
- **The 165s are turned 180°,** so their LATCH/SCK pins face away from the D-sub and their chain pins face it.
- **DRDY buffer (U1)** went from the east end to the west end, next to SKB 34.
- **SAMPLE transistor (Q1) and its pull-down** went from the east end to the strip south of the D-sub, in line with SKB 39.
- **Optocouplers, west to east:** DRDY, MISO, LATCH, MOSI, OE_N, SCK. That puts DRDY next to U1 and MISO next to the head of the 165 chain.

**How it was chosen:** the new `scripts/optimise_placement.py` tried every arrangement of the register row, both orientations of each register type, a few checked spots for U1 and Q1, and every opto order. It ran a short pin-swap search for each candidate. This version also scores the control buses, the transistor's drain to SKB 39 and the MCU-to-opto nets.

| DVM-side ratsnest | Original | Pin swap | Pin swap + moved parts |
|---|---|---|---|
| Swappable nets | 1543 mm | 860 mm | 678 mm |
| All nets above, plus control and MCU-to-opto nets | 1889 mm | 1206 mm | 985 mm |
| Crossings, all of the above | 1000 | 297 | 112 |

**Checks after the move:**
- The layout's nets match the pin map, and the isolation, overlap and jackscrew keep-out checks pass.
- The schematic ERC is still 0 errors and 0 warnings.
- I regenerated the gerbers, prints and renders.

**Changed for firmware:** the read-frame and command-word bit maps in the README changed again.

**One risk to check when routing:** with Q1 south of the D-sub, its drain to SKB 39 and its gate from a 595 both have to pass between the D-sub pins. If that turns out too tight, the west-end spot scored only slightly worse.

The second 40-minute Freerouting comparison (pin swap only vs pin swap + moved parts) is about 15 minutes in. So far the moved layout is ahead: 33 connections left unrouted after 24 passes, against 47 after 13. I'll add the final numbers to the README when it finishes.

*Background command "Autoroute pin-swap-only and moved boards side by side" completed (exit code 0).*

### Claude

<details><summary>1 tool call</summary>

- Bash: Summarise the second routing comparison

</details>

Second routing comparison finished. Updating the README with the result.

<details><summary>1 tool call</summary>

- Bash: Add second routing comparison to README and push

</details>

The second Freerouting comparison is in: moving the parts helps the autorouter early on, but makes little difference to how far it gets in 40 minutes.

| Freerouting 2.1, 40 min, two boards side by side | Pin swap only | Pin swap + moved parts |
|---|---|---|
| Passes completed | 432 | 508 |
| Best unrouted connections after 20 passes | 40 | 33 |
| Best unrouted connections within 40 min | 31 | 30 |

The pin swap was the big improvement: the first comparison went from 55 unrouted on the original board to 30. Moving parts mainly shows up in the ratsnest numbers (crossings down from 297 to 112), not in the autorouter's final count.

Neither run finished routing the board. Freerouting doesn't save its result when it's stopped at the time limit, so I can't tell which 30 or so connections it still fails on.

The table is in the README, committed and pushed to `claude/dazzling-mendel-wb2g7k` as `96880e2`, but not merged into `main`. The board in the repo is still unrouted.
