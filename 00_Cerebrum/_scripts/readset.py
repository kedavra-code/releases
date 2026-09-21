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
import subprocess
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
    # Newest first, today's entries included. This skipped same-day entries
    # until 08.09.2026, on the reasonable-looking guard that a run must not
    # read its own baseline — but the entry is written at the *end* of a run
    # and this is a planning step, so every entry on disk belongs to an
    # earlier one. The cost showed up the day a second sweep ran hours after
    # the first: the baseline came back as 31.08, nine days stale, and the
    # read set would have been 135 concepts the morning had already covered.
    hits = ENTRY.findall(open(f, encoding='utf-8').read())
    return hits[0] if hits else None


def run_committed_at(kb, day):
    """When the health check of `day` was committed, as a Unix time, or None.

    Day granularity was the fault of Gamma_kb AI-2026-08-31-7: `mt > since`
    on date strings lets nothing modified on the day of the previous health
    check into the read set, so 84 concepts repaired on the evening of
    22.08.2026, after that day's health check, were never read by the next
    one, and a run's own drafts, written on the day of its entry, never
    entered any later read set. The commit that added the run's CHANGELOG
    heading is the moment its work was finished; anything touched after it is
    changed since, whatever the day. Read with --no-optional-locks, so this
    never takes the index lock.
    """
    try:
        out = subprocess.run(
            ['git', '--no-optional-locks', '-C', VAULT, 'log', '--format=%ct',
             '-S', '## %s — Health check' % day, '--',
             '%s/CHANGELOG.md' % kb],
            capture_output=True, text=True, timeout=60).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return int(out[-1]) if out else None


def body_changed_since(kb, rel, since):
    """Did the concept's PROSE change, or only its frontmatter?

    Compares the file on disk with the newest commit made on or before the
    previous health check's date, frontmatter stripped from both. Returns True
    — read it — whenever the question cannot be answered: no git, no such
    commit, an unreadable blob. A read that was not needed costs tokens; a
    concept wrongly dropped from the set costs a missed error, and the rule
    this script exists to enforce says nothing about saving money.
    """
    path = '%s/%s' % (kb, rel.replace(os.sep, '/'))
    try:
        rev = subprocess.run(
            ['git', '--no-optional-locks', '-C', VAULT, 'rev-list', '-1',
             '--before=%s 23:59:59' % since, 'HEAD', '--', path],
            capture_output=True, text=True, timeout=20).stdout.strip()
        if not rev:
            return True
        old = subprocess.run(
            ['git', '--no-optional-locks', '-C', VAULT, 'show',
             '%s:%s' % (rev, path)],
            capture_output=True, text=True, timeout=20)
        if old.returncode != 0:
            return True
        with open(os.path.join(VAULT, path), encoding='utf-8') as fh:
            now = fh.read()
    except (OSError, subprocess.SubprocessError):
        return True
    return _strip_fm(old.stdout) != _strip_fm(now)


def _strip_fm(text):
    """The body, with leading YAML frontmatter removed and space normalised."""
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) == 3:
            text = parts[2]
    return re.sub(r'\s+', ' ', text).strip()


def changed_since(mtime, since, committed):
    """Whether a file modified at `mtime` changed after the previous run."""
    if committed is not None:
        return mtime > committed
    return datetime.date.fromtimestamp(mtime).isoformat() > since


def main():
    kb = sys.argv[1]
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 15
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv \
        else previous_run(kb)
    root = os.path.join(VAULT, kb)
    committed = (run_committed_at(kb, since)
                 if since and '--since' not in sys.argv else None)

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
        mtime = os.path.getmtime(p)
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
        elif changed_since(mtime, since, committed):
            if body_changed_since(kb, rel, since):
                reasons[rel].append('changed since %s' % since)
            else:
                reasons[rel].append(None)      # frontmatter only; see below
    # A frontmatter-only change is not a reason to re-read a concept. The
    # cheapest edit in the vault used to produce the most expensive possible
    # read set: the dating pass of 20.09.2026 rewrote `last_modified` on 4'735
    # citations without touching one sentence of prose, and the health check
    # that followed had to read all six bundles end to end on the strength of
    # it. Nothing in the read rule's three arms is about frontmatter — the
    # changed-since arm exists because new work is where fresh error lives,
    # and a scripted key rewrite is neither new work nor prose. The value the
    # key holds is still checked, unconditionally, by `verify.py`, which never
    # samples. (`Beta_kb` AI-2026-09-20-2.)
    for rel in list(reasons):
        reasons[rel] = [r for r in reasons[rel] if r is not None]
        if not reasons[rel]:
            del reasons[rel]
    for rel, n in inbound.most_common(top):
        reasons[rel].append('top %d by inbound links (%d)' % (top, n))

    size = sum(len(b) for b in bodies.values())
    print('%s: %d concepts, %.1f MB of body text' % (kb, len(concepts), size / 1e6))
    print('previous health check: %s%s' % (
        since or 'none found',
        ', committed %s' % datetime.datetime.fromtimestamp(committed)
        .strftime('%H:%M') if committed else ''))
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
