#!/usr/bin/env python3
"""Session statistics for the Konnect run (konnect/CONVERSATION.md, root README).

Reads the Claude Code session transcript (JSONL) and takes every API call from
the first prompt up to, but not including, the export request. Each call is put
in one category (Schematic & research / PCB / Other), its active time is
measured, and its tokens are priced. Prints the Totals and Breakdown tables and
writes calls.csv next to this script.

Usage:
    python3 konnect/stats.py [path/to/session.jsonl]
"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

DEFAULT_JSONL = os.path.expanduser(
    "~/.claude/projects/-Users-chris-repos-llm-circuitgen-tests/"
    "47e5c69c-808f-4cd7-8f0d-34a4d53529bd.jsonl")
EXPORT_MARKER = "Export this conversation to a Markdown file"
HERE = os.path.dirname(os.path.abspath(__file__))

# Published per-token prices in USD per million tokens, from
# https://platform.claude.com/docs/en/about-claude/pricing (read 2026-10-15).
# Opus 5.5 has the full 1M context at standard prices. Haiku 5.5 is priced by
# prompt length; every Haiku request in this session was under 100k tokens.
PRICES = {
    "claude-opus-5-5": dict(input=4.0, cw_5m=5.0, cw_1h=8.0, cache_read=0.20, output=20.0),
    "claude-haiku-5-5": dict(input=0.10, cw_5m=0.125, cw_1h=0.20, cache_read=0.01, output=0.50),
}
WEB_SEARCH_USD = 10.0 / 1000  # $10 per 1,000 searches

SCH, PCB, OTHER = "Schematic & research", "PCB", "Other"
CATEGORIES = (SCH, PCB, OTHER)


def category(n):
    """Category of call n (0-based, in transcript order). See calls.csv for what
    each call did."""
    # Commits, status checks and final summaries.
    if n in (1,          # create the branch, inspect the blank project
             193, 194,   # commit the schematic, usage-limit summary
             195, 196,   # check MCP connectors after the usage-limit stop
             516, 517, 518, 519):  # stage and commit, send render, final summary
        return OTHER
    # Footprints, placement, routing, DRC, Gerbers and prints.
    if n == 43 or 68 <= n <= 71:  # DD-50 footprint (KiCad D-sub convention, pads, outline)
        return PCB
    if 153 <= n <= 515:  # PCB from schematic onwards, incl. rect-pad footprints
        return PCB
    # Datasheet, part search, symbols, schematic capture, ERC and netlist checks.
    return SCH


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc)


def is_prompt(r):
    """A message the user typed (not a tool result, notification or injected note)."""
    if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"):
        return False
    c = r["message"]["content"]
    if isinstance(c, list):
        if any(b.get("type") == "tool_result" for b in c):
            return False
        c = " ".join(b.get("text", "") for b in c if b.get("type") == "text")
    return not c.lstrip().startswith("<task-notification>")


def prompt_text(r):
    c = r["message"]["content"]
    if isinstance(c, list):
        c = " ".join(b.get("text", "") for b in c if b.get("type") == "text")
    return c


def has_tool_result(r):
    c = r.get("message", {}).get("content")
    return isinstance(c, list) and any(b.get("type") == "tool_result" for b in c)


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def call_price(u, model="claude-opus-5-5"):
    p = PRICES[model]
    cc = u.get("cache_creation") or {}
    cw5 = cc.get("ephemeral_5m_input_tokens", 0)
    cw1 = cc.get("ephemeral_1h_input_tokens", 0)
    rest = u["cache_creation_input_tokens"] - cw5 - cw1  # unsplit writes, priced as 5m
    return (u["input_tokens"] * p["input"] + (cw5 + rest) * p["cw_5m"] + cw1 * p["cw_1h"]
            + u["cache_read_input_tokens"] * p["cache_read"] + u["output_tokens"] * p["output"]) / 1e6


def analyse(path=DEFAULT_JSONL):
    recs = [json.loads(line) for line in open(path)]
    end = next(i for i, r in enumerate(recs)
               if r.get("type") == "user" and not r.get("isMeta")
               and EXPORT_MARKER in prompt_text(r))
    recs = recs[:end]

    # --- segments: from each typed prompt until the reply finished
    prompts = [i for i, r in enumerate(recs) if is_prompt(r)]
    segments = []
    for k, p in enumerate(prompts):
        stop = prompts[k + 1] if k + 1 < len(prompts) else len(recs)
        last = max(i for i in range(p, stop)
                   if recs[i].get("type") == "assistant" or has_tool_result(recs[i]))
        limit = any((recs[i].get("type") == "assistant" and recs[i].get("error") == "rate_limit")
                    or (recs[i].get("isMeta") and "Usage limit reached" in prompt_text(recs[i]))
                    for i in range(p, stop))
        segments.append(dict(start=ts(recs[p]["timestamp"]), end=ts(recs[last]["timestamp"]),
                             first=p, stop=stop, usage_limit=limit,
                             prompt=prompt_text(recs[p])))

    # --- waits for the user inside a turn (AskUserQuestion)
    tu_ts = {}
    waits = []
    for r in recs:
        if r.get("type") == "assistant":
            for b in r["message"]["content"]:
                if b.get("type") == "tool_use" and b["name"] == "AskUserQuestion":
                    tu_ts[b["id"]] = ts(r["timestamp"])
        elif has_tool_result(r):
            for b in r["message"]["content"]:
                if b.get("type") == "tool_result" and b["tool_use_id"] in tu_ts:
                    waits.append((tu_ts[b["tool_use_id"]], ts(r["timestamp"])))

    # --- compaction (not a call)
    compactions = []
    for r in recs:
        if r.get("type") == "system" and r.get("subtype") == "compact_boundary":
            t1 = ts(r["timestamp"])
            compactions.append((t1 - r["compactMetadata"]["durationMs"] / 1000, t1))

    # --- calls: one per assistant message.id, API error messages skipped
    calls, by_id = [], {}
    last_user_ts = None
    for i, r in enumerate(recs):
        if r.get("type") == "user":
            last_user_ts = ts(r["timestamp"])
            continue
        if r.get("type") != "assistant" or r.get("isApiErrorMessage"):
            continue
        m = r["message"]
        c = by_id.get(m["id"])
        if c is None:
            seg = max(k for k, s in enumerate(segments) if s["first"] <= i)
            c = by_id[m["id"]] = dict(
                n=len(calls), id=m["id"], idx=i, seg=seg, request=last_user_ts,
                model=m["model"], usage=m["usage"], tools=[], text="")
            calls.append(c)
        for b in m["content"]:
            if b.get("type") == "tool_use":
                inp = b["input"]
                d = inp.get("description") or inp.get("file_path") or inp.get("query") or ""
                c["tools"].append(b["name"].replace("mcp__konnect__", "konnect:")
                                  + (f" ({d})" if d else ""))
            elif b.get("type") == "text":
                c["text"] += b["text"]

    for k, c in enumerate(calls):
        nxt = calls[k + 1] if k + 1 < len(calls) else None
        c_end = nxt["request"] if nxt and nxt["seg"] == c["seg"] else segments[c["seg"]]["end"]
        span = c_end - c["request"]
        span -= sum(overlap(c["request"], c_end, a, b) for a, b in waits)
        span -= sum(overlap(c["request"], c_end, a, b) for a, b in compactions)
        c["active"] = span
        c["category"] = category(c["n"])
        u = c["usage"]
        cc = u.get("cache_creation") or {}
        c.update(input=u["input_tokens"], cw=u["cache_creation_input_tokens"],
                 cw5=cc.get("ephemeral_5m_input_tokens", 0), cw1=cc.get("ephemeral_1h_input_tokens", 0),
                 cr=u["cache_read_input_tokens"], out=u["output_tokens"],
                 think=(u.get("output_tokens_details") or {}).get("thinking_tokens", 0),
                 price=call_price(u, c["model"]))

    # --- session counters: the cost-state records before the export request
    states = [r for r in recs if r.get("type") == "cost-state"]
    cost = states[-1]

    return dict(recs=recs, segments=segments, waits=waits, compactions=compactions,
                calls=calls, states=states, cost=cost)


def check_prices(states):
    """Price each distinct cost-state snapshot with the published prices.
    Cache writes are priced as 1-hour writes: every write the transcript logs
    is a 1-hour write, and the counters don't split them."""
    seen, rows = set(), []
    for s in states:
        key = json.dumps(s["modelUsage"], sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        for model, mu in s["modelUsage"].items():
            p = PRICES[model]
            est = (mu["inputTokens"] * p["input"] + mu["cacheCreationInputTokens"] * p["cw_1h"]
                   + mu["cacheReadInputTokens"] * p["cache_read"]
                   + mu["outputTokens"] * p["output"]) / 1e6
            est += mu.get("webSearchRequests", 0) * WEB_SEARCH_USD
            rows.append((model, mu["costUSD"], est))
    return len(seen), rows


# --- number formats used in the root README
def f_dur(sec):
    m = int(round(sec / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def f_m1(n):
    return f"{n / 1e6:.1f} M"


def f_m2(n):
    return f"{n / 1e6:.2f} M"


def f_k(n):
    return f"{n / 1e3:.0f} k"


def f_usd(x):
    return f"${x:.2f}"


def totals(a):
    cost = a["cost"]
    mu = cost["modelUsage"]
    tot = dict(input=0, cw=0, cr=0, out=0, think=0)
    for m in mu.values():
        tot["input"] += m["inputTokens"]
        tot["cw"] += m["cacheCreationInputTokens"]
        tot["cr"] += m["cacheReadInputTokens"]
        tot["out"] += m["outputTokens"]
        tot["think"] += m["thinkingTokens"]
    tot["all"] = tot["input"] + tot["cw"] + tot["cr"] + tot["out"]
    tot["excl_cr"] = tot["all"] - tot["cr"]
    tot["price"] = cost["totalCostUSD"]
    segs = a["segments"]
    tot["active"] = sum(s["end"] - s["start"] for s in segs) - sum(b - w for w, b in a["waits"])
    tot["wall"] = segs[-1]["end"] - segs[0]["start"]
    tot["waiting"] = tot["wall"] - tot["active"]
    tot["limit_stops"] = sum(segs[k + 1]["start"] - s["end"]
                             for k, s in enumerate(segs[:-1]) if s["usage_limit"])
    tot["api_time"] = cost["totalAPIDuration"] / 1000
    tot["tool_time"] = cost["totalToolDuration"] / 1000
    tot["calls"] = len(a["calls"])
    return tot


def breakdown(a):
    tot = totals(a)
    cols = {}
    for cat in CATEGORIES:
        cs = [c for c in a["calls"] if c["category"] == cat]
        cols[cat] = dict(
            active=sum(c["active"] for c in cs), calls=len(cs),
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


def short(s):
    """Shorten the session's scratchpad path, as in CONVERSATION.md."""
    return re.sub(r"(/private)?/tmp/claude-501/[^/]+/[0-9a-f-]{36}/scratchpad", "$SCRATCH", s)


def write_csv(a, path):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["call", "message_id", "request_utc", "category", "active_s", "input_tokens",
                    "cache_write_5m", "cache_write_1h", "cache_read", "output_tokens",
                    "thinking_tokens", "price_usd", "tools", "text"])
        for c in a["calls"]:
            w.writerow([c["n"], c["id"],
                        utc(c["request"]).strftime("%Y-%m-%d %H:%M:%S"),
                        c["category"], f"{c['active']:.1f}", c["input"], c["cw5"], c["cw1"],
                        c["cr"], c["out"], c["think"], f"{c['price']:.4f}",
                        short(" | ".join(c["tools"])), short(" ".join(c["text"].split()))[:160]])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSONL
    a = analyse(path)
    tot, cols = breakdown(a)
    write_csv(a, os.path.join(HERE, "calls.csv"))

    n_snap, rows = check_prices(a["states"])
    print(f"Distinct cost-state snapshots: {n_snap}")
    for model, reported, est in rows:
        print(f"  {model}: reported ${reported:.4f}, published prices ${est:.4f} "
              f"(diff ${est - reported:+.4f})")

    print("\nSegments (typed prompt -> reply finished):")
    for s in a["segments"]:
        print(f"  {utc(s['start']):%Y-%m-%d %H:%M:%S} -> "
              f"{utc(s['end']):%Y-%m-%d %H:%M:%S}"
              f"{'  (usage limit)' if s['usage_limit'] else ''}  {s['prompt'][:40]!r}")
    print(f"Waits for the user inside turns: {[round(b - w) for w, b in a['waits']]} s")
    print(f"Compaction: {[round(b - w) for w, b in a['compactions']]} s")

    mu = a["cost"]["modelUsage"]
    print("\nTotals (last cost-state before the export request):")
    for model, m in mu.items():
        print(f"  {model}: input {m['inputTokens']:,}, cache writes {m['cacheCreationInputTokens']:,}, "
              f"cache reads {m['cacheReadInputTokens']:,}, output {m['outputTokens']:,} "
              f"(thinking {m['thinkingTokens']:,}), web searches {m['webSearchRequests']}, "
              f"${m['costUSD']:.4f}")
    print(f"  API time {tot['api_time'] / 60:.1f} min, tool time {tot['tool_time'] / 60:.1f} min, "
          f"cost ${tot['price']:.2f}")
    print(f"  Active {tot['active'] / 60:.1f} min ({f_dur(tot['active'])}), wall {f_dur(tot['wall'])}, "
          f"waiting {f_dur(tot['waiting'])}, usage-limit stops {f_dur(tot['limit_stops'])}")
    print(f"  API calls {tot['calls']}, total tokens {tot['all']:,}")

    logged = {k: sum(c[k] for c in a["calls"]) for k in ("input", "cw", "cr", "out", "think")}
    print(f"  Logged per-call usage: {logged}")

    print("\n" + breakdown_table(cols))
    print(f"\nResults row: {f_dur(tot['active'])} | {f_dur(tot['tool_time'])} | {f_m1(tot['all'])} | "
          f"{tot['calls']} | {f_usd(tot['price'])}")


if __name__ == "__main__":
    main()
