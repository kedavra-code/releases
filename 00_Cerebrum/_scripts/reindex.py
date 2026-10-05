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
bundle-root index.md is never rebuilt, because its sections are written by
hand, but the concept lists inside it are kept current; see `requote`.

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

import bundle  # noqa: E402

VAULT = verify.VAULT


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
        # One concept with unparseable frontmatter must not stop the run.
        # An unquoted colon in a `description` raised here on 16.09.2026 and
        # took `verify.py`'s index check down with it, so a single bad file
        # made the whole audit unrunnable for every worker. `verify.py`
        # reports unparseable frontmatter as a defect of its own, which is
        # where that fault belongs; here it is skipped.
        try:
            fm = bundle.mapping(m.group(1))
        except yaml.YAMLError:
            continue
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
    listed = [(i, m.group(1), m.group(3)) for i, m in
              ((i, ENTRY.match(ln)) for i, ln in enumerate(lines)) if m]
    if not listed:
        return None
    first, last, bullet = listed[0][0], listed[-1][0], listed[0][1]

    # The entries whose file still exists, in the order they stand in. The
    # order is tested once and gives one sort key: by title, else by file
    # name, else none, which appends. Until the review of 04.10.2026 the two
    # sorted cases were two branches with the same insert; `requote()` below
    # already chose its key once. 4'000 generated directories gave the same
    # text from both forms that day, and so did every index in the vault.
    order = [fn for _, _, fn in listed if fn in have]
    by_title = lambda f: sortkey(have[f][0])
    key = (by_title if order == sorted(order, key=by_title)
           else (lambda f: f) if order == sorted(order) else None)
    for fn in sorted(have):
        if fn in order:
            continue
        pos = next((j for j, f2 in enumerate(order) if key(f2) > key(fn)),
                   len(order)) if key else len(order)
        order.insert(pos, fn)
    body = [line_for(fn, have[fn][0], have[fn][1], bullet) for fn in order]
    return '\n'.join(lines[:first] + body + lines[last + 1:])


QUOTE = re.compile(r'^(\s*[*-] )\[([^\]]*)\]\(([^)#\s]+)\) - (.*)$')


def requote(text, d, is_root):
    """Keep entries current where they list concepts from another directory.

    `rebuild` compares an index only with the concepts in its own directory,
    and until 14.09.2026 the bundle-root index was skipped outright, on the
    reasoning that it carries navigation rather than a concept list. Three
    bundles' root indexes do list concepts, in the `[title](path) -
    description` form, and nothing kept them current. Zeta_kb's quoted a
    description eleven days out of date (AI-2026-09-13-1); Beta_kb's quoted
    five disproven readings, one a job title its concept had withdrawn, and
    lacked 36 people written since it was last edited.

    So an entry in that form pointing into another directory has its title
    and description refreshed. A root entry pointing at a file beside it,
    `questions.md`, is navigation: its description is refreshed and its link
    text is left to whoever wrote it. And where the root index lists concepts
    from a directory, a concept of that directory it does not link at all is
    added beside the others, in sorted position when they are sorted and
    after the last of them otherwise, as `rebuild` does. Nothing is dropped
    or reordered, and entries in any other form are not touched.
    """
    cache = {}

    def have(home):
        if home not in cache:
            cache[home] = concepts_in(home)
        return cache[home]

    lines = text.split('\n')
    linked = set()
    runs = {}
    for i, ln in enumerate(lines):
        e = ENTRY.match(ln)
        if e:
            linked.add(os.path.normpath(os.path.join(d, e.group(3))))
        m = QUOTE.match(ln)
        if not m:
            continue
        bullet, name, path, quote = m.groups()
        tgt = os.path.normpath(os.path.join(d, path))
        home = os.path.dirname(tgt)
        if (not (is_root or home != d) or not os.path.isfile(tgt)
                or os.path.basename(tgt) in ('index.md', 'log.md')):
            continue
        title, desc = have(home).get(os.path.basename(tgt), ('', ''))
        if home != d and title:
            name = title
        if desc and ' '.join(quote.split()) != desc:
            quote = desc
        if (name, quote) != m.group(2, 4):
            lines[i] = '%s[%s](%s) - %s' % (bullet, name, path, quote)
        if is_root and home != d:
            runs.setdefault(home, []).append((i, bullet, os.path.basename(tgt)))

    before = {}
    for home, run in runs.items():
        known = have(home)
        missing = [fn for fn in known if os.path.join(home, fn) not in linked]
        if not missing:
            continue
        names = [fn for _, _, fn in run]
        by_title = names == sorted(names, key=lambda f: sortkey(known[f][0]))
        key = ((lambda f: sortkey(known[f][0])) if by_title
               else (lambda f: f) if names == sorted(names) else None)
        rel = os.path.relpath(home, d)
        for fn in (sorted(missing, key=key) if key else sorted(missing)):
            at = run[-1][0] + 1
            if key:
                at = next((i for i, _, f in run if key(f) > key(fn)), at)
            before.setdefault(at, []).append(line_for(
                os.path.join(rel, fn), known[fn][0], known[fn][1], run[-1][1]))
    out = []
    for i, ln in enumerate(lines):
        out.extend(before.get(i, []))
        out.append(ln)
    out.extend(before.get(len(lines), []))
    return '\n'.join(out)


def expected(idx):
    """What an existing index.md should read. reindex.py writes it and
    verify.py compares against it, so the two cannot disagree."""
    d = os.path.dirname(idx)
    is_root = os.path.basename(d) == 'Wiki' \
        and os.path.basename(os.path.dirname(d)).endswith('_kb')
    old = open(idx, encoding='utf-8').read()
    new = None if is_root else rebuild(idx)
    return requote(old if new is None else new, d, is_root)


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
    # `verify.discover()` asks for a CLAUDE.md as well as a Wiki/. The list
    # written out here until 04.10.2026 asked for the Wiki/ alone; every
    # folder with one had the other that day, so the six bases are the same.
    kbs = ([a for a in sys.argv[1:] if not a.startswith('--')]
           or verify.discover())
    stale = written = 0
    for kb in kbs:
        root = os.path.join(VAULT, kb, 'Wiki')
        dirs = sorted({os.path.dirname(f) for f in
                       glob.glob(os.path.join(root, '**', '*.md'),
                                 recursive=True)})
        for d in dirs:
            if '_to_delete' in d:
                continue
            idx = os.path.join(d, 'index.md')
            if not os.path.exists(idx):
                if d == root:
                    continue
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
            new = expected(idx)
            if new == open(idx, encoding='utf-8').read():
                continue
            stale += 1
            rel = os.path.relpath(idx, VAULT)
            if check:
                print('stale: %s' % rel)
            else:
                open(idx, 'w', encoding='utf-8').write(new)
                written += 1
                print('rewrote %s (%s)' % (rel, 'bundle root' if d == root
                      else '%d concepts' % len(concepts_in(d))))
    if check:
        print('%d index files stale or missing' % stale)
        sys.exit(1 if stale else 0)
    print('%d index files written' % written)


if __name__ == '__main__':
    main()
