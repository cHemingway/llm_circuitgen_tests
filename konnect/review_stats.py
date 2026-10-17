#!/usr/bin/env python3
"""Review statistics and log for the Konnect run (konnect/REVIEW_CONVERSATION.md).

Reads the Claude Code session transcript (JSONL) from the first review comment
up to, but not including, the review-export request. This resumed session
writes no cost-state records, so every figure comes from the transcript:

- API calls and tokens: one call per assistant message.id (its records repeat
  the same usage, so each id is counted once); API error messages are skipped.
- Tool time: the time from each tool_use record to its tool_result record,
  with overlapping (parallel) calls counted once. AskUserQuestion is a wait for
  the user, not tool time.
- Active time: each typed prompt until the last assistant record or tool
  result before the next prompt, minus waits for the user. Usage-limit stops
  and the network outage on 16 Oct fall outside those spans.
- Model time: active time minus tool time.
- Price: published per-token prices (PRICES below).

Each call is put in one category (Schematic & research / PCB / Other) and its
active time is measured from its request until the next call's request in the
same turn. Prints the tables, writes review_calls.csv next to this script and,
with --write-md, writes REVIEW_CONVERSATION.md.

Usage:
    python3 konnect/review_stats.py [--write-md] [path/to/session.jsonl]
"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

DEFAULT_JSONL = os.path.expanduser(
    "~/.claude/projects/-Users-chris-repos-llm-circuitgen-tests/"
    "3539381d-9d8c-4a98-ba5a-6f556d276d24.jsonl")
SESSION_ID = "3539381d-9d8c-4a98-ba5a-6f556d276d24"
START_MARKER = "Can you tidy up the routing through pin swapping"
END_MARKER = "Export the review part of this conversation"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRATCH_RE = re.compile(r"(/private)?/tmp/claude-501/[^/\s]+/[0-9a-f-]{36}/scratchpad")
TMP_RE = re.compile(r"(/private)?/tmp/claude-501/[^/\s]+/[0-9a-f-]{36}")

# Published per-token prices in USD per million tokens, from
# https://platform.claude.com/docs/en/about-claude/pricing (read 2026-10-15 for
# stats.py and again on 2026-10-17). Opus 5.5 has the full 1M context at
# standard prices. Every call in the span ran at standard speed and tier on the
# global endpoint, with no web searches, so no multipliers apply.
PRICES = {
    "claude-opus-5-5": dict(input=4.0, cw_5m=5.0, cw_1h=8.0, cache_read=0.20, output=20.0),
}

SCH, PCB, OTHER = "Schematic & research", "PCB", "Other"
CATEGORIES = (SCH, PCB, OTHER)

# Category of each call, by call number (0-based, in transcript order); see
# review_calls.csv for what each call did. Ranges are inclusive.
RANGES = [
    # Review 1: pin swapping
    (0, 1, SCH),        # Konnect skill and reliability contract (tool documentation)
    (2, 4, PCB),        # earlier routing scripts, board render
    (5, 5, SCH),        # export the netlist, list shift-register and array nets
    (6, 12, PCB),       # measure and plot the current meter-side routing
    (13, 15, SCH),      # open the project, pad positions and schematic notes for the swap
    (16, 17, PCB),      # earlier Freerouting command and DSN structure
    (18, 18, SCH),      # compute the new pin assignment
    (19, 21, PCB),      # DSN builder, Freerouting runs
    (22, 23, SCH),      # schematic label tools, list labels
    (24, 24, PCB),      # routing progress
    (25, 26, SCH),      # find the labels on the swapped pins
    (27, 40, PCB),      # routing experiments
    (41, 41, SCH),      # compare straight-line lengths of old and new assignment
    (42, 88, PCB),      # routing experiments, clearance checks, question on clearing copper
    (89, 110, SCH),     # relabel the schematic, serial-link note, ERC
    (111, 251, PCB),    # clear copper, footprint swaps, SES import, ground fixes, DRC, fab outputs
    (252, 256, OTHER),  # README, commit, send the comparison image, summary
    # Review 2: question about swaps between parts
    (257, 258, SCH),    # count cross-part swaps, measure chain and command nets, answer
    # Review 3: moving parts
    (259, 276, PCB),    # placement analysis
    (277, 278, SCH),    # first Review 3 pin assignment
    (279, 292, PCB),    # placement variants routed with Freerouting
    (293, 293, SCH),    # pin assignment for the scripted input pattern
    (294, 316, PCB),    # scripted input pattern, fixed copper, routing
    (317, 335, SCH),    # relabel the schematic, netlist check, ERC, serial-link note
    (336, 404, PCB),    # clear copper, footprint swaps, SES import, ground fixes, DRC, fab outputs
    (405, 412, OTHER),  # README, commit, send the comparison image, summary
]


def category(n):
    for lo, hi, cat in RANGES:
        if lo <= n <= hi:
            return cat
    return PCB


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc)


def content_text(r):
    c = r.get("message", {}).get("content")
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if b.get("type") == "text")
    return c or ""


def has_tool_result(r):
    c = r.get("message", {}).get("content")
    return isinstance(c, list) and any(b.get("type") == "tool_result" for b in c)


def is_prompt(r):
    """A message the user typed (not a tool result, notification or injected note)."""
    if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"):
        return False
    if has_tool_result(r):
        return False
    t = content_text(r).lstrip()
    return not (t.startswith("<task-notification>") or t.startswith("<command-")
                or t.startswith("<local-command"))


def is_activity(r):
    """A record that shows Claude working: a real reply or a tool result."""
    if r.get("type") == "assistant":
        return not r.get("isApiErrorMessage") and r["message"].get("model") != "<synthetic>"
    return has_tool_result(r)


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def union_length(intervals):
    total, end = 0.0, None
    for a, b in sorted(intervals):
        if end is None or a > end:
            total += b - a
            end = b
        elif b > end:
            total += b - end
            end = b
    return total


def call_price(u, model):
    p = PRICES[model]
    cc = u.get("cache_creation") or {}
    cw5 = cc.get("ephemeral_5m_input_tokens", 0)
    cw1 = cc.get("ephemeral_1h_input_tokens", 0)
    rest = u["cache_creation_input_tokens"] - cw5 - cw1  # unsplit writes, priced as 5m
    return (u["input_tokens"] * p["input"] + (cw5 + rest) * p["cw_5m"] + cw1 * p["cw_1h"]
            + u["cache_read_input_tokens"] * p["cache_read"] + u["output_tokens"] * p["output"]) / 1e6


def short_path(p):
    p = SCRATCH_RE.sub("scratchpad", p)
    p = TMP_RE.sub("scratchpad/..", p)
    return p.replace(REPO + "/", "")


def tool_line(name, inp):
    """One line per tool call: the tool name and its description or file path."""
    if name == "Bash":
        d = inp.get("description") or inp.get("command", "").splitlines()[0][:80]
        return f"Bash: {d}" + (" (background)" if inp.get("run_in_background") else "")
    if name in ("Read", "Write", "Edit"):
        return f"{name} `{short_path(inp.get('file_path', ''))}`"
    if name == "Skill":
        return f"Skill: {inp.get('skill', '')}"
    if name == "ToolSearch":
        return f"ToolSearch: {inp.get('query', '')}"
    if name == "SendUserFile":
        return "SendUserFile " + ", ".join(f"`{short_path(f)}`" for f in inp.get("files", []))
    if name.startswith("mcp__konnect__"):
        return f"Konnect: {name[len('mcp__konnect__'):]}"
    if name.startswith("mcp__computer-use__"):
        s = inp.get("action_summary")
        if not s and name.endswith("_batch"):
            s = "; ".join(x.get("action_summary") or x.get("action", "") for x in inp.get("actions", []))
        return f"Computer use: {name[len('mcp__computer-use__'):]}" + (f" ({s})" if s else "")
    if name.startswith("mcp__"):
        return name.split("__", 2)[-1]
    d = inp.get("description") or ""
    return name + (f": {d}" if d else "")


def analyse(path=DEFAULT_JSONL):
    allrecs = [json.loads(line) for line in open(path)]
    start = next(i for i, r in enumerate(allrecs) if is_prompt(r) and START_MARKER in content_text(r))
    end = next(i for i, r in enumerate(allrecs) if r.get("type") == "user" and END_MARKER in content_text(r))
    recs = allrecs[start:end]

    # --- turns: from each typed prompt until the last activity before the next one
    prompts = [i for i, r in enumerate(recs) if is_prompt(r)]
    segments = []
    for k, p in enumerate(prompts):
        stop = prompts[k + 1] if k + 1 < len(prompts) else len(recs)
        last = max(i for i in range(p, stop) if is_activity(recs[i]))
        segments.append(dict(start=ts(recs[p]["timestamp"]), end=ts(recs[last]["timestamp"]),
                             first=p, stop=stop, prompt=content_text(recs[p])))

    # --- tool intervals; AskUserQuestion is a wait for the user
    tu, waits, tool_iv, n_tools = {}, [], [], 0
    for r in recs:
        if r.get("type") == "assistant" and is_activity(r):
            for b in r["message"]["content"]:
                if b.get("type") == "tool_use":
                    tu[b["id"]] = (ts(r["timestamp"]), b["name"])
        elif has_tool_result(r):
            for b in r["message"]["content"]:
                if b.get("type") == "tool_result" and b["tool_use_id"] in tu:
                    t0, name = tu[b["tool_use_id"]]
                    iv = (t0, ts(r["timestamp"]))
                    (waits if name == "AskUserQuestion" else tool_iv).append(iv)
    n_tools = len(tu)

    compactions = []
    for r in recs:
        if r.get("type") == "system" and r.get("subtype") == "compact_boundary":
            t1 = ts(r["timestamp"])
            compactions.append((t1 - r["compactMetadata"]["durationMs"] / 1000, t1))

    # --- calls: one per assistant message.id, API error messages skipped
    calls, by_id, last_user_ts = [], {}, None
    for i, r in enumerate(recs):
        if r.get("type") == "user":
            last_user_ts = ts(r["timestamp"])
            continue
        if r.get("type") != "assistant" or not is_activity(r):
            continue
        m = r["message"]
        c = by_id.get(m["id"])
        if c is None:
            seg = max(k for k, s in enumerate(segments) if s["first"] <= i)
            c = by_id[m["id"]] = dict(n=len(calls), id=m["id"], idx=i, seg=seg, request=last_user_ts,
                                      model=m["model"], usage=m["usage"], tools=[], text="")
            calls.append(c)
        for b in m["content"]:
            if b.get("type") == "tool_use":
                c["tools"].append(tool_line(b["name"], b["input"]))
            elif b.get("type") == "text":
                c["text"] += b["text"]

    for k, c in enumerate(calls):
        nxt = calls[k + 1] if k + 1 < len(calls) else None
        c_end = nxt["request"] if nxt and nxt["seg"] == c["seg"] else segments[c["seg"]]["end"]
        span = max(0.0, c_end - c["request"])
        span -= sum(overlap(c["request"], c_end, a, b) for a, b in waits)
        span -= sum(overlap(c["request"], c_end, a, b) for a, b in compactions)
        u = c["usage"]
        cc = u.get("cache_creation") or {}
        c.update(active=span, category=category(c["n"]),
                 input=u["input_tokens"], cw=u["cache_creation_input_tokens"],
                 cw5=cc.get("ephemeral_5m_input_tokens", 0), cw1=cc.get("ephemeral_1h_input_tokens", 0),
                 cr=u["cache_read_input_tokens"], out=u["output_tokens"],
                 think=(u.get("output_tokens_details") or {}).get("thinking_tokens", 0),
                 price=call_price(u, c["model"]))

    return dict(recs=recs, segments=segments, waits=waits, tool_iv=tool_iv, n_tools=n_tools,
                compactions=compactions, calls=calls)


# --- number formats used in the root README
def f_dur(sec):
    m = int(round(sec / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def f_short(sec):
    return f"{int(round(sec))} s" if sec < 60 else f_dur(sec)


def f_m1(n):
    return f"{n / 1e6:.1f} M"


def f_m2(n):
    return f"{n / 1e6:.2f} M"


def f_k(n):
    return f"{n / 1e3:,.0f} k"


def f_usd(x):
    return f"${x:.2f}"


def totals(a):
    cs = a["calls"]
    tot = {k: sum(c[k] for c in cs) for k in ("input", "cw", "cw5", "cw1", "cr", "out", "think", "price")}
    tot["all"] = tot["input"] + tot["cw"] + tot["cr"] + tot["out"]
    tot["excl_cr"] = tot["all"] - tot["cr"]
    segs = a["segments"]
    seg_iv = [(s["start"], s["end"]) for s in segs]
    tot["active"] = sum(e - s for s, e in seg_iv) - sum(
        overlap(s, e, w0, w1) for s, e in seg_iv for w0, w1 in a["waits"])
    tot["tool_time"] = union_length([(max(a0, s), min(a1, e)) for a0, a1 in a["tool_iv"]
                                     for s, e in seg_iv if overlap(a0, a1, s, e) > 0])
    tot["model_time"] = tot["active"] - tot["tool_time"]
    tot["wall"] = segs[-1]["end"] - segs[0]["start"]
    tot["calls"] = len(cs)
    tot["tools"] = a["n_tools"]
    tot["prompts"] = len(segs)
    return tot


def breakdown(a):
    tot = totals(a)
    cols = {}
    for cat in CATEGORIES:
        cs = [c for c in a["calls"] if c["category"] == cat]
        cols[cat] = dict(active=sum(c["active"] for c in cs), calls=len(cs),
                         all=sum(c["input"] + c["cw"] + c["cr"] + c["out"] for c in cs),
                         excl_cr=sum(c["input"] + c["cw"] + c["out"] for c in cs),
                         out=sum(c["out"] for c in cs), price=sum(c["price"] for c in cs))
    na = {k: tot[k] - sum(cols[c][k] for c in CATEGORIES)
          for k in ("active", "all", "excl_cr", "out", "price")}
    na["calls"] = None
    cols["Not attributable"] = na
    cols["Total"] = dict(active=tot["active"], calls=tot["calls"], all=tot["all"],
                         excl_cr=tot["excl_cr"], out=tot["out"], price=tot["price"])
    return tot, cols


def breakdown_table(cols):
    names = list(cols)
    rows = [
        ("Active time", lambda v: f_dur(v["active"])),
        ("API calls", lambda v: "–" if v["calls"] is None else str(v["calls"])),
        ("Total tokens", lambda v: f_m1(v["all"])),
        ("Tokens excl. cache reads", lambda v: f_m2(v["excl_cr"])),
        ("Output tokens", lambda v: f_k(v["out"])),
        ("API-price estimate", lambda v: f_usd(v["price"])),
    ]
    out = ["| | " + " | ".join(names) + " |", "| --- " * (len(names) + 1) + "|"]
    for label, fn in rows:
        out.append(f"| {label} | " + " | ".join(fn(cols[n]) for n in names) + " |")
    return "\n".join(out)


def write_csv(a, path):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["call", "message_id", "request_utc", "turn", "category", "active_s", "input_tokens",
                    "cache_write_5m", "cache_write_1h", "cache_read", "output_tokens",
                    "thinking_tokens", "price_usd", "tools", "text"])
        for c in a["calls"]:
            w.writerow([c["n"], c["id"], utc(c["request"]).strftime("%Y-%m-%d %H:%M:%S"), c["seg"] + 1,
                        c["category"], f"{c['active']:.1f}", c["input"], c["cw5"], c["cw1"],
                        c["cr"], c["out"], c["think"], f"{c['price']:.4f}",
                        short_path(" | ".join(c["tools"])), short_path(" ".join(c["text"].split()))[:160]])


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    a = analyse(args[0] if args else DEFAULT_JSONL)
    tot, cols = breakdown(a)
    write_csv(a, os.path.join(HERE, "review_calls.csv"))
    print("Turns (typed prompt -> last activity):")
    for k, s in enumerate(a["segments"]):
        n = sum(1 for c in a["calls"] if c["seg"] == k)
        print(f"  {utc(s['start']):%Y-%m-%d %H:%M:%S} -> {utc(s['end']):%Y-%m-%d %H:%M:%S} "
              f"{f_short(s['end'] - s['start']):>10}  calls {n:4d}  {s['prompt'][:50]!r}")
    print(f"Waits for the user: {[round(b - w) for w, b in a['waits']]} s; "
          f"compactions: {[round(b - w) for w, b in a['compactions']]} s")
    print(f"Active {f_dur(tot['active'])} ({tot['active']:.0f} s), tool {f_dur(tot['tool_time'])}, "
          f"model {f_dur(tot['model_time'])}, wall {f_dur(tot['wall'])}")
    print(f"Calls {tot['calls']}, tool calls {tot['tools']}, prompts {tot['prompts']}")
    print(f"Tokens: input {tot['input']:,}, cache writes {tot['cw']:,} (5m {tot['cw5']:,}, 1h {tot['cw1']:,}), "
          f"cache reads {tot['cr']:,}, output {tot['out']:,} (thinking {tot['think']:,}), "
          f"total {tot['all']:,}, excl. cache reads {tot['excl_cr']:,}, price ${tot['price']:.2f}")
    print("\n" + breakdown_table(cols))
    if "--write-md" in sys.argv:
        write_md(a, tot, cols, os.path.join(HERE, "REVIEW_CONVERSATION.md"))


# --- review log --------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
KEEP_EMAILS = {"noreply@anthropic.com"}
SECRET_RES = [re.compile(p) for p in (
    r"sk-ant-[A-Za-z0-9_-]{10,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_\w+",
    r"xox[abp]-[\w-]+", r"AKIA[0-9A-Z]{16}", r"Bearer [A-Za-z0-9._-]{20,}")]


def clean(s):
    s = SCRATCH_RE.sub("scratchpad", s)
    s = TMP_RE.sub("scratchpad/..", s)
    s = EMAIL_RE.sub(lambda m: m.group(0) if m.group(0) in KEEP_EMAILS else "[email redacted]", s)
    for r in SECRET_RES:
        s = r.sub("[redacted]", s)
    return s


def quote(s):
    return "\n".join("> " + line if line.strip() else ">" for line in s.strip().splitlines())


def day(t):
    return utc(t).strftime("%d %b")


def write_md(a, tot, cols, path):
    recs, segs = a["recs"], a["segments"]
    tu_by_id = {}
    out, tools = [], []
    state = dict(heading=True)

    def flush():
        if tools:
            n = len(tools)
            out.append(f"<details><summary>{n} tool call{'s' if n > 1 else ''}</summary>\n\n"
                       + "\n".join("- " + clean(t) for t in tools) + "\n\n</details>")
            tools.clear()

    def claude():
        if state["heading"]:
            out.append("### Claude")
            state["heading"] = False

    def note(text):
        flush()
        out.append(f"*{text}*")
        state["heading"] = True

    n_prompt = 0
    for r in recs:
        typ = r.get("type")
        if typ == "system" and r.get("subtype") == "compact_boundary":
            d = r["compactMetadata"]["durationMs"] / 1000
            note(f"The context window filled up here and the conversation was automatically "
                 f"compacted ({d:.0f} s).")
            continue
        if typ == "user":
            if is_prompt(r):
                flush()
                n_prompt += 1
                t = ts(r["timestamp"])
                out.append(f"### User ({n_prompt}), {utc(t):%d %b %Y %H:%M} UTC")
                out.append(quote(clean(content_text(r))))
                state["heading"] = True
            elif r.get("isMeta") and "cut off mid-stream" in content_text(r):
                note("The reply above was cut off mid-stream. At 13:00 the app sent Claude a note asking "
                     "it to resume, but the API could not be reached; the session retried until 13:54.")
            elif has_tool_result(r):
                for b in r["message"]["content"]:
                    if b.get("type") == "tool_result" and tu_by_id.get(b["tool_use_id"]) == "AskUserQuestion":
                        c = b.get("content")
                        c = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c)
                        m = re.search(r'"=\"(.*?)\"', c)
                        note("The user answered the question with: \"" + (m.group(1) if m else c) + "\"")
            continue
        if typ != "assistant":
            continue
        m = r["message"]
        if not is_activity(r):
            txt = " ".join(b.get("text", "") for b in m["content"] if b.get("type") == "text")
            note(f"API error shown to the user: \"{clean(txt)}\". The session stopped here until the "
                 "next message.")
            continue
        for b in m["content"]:
            if b.get("type") == "tool_use":
                claude()
                tu_by_id[b["id"]] = b["name"]
                tools.append(tool_line(b["name"], b["input"]))
                if b["name"] == "AskUserQuestion":
                    q = b["input"]["questions"][0]
                    tools[-1] = "AskUserQuestion: " + q["header"]
                    flush()
                    out.append("*Claude asked: \"" + clean(q["question"]) + "\" The options were: "
                               + "; ".join(f"\"{o['label']}\"" for o in q["options"]) + ".*")
            elif b.get("type") == "text" and b["text"].strip():
                claude()
                flush()
                out.append(clean(b["text"]).strip())
    flush()

    # --- statistics
    rows = []
    for k, s in enumerate(segs):
        cs = [c for c in a["calls"] if c["seg"] == k]
        act = (s["end"] - s["start"]) - sum(overlap(s["start"], s["end"], w0, w1) for w0, w1 in a["waits"])
        p = " ".join(s["prompt"].split())
        p = p if len(p) <= 57 else p[:57] + "..."
        rows.append(f"| {k + 1} | {p} | {utc(s['start']):%d %b %H:%M} | {f_short(act)} | {len(cs)} | "
                    f"{f_k(sum(c['out'] for c in cs))} |")
    first, last = segs[0]["start"], segs[-1]["end"]
    waits = sum(b - w for w, b in a["waits"])
    comp = sum(b - w for w, b in a["compactions"])
    head = f"""# Review conversation: Solartron 7075 USB interface in Konnect

