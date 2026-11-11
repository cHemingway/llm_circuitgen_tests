#!/usr/bin/env python3
"""Statistics for the review part of the session (REVIEW_EXPORT_PROMPT.md).

Reads the session's Claude Code transcript (not in the repo). The span runs
from the first review comment to the request to export the review log. It
writes stats/review_breakdown_calls.csv and prints the figures used in
REVIEW_CONVERSATION.md and the root README.

Claude Code wrote a cost-state snapshot after the first review turn, but none
after the other two; the last one before the review was written before an
unrelated turn (11:29 UTC), which is left out. So:
  * turn 1: tokens, model time, tool time and cost are the change in the
    cost-state counters, minus that unrelated turn (its logged tokens, its
    tool time from timestamps, the rest of its active time as model time, and
    its tokens at the fitted prices);
  * turns 2-3: tokens are summed from the per-response usage, tool time from
    the tool_use -> tool_result timestamps (overlapping calls once), model time
    is active time minus tool time, and cost uses the per-token prices fitted
    to all of the session's snapshots.
"""

import csv
import datetime as dt
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                   "/root/.claude/projects/-home-user-llm-circuitgen-tests/"
                   "b9887086-5cdc-5f4c-8ea0-af5f1f17c5ba.jsonl")
FIRST = "Can you tidy up the routing through pin swapping"
STOP = "Export the review log as per REVIEW_EXPORT_PROMPT.md"

S, P, O = "Schematic & research", "PCB", "Other"
# Call index ranges (0-based, transcript order), inclusive. Pin swaps and the
# SKiDL tables count as circuit work; moving parts, routing, DRC, renders and
# routing figures as PCB; git, README text, task lists and replies as Other.
RANGES = [
    (0, 1, S), (2, 3, P), (4, 5, O), (6, 9, P), (10, 16, S), (17, 17, P), (18, 23, O),
    (24, 24, P), (25, 27, S), (28, 32, P), (33, 33, S), (34, 39, O),
    (40, 40, P), (41, 42, O), (43, 47, P), (48, 48, S), (49, 49, P), (50, 51, O),
    (52, 59, P), (60, 60, S), (61, 64, O),
]


def main_model(usage):
    """The session's main model: the modelUsage entry with the most output."""
    return max(usage.values(), key=lambda m: m["outputTokens"])


def ts(r):
    return dt.datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))


def is_prompt(r):
    if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"):
        return False
    c = r["message"]["content"]
    if isinstance(c, str):
        return not c.startswith("<task-notification>")
    return any(b.get("type") == "text" for b in c) and not any(b.get("type") == "tool_result" for b in c)


def prompt_text(r):
    c = r["message"]["content"]
    return c if isinstance(c, str) else "\n".join(b["text"] for b in c if b.get("type") == "text")


def tokens(u):
    return np.array([u.get("input_tokens") or 0, u.get("cache_creation_input_tokens") or 0,
                     u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0], float)


def snap(r):
    m = main_model(r["modelUsage"])
    return dict(tok=np.array([m["inputTokens"], m["cacheCreationInputTokens"], m["cacheReadInputTokens"],
                              m["outputTokens"]], float), thinking=m["thinkingTokens"],
                cost=r["totalCostUSD"], api=r["totalAPIDuration"] / 1000, tool=r["totalToolDuration"] / 1000)


def union_seconds(iv):
    total, cur = 0.0, None
    for a, b in sorted(iv):
        if cur and a <= cur[1]:
            cur = (cur[0], max(cur[1], b))
        else:
            if cur:
                total += (cur[1] - cur[0]).total_seconds()
            cur = (a, b)
    return total + ((cur[1] - cur[0]).total_seconds() if cur else 0.0)


def left_out(rows, a, z):
    """Logged usage and timing of the unrelated turn(s) between rows a and z."""
    tok, seen, starts, iv, t0, t1 = np.zeros(4), set(), {}, [], None, None
    for r in rows[a:z]:
        if "timestamp" not in r:
            continue
        if is_prompt(r):
            t0 = t0 or ts(r)
        elif r.get("type") in ("assistant", "user") or r.get("subtype") == "stop_hook_summary":
            t1 = ts(r)
        if r.get("type") == "assistant" and not r.get("isApiErrorMessage") and r["message"]["id"] not in seen:
            seen.add(r["message"]["id"])
            tok += tokens(r["message"]["usage"])
        for blk in (r.get("message") or {}).get("content") or []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                starts[blk["id"]] = ts(r)
            if isinstance(blk, dict) and blk.get("type") == "tool_result" and blk["tool_use_id"] in starts:
                iv.append((starts.pop(blk["tool_use_id"]), ts(r)))
    active = (t1 - t0).total_seconds() if t0 else 0.0
    tool = union_seconds(iv)
    return dict(tok=tok, calls=len(seen), active=active, tool=tool, model=active - tool)


