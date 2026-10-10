#!/usr/bin/env python3
"""Split the design session's statistics into Schematic & research / PCB / Other.

Reads the Claude Code transcript of the session (not in the repo), counts every
API call (one assistant message.id) from the first prompt up to the request to
export the conversation, assigns it a category from the hand-made ranges below,
and writes stats/breakdown_calls.csv plus the README table (to stdout).

Per-token prices are fitted by least squares to the session's cost-state
snapshots and applied to each category's tokens.
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
MODEL = "claude-opus-5-5"
# Results-row active time (README): measured from the transcript turns, 149.3 min
RESULTS_ACTIVE_MIN = None  # recomputed below from the same turn boundaries

S, P, O = "Schematic & research", "PCB", "Other"
# Call index ranges (0-based, in transcript order), inclusive. Judgement calls:
# KiCad/SKiDL installs count as tool research; checking footprints for chosen
# parts, the DD-50 footprint, kinet2pcb, placement, routing, DRC, schematic
# parity (link_schematic.py), Gerbers, 3D renders and prints are PCB; the BOM
# and LED/passive part swaps are part selection; task-list updates, git, README
# and final summaries are Other.
RANGES = [
    (0, 12, S), (13, 13, P), (14, 45, S), (46, 47, O), (48, 62, S), (63, 64, P),
    (65, 67, S), (68, 80, P), (81, 111, S), (112, 133, P), (134, 135, S),
    (136, 140, P), (141, 143, S), (144, 144, P), (145, 145, S), (146, 202, P),
    (203, 208, S), (209, 216, P), (217, 226, S),
    # turn 2 ("Continue"): tidy-up, README, final rebuild, commit
    (227, 228, O), (229, 229, S), (230, 233, O), (234, 235, P), (236, 239, O),
    # turn 3: single-page schematic, schematic parity, README split
    (240, 263, S), (264, 266, P), (267, 280, S), (281, 286, P), (287, 292, S),
    (293, 299, P), (300, 301, S), (302, 304, P), (305, 305, S), (306, 308, O),
    (309, 309, S), (310, 313, O),
    # turn 4: Gerbers and prints
    (314, 341, P), (342, 346, O),
]


def ts(r):
    return dt.datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))


def is_prompt(r):
    if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"):
        return False
    c = r["message"]["content"]
    if isinstance(c, str):
        return not c.startswith("<task-notification>")
    return any(b.get("type") == "text" for b in c) and not any(b.get("type") == "tool_result" for b in c)


def main():
    rows = [json.loads(l) for l in open(SRC)]
    snaps = {}
    for r in rows:  # all distinct cost snapshots of the session, for the price fit
        if r.get("type") == "cost-state":
            m = r["modelUsage"][MODEL]
            snaps[(m["inputTokens"], m["cacheCreationInputTokens"], m["cacheReadInputTokens"],
                   m["outputTokens"])] = r["totalCostUSD"]
    cut = next(i for i, r in enumerate(rows) if r.get("type") == "queue-operation"
               and r.get("operation") == "enqueue" and "Export this conversation" in str(r.get("content")))
    rows = rows[:cut]
    results = [r for r in rows if r.get("type") == "cost-state"][-1]
    rm = results["modelUsage"][MODEL]
    res_tok = np.array([rm["inputTokens"], rm["cacheCreationInputTokens"],
                        rm["cacheReadInputTokens"], rm["outputTokens"]], float)

    # Price fit
    A = np.array([k for k in snaps], float)
    b = np.array([v for v in snaps.values()])
    price, *_ = np.linalg.lstsq(A, b, rcond=None)
    resid = A @ price - b
    assert np.abs(resid).max() < 0.005, resid

    # Turns, calls, request times
    turns, calls, order = [], {}, []
    last_req = None
    compact = []
    for i, r in enumerate(rows):
        if "timestamp" not in r:
            continue
        t = r.get("type")
        if is_prompt(r):
            turns.append([ts(r), ts(r)])
            last_req = ts(r)
            continue
        if not turns:
            continue
        if t in ("assistant", "user") or (t == "system" and r.get("subtype") == "stop_hook_summary"):
            turns[-1][1] = max(turns[-1][1], ts(r))
        if t == "user":
            last_req = ts(r)
        if t == "system" and r.get("subtype") == "compact_boundary":
            compact.append((last_req, ts(r)))
            last_req = ts(r)
        if t == "assistant" and not r.get("isApiErrorMessage"):
            mid = r["message"]["id"]
            if mid not in calls:
                u = r["message"]["usage"]
                tok = np.array([u.get("input_tokens") or 0, u.get("cache_creation_input_tokens") or 0,
                                u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0], float)
                calls[mid] = dict(turn=len(turns) - 1, req=last_req, tok=tok, row=i, tools=[])
                order.append(mid)
            for blk in r["message"]["content"]:
                if blk.get("type") == "tool_use":
                    d = blk["input"].get("description") or blk["input"].get("file_path") or ""
                    calls[mid]["tools"].append(f"{blk['name']}: {d}" if d else blk["name"])

    # Active time: from a call's request to the next call's request in the same
    # turn (the last call runs to the end of the turn); compaction is not a call
    for k, mid in enumerate(order):
        c = calls[mid]
        nxt = calls[order[k + 1]] if k + 1 < len(order) else None
        end = nxt["req"] if nxt and nxt["turn"] == c["turn"] else turns[c["turn"]][1]
        for a, _ in compact:
            if c["req"] < a < end:
                end = a
        c["sec"] = (end - c["req"]).total_seconds()

    cat_of = {}
    for a, z, cat in RANGES:
        for k in range(a, z + 1):
            cat_of[k] = cat
    assert sorted(cat_of) == list(range(len(order))), "every call needs exactly one category"

    active_total = sum((e - s).total_seconds() for s, e in turns)
    cats = {x: dict(sec=0.0, n=0, tok=np.zeros(4)) for x in (S, P, O)}
    out = HERE / "stats" / "breakdown_calls.csv"
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
                        *map(int, c["tok"]), " | ".join(c["tools"])])

    na = dict(sec=active_total - sum(v["sec"] for v in cats.values()), n=None,
              tok=res_tok - sum(v["tok"] for v in cats.values()))
    total = dict(sec=active_total, n=len(order), tok=res_tok)
    cols = [cats[S], cats[P], cats[O], na, total]
    cost_total = results["totalCostUSD"]
    costs = [float(v["tok"] @ price) for v in cols[:3]]
    costs += [cost_total - sum(costs), cost_total]
    assert abs(float(na["tok"] @ price) - costs[3]) < 0.01

    def hm(sec):
        m = round(sec / 60)
        return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"

    def mega(x, nd):
        return f"{x / 1e6:.{nd}f} M"

    lines = [
        "| | Schematic & research | PCB | Other | Not attributable | Total |",
        "| --- | --- | --- | --- | --- | --- |",
        "| Active time | " + " | ".join(hm(v["sec"]) for v in cols) + " |",
        "| API calls | " + " | ".join("–" if v["n"] is None else str(v["n"]) for v in cols) + " |",
        "| Total tokens | " + " | ".join(mega(v["tok"].sum(), 1) for v in cols) + " |",
        "| Tokens excl. cache reads | " + " | ".join(mega(v["tok"].sum() - v["tok"][2], 2) for v in cols) + " |",
        "| Output tokens | " + " | ".join(f"{v['tok'][3] / 1e3:.0f} k" for v in cols) + " |",
        "| API-price estimate | " + " | ".join(f"${x:.2f}" for x in costs) + " |",
    ]
    print("\n".join(lines))
    print("\nprices $/MTok (input, cache write, cache read, output):",
          ", ".join(f"{x * 1e6:.3f}" for x in price), "; max snapshot residual $%.2e" % np.abs(resid).max(),
          "; compaction", sum((z - a).total_seconds() for a, z in compact), "s", file=sys.stderr)


if __name__ == "__main__":
    main()