Review feedback on the finished Konnect design, in Claude Code session `{SESSION_ID}`, model `claude-opus-5-5`, {utc(first):%d}–{utc(last):%d %b %Y}. It continues [`CONVERSATION.md`](CONVERSATION.md), whose original session was resumed as this one for the conversation export; the review followed in the same resumed session. It was exported from that session's transcript.

This file contains:

- User prompts and Claude's replies, verbatim.
- Tool calls as one-line entries under each reply.
- Notes where a stop hook or a finished background job prompted Claude. Neither happened in this review. The notes here mark a question to the user, usage-limit stops, a compaction and a reply that was cut off.
- No thinking, tool output or system reminders.

## Statistics

| Measure | Value |
| --- | --- |
| **Active time** (Claude working, excluding waits for the user) | **{f_dur(tot['active'])}** |
| &nbsp;&nbsp;model time (API calls) | {f_dur(tot['model_time'])} |
| &nbsp;&nbsp;tool time (Freerouting runs, routing scripts, KiCad edits through Konnect, exports) | {f_dur(tot['tool_time'])} |
| Wall-clock span, first prompt to last reply | {f_dur(tot['wall'])} |
| User prompts | {tot['prompts']} |
| API calls / tool calls | {tot['calls']} / {tot['tools']} |
| **Total tokens** | **{f_m2(tot['all'])}** |
| &nbsp;&nbsp;input read from prompt cache | {f_m2(tot['cr'])} |
| &nbsp;&nbsp;input written to prompt cache | {f_k(tot['cw'])} |
| &nbsp;&nbsp;input, uncached | {f_k(tot['input'])} |
| &nbsp;&nbsp;output (of which thinking) | {f_k(tot['out'])} ({f_k(tot['think'])}) |
| Tokens excluding cache reads | {f_k(tot['excl_cr'])} |
| API-equivalent cost (published prices) | {f_usd(tot['price'])} |

