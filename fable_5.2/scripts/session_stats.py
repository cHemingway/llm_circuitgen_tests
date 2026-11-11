#!/usr/bin/env python3
"""Session statistics and conversation export for the fable_5.2 run.

    python3 -I scripts/session_stats.py <session.jsonl>

Reads the Claude Code session transcript (JSONL) and writes, in the folder above
this script:
    CONVERSATION.md      the conversation export (up to the export request)
    session_calls.csv    every API call with its category, timing and tokens
    session_breakdown.json   the figures used in the README tables
and prints the Totals / Breakdown tables.

The span is the first prompt up to, not including, the first "Export this
conversation" request.  Each assistant message.id is one API call; API error
messages (usage-limit notices) are not calls.  The totals are checked against the
last cost-state record before the request.
"""
import csv
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))
SRC = sys.argv[1]
SCRATCH = '/tmp/claude-0/-home-user-llm-circuitgen-tests/9332df17-6fb3-52d5-8cfe-c3e145280a66/scratchpad'
TOOL = 'Fable 5.2 + KiCad'
ASSISTANT = 'Claude'
MODEL = 'claude-fable-5-2'

# Published Claude Fable 5.2 prices, USD per million tokens (claude-api skill, shared/models.md):
# $8 in / $40 out, cache reads $0.20, 5-minute cache writes $10, 1-hour cache writes $16.
PRICE = dict(inp=8.0, out=40.0, cr=0.20, w5=10.0, w1=16.0)

# Category of each call, by the last 6 characters of its message id.  A marker applies to that call
# and every later call until the next marker.  S = Schematic & research, P = PCB, O = Other.
MARKERS = [
    ('1bZ2sx', 'S'),   # start: repo/KiCad check, reading the manual, part search, datasheets
    ('KfakNY', 'P'),   # D-sub datasheet and mechanical drawing, for the footprint
    ('tLQ44m', 'P'),   # pcbnew / Freerouting toolchain check
    ('u43Atm', 'S'),   # branch + reference datasheets, TPIC6C595 / RP2350 checks, parts, symbols, schematic
    ('6Sf4rW', 'P'),   # moves on to the board
    ('oCSbbN', 'O'),   # status check after restart, checkpoint commit
    ('7X9dH2', 'P'),   # DC-DC footprint
    ('3R7SdK', 'S'),   # netlist inspection
    ('dX4jaH', 'P'),   # RP2350 regulator reference layout
    ('PBxG4q', 'S'),   # inductor polarity, netlist reader, net names
    ('eyBShU', 'P'),   # board generator, placement, routing, DRC, exports
    ('CLq7Ji', 'O'),   # README
    ('6Jan9W', 'P'),   # wait for the build, verify outputs
    ('xmgCvh', 'O'),   # status check after restart
    ('PfrqHj', 'P'),   # 3D models, re-export
    ('X9y3op', 'O'),   # commit, push, final summary
]
CATS = [('S', 'Schematic & research'), ('P', 'PCB'), ('O', 'Other')]

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
SECRETS = [
    re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{20,}'),
    re.compile(r'(?i)((?:api[_-]?key|token|secret|password|passwd)["\']?\s*[=:]\s*["\']?)[A-Za-z0-9._~+/=-]{12,}'),
    re.compile(r'(https?://[^/\s:@]+:)[^@\s/]{6,}(@)'),
]


def clean(s):
    s = s.replace(SCRATCH, '$SCRATCH').replace(os.path.dirname(SCRATCH), '$SCRATCH/..')
    s = EMAIL.sub('[email redacted]', s)
    for r in SECRETS:
        if r.groups:
            s = r.sub(lambda m: m.group(1) + '[redacted]' + (m.group(2) if r.groups > 1 else ''), s)
        else:
            s = r.sub('[redacted]', s)
    return s


def cut(s, n):
    s = clean(s)
    if len(s) <= n:
        return s
    return s[:n] + '… [%d more characters truncated]' % (len(s) - n)


def fence(text, lang=''):
    n = 3
    for m in re.finditer(r'`+', text):
        n = max(n, len(m.group(0)) + 1)
    f = '`' * n
    return '%s%s\n%s\n%s' % (f, lang, text, f)


