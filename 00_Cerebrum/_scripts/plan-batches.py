#!/usr/bin/env python3
"""Plan a compile: work out what is unread and cut it into batches.

`_BATCHES.json` and the `_batch-<id>.txt` manifests were made by hand for the
Gamma compile of 15.08.2026, and the hand-made plan carried a hand-made error —
"19 batches remain" was 1'029 pages divided by 55, while the plan actually held
21, because four of them were short tails. The page count was right and the
batch count was wrong, and it survived in two files because nothing recomputed
it. Beta is 2'341 pages and Alpha is 10'561; neither should be planned by hand.

What counts as unread is the same question `coverage.py` answers, asked the
other way round: a page is unread when no concept cites it and the compile
ledger does not record it. This script and `coverage.py` therefore have to
agree, and both parse frontmatter with YAML rather than regex for the reason
documented in `coverage.py`.

Batches are cut inside a scope, never across one. A batch spanning two
notebooks costs the agent the orientation of both and gives it the coherence
of neither, and the scope is what the coverage table reports against.

Usage:  python3 _scripts/plan-batches.py <KB> [--size 55] [--dry-run]
        python3 _scripts/plan-batches.py <KB> --exclude <file-of-paths>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_cov = __import__('importlib').import_module('importlib.util')
_spec = _cov.spec_from_file_location(
    'coverage_mod', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'coverage.py'))
coverage = _cov.module_from_spec(_spec)
_spec.loader.exec_module(coverage)

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SIZE = 55


def scope_id(name, taken):
    """A short, stable, unique batch prefix from a scope's folder name.

    Kept deterministic rather than clever: the ids end up in filenames, in
    the ledger and in CHANGELOG entries, so a plan regenerated next month
    must produce the same ones.

    Uniqueness is not decoration. Beta has eight `Bila XXX` folders, and plain
    initials gave `Bila ABL` and `Bila ABO` the same id — which does not fail,
    it silently overwrites one manifest with the other and loses a hundred
    pages from the plan. Where the last word is an all-caps Kürzel it is kept
    whole, which is both unique and readable; anything still colliding gets
    letters appended until it is not.
    """
    words = [w for w in name.replace('-', ' ').replace('_', ' ').split() if w]
    if len(words) == 1:
        base = words[0][:6].upper()
    elif words[-1].isupper() and len(words[-1]) <= 4:
        base = (''.join(w[0] for w in words[:-1]) + words[-1]).upper()
    else:
        base = ''.join(w[0] for w in words)[:6].upper()
    cand, flat = base, ''.join(c for c in name if c.isalnum()).upper()
    i = len(base)
    while cand in taken:
        i += 1
        cand = (flat[:i] if i <= len(flat) else cand + 'X')
    taken.add(cand)
    return cand


def main():
    kb = sys.argv[1]
    size = int(sys.argv[sys.argv.index('--size') + 1]
               if '--size' in sys.argv else DEFAULT_SIZE)
    dry = '--dry-run' in sys.argv
    root = os.path.join(VAULT, kb)
    ex = os.path.join(root, '_extractions')

    excluded = set()
    if '--exclude' in sys.argv:
        p = sys.argv[sys.argv.index('--exclude') + 1]
        for line in open(p, encoding='utf-8'):
            if line.strip():
                excluded.add(os.path.abspath(os.path.join(root, line.strip())))

    # coverage.cited() returns (paths, n_concepts, n_citations)
    done = coverage.cited(kb)[0] | coverage.ledger(kb)
    plan, manifests, seen_ids, taken = [], {}, {}, set()
    for chapter in coverage.archive_roots(kb):
        # Deepest scope first, chapter root last. The root walks recursively,
        # so visiting it first claims every page in the chapter and collapses
        # thirteen notebooks into one undifferentiated run of batches — which
        # is exactly what the first run of this script did to Beta.
        for scope_dir in ([os.path.join(chapter, d)
                           for d in sorted(os.listdir(chapter))
                           if os.path.isdir(os.path.join(chapter, d))
                           and d != '_assets'] + [chapter]):
            todo = sorted(p for p in coverage.pages(scope_dir)
                          if p not in done and p not in excluded)
            # a page belongs to the deepest scope that holds it, so drop
            # anything a nested scope has already claimed
            todo = [p for p in todo if p not in seen_ids]
            if not todo:
                continue
            for p in todo:
                seen_ids[p] = True
            sid = scope_id(os.path.basename(scope_dir), taken)
            n = 0
            for i in range(0, len(todo), size):
                n += 1
                bid = '%s-%02d' % (sid, n)
                chunk = todo[i:i + size]
                plan.append({'id': bid,
                             'scope': os.path.relpath(scope_dir, root),
                             'n': len(chunk)})
                manifests[bid] = [os.path.relpath(p, root) for p in chunk]

    total = sum(b['n'] for b in plan)
    for b in plan:
        print('  %-10s %3d pages   %s' % (b['id'], b['n'], b['scope']))
    print('%s: %d batches, %d pages unread%s'
          % (kb, len(plan), total,
             ', %d excluded' % len(excluded) if excluded else ''))
    if dry:
        return
    os.makedirs(ex, exist_ok=True)
    json.dump(plan, open(os.path.join(ex, '_BATCHES.json'), 'w',
                         encoding='utf-8'), indent=1)
    for bid, files in manifests.items():
        open(os.path.join(ex, '_batch-%s.txt' % bid), 'w',
             encoding='utf-8').write('\n'.join(files) + '\n')
    print('wrote _BATCHES.json and %d manifests' % len(manifests))


if __name__ == '__main__':
    main()
