#!/usr/bin/env python3
"""Regenerates every directory index.md from the concepts' own frontmatter.

Written 15.08.2026. The stale-index class had been *detected* since the
beginning — verify.py reports "not listed in its directory index" — but the
repair was manual every time, and a manual repair is one that gets skipped.
The compile of 15.08.2026 left 116 stale entries in Gamma_kb and 149 in
Beta_kb, and the cause is structural rather than careless: **a compile agent
may not touch index.md**, so a compile always leaves the indexes stale by
exactly the number of concepts it added. Telling a health check to remember
is not a fix; the vault's own rule is that a defect class is not fixed until
something executable handles its recurrence.

So the constraint stays — agents still never write an index — and this script
does it afterwards, from the concepts themselves. Run it at the end of every
compile wave and every health check.

**It never reorders an index.** That was the first design and it was wrong.
Three different orders are in use and each is deliberate: `people/` is
alphabetical, `decisions/` is filename order which is chronological because
the filenames carry dates, and `Zeta_kb/Wiki/ai/system-cards/` is a
curated reading order that follows the argument rather than the alphabet.
A generator that sorts would have rewritten 25 lines of one index and 6 of
another and called it a repair, burying the two real staleness cases in a
diff nobody could skim.

So the order belongs to whoever wrote it. This script only ever:

    refreshes the description of an entry that is already listed
    adds an entry for a concept that is missing
    drops an entry whose file no longer exists

A new entry is inserted in sorted position when the list is detectably sorted
by title or by filename, and appended otherwise, because appending to a
curated order is the one thing that cannot be wrong.

Everything above the first list item — heading, prose, any Navigation block —
is hand-written, not derived, and is copied through untouched. The
bundle-root index.md is left alone entirely: it carries `okf_version` and a
navigation section rather than a concept list.

Usage:  python3 _scripts/reindex.py [KnowledgeBase ...]   (default: all)
        python3 _scripts/reindex.py --check               (exit 1 if stale)
"""
import glob
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify  # noqa: E402

try:
    import yaml
except ImportError:
    sys.exit('reindex.py needs PyYAML')

VAULT = verify.VAULT
BULLET = re.compile(r'^\s*[*-] \[', re.M)


