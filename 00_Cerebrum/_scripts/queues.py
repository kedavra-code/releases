#!/usr/bin/env python3
"""Every queue of a knowledge base in one measure, and the guard that keeps a
run working them from looping.

Written 07.11.2026 on the owner's instruction that the compile, the health
check and the action sitting "work all open items until done" and "not get
into a infinite loop". The same day had found every queue standing with
nobody told to empty it: 2'140 unread pairs, 218 Raw files with no fate, 57
drafts, deferred dates passed unseen, 1'163 open-question bullets.

Two kinds of queue, and the difference is the whole design:

  librarian  a run can drain it by itself: read, settle, fix, record.
  waiting    it moves only on the owner's answer or an outside event:
             open and deferred action items. A run never loops on these;
             it hands them to the action sitting or leaves them deferred.

A run is **done** when every librarian queue is zero. It works in passes,
and each pass must make the librarian total strictly smaller, because fixing
a concept re-queues its contradiction pairs and a reading can find a fix:
work that makes work. A pass that does not shrink the total stops the run,
and at most three passes run. What is left after that is raised as action
items, which is a waiting queue, so the next run starts from less.

    python3 _scripts/queues.py [KB ...]                  # the table
    python3 _scripts/queues.py [KB ...] --json           # one object
    python3 _scripts/queues.py [KB ...] --save FILE      # snapshot a pass
    python3 _scripts/queues.py --compare BEFORE AFTER    # the guard

`--compare` exits 0 when the librarian total fell (go on), 2 when it is zero
(done), 1 when it did not fall (stop: report and raise what is left).
It reads only; `verify.py` runs with `--no-clock`.
"""
import collections
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bundle
import actionitems

VAULT = bundle.VAULT
PY = sys.executable

# The verify.py gauges this measure counts, by the words that open each.
GAUGES = [
    ('author_splits', r'(\d+) archive page\(s\) cited with two or more different authors'),
    ('date_splits', r'(\d+) archive page\(s\) are cited with more than one last_modified'),
    ('descriptions_behind', r'(\d+) description\(s\) name a newest year'),
    ('stamps_behind', r'(\d+) source stamp\(s\) name a date older'),
    ('memory_too_long', r'memory\.md is (\d+) lines long'),
    ('body_after_footnotes', r'(\d+) concept\(s\) carry body content after their footnote'),
    ('paths_unresolved', r'(\d+) backticked bundle path\(s\) resolve to nothing'),
]

LIBRARIAN = ['pairs_unread', 'raw_without_fate', 'drafts_unnamed', 'open_question_bullets',
             'held_readings', 'stale_claims', 'changed_pages', 'attachments_pending'] \
    + [g for g, _ in GAUGES]
WAITING = ['items_open', 'items_deferred', 'deferred_passed']


def run(*args):
    return subprocess.run([PY] + [os.path.join(VAULT, '_scripts', args[0])] + list(args[1:]),
                          cwd=VAULT, capture_output=True, text=True).stdout


def first_int(pattern, text):
    m = re.search(pattern, text, re.M)
    return int(m.group(1)) if m else 0


def held_lines(text):
    """Rows of the *Held by …* and *Held from …* sections of questions.md
    that are not marked settled."""
    out = []
    for m in re.finditer(r'^## Held (?:by|from)[^\n]*\n(.*?)(?=^#{1,2} |\Z)', text, re.S | re.M):
        for line in m.group(1).splitlines():
            if re.match(r'^(\| \[|\d+\. )', line) and not re.search(r'Settled|Gap stated|Dissolved|No longer held', line):
                out.append(line)
    return out


def held_rows(text):
    return len(held_lines(text))


def bullets(f):
    """The open bullets of a concept's `# Open questions`, as written,
    without the list mark. questions.md has none."""
    if f.endswith('questions.md'):
        return []
    t = open(f, encoding='utf-8').read()
    q = re.search(r'^# Open questions\n(.*?)(?=^# |\Z)', t, re.S | re.M)
    return [re.sub(r'^\s*[-*] ', '', l).strip() for l in q.group(1).splitlines()
            if re.match(r'^\s*[-*] ', l) and '~~' not in l] if q else []