def ts(d):
    return dt.datetime.strptime(d['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')


def hm(t):
    return t.strftime('%H:%M')


def fmt_dur(sec, hours=True):
    m = int(round(sec / 60.0))
    if hours and m >= 60:
        return '%d h %02d min' % (m // 60, m % 60)
    return '%d min' % m


def fmt_tok(n):
    if n >= 1e6:
        return ('%.1f M' if n >= 1e7 else '%.2f M') % (n / 1e6) if False else ('%.1f M' % (n / 1e6) if n >= 1e7 else '%.2f M' % (n / 1e6))
    if n >= 1e3:
        return '%d k' % round(n / 1e3)
    return str(int(n))


def fmt_tok_total(n):
    return '0' if n == 0 else '%.1f M' % (n / 1e6)


def price(u):
    return (u['inp'] * PRICE['inp'] + u['out'] * PRICE['out'] + u['cr'] * PRICE['cr'] +
            u['w5'] * PRICE['w5'] + u['w1'] * PRICE['w1']) / 1e6


def main():
    rows = [json.loads(l) for l in open(SRC)]
    # ---- span ---------------------------------------------------------------------------------------
    cut_idx = next(i for i, d in enumerate(rows) if d['type'] == 'user' and isinstance(d['message']['content'], str)
                   and d['message']['content'].startswith('Export this conversation'))
    span = rows[:cut_idx]
    cost = [d for d in span if d['type'] == 'cost-state'][-1]
    mu = cost['modelUsage'][MODEL]
    # ---- calls --------------------------------------------------------------------------------------
    calls = {}
    order = []
    for i, d in enumerate(span):
        if d['type'] != 'assistant' or d.get('isApiErrorMessage') or d['message'].get('model') == '<synthetic>':
            continue
        m = d['message']
        c = calls.get(m['id'])
        if c is None:
            c = calls[m['id']] = dict(id=m['id'], first=i, last=i, blocks=[], t0=ts(d))
            order.append(m['id'])
        c['last'] = i
        c['usage'] = m['usage']
        c['t1'] = ts(d)
        c['blocks'] += m['content']
    errors = [(i, d) for i, d in enumerate(span) if d['type'] == 'assistant' and
              (d.get('isApiErrorMessage') or d['message'].get('model') == '<synthetic>')]
    # tokens
    for c in calls.values():
        u = c['usage']
        cc = u.get('cache_creation') or {}
        c['tok'] = dict(inp=u['input_tokens'], out=u['output_tokens'], cr=u['cache_read_input_tokens'],
                        w5=cc.get('ephemeral_5m_input_tokens', 0), w1=cc.get('ephemeral_1h_input_tokens', 0))
        if c['tok']['w5'] + c['tok']['w1'] != u['cache_creation_input_tokens']:
            c['tok']['w5'] = u['cache_creation_input_tokens'] - c['tok']['w1']
    tot = {k: sum(c['tok'][k] for c in calls.values()) for k in ('inp', 'out', 'cr', 'w5', 'w1')}
    assert tot['inp'] == mu['inputTokens'] and tot['out'] == mu['outputTokens'] and tot['cr'] == mu['cacheReadInputTokens'], tot
    assert tot['w5'] + tot['w1'] == mu['cacheCreationInputTokens']
    # published prices must reproduce the cost counter
    est = price(tot)
    assert abs(est - mu['costUSD']) < 0.02, (est, mu['costUSD'])
    for d in span:                                   # and every cost-state snapshot
        if d['type'] == 'cost-state':
            x = d['modelUsage'][MODEL]
            p = price(dict(inp=x['inputTokens'], out=x['outputTokens'], cr=x['cacheReadInputTokens'],
                           w5=x['cacheCreationEphemeral5mInputTokens'], w1=x['cacheCreationEphemeral1hInputTokens']))
            assert abs(p - x['costUSD']) < 0.02, (p, x['costUSD'])
    # ---- turns (user messages) ---------------------------------------------------------------------
    # user messages: the first prompt, and the two "usage limit has reset" notes (queued, absorbed mid-turn)
    msgs = []   # (time, text, mid_work)
    first = next(d for d in span if d['type'] == 'user')
    msgs.append((ts(first), first['message']['content'], False))
    for d in span:
        if (d['type'] == 'queue-operation' and d['operation'] == 'enqueue' and
                d.get('content', '').startswith('I hit my usage limit')):
            msgs.append((dt.datetime.strptime(d['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ'), d['content'], True))
    msgs.sort(key=lambda x: x[0])
    # usage-limit notices are the end of a turn; the later retry errors (after a worker restart) are not
    err_times = [ts(d) for _, d in errors]
    turns = []
    for k, (t, text, mid) in enumerate(msgs):
        nxt = msgs[k + 1][0] if k + 1 < len(msgs) else dt.datetime.max
        cs = [calls[i] for i in order if t <= calls[i]['t0'] < nxt]
        end = max(c['t1'] for c in cs)
        # reply finished: last record of the turn (assistant text, or the usage-limit notice that stopped it)
        lim = [e for e in err_times if t <= e < nxt and e - end < dt.timedelta(minutes=2)]
        if lim:
            end = min(lim)
        turns.append(dict(start=t, end=end, nxt=nxt, calls=[c['id'] for c in cs], text=text, mid=mid))
    # last tool_result of a turn may arrive after the last assistant record; extend to it
    results = {}
    for i, d in enumerate(span):
        if d['type'] == 'user' and isinstance(d['message']['content'], list):
            for b in d['message']['content']:
                if b.get('type') == 'tool_result':
                    results[b['tool_use_id']] = (b, ts(d))
    # ---- per-call times ------------------------------------------------------------------------------
    for tn in turns:
        ids = tn['calls']
        for k, cid in enumerate(ids):
            c = calls[cid]
            if k == 0:
                c['req'] = tn['start']
            else:
                prev = calls[ids[k - 1]]
                us = [ts(d) for d in span[prev['last'] + 1:c['first']] if d['type'] == 'user']
                c['req'] = max(us) if us else prev['t1']
        for k, cid in enumerate(ids):
            c = calls[cid]
            c['dur'] = ((calls[ids[k + 1]]['req'] if k + 1 < len(ids) else tn['end']) - c['req']).total_seconds()
        # the last tool result of the final call may arrive after its last record but before the turn end
    active = sum((t['end'] - t['start']).total_seconds() for t in turns)
    assert abs(active - sum(c['dur'] for c in calls.values())) < 1.0, (active, sum(c['dur'] for c in calls.values()))
    # ---- categories -----------------------------------------------------------------------------------
    marks = {}
    for suf, cat in MARKERS:
        hits = [i for i in order if i.endswith(suf)]
        assert len(hits) == 1, suf
        marks[hits[0]] = cat
    cat = None
    for i in order:
        cat = marks.get(i, cat)
        calls[i]['cat'] = cat
    # ---- tool time from the transcript (cross-check only; the cost-state counter is reported) --------
    iv = []
    for c in calls.values():
        for b in c['blocks']:
            if b['type'] == 'tool_use' and b['id'] in results:
                a = c['t0'] if False else None
                iv.append((c['t1'] if False else None, None))
    iv = []
    for i, d in enumerate(span):
        if d['type'] == 'assistant' and not d.get('isApiErrorMessage'):
            for b in d['message']['content']:
                if b['type'] == 'tool_use' and b['id'] in results:
                    iv.append((ts(d), results[b['id']][1]))
    iv.sort()
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    tool_tr = sum((b - a).total_seconds() for a, b in merged)
    # ---- breakdown -------------------------------------------------------------------------------------
    names = dict(CATS)
    bd = {}
    for k, n in CATS:
        cs = [c for c in calls.values() if c['cat'] == k]
        t = {x: sum(c['tok'][x] for c in cs) for x in ('inp', 'out', 'cr', 'w5', 'w1')}
        bd[n] = dict(active=sum(c['dur'] for c in cs), calls=len(cs), total=sum(t.values()) - 0,
                     excl=t['inp'] + t['w5'] + t['w1'] + t['out'], out=t['out'], price=price(t), tok=t)
    sess_tot = dict(active=active, calls=len(calls), total=sum(tot.values()),
                    excl=tot['inp'] + tot['w5'] + tot['w1'] + tot['out'], out=tot['out'], price=mu['costUSD'])
    na = {k: sess_tot[k] - sum(bd[n][k] for _, n in CATS) for k in ('active', 'total', 'excl', 'out', 'price')}
    # ---- CSV --------------------------------------------------------------------------------------------
    with open(os.path.join(OUT, 'session_calls.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['n', 'message_id', 'request_utc', 'category', 'active_s', 'input', 'cache_write_5m', 'cache_write_1h',
                    'cache_read', 'output', 'what'])
        for n, i in enumerate(order, 1):
            c = calls[i]
            what = []
            for b in c['blocks']:
                if b['type'] == 'tool_use':
                    inp = b['input']
                    what.append('%s: %s' % (b['name'], (inp.get('description') or inp.get('file_path') or
                                                         inp.get('command') or json.dumps(inp))[:100].replace('\n', ' ')))
                elif b['type'] == 'text':
                    what.append('text: ' + b['text'][:60].replace('\n', ' '))
            w.writerow([n, i, c['req'].strftime('%Y-%m-%d %H:%M:%S'), names[c['cat']], '%.1f' % c['dur'],
                        c['tok']['inp'], c['tok']['w5'], c['tok']['w1'], c['tok']['cr'], c['tok']['out'], ' | '.join(what)])
    # ---- totals --------------------------------------------------------------------------------------------
    t_first = turns[0]['start']
    t_last = turns[-1]['end']
    wall = (t_last - t_first).total_seconds()
    limit_stop = 0.0
    for a, b in zip(turns, turns[1:]):
        limit_stop += (b['start'] - a['end']).total_seconds()
    wait = wall - active
    api_s = cost['totalAPIDuration'] / 1000.0
    tool_s = cost['totalToolDuration'] / 1000.0
    res = dict(
        start=t_first.strftime('%Y-%m-%d %H:%M'), end=t_last.strftime('%Y-%m-%d %H:%M'),
        active_s=active, wall_s=wall, wait_s=wait, limit_s=limit_stop, api_s=api_s, tool_s=tool_s, tool_transcript_s=tool_tr,
        tokens=tot, thinking=mu['thinkingTokens'], calls=len(calls), cost=mu['costUSD'],
        breakdown=bd, not_attributable=na, session=sess_tot, prices=PRICE)
    json.dump(res, open(os.path.join(OUT, 'session_breakdown.json'), 'w'), indent=1, default=str)

    # ---- tables ---------------------------------------------------------------------------------------------
    def row(label, fn):
        cells = [fn(bd[n]) for _, n in CATS]
        return '| %s | %s |' % (label, ' | '.join(cells))

    def money(x):
        return '$%.2f' % (0.0 if abs(x) < 0.005 else x)
    brk = ['| | Schematic & research | PCB | Other | Not attributable | Total |', '| --- | --- | --- | --- | --- | --- |']
    brk.append('| Active time | %s | %s | %s | %s | %s |' % (
        *[fmt_dur(bd[n]['active']) for _, n in CATS], fmt_dur(max(na['active'], 0.0)), fmt_dur(sess_tot['active'])))
    brk.append('| API calls | %s | – | %d |' % (' | '.join(str(bd[n]['calls']) for _, n in CATS), sess_tot['calls']))
    brk.append('| Total tokens | %s | %s | %s |' % (' | '.join(fmt_tok_total(bd[n]['total']) for _, n in CATS),
                                                   fmt_tok_total(na['total']), fmt_tok_total(sess_tot['total'])))
    brk.append('| Tokens excl. cache reads | %s | %s | %s |' % (
        ' | '.join('%.2f M' % (bd[n]['excl'] / 1e6) for _, n in CATS), '0' if na['excl'] == 0 else '%.2f M' % (na['excl'] / 1e6),
        '%.2f M' % (sess_tot['excl'] / 1e6)))
    brk.append('| Output tokens | %s | %s | %s |' % (' | '.join('%d k' % round(bd[n]['out'] / 1e3) for _, n in CATS),
                                                   '0' if na['out'] == 0 else '%d k' % round(na['out'] / 1e3), '%d k' % round(sess_tot['out'] / 1e3)))
    brk.append('| API-price estimate | %s | %s | %s |' % (' | '.join(money(bd[n]['price']) for _, n in CATS),
                                                         money(na['price']), money(sess_tot['price'])))
    res['breakdown_table'] = '\n'.join(brk)

    # ---- conversation ------------------------------------------------------------------------------------------
    tool_names_seen = set()
    md = []
    day = None

    def stamp(t, first_of_day):
        return t.strftime('%Y-%m-%d %H:%M') if first_of_day else t.strftime('%H:%M')

    def render_tool(b):
        name, inp = b['name'], b['input']
        out = []
        if name == 'Bash':
            title = inp.get('description') or inp.get('command', '')[:60]
            out.append('<details><summary>🔧 Bash: %s</summary>\n' % clean(title).replace('\n', ' '))
            out.append(fence(cut(inp.get('command', ''), 1500), 'bash') + '\n')
        elif name == 'Read':
            out.append('<details><summary>🔧 Read: %s</summary>\n' % clean(inp.get('file_path', '')))
        elif name == 'Write':
            out.append('<details><summary>🔧 Write: %s</summary>\n' % clean(inp.get('file_path', '')))
            out.append(fence(cut(inp.get('content', ''), 1500)) + '\n')
        elif name == 'Edit':
            out.append('<details><summary>🔧 Edit: %s</summary>\n' % clean(inp.get('file_path', '')))
            out.append('old:\n' + fence(cut(inp.get('old_string', ''), 1500)) + '\nnew:\n' + fence(cut(inp.get('new_string', ''), 1500)) + '\n')
        else:
            out.append('<details><summary>🔧 %s</summary>\n' % name)
            out.append(fence(cut(json.dumps(inp, indent=2, ensure_ascii=False), 1500), 'json') + '\n')
        r = results.get(b['id'])
        if r:
            c = r[0].get('content')
            parts = []
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, list):
                for x in c:
                    parts.append(x.get('text', '') if x.get('type') == 'text' else '[image]')
            text = '\n'.join(p for p in parts if p != '') if parts else ''
            out.append('result:\n' + fence(cut(text, 800)) + '\n')
        out.append('</details>\n')
        return '\n'.join(out)

    for tn in turns:
        t = tn['start']
        first_of_day = day != t.date()
        day = t.date()
        who = 'User (%s UTC%s)' % (stamp(t, first_of_day), ', sent while %s was working' % ASSISTANT if tn['mid'] else '')
        md.append('## %s\n\n%s\n' % (who, clean(tn['text'])))
        # records of this turn in order
        cids = set(tn['calls'])
        lo = calls[tn['calls'][0]]['first']
        hi = calls[tn['calls'][-1]]['last']
        seen_blocks = set()
        heading_open = False
        pending_text = False
        for i in range(lo, len(span)):
            if i >= len(span):
                break
            d = span[i]
            if d['type'] != 'assistant':
                continue
            m = d['message']
            is_err = d.get('isApiErrorMessage') or m.get('model') == '<synthetic>'
            if not is_err and m['id'] not in cids:
                continue
            if is_err and not (tn['start'] <= ts(d) < tn['nxt']):
                continue
            for b in m['content']:
                if b['type'] == 'text' and b['text'].strip():
                    if (i, b['text']) in seen_blocks:
                        continue
                    seen_blocks.add((i, b['text']))
                    fd = False
                    if not heading_open or pending_text is False:
                        pass
                    md.append('## %s (%s UTC)\n' % (ASSISTANT, hm(ts(d))))
                    heading_open = True
                    pending_text = True
                    if is_err:
                        md.append('> *Usage limit notice shown to the user:* %s\n' % clean(b['text']))
                    else:
                        md.append(clean(b['text']) + '\n')
                elif b['type'] == 'tool_use':
                    if not heading_open:
                        md.append('## %s (%s UTC)\n' % (ASSISTANT, hm(ts(d))))
                        heading_open = True
                    md.append(render_tool(b))
            # a tool-call-only message keeps the current heading; text starts a new one
        md.append('')
    header = '# Conversation export: %s Solartron 7075 USB interface\n\n' % TOOL
    header += ('%s Code session (model Fable 5.2) on `cHemingway/llm_circuitgen_tests`, branch `fable_5.2`, %s – %s UTC.\n'
               'This export covers every message up to, but not including, the request to export it.\n\n') % (
        ASSISTANT, res['start'], res['end'])
    am = active / 60.0

    def hh(s):
        m = int(round(s / 60.0))
        return '%d h %02d min' % (m // 60, m % 60)
    top = []
    top.append('## Totals\n')
    top.append('| Time | |\n|---|---|')
    top.append('| **Active time** (from each user message until the reply finished) | **%.1f min (%s)** |' % (am, hh(active)))
    top.append('| Tool\'s own counters: model (API) time + tool time | %.1f + %.1f = %.1f min |' % (api_s / 60, tool_s / 60, (api_s + tool_s) / 60))
    top.append('| Wall clock, first message to last reply | %s |' % hh(wall))
    top.append('| Of which waiting for the user | %s |' % hh(wait))
    top.append('| … including stops at a usage limit | %s |' % hh(limit_stop))
    top.append('')
    top.append('| Tokens | |\n|---|---|')
    top.append('| Input, uncached | {:,} |'.format(tot['inp']))
    top.append('| Input, written to the prompt cache | {:,} |'.format(tot['w5'] + tot['w1']))
    top.append('| Input, read from the prompt cache | {:,} |'.format(tot['cr']))
    top.append('| Output (of which {:,} thinking) | {:,} |'.format(mu['thinkingTokens'], tot['out']))
    top.append('| **Total, main model** ({} API responses) | **{:,}** |'.format(len(calls), sess_tot['total']))
    top.append('| Helper models (e.g. web tools) | 0 |')
    top.append('| **Grand total** | **{:,}** |'.format(sess_tot['total']))
    top.append('| API-price estimate reported by the tool | ${:.2f} |'.format(mu['costUSD']))
    top.append('')
    top.append('### Breakdown\n')
    top.append(res['breakdown_table'])
    top.append('')
    top.append(
        'Totals come from the last cost-state record before the export request; summing the %d distinct API responses '
        '(each message id once, the four usage-limit notices skipped) gives the same token counts, so nothing is left '
        'unattributed. Active time is measured from each of the three user messages (the brief and the two "usage limit has '
        'reset" notes) until the reply stopped, which leaves out the two usage-limit stops; it agrees with the tool\'s own '
        'API + tool time. Each call is credited with the time until the next call\'s request. The estimate uses the published '
        'Claude Fable 5.2 prices ($8 in, $40 out, $0.20 cache read, $10 / $16 cache write for 5 min / 1 h), which reproduce all '
        'three cost-state snapshots to the cent; too few snapshots exist to fit prices. All cache writes were 1-hour. '
        'The run stopped twice at a usage limit and the session worker restarted four times.\n'
        % len(calls))
    top.append('### Notes on this export\n')
    top.append('* Each tool call is folded into a collapsible block. Inputs are cut at 1500 characters and outputs at 800; images show as `[image]`.')
    top.append('* Hidden reasoning, system reminders and background-task notifications are not included.')
    top.append('* The scratchpad path is shortened to `$SCRATCH`, and the user\'s email address is redacted.')
    top.append('* The two "usage limit has reset" messages were typed while the session was stopped; the session absorbed them mid-turn and they are placed at the time they were sent. The synthetic "worker process was restarted" messages are left out. The usage-limit notices (including the repeat after each worker restart) are shown as quoted lines.')
    top.append('* The context was not compacted within this span (the compaction came after the export request).')
    top.append('\n---\n\n# Conversation\n')
    text = header + '\n'.join(top) + '\n' + '\n'.join(md)
    open(os.path.join(OUT, 'CONVERSATION.md'), 'w').write(text)
    print(text[:len(header) + 4500])
    print('transcript tool time %.1f min (merged tool_use->tool_result), counter %.1f min' % (tool_tr / 60, tool_s / 60))
    print('est %.2f counter %.2f' % (est, mu['costUSD']))
    print('na', na)


if __name__ == '__main__':
    main()
