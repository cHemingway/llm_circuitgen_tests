# Export prompt

The request each tool's session is given once its original design work is
finished. It exports the session log, then adds the session's figures to the
Results and Breakdown tables in this repository's root README. Replace
`<tool>` and `<branch>` before sending it.

`````text
Export this conversation to a Markdown file, leaving out this request and anything after it. Then add this session's figures to the root README on `main`. Work on your branch `<branch>`; the tool's folder is `<tool>/`.

## 1. Where the numbers come from

Use the real session records, not memory. In Claude Code the full transcript (including anything from before a context compaction) is the JSONL file under ~/.claude/projects/<project>/<session-id>.jsonl:
- One API call is one assistant `message.id`. Its records are split one per content block and repeat the same usage, so count each id once. Skip API error messages (e.g. a usage-limit notice); they are not calls.
- The tool-call descriptions and the text in each call say what it was doing.
- "cost-state" records hold the session totals: tokens per model (input, cache writes, cache reads, output, thinking), API time, tool time and cost. Use the last one before this request.
If there is no cost-state record (some local runs don't write one), work the figures out from the transcript instead:
- **Tokens and API calls:** sum them from the per-response usage.
- **Tool time:** for each tool call, take the time from the record holding its `tool_use` to the record holding its `tool_result`. Add these up over the span, counting overlapping (parallel) calls once. A background task counts only until its call returns. Checked against a session that has the counter, this method reads about 4 % high (61.7 min against 59.5 min), because it includes the overhead around each run.
- **API-price estimate:** apply the model's published per-token prices for input, cache writes, cache reads and output. Cache writes are priced by cache lifetime, and each response's usage splits them into `cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`, so price the two separately. Name the prices and where you found them in `<tool>/README.md`.
- In the Results row's Notes, say which figures came from the transcript and which from published prices.
Put "–" for anything you still can't measure. Don't guess any figure.

**Span:** from the first prompt of the conversation up to, not including, this request. If the session has already had the review comments listed under "## Review feedback" in the root README, stop before the first of them and leave them and everything after them out.

## 2. The conversation export

Write `<tool>/CONVERSATION.md`, following the template at the end of this prompt.
- Times are UTC. Show the date only on the first heading of each day.
- Active time: for each user message, the time from that message until your reply finished, summed. Leave out time waiting for the user and time stopped at a usage limit, but report both.
- Leave out hidden reasoning, system reminders and background-task notifications.
- Fold every tool call into a <details> block. Cut inputs at 1500 characters and outputs at 800, ending a cut with "… [N more characters truncated]". Show images as [image]. If the text itself contains ```, use a longer fence.
- Replace the scratch/temp directory with $SCRATCH. Redact email addresses, API keys and tokens.
- Mark a user message typed while you were still working as "sent while <assistant> was working", placed at the time it was sent.
- If the context was compacted, put a note at that point and include the summary you were given in a folded block.
- Check that every fence and every <details> block is closed.

## 3. Breakdown by kind of work

Put every API call in the span into exactly one category, by what it was doing:
- **Schematic & research:** reading the manual, choosing parts and looking them up, datasheets and tool documentation, writing the circuit, and netlist and schematic work.
- **PCB:** footprints, placement, routing, DRC and other board checks, Gerbers, fabrication fixes and PCB prints.
- **Other:** commits, pushes, README writing, status checks and final summaries.
Assign a call that did both kinds of work by its main purpose. If your tool made no board, PCB covers only any footprint work, and may be zero.

For each category compute:
- **Active time:** credit each call with the time from its request until the next call's request in the same turn, including the tool runs it started. The last call of a turn runs to the end of the turn. Time spent compacting the context is not a call.
- **API calls.**
- **Total tokens:** input + cache writes + cache reads + output.
- **Tokens excluding cache reads.**
- **Output tokens.**
- **API-price estimate:** fit per-token prices (input, cache write, cache read, output) to the session's distinct cost-state snapshots by least squares, check that they reproduce the snapshots, then apply them to each category's tokens. If there are fewer than four distinct snapshots, use the model's published per-token prices instead, but only if they reproduce the snapshots; if they don't, put "–" and say why in `<tool>/README.md`. If there is no cost-state record, use the published prices as described in section 1.

Add a **Not attributable** column: the session totals for the span minus the sum of the three categories. It covers calls the counters include but the transcript doesn't log, such as the compaction summary, and the compaction time. The **Total** column must equal the session totals for the span, which are also your Results row.

Keep the per-call categories reproducible: save the script that computes the table, and a CSV listing every call with its category, in `<tool>/`. Put any caveats, such as judgement calls on categories and the fitted prices, in `<tool>/README.md`.

