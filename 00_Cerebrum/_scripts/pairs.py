#!/usr/bin/env python3
"""The contradiction reading queue: which candidate pairs nobody has read
since either side changed.

Two concepts can only contradict each other about something both describe,
and shared sources are the cheap proxy for that: a pair sharing three pages or
more is a candidate, at the `contradiction_threshold` of its base. Whether the
two disagree is a reading, and a health check reads a slice.

Until 05.10.2026 the read state was kept by hand, as a table in each base's
`Wiki/questions.md`, and `verify.py` counted every candidate, read or not. So
the gauge could only rise, 611 to 1'585 in `Alpha_kb` in a month, and each run
worked out by hand which pairs a change had put back: "eight pairs re-queued
because the re-shelve of 01.09.2026 changed one or both concepts". Two of the
five tables hold counts and no pairs, so nothing could check them.

A reading is recorded here as `stale-claims.py` records one: `--mark-read`
stores the pair with a hash of both concept bodies in
`_scripts/pairs-read.json`, and the pair is unread again when either body
changes. A change is exactly when two concepts can have come to disagree. The
verdict of a reading stays in the queue in `questions.md`; this file holds
only that it was read, and of what.

The ledger was seeded on 05.10.2026 from the three tables that name their
pairs, `Alpha_kb`, `Gamma_kb` and `Beta_kb`: a row is carried where both concept
bodies are the same today as in the commit that recorded the row. That held
for 8 of 163 rows; 150 name a concept changed since its reading. `Epsilon_kb`
and `Delta_kb` recorded counts, so their pairs start unread.

Usage:  python3 _scripts/pairs.py [KB ...] [--all] [--tsv]
        python3 _scripts/pairs.py KB --mark-read A B [A B ...]

A and B are concept paths as the list prints them, relative to `Wiki/`.
"""
import functools
import hashlib
import itertools
import json
import os
import sys

import bundle
from bundle import VAULT, FM, assertions, concept_files, discover

READ = os.path.join(VAULT, '_scripts', 'pairs-read.json')


def threshold(kb):
    """Shared pages that make a pair a candidate: three, or the base's own."""
    return int(assertions(kb).get('contradiction_threshold') or 3)


def cited(kb):
    """Each concept of a base with the set of pages it cites."""
    return {f: {p for _, p in bundle.sources(f) if p}
            for f in concept_files(kb)}


def candidates(resources, thr):
    """(overlap, a, b) for every two concepts sharing `thr` pages or more.
    `verify.py` hands in the sets it built while resolving citations."""
    return [(len(resources[a] & resources[b]), a, b)
            for a, b in itertools.combinations(sorted(resources), 2)
            if len(resources[a] & resources[b]) >= thr]


@functools.lru_cache(maxsize=None)
def _body(f):
    raw = open(f, encoding='utf-8').read()
    m = FM.match(raw)
    return hashlib.sha1(raw[m.end() if m else 0:].encode('utf-8')).hexdigest()


def digest(a, b):
    """What a reading of the pair read: both bodies, frontmatter left out, so
    a restamp alone does not put a pair back."""
    return _body(a) + ':' + _body(b)


def name(kb, f):
    return os.path.relpath(f, os.path.join(VAULT, kb, 'Wiki')).replace(os.sep, '/')


def key(kb, a, b):
    return '%s|%s|%s' % (kb, name(kb, a), name(kb, b))


def read_state():
    try:
        return json.load(open(READ, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def unread(kb, pairs, done=None):
    """The pairs no reading holds as they stand today."""
    done = read_state() if done is None else done
    return [p for p in pairs if done.get(key(kb, p[1], p[2])) != digest(p[1], p[2])]


def mark(kb, wanted, pairs, done):
    """Record a reading of each (A, B) in `wanted`, in either order. Returns
    the names that are no candidate pair today, and records none of those: a
    mistyped path must not read as a reading."""
    by_name = {frozenset((name(kb, a), name(kb, b))): (a, b) for _, a, b in pairs}
    missing = []
    for x, y in wanted:
        hit = by_name.get(frozenset((x, y)))
        if hit:
            done[key(kb, *hit)] = digest(*hit)
        else:
            missing.append((x, y))
    return missing


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--mark-read' in sys.argv:
        if len(args) < 3 or len(args) % 2 == 0:
            sys.exit('usage: pairs.py KB --mark-read A B [A B ...]')
        kb, names = args[0], [n[5:] if n.startswith('Wiki/') else n for n in args[1:]]
        done = read_state()
        missing = mark(kb, list(zip(names[::2], names[1::2])),
                       candidates(cited(kb), threshold(kb)), done)
        if missing:
            sys.exit('no candidate pair today, nothing recorded:\n'
                     + '\n'.join('  %s <-> %s' % m for m in missing))
        json.dump(done, open(READ, 'w', encoding='utf-8'), indent=0,
                  sort_keys=True, ensure_ascii=False)
        print('%d pair(s) recorded as read' % (len(names) // 2))
        return
    tsv = '--tsv' in sys.argv
    if tsv:
        print('kb\toverlap\ta\tb\tstate')
    for kb in args or discover():
        pairs = sorted(candidates(cited(kb), threshold(kb)),
                       key=lambda p: (-p[0], p[1], p[2]))
        open_ = set(map(tuple, unread(kb, pairs)))
        for p in pairs:
            if p not in open_ and '--all' not in sys.argv:
                continue
            state = 'unread' if p in open_ else 'read'
            if tsv:
                print('%s\t%d\t%s\t%s\t%s' % (kb, p[0], name(kb, p[1]),
                                              name(kb, p[2]), state))
            else:
                print('%s  %3d  %s <-> %s%s' % (kb, p[0], name(kb, p[1]),
                                                name(kb, p[2]),
                                                '' if p in open_ else '  [read]'))
        if not tsv:
            print('%s: %d candidate pair(s) at %d+ shared sources, %d unread'
                  % (kb, len(pairs), threshold(kb), len(open_)))


if __name__ == '__main__':
    main()