def measure(kb):
    A = bundle.assertions(kb)
    out = collections.OrderedDict()
    pairs = bundle.script('pairs.py')
    cand = pairs.candidates({f: {p for _, p in bundle.sources(f) if p}
                             for f in bundle.concept_files(kb)}, pairs.threshold(kb))
    out['pairs_unread'] = len(pairs.unread(kb, cand))
    out['raw_without_fate'] = len(bundle.raw_without_fate(kb))
    items = actionitems.items(kb)
    named = ' '.join(i['item'] + ' ' + i['res'] for i in items if i['state'] in ('open', 'deferred'))
    drafts = nbullets = 0
    for f in bundle.concept_files(kb):
        t = open(f, encoding='utf-8').read()
        m = bundle.FM.match(t)
        fm = bundle.mapping(m.group(1)) if m else {}
        rel = os.path.relpath(f, os.path.join(VAULT, kb, 'Wiki'))
        if fm.get('status') == 'draft' and rel not in named:
            drafts += 1
        nbullets += len(bullets(f))
    out['drafts_unnamed'] = drafts
    out['open_question_bullets'] = nbullets
    qpath = os.path.join(VAULT, kb, 'Wiki', 'questions.md')
    out['held_readings'] = held_rows(open(qpath, encoding='utf-8').read()) if os.path.exists(qpath) else 0
    out['stale_claims'] = first_int(r'^(\d+) candidate', run('stale-claims.py', kb))
    out['changed_pages'] = first_int(r': (\d+) concept\(s\) written before', run('changed-pages.py', kb))
    ap = os.path.join(VAULT, kb, '_ATTACHMENT-PASS.md')
    # The register's own count, which `attachment-register.py` writes.
    out['attachments_pending'] = first_int(r'^\| Rows in this register \| (\d+)',
                                           open(ap, encoding='utf-8').read()) if os.path.exists(ap) else 0
    v = run('verify.py', '--no-clock', kb)
    for name, pat in GAUGES:
        n = first_int(pat, v)
        out[name] = max(0, n - 60) if name == 'memory_too_long' and n else n
    out['items_open'] = sum(i['state'] == 'open' for i in items)
    out['items_deferred'] = sum(i['state'] == 'deferred' for i in items)
    out['deferred_passed'] = len(re.findall(r'is deferred until .*?, which has passed', v))
    # A queue too large for one run is raised once as an action item, and the
    # item names it as `queue: <name>`. While that item stands open or
    # deferred, the queue waits on the owner: it leaves the librarian total,
    # or the guard would stop every later run on it and the loop could never
    # report done.
    raised = set()
    for i in items:
        if i['state'] in ('open', 'deferred'):
            for m in re.finditer(r'queue: ([a-z_]+(?:, [a-z_]+)*)', i['item']):
                raised.update(m.group(1).split(', '))
    out['raised_as_item'] = sorted(q for q in raised if q in LIBRARIAN)
    out['librarian_total'] = sum(out[k] for k in LIBRARIAN if k not in raised)
    return out


def snapshot(kbs):
    data = {'at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'bases': {kb: measure(kb) for kb in kbs}}
    data['librarian_total'] = sum(b['librarian_total'] for b in data['bases'].values())
    return data


def compare(before, after):
    b, a = before['librarian_total'], after['librarian_total']
    print('librarian queues: %d before, %d after' % (b, a))
    for kb in after['bases']:
        for k in LIBRARIAN:
            x, y = before['bases'].get(kb, {}).get(k, 0), after['bases'][kb][k]
            if x != y:
                print('  %-12s %-24s %5d -> %d' % (kb, k, x, y))
    if a == 0:
        print('done: every librarian queue is empty')
        return 2
    if a < b:
        print('smaller: another pass may run')
        return 0
    print('not smaller: stop, report, and raise what is left as action items')
    return 1


def table(data):
    kbs = list(data['bases'])
    rows = LIBRARIAN + ['librarian_total'] + WAITING
    print('%-24s' % 'queue' + ''.join('%12s' % k.replace('_kb', '') for k in kbs))
    for r in rows:
        if r == 'items_open':
            print('-- waiting on the owner or an outside event')
        print('%-24s' % r + ''.join('%12d' % data['bases'][k][r] for k in kbs))
    for k in kbs:
        if data['bases'][k]['raised_as_item']:
            print('%s: raised as an action item, outside the total: %s' % (k, ', '.join(data['bases'][k]['raised_as_item'])))


def main(argv):
    if argv[:1] == ['--compare']:
        return compare(json.load(open(argv[1])), json.load(open(argv[2])))
    kbs = [a for a in argv if not a.startswith('--') and a.endswith('_kb')] or bundle.live()
    data = snapshot(kbs)
    if '--save' in argv:
        json.dump(data, open(argv[argv.index('--save') + 1], 'w'), indent=1)
    if '--json' in argv:
        print(json.dumps(data, indent=1))
    else:
        table(data)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