How these figures were measured:

- **Active time:** each turn runs from the user's prompt to Claude's last action before the next prompt; the turns are summed.
  - This excludes time spent waiting for the user: {f_dur(waits)} while a question about clearing the board's copper was open.
  - It also excludes the two usage-limit stops (15 Oct 20:37 to 16 Oct 07:38, and 16 Oct 08:51 to 12:31). It also excludes the time after the reply was cut off on 16 Oct at 12:52: from 13:00 the API could not be reached, and after retrying until 13:54 the session sat idle until the next prompt on 17 Oct.
  - It includes the {comp:.0f} s automatic compaction and time spent on background jobs such as Freerouting runs.
- **No turn was left out.** Every turn in the span belongs to the review; the conversation export and the README statistics came before it.
- **Where the figures come from:** this resumed session wrote no cost-state records, so every figure comes from the transcript.
  - Tokens and API calls are summed from the per-response usage. Each API call is one assistant message id, counted once; the three API error messages are not calls. The compaction's own tokens are not in the transcript, so the totals leave them out.
  - Tool time is the time from each tool call's request to its result, with overlapping (parallel) calls counted once. AskUserQuestion counts as waiting, not tool time. Checked against a session that has Claude Code's tool-time counter, this method reads about 4 % high, because it includes the overhead around each run.
  - Model time is active time minus tool time.