## 4. The root README on main

1. Pull `main` and merge it into your branch, so you start from main's current README.
2. Under "## Results", add one row for your tool to the table. Use the existing columns, in this order: Tool (linked to the tool's site), Folder, Active time, of which tool time, Total tokens, API calls, API-price estimate, Schematic (a link to the schematic file, or "–"), PCB prints (a link to the prints, or "–"), Notes. In Notes, give the tool version, where the parts came from, anything unusual about the run, where tool time and the price estimate came from if not from the tool's own counters, and "Statistics run to the conversation export, and exclude the merge into `main` that came after it", and end with "Session log and statistics: [`<tool>/CONVERSATION.md`](<tool>/CONVERSATION.md)".
3. Under "## Breakdown", add your table as "### <tool>" after the existing tables. Use exactly the same rows and columns as the tables already there. Don't add notes under it.
4. If your tool has no row yet in the "## Review feedback" table, add one with "–" in every figure column.
5. If your folder isn't listed under "## Layout", add it.
6. Format numbers the way the existing rows do: "1 h 08 min", "46 min", "61.6 M", "1.33 M", "169 k", "$24.69". Use "–" for anything you can't measure. Don't change the shared text or other tools' rows and tables.
7. Commit and push your branch. Then pull `main` again, merge your branch into it, and push `main`. If the README conflicts, take main's version and add only your rows and table back.

## Template for <tool>/CONVERSATION.md

Replace each <…>, and drop rows that don't apply.

# Conversation export: <tool> <project name>

<Assistant> session on `<owner/repo>`, branch `<branch>`, <YYYY-MM-DD HH:MM> – <YYYY-MM-DD HH:MM> UTC.
This export covers every message up to, but not including, the request to export it.

## Totals

| Time | |
|---|---|
| **Active time** (from each user message until the reply finished) | **<m.m> min (<h> h <mm> min)** |
| Tool's own counters: model (API) time + tool time | <a> + <b> = <c> min |
| Wall clock, first message to last reply | <h> h <mm> min |
| Of which waiting for the user | <h> h <mm> min |
| … including stops at a usage limit | <h> h <mm> min |

| Tokens | |
|---|---|
| Input, uncached | <n> |
| Input, written to the prompt cache | <n> |
| Input, read from the prompt cache | <n> |
| Output (of which <n> thinking) | <n> |
| **Total, main model** (<n> API responses) | **<n>** |
| Helper models (e.g. web tools) | <n> |
| **Grand total** | **<n>** |
| API-price estimate reported by the tool | $<x.xx> |

### Breakdown

| | Schematic & research | PCB | Other | Not attributable | Total |
| --- | --- | --- | --- | --- | --- |
| Active time | <h h mm min> | … | … | … | … |
| API calls | <n> | <n> | <n> | – | <n> |
| Total tokens | <x.x M> | … | … | … | … |
| Tokens excl. cache reads | <x.xx M> | … | … | … | … |
| Output tokens | <n k> | … | … | … | … |
| API-price estimate | $<x.xx> | … | … | … | … |

<One short paragraph: where the totals came from, how active time was measured, how the prices were fitted, and any permission prompts or usage-limit stops.>

### Notes on this export

* Each tool call is folded into a collapsible block. Inputs are cut at 1500 characters and outputs at 800; images show as `[image]`.
* Hidden reasoning, system reminders and background-task notifications are not included.
* The scratchpad path is shortened to `$SCRATCH`, and the user's email address is redacted.

---

# Conversation

## User (<YYYY-MM-DD HH:MM> UTC)

<user message, verbatim>

## <Assistant> (<HH:MM> UTC)

<assistant text, verbatim>

<details><summary>🔧 Bash: <the command's description></summary>

```bash
<command>
```

result:
```
<output>
```
</details>

<details><summary>🔧 Read: <path></summary>

result:
```
<output>
```
</details>

<details><summary>🔧 Edit: <path></summary>

old:
```
<old text>
```
new:
```
<new text>
```

result:
```
<output>
```
</details>

<details><summary>🔧 Write: <path></summary>

```
<file content>
```

result:
```
<output>
```
</details>

<details><summary>🔧 <ToolName></summary>

```json
<input as indented JSON>
```

result:
```
<output>
```
</details>

## User (<HH:MM> UTC, sent while <Assistant> was working)

<message>

> *The context window filled up here and the conversation was automatically compacted.*

<details><summary>Automatic summary given to <Assistant> after compaction</summary>

````
<summary text>
````
</details>
`````
