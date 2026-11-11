# Review export prompt

The request each tool's session is given once it has answered the review
comments listed under "Review feedback" in the root README. It exports the
review part of the session and fills in the tool's row of the Review feedback
table. The original design work is covered separately, by
[`EXPORT_PROMPT.md`](EXPORT_PROMPT.md). Replace `<tool>` and `<branch>` before
sending it.

`````text
Export the review part of this conversation to a Markdown file, then fill in this tool's row of the "## Review feedback" table in the root README on `main`. Work on your branch `<branch>`; the tool's folder is `<tool>/`.

## 1. Span

Start at the first review comment ("Can you tidy up the routing through pin swapping…"), and include the other review comments listed under "## Review feedback" in the root README, your replies, and anything I said in between. Stop before this request. The original design work before the first review comment is already in `<tool>/CONVERSATION.md`, so leave it out. If a turn inside the span was about something unrelated (for example an export or README statistics), leave that turn out of the log and the figures, and say so in the log.

## 2. Where the numbers come from

Use the real session records, not memory. In Claude Code the full transcript (including anything from before a context compaction) is the JSONL file under ~/.claude/projects/<project>/<session-id>.jsonl:
- One API call is one assistant `message.id`. Its records are split one per content block and repeat the same usage, so count each id once. Skip API error messages (e.g. a usage-limit notice); they are not calls.
- "cost-state" records hold running session totals: tokens per model, API time, tool time and cost. The review's figures are the change between the last record before the first review comment and the last record before this request. If a left-out turn falls inside the span, subtract its change too.
- Active time: for each review prompt, the time from the prompt until your reply finished, summed. Leave out time waiting for the user and time stopped at a usage limit. Model time is the change in the API-time counter, and tool time is active time minus model time.

If there is no cost-state record (some local runs don't write one), work the figures out from the transcript instead:
- **Tokens and API calls:** sum them from the per-response usage in the span.
- **Tool time:** for each tool call, take the time from the record holding its `tool_use` to the record holding its `tool_result`. Add these up over the span, counting overlapping (parallel) calls once. A background task counts only until its call returns. Checked against a session that has the counter, this method reads about 4 % high, because it includes the overhead around each run. Model time is then active time minus tool time.
- **API-price estimate:** apply the model's published per-token prices for input, cache writes, cache reads and output. Cache writes are priced by cache lifetime, and each response's usage splits them into `cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`, so price the two separately. Name the prices and where you found them in the log.
- Say in the log, and in the README row's Notes, which figures came from the transcript and which from published prices.
Put "–" for anything you still can't measure. Don't guess any figure.

## 3. The review log

Write `<tool>/REVIEW_CONVERSATION.md`, following the template at the end of this prompt. It uses the same compact format as the existing review logs (`tscircuit/REVIEW_CONVERSATION.md`, `atopile/REVIEW_CONVERSATION.md`), so read one of them first:
- User prompts and your replies verbatim. Each run of tool calls between pieces of text is folded into one <details> block, one line per call (the tool name and its description or file path), with no tool output.
- Add a one-line note wherever a stop hook or a finished background job prompted you rather than the user.
- Leave out hidden reasoning, tool output and system reminders.
- Times are UTC. Replace the scratch/temp directory with `scratchpad/` and redact email addresses, API keys and tokens.
- Check that every <details> block is closed.

**Breakdown.** Put every API call in the span into exactly one category, by its main purpose:
- **Schematic & research:** reading the manual, choosing parts and looking them up, datasheets and tool documentation, writing the circuit, and netlist and schematic work. This includes pin swaps and other changes to the circuit description.
- **PCB:** footprints, placement, routing, DRC and other board checks, Gerbers, fabrication fixes and PCB prints.
- **Other:** commits, pushes, README writing, status checks and final summaries.
For each category give active time (each call is credited with the time from its request until the next call's request in the same turn, including the tool runs it started; the last call of a turn runs to the end of the turn), API calls, total tokens, tokens excluding cache reads, output tokens and the API-price estimate. For the price, fit per-token prices to the session's cost-state snapshots by least squares and check that they reproduce them, or use the published prices as above. Add a **Not attributable** column, the review totals minus the three categories, and a **Total** column equal to the review totals. Save the script and a CSV listing every call with its category in `<tool>/`.

## 4. The root README on main

1. Pull `main` and merge it into your branch, so you start from main's current README.
2. In the "## Review feedback" table, replace your tool's row of dashes (or add a row if there is none) with: Tool (linked to the tool's site), Active time, of which tool time, Total tokens, API calls, API-price estimate, Notes. In Notes, say where tool time and the price came from if not from the tool's own counters, and end with "Review log and statistics: [`<tool>/REVIEW_CONVERSATION.md`](<tool>/REVIEW_CONVERSATION.md)".
3. Format numbers the way the existing rows do: "1 h 35 min", "46 min", "48.9 M", "$16.38". Use "–" for anything you can't measure.
4. Don't change the Results row or the "## Breakdown" table for your tool; they cover the original design work. Don't change the shared text or other tools' rows.
5. If the review changed the design, make sure `<tool>/README.md` describes the result (for example the new pin assignment and routing figures).
6. Commit and push your branch. Then pull `main` again, merge your branch into it, and push `main`. If the README conflicts, take main's version and put back only your row.

## Template for <tool>/REVIEW_CONVERSATION.md

Replace each <…>, and drop rows that don't apply.

# Review conversation: Solartron 7075 USB interface in <tool>

Review feedback on the finished <tool> design, in <assistant> session `<session-id>`, model `<model>`, <DD Mon YYYY>. It continues [`CONVERSATION.md`](CONVERSATION.md) in the same session and was exported from the session transcript.

This file contains:

- User prompts and <assistant>'s replies, verbatim.
- Tool calls as one-line entries under each reply.
- Notes where a stop hook or a finished background job prompted <assistant>.
- No thinking, tool output or system reminders.

## Statistics

| Measure | Value |
| --- | --- |
| **Active time** (<assistant> working, excluding waits for the user) | **<h h mm min>** |
| &nbsp;&nbsp;model time (API calls) | <mm min> |
| &nbsp;&nbsp;tool time (<what the tools did, e.g. builds, autorouting, exports>) | <h h mm min> |
| Wall-clock span, first prompt to last reply | <h h mm min> |
| User prompts | <n> |
| API calls / tool calls | <n> / <n> |
| **Total tokens** | **<x.xx M>** |
| &nbsp;&nbsp;input read from prompt cache | <x.xx M> |
| &nbsp;&nbsp;input written to prompt cache | <n k> |
| &nbsp;&nbsp;input, uncached | <n k> |
| &nbsp;&nbsp;output (of which thinking) | <n k> (<n k>) |
| Tokens excluding cache reads | <n k> |
| API-equivalent cost (<the tool's estimate, or "published prices">) | $<x.xx> |

How these figures were measured:

- **Active time:** each turn runs from the user's prompt to <assistant>'s last action before the next prompt; the turns are summed.
  - This excludes time spent waiting for the user.
  - It includes time spent on background jobs such as autorouter runs.
  - Tool time is active time minus model time.
- **Tokens and cost:** <where they came from: the change in the session's cost-state counters from just before the first review prompt to just after the last reply, or the transcript's per-response usage>.
- **Cost:** an API list-price estimate, not a bill.

| # | Prompt | Started (UTC) | Active | API calls | Output tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | <first 57 characters of the prompt>... | <DD Mon HH:MM> | <time> | <n> | <n k> |

### Breakdown

| | Schematic & research | PCB | Other | Not attributable | Total |
| --- | --- | --- | --- | --- | --- |
| Active time | <h h mm min> | … | … | … | … |
| API calls | <n> | <n> | <n> | – | <n> |
| Total tokens | <x.x M> | … | … | … | … |
| Tokens excl. cache reads | <x.xx M> | … | … | … | … |
| Output tokens | <n k> | … | … | … | … |
| API-price estimate | $<x.xx> | … | … | … | … |

---

## Conversation

### User (1), <DD Mon YYYY HH:MM> UTC

> <prompt, verbatim>

### <Assistant>

<details><summary><n> tool calls</summary>

- Bash: <description>
- Read `<path>`
- Write `<path>`

</details>

<text, verbatim>

*<Note, e.g. "A background Freerouting run finished and prompted <assistant>.">*
`````
