#!/usr/bin/env python3
"""Packs the unread contradiction pairs for reading on their shared pages.

A pair is two concepts of one base that cite three or more of the same pages
(`pairs.py`). Two concepts can only contradict each other about what both
describe, so a reader compares them where they meet: for each page both
cite, the sentences of each that cite it, side by side. This script writes
those packs; a reader compares each, opens the page wherever the two
disagree, and `pairs.py --mark-read` records the pair once its fixes are in.

Written 07.11.2026, when 2'204 unread pairs were read this way by 24
readers. Whole paragraphs made 22 MB of packs; the sentence that carries the
footnote, cut at 280 characters, made 8 MB. A reader takes about 250 KB.

    python3 _scripts/pair-packs.py <KB> [more] --out DIR [--size 250000] [--changed-since REV]

`--changed-since REV` packs, of each unread pair, only the shared pages where
the citing sentences of either concept differ from the concept at REV, and
records the rest as read with `pairs.py --mark-read`: the second pass of a
loop reads what the first pass changed, not what it already read. A pair
with no changed page is recorded read at once. Written 07.11.2026, when the
open-question sort changed 270 concepts after every pair had been read that
morning.

Writes DIR/pack-01.txt … and DIR/pairs.json (the pairs, in pack order), and
prints one line per pack. It changes nothing in the vault, save that
`--changed-since` records the pairs it found unchanged as read.
"""
import collections
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bundle

FN = re.compile(r'\[\^([^\]]+)\]')
SENT = re.compile(r'(?<=[.!?\]])\s+(?=[A-Z*"(\[])')


def claims(path, text=None):
    """For each page a concept cites, the sentences or table rows citing it.
    `text` reads an earlier version of the concept in place of the file."""
    t = text if text is not None else open(path, encoding='utf-8').read()
    m = bundle.FM.match(t)
    body = t[m.end():] if m else t
    d = os.path.dirname(path)
    pages = {s['id']: bundle.canon(os.path.join(d, str(s['resource'])))
             for s in bundle.entries(m.group(1) if m else '') if s.get('id') and s.get('resource')}
    out = collections.defaultdict(list)
    for line in body.split('\n'):
        if not line.strip() or line.lstrip().startswith('[^'):
            continue
        for s in ([line] if line.startswith('|') else SENT.split(line)):
            for i in set(FN.findall(s)):
                if i in pages:
                    out[pages[i]].append(re.sub(r'\[\^[^\]]+\]', '', s).strip()[:280])
    return out


def at(rev, path):
    """The concept as it stood at `rev`, or None where it did not exist."""
    r = subprocess.run(['git', '-C', bundle.VAULT, 'show', '%s:%s' % (rev, os.path.relpath(path, bundle.VAULT))],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def packs(kb, since=None, done=None):
    rows = [l.split('\t') for l in subprocess.run(
        [sys.executable, os.path.join(bundle.VAULT, '_scripts', 'pairs.py'), kb, '--tsv'],
        capture_output=True, text=True).stdout.splitlines()[1:]]
    wiki = os.path.join(bundle.VAULT, kb, 'Wiki')
    seen = {}
    for r in rows:
        if r[4].strip() != 'unread':
            continue
        a, b = (seen.setdefault(x, claims(os.path.join(wiki, x))) for x in (r[2], r[3]))
        shared = sorted(set(a) & set(b))
        if since:
            olds = []
            for x in (r[2], r[3]):
                key = ('old', x)
                if key not in seen:
                    old = at(since, os.path.join(wiki, x))
                    seen[key] = claims(os.path.join(wiki, x), old) if old is not None else {}
                olds.append(seen[key])
            shared = [p for p in shared if a[p] != olds[0].get(p, []) or b[p] != olds[1].get(p, [])]
            if not shared:
                done.append([kb, r[2], r[3]])
                continue
        text = ['=== PAIR %s | %s <-> %s' % (kb, r[2], r[3])]
        for page in shared:
            text.append('-- ' + os.path.relpath(page, bundle.VAULT))
            text += ['A: ' + x for x in list(dict.fromkeys(a[page]))[:3]]
            text += ['B: ' + x for x in list(dict.fromkeys(b[page]))[:3]]
        yield [kb, r[2], r[3]], '\n'.join(text)


def main(argv):
    kbs = [a for a in argv if a.endswith('_kb')]
    out = argv[argv.index('--out') + 1]
    size = int(argv[argv.index('--size') + 1]) if '--size' in argv else 250000
    os.makedirs(out, exist_ok=True)
    since = argv[argv.index('--changed-since') + 1] if '--changed-since' in argv else None
    order, cur, n, k, done = [], [], 0, 1, []
    for kb in kbs:
        for pair, text in packs(kb, since, done):
            order.append(pair)
            cur.append(text)
            n += len(text)
            if n >= size:
                open(os.path.join(out, 'pack-%02d.txt' % k), 'w').write('\n\n'.join(cur))
                print('pack-%02d.txt  %d pairs  %d bytes' % (k, len(cur), n))
                cur, n, k = [], 0, k + 1
    if cur:
        open(os.path.join(out, 'pack-%02d.txt' % k), 'w').write('\n\n'.join(cur))
        print('pack-%02d.txt  %d pairs  %d bytes' % (k, len(cur), n))
    json.dump(order, open(os.path.join(out, 'pairs.json'), 'w'))
    print('%d unread pair(s) packed' % len(order))
    if done:
        by = {}
        for kb, x, y in done:
            by.setdefault(kb, []).extend([x, y])
        for kb, args in by.items():
            for i in range(0, len(args), 400):
                subprocess.run([sys.executable, os.path.join(bundle.VAULT, '_scripts', 'pairs.py'),
                                kb, '--mark-read'] + args[i:i + 400], capture_output=True)
        print('%d pair(s) with no changed shared page recorded read' % len(done))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