def sortkey(text):
    """Diacritic-insensitive, so André files with Andreas rather than after it.

    The hand-maintained indexes collate this way and a naive `.lower()` moved
    two entries in Gamma_kb/Wiki/people/index.md on 15.08.2026.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


ENTRY = re.compile(r'^(\s*[*-] )\[([^\]]*)\]\(([^)]+)\)(.*)$')


def concepts_in(d):
    """{filename: (title, description)} for every concept in one directory."""
    out = {}
    for f in sorted(glob.glob(os.path.join(d, '*.md'))):
        if os.path.basename(f) in ('index.md', 'log.md'):
            continue
        t = verify.FENCE.sub('', open(f, encoding='utf-8').read())
        m = verify.FM.match(t)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        out[os.path.basename(f)] = (
            str(fm.get('title') or os.path.basename(f)[:-3]).strip(),
            ' '.join(str(fm.get('description') or '').split()))
    return out


def line_for(fn, title, desc, bullet='* '):
    return '%s[%s](%s)%s' % (bullet, title, fn, ' - ' + desc if desc else '')


def rebuild(idx):
    """New text for one index.md, or None if it carries no concept list."""
    old = open(idx, encoding='utf-8').read()
    have = concepts_in(os.path.dirname(idx))
    if not have:
        return None
    lines = old.split('\n')
    first = last = None
    listed = []
    for i, ln in enumerate(lines):
        m = ENTRY.match(ln)
        if not m:
            continue
        if first is None:
            first = i
        last = i
        listed.append((i, m.group(1), m.group(3)))
    if first is None:
        return None

    bullet = listed[0][1]
    order = [fn for _, _, fn in listed]
    kept = [fn for fn in order if fn in have]
    sorted_by_file = kept == sorted(kept)
    sorted_by_title = kept == sorted(kept, key=lambda f: sortkey(have[f][0]))

    body = [line_for(fn, have[fn][0], have[fn][1], bullet)
            for fn in order if fn in have]
    for fn in sorted(have):
        if fn in order:
            continue
        new = line_for(fn, have[fn][0], have[fn][1], bullet)
        if sorted_by_title:
            k = sortkey(have[fn][0])
            pos = next((j for j, f2 in enumerate([f for f in order if f in have])
                        if sortkey(have[f2][0]) > k), len(body))
            body.insert(pos, new)
            order = [f for f in order if f in have]
            order.insert(pos, fn)
        elif sorted_by_file:
            pos = next((j for j, f2 in enumerate([f for f in order if f in have])
                        if f2 > fn), len(body))
            body.insert(pos, new)
            order = [f for f in order if f in have]
            order.insert(pos, fn)
        else:
            body.append(new)
            order = [f for f in order if f in have] + [fn]
    return '\n'.join(lines[:first] + body + lines[last + 1:])


DIR_TITLE = {
    'decisions': ('Decisions', 'Rulings taken, with what was decided, by whom '
                               'and on what evidence'),
    'meeting-series': ('Meeting Series', 'Recurring meetings, their cadence, '
                                         'participants and running record'),
    'organisation': ('Organisation', 'Units, their mandate, structure and '
                                     'changes over time'),
    'projects': ('Projects', 'Work with a start, a course and an end'),
    'references': ('References', 'Digests of documents that are not themselves '
                                 'concepts'),
    'people': ('People', 'Individuals as the archive records them'),
    'systems': ('Systems', 'Services, platforms and tools'),
    'timelines': ('Timelines', 'Dated chronologies'),
    'vendors': ('Vendors', 'Suppliers and the agreements with them'),
    'digests': ('Digests', 'Condensed source documents'),
}


def create(d):
    """A first index.md for a directory that has none.

    `rebuild` refuses a file with no concept list, which is right for an index
    someone wrote as prose — but it also meant five Alpha_kb directories holding
    182 concepts had no index at all and nothing reported it, because the
    staleness check only ever compares indexes that exist (22.08.2026).

    A new index has no established order to respect, so this sorts by title.
    The order belongs to whoever edits it afterwards; `rebuild` will then
    preserve whatever they chose.
    """
    have = concepts_in(d)
    if not have:
        return None
    name = os.path.basename(d)
    title, desc = DIR_TITLE.get(
        name, (name.replace('-', ' ').title(), 'Concepts in this directory'))
    body = [line_for(fn, have[fn][0], have[fn][1], '* ')
            for fn in sorted(have, key=lambda f: sortkey(have[f][0]))]
    return ('# %s\n\n%s.\n\nGenerated by `_scripts/reindex.py`; order is '
            'editable and will be preserved.\n\n' % (title, desc)
            + '\n'.join(body) + '\n')


def main():
    check = '--check' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')] or sorted(
        d for d in os.listdir(VAULT)
        if os.path.isdir(os.path.join(VAULT, d, 'Wiki')))
    stale = written = 0
    for kb in kbs:
        root = os.path.join(VAULT, kb, 'Wiki')
        dirs = sorted({os.path.dirname(f) for f in
                       glob.glob(os.path.join(root, '**', '*.md'),
                                 recursive=True)})
        for d in dirs:
            if d == root or '_to_delete' in d:
                continue
            idx = os.path.join(d, 'index.md')
            if not os.path.exists(idx):
                made = create(d)
                if made is None:
                    continue
                stale += 1
                rel = os.path.relpath(idx, VAULT)
                if check:
                    print('missing: %s' % rel)
                else:
                    open(idx, 'w', encoding='utf-8').write(made)
                    written += 1
                    print('created %s (%d concepts)'
                          % (rel, len(concepts_in(d))))
                continue
            new = rebuild(idx)
            if new is None or new == open(idx, encoding='utf-8').read():
                continue
            stale += 1
            rel = os.path.relpath(idx, VAULT)
            if check:
                print('stale: %s' % rel)
            else:
                open(idx, 'w', encoding='utf-8').write(new)
                written += 1
                print('rewrote %s (%d concepts)'
                      % (rel, len(concepts_in(os.path.dirname(idx)))))
    if check:
        print('%d index files stale or missing' % stale)
        sys.exit(1 if stale else 0)
    print('%d index files written' % written)


if __name__ == '__main__':
    main()
