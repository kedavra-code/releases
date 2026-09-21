#!/usr/bin/env python3
"""Keeps Date tables in date order: the check, the sort, and the merge hook.

A table whose first column is headed Date is chronological by its declared
shape, and 238 of them were not on 15.09.2026, with 527 backward jumps across
Alpha_kb, Beta_kb, Gamma_kb and Epsilon_kb. The career timeline ran to 2026 and
then restarted at 2022. The cause was the same everywhere: a compile appends
new rows at the bottom of the table they belong to, so each wave leaves an
ordered run behind the last one. Three hand measurements of the class, on
31.08., 08.09. and 14.09.2026, disagreed with each other because each defined
"a dated table" differently. This file is the definition, and it has three
users that must agree: `verify.py` reports a table out of order, the command
line below sorts one, and `merge-appends.py` sorts the table it appends to.
Owner's decision of 15.09.2026 (Alpha_kb and Beta_kb AI-2026-08-31-2).

What counts:
  - the header's first cell is `Date` (any case, emphasis ignored);
  - a row's date is read from the start of its first cell: `YYYY-MM-DD`,
    `YYYY-MM`, `YYYY`, `DD.MM.YYYY`, `MM.YYYY`, each optionally after `ca.`
    or `~`; a range is dated by its start;
  - a row whose first cell carries no date belongs to the dated row above it
    and moves with it.

Two dates are compared only as precisely as both are written, so `2017` and
`2017-03` are not out of order either way round. The sort is stable, so rows
of the same date keep the order a writer gave them, and a year-only row sorts
before the dated rows of that year.

A lone row out of place — one dip or spike in an otherwise ascending run —
may be a wrong date rather than a late append, and moving it would hide that.
The command line checks such a row against the page its footnote cites: the
row moves only when that page carries the row's date, and otherwise stays and
is listed. Beta_kb counted 34 single stray rows on 08.09.2026, which is why.

Usage:  python3 _scripts/tableorder.py <KB> [more KBs...] [--dry-run]
"""
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FENCE_LINE = re.compile(r'^\s*```')
SEP = re.compile(r'^\s*\|[\s:|-]+\|\s*$')
DATE_CELL = re.compile(
    r'^(?:ca\.\s*|~\s*)?(?:(\d{4})(?:-(\d\d)(?:-(\d\d))?)?(?!\d)'
    r'|(\d{1,2})\.(\d{1,2})\.(\d{4})|(\d{1,2})\.(\d{4}))')


def cells(row):
    return [c.strip() for c in row.strip().strip('|').replace('\\|', '\x00')
            .split('|')]


def date_key(cell):
    """(year, month, day) with 0 for what the cell does not state, or None."""
    c = re.sub(r'[*_`]', '', cell).strip()
    m = DATE_CELL.match(c)
    if not m:
        return None
    g = m.groups()
    if g[0]:
        return (int(g[0]), int(g[1] or 0), int(g[2] or 0))
    if g[3]:
        return (int(g[5]), int(g[4]), int(g[3]))
    return (int(g[7]), int(g[6]), 0)


def before(a, b):
    """True when a is earlier than b at the precision both carry."""
    n = 1 + (a[1] > 0 and b[1] > 0) + (a[1] > 0 and b[1] > 0
                                      and a[2] > 0 and b[2] > 0)
    return a[:n] < b[:n]


def date_tables(lines):
    """Yield (header_index, first_row_index, end_index) for each Date table."""
    i, infence = 0, False
    while i < len(lines):
        if FENCE_LINE.match(lines[i]):
            infence = not infence
        if (not infence and lines[i].lstrip().startswith('|')
                and i + 1 < len(lines) and SEP.match(lines[i + 1])
                and (i == 0 or not lines[i - 1].lstrip().startswith('|'))):
            head = re.sub(r'[*_`]', '', cells(lines[i])[0]).strip().lower()
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith('|'):
                j += 1
            if head == 'date':
                yield i, i + 2, j
            i = j
            continue
        i += 1


def units(rows):
    """Group rows into (key, [rows]); an undated row joins the unit above."""
    out = []
    for r in rows:
        k = date_key(cells(r)[0])
        if k is None and out:
            out[-1][1].append(r)
        else:
            out.append([k, [r]])
    return out


def jumps(rows):
    """Number of dated rows earlier than the dated row before them."""
    n, prev = 0, None
    for k, _ in units(rows):
        if k is None:
            continue
        if prev is not None and before(k, prev):
            n += 1
        prev = k
    return n