def analyse():
    rows = [json.loads(l) for l in open(SRC)]
    # Price fit over every distinct snapshot of the session
    snaps = {}
    for r in rows:
        if r.get("type") == "cost-state":
            s = snap(r)
            snaps[tuple(s["tok"])] = s["cost"]
    A, b = np.array(list(snaps)), np.array(list(snaps.values()))
    price, *_ = np.linalg.lstsq(A, b, rcond=None)
    resid = float(np.abs(A @ price - b).max())

    i0 = next(i for i, r in enumerate(rows) if is_prompt(r) and FIRST in prompt_text(r))
    i1 = next(i for i, r in enumerate(rows) if r.get("type") == "queue-operation"
              and r.get("operation") == "enqueue" and STOP in str(r.get("content")))
    b_row = max(i for i, r in enumerate(rows[:i0]) if r.get("type") == "cost-state")
    before = snap(rows[b_row])
    pre = left_out(rows, b_row, i0)
    inside = [(i, snap(r)) for i, r in enumerate(rows[i0:i1], i0) if r.get("type") == "cost-state"]

    turns, calls, order, tool_iv, starts = [], {}, [], [], {}
    last_req = None
    for i in range(i0, i1):
        r = rows[i]
        if "timestamp" not in r:
            continue
        t = r.get("type")
        if is_prompt(r):
            turns.append(dict(start=ts(r), end=ts(r), prompt=prompt_text(r).strip(), first_row=i))
            last_req = ts(r)
            continue
        if t in ("assistant", "user") or (t == "system" and r.get("subtype") == "stop_hook_summary"):
            turns[-1]["end"] = max(turns[-1]["end"], ts(r))
            turns[-1]["last_row"] = i
        if t == "user":
            last_req = ts(r)
            for blk in r["message"]["content"] if isinstance(r["message"]["content"], list) else []:
                if blk.get("type") == "tool_result" and blk["tool_use_id"] in starts:
                    tool_iv.append((len(turns) - 1, starts.pop(blk["tool_use_id"]), ts(r)))
        if t == "assistant" and not r.get("isApiErrorMessage"):
            mid = r["message"]["id"]
            if mid not in calls:
                calls[mid] = dict(turn=len(turns) - 1, req=last_req, tok=tokens(r["message"]["usage"]),
                                  thinking=(r["message"]["usage"].get("output_tokens_details") or {})
                                  .get("thinking_tokens", 0), tools=[], row=i)
                order.append(mid)
            for blk in r["message"]["content"]:
                if blk.get("type") == "tool_use":
                    starts[blk["id"]] = ts(r)
                    d = blk["input"].get("description") or blk["input"].get("file_path") or ""
                    calls[mid]["tools"].append(f"{blk['name']}: {d}" if d else blk["name"])

    for k, mid in enumerate(order):
        c = calls[mid]
        nxt = calls[order[k + 1]] if k + 1 < len(order) else None
        end = nxt["req"] if nxt and nxt["turn"] == c["turn"] else turns[c["turn"]]["end"]
        c["sec"] = (end - c["req"]).total_seconds()

    cat_of = {k: cat for a, z, cat in RANGES for k in range(a, z + 1)}
    assert sorted(cat_of) == list(range(len(order))), (len(order), sorted(set(range(len(order))) - set(cat_of)))

    # Per turn: counters where a snapshot closes the turn, else the transcript
    for k, tr in enumerate(turns):
        tr["calls"] = [calls[m] for m in order if calls[m]["turn"] == k]
        tr["active"] = (tr["end"] - tr["start"]).total_seconds()
        tr["log_tok"] = sum((c["tok"] for c in tr["calls"]), np.zeros(4))
        tr["tool_ts"] = union_seconds([(a, b) for t, a, b in tool_iv if t == k])
        nxt_row = turns[k + 1]["first_row"] if k + 1 < len(turns) else i1
        closing = [s for i, s in inside if tr["last_row"] < i < nxt_row]
        opening = before if k == 0 else None
        if closing and k == 0:
            s1 = closing[-1]
            tr["src"] = "counters"
            tr["tok"] = s1["tok"] - opening["tok"] - pre["tok"]
            tr["thinking"] = sum(c["thinking"] for c in tr["calls"])
            tr["cost"] = s1["cost"] - opening["cost"] - float(pre["tok"] @ price)
            tr["model"] = s1["api"] - opening["api"] - pre["model"]
            tr["tool"] = tr["active"] - tr["model"]
        else:
            tr["src"] = "transcript"
            tr["tok"] = tr["log_tok"]
            tr["thinking"] = sum(c["thinking"] for c in tr["calls"])
            tr["cost"] = float(tr["tok"] @ price)
            tr["tool"] = tr["tool_ts"]
            tr["model"] = tr["active"] - tr["tool"]

    cats = {x: dict(sec=0.0, n=0, tok=np.zeros(4)) for x in (S, P, O)}
    out = HERE / "stats" / "review_breakdown_calls.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["call", "turn", "request_utc", "category", "active_s", "input", "cache_write",
                    "cache_read", "output", "tools"])
        for k, mid in enumerate(order):
            c, cat = calls[mid], cat_of[k]
            cats[cat]["sec"] += c["sec"]
            cats[cat]["n"] += 1
            cats[cat]["tok"] += c["tok"]
            w.writerow([k, c["turn"] + 1, c["req"].strftime("%Y-%m-%d %H:%M:%S"), cat, round(c["sec"], 1),
                        *map(int, c["tok"]), " | ".join(c["tools"]).replace("/tmp/claude-0/-home-user-llm-circuitgen-tests/b9887086-5cdc-5f4c-8ea0-af5f1f17c5ba/scratchpad/", "scratchpad/")])

    total = dict(sec=sum(t["active"] for t in turns), n=len(order), tok=sum((t["tok"] for t in turns), np.zeros(4)),
                 cost=sum(t["cost"] for t in turns))
    na = dict(sec=total["sec"] - sum(v["sec"] for v in cats.values()), n=None,
              tok=total["tok"] - sum(v["tok"] for v in cats.values()))
    costs = [float(v["tok"] @ price) for v in cats.values()]
    na_cost = total["cost"] - sum(costs)
    costs += [0.0 if abs(na_cost) < 0.005 else na_cost, total["cost"]]
    return dict(turns=turns, cats=cats, na=na, total=total, costs=costs, price=price, resid=resid, pre=pre,
                nsnaps=len(snaps), calls=calls, order=order, tool_calls=len(tool_iv) + 0,
                n_tool_use=sum(len(calls[m]["tools"]) for m in order), rows=rows, i0=i0, i1=i1)


