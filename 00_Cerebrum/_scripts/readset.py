#!/usr/bin/env python3
"""Derives the set of concepts a health check must read in full.

The read rule, settled 15.08.2026 as AI-2026-08-15-7. Until then the skill
said one run type and every run reads every concept, with the trigger for
revisiting it stated as "roughly 500 concepts". The real trigger is size, and
Gamma_kb hit it at 219 concepts and 2.5 MB of body text because the compile
writes long concepts. The runs were already truncating; the only thing making
it visible was a CHANGELOG line naming what had been read, which is the
honest version of the wrong thing.

So the full read is redefined rather than abandoned:

    every concept is machine-scanned, unconditionally     (verify.py)
    a concept is read in full when it is
      * changed since the previous health check, or
      * among the N most-linked in the bundle, or
      * in a contradiction cluster this run reads

The first arm catches new work, the second catches the concepts where a wrong
claim propagates furthest, and the third is the sweep the skill already
requires. What it deliberately does not do is sample at random, which is the
practice removed on 09.08.2026 for having no principled basis.

This script exists so the read set is derived rather than chosen to fit. A
run that picks its own scope will always pick the scope it had budget for.

Usage:  python3 _scripts/readset.py <KnowledgeBase> [--top N] [--since DATE]
Prints the read set with the reason each concept is in it, then the arithmetic
the CHANGELOG entry has to carry.
"""
import collections
import datetime
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify  # noqa: E402

VAULT = verify.VAULT
LINK = re.compile(r'\]\((?!http)([^)]+\.md)\)')
ENTRY = re.compile(r'^## (\d{4}-\d{2}-\d{2}) — Health check', re.M)


def previous_run(kb):
    """The date of the last health check, from the CHANGELOG itself."""
    f = os.path.join(VAULT, kb, 'CHANGELOG.md')
    if not os.path.exists(f):
        return None
    hits = ENTRY.findall(open(f, encoding='utf-8').read())
    today = datetime.date.today().isoformat()
    for d in hits:
        if d < today:
            return d
    return hits[-1] if hits else None


def main():
    kb = sys.argv[1]
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 15
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv \
        else previous_run(kb)
    root = os.path.join(VAULT, kb)

    concepts, bodies = [], {}
    for p in sorted(glob.glob(os.path.join(root, 'Wiki', '**', '*.md'),
                              recursive=True)):
        if os.path.basename(p) in ('index.md', 'log.md') or '_to_delete' in p:
            continue
        rel = os.path.relpath(p, root).replace(os.sep, '/')
        concepts.append(rel)
        t = verify.FENCE.sub('', open(p, encoding='utf-8').read())
        m = verify.FM.match(t)
        bodies[rel] = t[m.end():] if m else t

    inbound = collections.Counter()
    for rel, body in bodies.items():
        if os.path.basename(rel) == 'index.md':
            continue
        for tgt in LINK.findall(body):
            q = os.path.normpath(os.path.join(os.path.dirname(rel), tgt))
            q = q.replace(os.sep, '/')
            if q in bodies and q != rel:
                inbound[q] += 1

    # Strictly after, not on-or-after. A health check edits the concepts it
    # repairs, and with `>=` every one of those re-entered the next run's read
    # set on the strength of the run's own edit — so a run that fixed 60
    # concepts handed its successor 60 concepts to read for no reason. Found
    # 22.08.2026, when the set came back as the whole bundle in two knowledge
    # bases at once and one of them had not been compiled at all.
    reasons = collections.defaultdict(list)
    for rel in concepts:
        p = os.path.join(root, rel)
        mt = datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
        if since is None:
            # No previous health check in the CHANGELOG. Until 31.08.2026 the
            # test read `if since and mt > since`, so this arm contributed
            # nothing at all and the read set collapsed to the top-N-by-inbound
            # arm — 15 concepts of 100 on Epsilon_kb's first run, taken the day
            # after the bundle was compiled from nothing. That inverts the rule
            # in the one case it names outright: on the run after a compile the
            # read set is the whole bundle, because everything changed, and it
            # is to be budgeted for rather than trimmed. This script exists so a
            # run cannot choose its own scope; silently choosing the smallest
            # possible one on its behalf is worse than letting it choose, because
            # the answer still looks derived.
            reasons[rel].append('no previous health check — first run reads '
                                'the whole bundle')
        elif mt > since:
            reasons[rel].append('changed since %s' % since)
    for rel, n in inbound.most_common(top):
        reasons[rel].append('top %d by inbound links (%d)' % (top, n))

    size = sum(len(b) for b in bodies.values())
    print('%s: %d concepts, %.1f MB of body text' % (kb, len(concepts), size / 1e6))
    print('previous health check: %s' % (since or 'none found'))
    print('\nread in full (%d of %d):' % (len(reasons), len(concepts)))
    for rel in sorted(reasons, key=lambda r: (-inbound[r], r)):
        print('  %-58s %s' % (rel, '; '.join(reasons[rel])))
    print('\nCHANGELOG arithmetic:')
    print('  machine-scanned: %d of %d' % (len(concepts), len(concepts)))
    print('  read in full: %d, chosen by the read rule, not by budget' % len(reasons))
    print('  not read in full: %d' % (len(concepts) - len(reasons)))
    print('  plus the concepts in the contradiction clusters this run reads')


if __name__ == '__main__':
    main()
