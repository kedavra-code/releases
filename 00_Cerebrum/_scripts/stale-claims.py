#!/usr/bin/env python3
"""Lists sentences a concept's own later content may have disproved.

An ingest appends new rows and paragraphs at the bottom of a concept and does
not revisit the section the new evidence closes, so the stale claim is the one
a reader meets first. `people/tomas-belka.md` said the job title "is not written
out anywhere in this material" nineteen lines above its own quotation of his
signature block (Alpha_kb AI-2026-08-31-1). Three health checks measured the rate
and it rose each time; the run of 14.09.2026 repaired 818 cases by reading.

This is a reading list, not a verdict, and that is deliberate. Two shapes are
listed:

  date     "to at least <date>", where the concept cites a source dated after
           that date. A full date, "Month YYYY", "the sitting of DD.MM.YYYY"
           and a bare year are all read, each at the end of the period it
           names. Only sources dated on or before today count: a contract end
           or a scheduled meeting is not evidence that a presence ran longer.
  absence  a claim that something is written nowhere, made from the pages a
           concept read about the pages it did not.

Neither shape can be decided by a script. Of the nine date hits on 15.09.2026
about half were still true ("planned around it from November 2025 to at least
May 2026" stays true whatever came later), which is why this never became a
DEFECT: three implementations of the date shape gave 15, 5 and 24 hits on one
bundle before its grammar was pinned here. `verify.py` reports the count as a
bundle gauge, which never escalates, and the health check reads this list
before anything else. Owner's decision of 15.09.2026.

questions.md is skipped: its tables quote the text of settled items verbatim.

A sentence read and found still true matches the same shape forever, and a
gauge that never falls is standing noise. So a reading is recorded: after a
pass, `--mark-read` stores each listed sentence with a hash of its concept's
body in `_scripts/stale-claims-read.json`, and the sentence is not listed again
until that concept changes. A change is exactly when the sentence can have gone
stale, because the fault this list exists for is an append below it. The first
reading of all 145 candidates was on 15.09.2026.

Usage:  python3 _scripts/stale-claims.py [KB ...] [--tsv] [--all]
        python3 _scripts/stale-claims.py [KB ...] --mark-read
"""
import datetime
import glob
import hashlib
import json
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READ = os.path.join(VAULT, '_scripts', 'stale-claims-read.json')
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
FENCE = re.compile(r'```.*?```', re.S)
MONTHS = ('january february march april may june july august september '
          'october november december').split()
DATE = re.compile(
    r'\bto at least (?:the (?:sitting|page|meeting) of )?'
    r'(?:(\d{1,2})\.(\d{1,2})\.(\d{4})|(\d{4})-(\d\d)-(\d\d)'
    r'|(' + '|'.join(m.capitalize() for m in MONTHS) + r') (\d{4})|(\d{4}))\b')
ABSENCE = re.compile(
    r"\b(?:is|are|was|were) not (?:written out|stated|recorded|named|given|"
    r"dated) (?:anywhere|in (?:this|the) (?:material|scope|archive|corpus))"
    r"|\bgives? no (?:start|end|start or end|exact) date\b"
    r"|\bno (?:other )?page in (?:this|the) (?:scope|material|archive|corpus)"
    r"\b[^.\n]{0,40}\b(?:states|names|gives|records|dates|says)\b"
    r"|\bnot resolved anywhere\b"
    r"|\bnowhere in (?:this|the) (?:material|scope|corpus|archive)\b"
    r"|\bthe pages read for this concept (?:do|does) not\b"
    r"|\bdoes not record a formal close\b", re.I)


def discover():
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))


def _period_end(m):
    g = m.groups()
    if g[0]:
        return '%s-%02d-%02d' % (g[2], int(g[1]), int(g[0]))
    if g[3]:
        return '%s-%s-%s' % (g[3], g[4], g[5])
    if g[6]:
        return '%s-%02d-31' % (g[7], MONTHS.index(g[6].lower()) + 1)
    return g[8] + '-12-31'


def _read_state():
    try:
        return json.load(open(READ, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _key(r):
    return '%s|%s|%s' % (r['kb'], r['concept'], r['text'])


def scan(kb, include_read=False):
    """Every candidate in one knowledge base, as dicts.

    Sentences recorded as read against the concept's current body are left out
    unless include_read is set."""
    import yaml
    done = {} if include_read else _read_state()
    today = datetime.date.today().isoformat()
    out = []
    root = os.path.join(VAULT, kb, 'Wiki')
    for f in sorted(glob.glob(os.path.join(root, '**', '*.md'),
                              recursive=True)):
        base = os.path.basename(f)
        if '_to_delete' in f or base in ('index.md', 'log.md',
                                         'questions.md'):
            continue
        raw = open(f, encoding='utf-8').read()
        m = FM.match(raw)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        body = raw[m.end():]
        offset = raw[:m.end()].count('\n')
        text = FENCE.sub(lambda x: '\n' * x.group(0).count('\n'), body)
        lms = [str(s.get('last_modified'))[:10]
               for s in fm.get('sources') or []
               if isinstance(s, dict)
               and re.match(r'\d{4}-\d\d-\d\d', str(s.get('last_modified')))]
        past = [x for x in lms if x <= today]
        newest = max(past) if past else ''
        rel = os.path.relpath(f, os.path.join(VAULT, kb))
        digest = hashlib.sha1(body.encode('utf-8')).hexdigest()
        found = []
        for dm in DATE.finditer(text):
            if newest and newest > _period_end(dm):
                found.append(dict(kb=kb, concept=rel, shape='date',
                                  line=offset + 1 + text.count('\n', 0,
                                                               dm.start()),
                                  text=dm.group(0), newest=newest))
        for am in ABSENCE.finditer(text):
            found.append(dict(kb=kb, concept=rel, shape='absence',
                              line=offset + 1 + text.count('\n', 0,
                                                           am.start()),
                              text=am.group(0), newest=newest))
        for r in found:
            r['digest'] = digest
            if done.get(_key(r)) != digest:
                out.append(r)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    tsv = '--tsv' in sys.argv
    if '--mark-read' in sys.argv:
        state = _read_state()
        rows = [r for kb in (args or discover()) for r in scan(kb, True)]
        for r in rows:
            state[_key(r)] = r['digest']
        json.dump(state, open(READ, 'w', encoding='utf-8'), indent=0,
                  sort_keys=True, ensure_ascii=False)
        print('%d sentence(s) recorded as read' % len(rows))
        return
    rows = [r for kb in (args or discover())
            for r in scan(kb, '--all' in sys.argv)]
    if tsv:
        print('kb\tconcept\tline\tshape\ttext\tnewest_source')
    for r in rows:
        if tsv:
            print('%(kb)s\t%(concept)s\t%(line)d\t%(shape)s\t%(text)s\t'
                  '%(newest)s' % r)
        else:
            print('%(kb)s/%(concept)s:%(line)d  [%(shape)s] %(text)s' % r)
    if not tsv:
        print('%d candidate(s); each needs reading against the concept\'s own '
              'cited pages' % len(rows))


if __name__ == '__main__':
    main()