def hm(sec, seconds=False):
    m = round(sec / 60)
    if seconds and sec < 60:
        return f"{round(sec)} s"
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def table(res):
    cols = [res["cats"][S], res["cats"][P], res["cats"][O], res["na"], res["total"]]
    return "\n".join([
        "| | Schematic & research | PCB | Other | Not attributable | Total |",
        "| --- | --- | --- | --- | --- | --- |",
        "| Active time | " + " | ".join(hm(v["sec"]) for v in cols) + " |",
        "| API calls | " + " | ".join("–" if v["n"] is None else str(v["n"]) for v in cols) + " |",
        "| Total tokens | " + " | ".join(f"{v['tok'].sum() / 1e6:.1f} M" for v in cols) + " |",
        "| Tokens excl. cache reads | " + " | ".join(f"{(v['tok'].sum() - v['tok'][2]) / 1e6:.2f} M" for v in cols) + " |",
        "| Output tokens | " + " | ".join(f"{v['tok'][3] / 1e3:.0f} k" for v in cols) + " |",
        "| API-price estimate | " + " | ".join(f"${x:.2f}" for x in res["costs"]) + " |",
    ])


def main():
    res = analyse()
    print(table(res))
    print("\nprices $/MTok (input, cache write, cache read, output):",
          ", ".join(f"{x * 1e6:.3f}" for x in res["price"]), f"from {res['nsnaps']} snapshots,",
          f"max residual ${res['resid']:.2e}")
    pre = res["pre"]
    print(f"left out before turn 1: {pre['calls']} calls, {pre['tok'].sum():,.0f} tokens, active {pre['active']:.0f} s, "
          f"tool {pre['tool']:.0f} s")
    for k, t in enumerate(res["turns"], 1):
        print(f"turn {k} [{t['src']}]: active {t['active']:.0f} s, model {t['model']:.0f} s, tool {t['tool']:.0f} s "
              f"(timestamps {t['tool_ts']:.0f} s), calls {len(t['calls'])}, tokens {t['tok'].sum():,.0f} "
              f"(logged {t['log_tok'].sum():,.0f}), output {t['tok'][3]:,.0f}, thinking {t['thinking']:,.0f}, "
              f"cost ${t['cost']:.2f}")


if __name__ == "__main__":
    main()