def sort_rows(rows, keep=()):
    """Stable date sort. Units whose index is in `keep` stay where they are."""
    us = units(rows)
    movable = [(i, u) for i, u in enumerate(us) if i not in keep
               and u[0] is not None]
    order = sorted(movable, key=lambda iu: (iu[1][0], iu[0]))
    slots = [i for i, _ in movable]
    placed = dict(zip(slots, [u for _, u in order]))
    out = []
    for i, u in enumerate(us):
        out.extend(placed.get(i, u)[1])
    return out


def lone_strays(rows):
    """Indexes of units that are a single dip or spike in an ascending run."""
    us = [u for u in units(rows)]
    ks = [u[0] for u in us]
    out = []
    for i in range(1, len(ks) - 1):
        a, b, c = ks[i - 1], ks[i], ks[i + 1]
        if None in (a, b, c):
            continue
        if before(b, a) and not before(c, a):
            out.append(i)
        elif before(c, b) and not before(c, a):
            out.append(i)
    return out


def out_of_order(body):
    """Count of Date tables in a concept body carrying a backward jump."""
    lines = body.split('\n')
    return sum(1 for h, s, e in date_tables(lines) if jumps(lines[s:e]))


def _page_carries(concept, row, date):
    """Whether a page cited in this row states the row's date."""
    labels = re.findall(r'\[\^([^\]]+)\]', row)
    if not labels:
        return False
    fm = re.match(r'^---\n(.*?)\n---\n', open(concept, encoding='utf-8')
                  .read(), re.S)
    if not fm:
        return False
    y, m, d = date
    forms = {str(y)} if not m else set()
    if m and not d:
        forms |= {'%d-%02d' % (y, m), '%02d.%d' % (m, y), '%d%02d' % (y, m)}
    if m and d:
        forms |= {'%d-%02d-%02d' % (y, m, d), '%02d.%02d.%d' % (d, m, y),
                  '%d%02d%02d' % (y, m, d), '%d.%d.%d' % (d, m, y),
                  '%02d.%02d.%02d' % (d, m, y % 100)}
    for lab in labels:
        rm = re.search(r'- id:\s*%s\s*\n\s*resource:\s*[\'"]?([^\'"\n]+)'
                       % re.escape(lab), fm.group(1))
        if not rm:
            continue
        tgt = os.path.normpath(os.path.join(os.path.dirname(concept),
                                            rm.group(1).strip()))
        hay = tgt
        if os.path.isfile(tgt) and tgt.endswith(('.md', '.txt', '.html')):
            hay += open(tgt, encoding='utf-8', errors='replace').read()
        if any(f in hay for f in forms):
            return True
    return False


def fix_file(path, dry=False):
    text = open(path, encoding='utf-8').read()
    m = re.match(r'^---\n.*?\n---\n', text, re.S)
    head, body = (text[:m.end()], text[m.end():]) if m else ('', text)
    lines = body.split('\n')
    moved, held = 0, []
    for h, s, e in list(date_tables(lines)):
        rows = lines[s:e]
        if not jumps(rows):
            continue
        us = units(rows)
        keep = set()
        for i in lone_strays(rows):
            if not _page_carries(path, ' '.join(us[i][1]), us[i][0]):
                keep.add(i)
                held.append(us[i][1][0][:140])
        new = sort_rows(rows, keep)
        assert sorted(new) == sorted(rows), path
        if new != rows:
            lines[s:e] = new
            moved += 1
    if moved and not dry:
        open(path, 'w', encoding='utf-8').write(head + '\n'.join(lines))
    return moved, held


def main():
    dry = '--dry-run' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')]
    tables = files = 0
    for kb in kbs:
        for f in sorted(glob.glob(os.path.join(VAULT, kb, 'Wiki', '**', '*.md'),
                                  recursive=True)):
            if '_to_delete' in f or os.path.basename(f) in ('index.md',
                                                            'log.md'):
                continue
            n, held = fix_file(f, dry)
            if n:
                files += 1
                tables += n
                print('%s %s: %d table(s)' % ('would sort' if dry else 'sorted',
                                              os.path.relpath(f, VAULT), n))
            for h in held:
                print('  HELD, its cited page does not carry the date: ' + h)
    print('%d table(s) in %d concept(s)%s' % (tables, files,
                                              ' (dry run)' if dry else ''))


if __name__ == '__main__':
    main()