- **Cost:** an API list-price estimate, not a bill. It uses the published Claude Opus 5.5 prices from <https://platform.claude.com/docs/en/about-claude/pricing> (read on 15 Oct 2026 and again on 17 Oct 2026), per million tokens:
  - $4 for input;
  - $5 for 5-minute cache writes and $8 for 1-hour cache writes;
  - $0.20 for cache reads;
  - $20 for output.

  Every cache write in this span was a 1-hour write. All calls ran at standard speed and tier on the global endpoint, so no multipliers apply.

| # | Prompt | Started (UTC) | Active | API calls | Output tokens |
| --- | --- | --- | --- | --- | --- |
""" + "\n".join(rows) + f"""

### Breakdown

{breakdown_table(cols)}

- Each API call is credited with the time from its request until the next call's request in the same turn, including the tool runs it started. The last call of a turn runs to the end of the turn.
- **Not attributable:** the review totals minus the three categories. Its time is the compaction. Its tokens and price are zero because the totals are themselves sums over the logged calls.
- **Categories:** `review_stats.py` sets them by call number, and `review_calls.csv` lists every call with its category. The judgement calls:
  - Computing each new pin assignment, relabelling the schematic, the serial-link note and the ERC and netlist checks are Schematic & research. So is the reply to review 2, which measured the swaps already made.
  - Reading the old routing scripts, measuring the current routing, placement work, every Freerouting and scripted-routing run, clearing the copper in KiCad's GUI, the footprint swaps and session imports, ground fixes, DRC and the fab outputs are PCB.
  - The README edits, commits, sending the comparison images and the end-of-review summaries are Other.

---

## Conversation

"""
    open(path, "w").write(head + "\n\n".join(out) + "\n")
    text = open(path).read()
    assert text.count("<details>") == text.count("</details>"), "unclosed <details>"
    print(f"wrote {path}: {text.count('<details>')} tool blocks, {len(text):,} characters")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
