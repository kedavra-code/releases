#!/usr/bin/env python3
"""Repairs the table boundaries a merge left unrenderable.

The sibling of fix-runons.py, one block level up. That script separates two
paragraphs a merge glued together, and it deliberately "leaves tables, lists,
headings, block quotes and footnote definitions alone on both sides" so that
its rule matches verify.py's exactly. The exemption is right for what it
guards, and it left the table-boundary variant with no repair at all: 330
sites in Alpha_kb alone after the rebuild of 22.08.2026.

Three shapes, all produced by merge-appends.py joining an appended chunk to
the section above it with a single newline.

  1. A table header glued to the paragraph above it. GFM absorbs the whole
     table into that paragraph and the reader sees literal pipes. Fixed with
     a blank line.

  2. An appended row sitting below prose, continuing a table further up. It
     has no header of its own, so it renders as literal pipes too. Fixed by
     hoisting the whole run of rows back into the table it continues, which
     leaves the prose below the table instead of inside it. Guarded: never
     across a heading, and only when the column count matches.

  3. A header row an append carried into a table that already had one. It
     renders as two spurious rows mid-table. Dropped when it is exactly equal
     to that table's own header; otherwise separated with a blank line,
     because a "| Section | ... |" table followed by a "| Date | Event |"
     table is two tables that happen to be the same width, and merging them
     would be worse than the defect.

All three are rendering faults rather than truth faults — every claim and
every citation survives untouched — which is why they accumulate: nothing is
wrong when you read the markdown, and the page is wrong when you look at it.

Deliberately narrow everywhere else. It touches a boundary only when the
prose side is an ordinary paragraph line: not a list item, block quote,
heading, footnote definition, indented line or fenced block. Rows it cannot
place are counted and left; there were 15 in Alpha_kb, each needing a look at
which table the row belongs to. So is a row under a list item, an indented
line or a footnote definition, and a table that opens on a data row: a blank
line there makes a table with no header. A second run can find more:
dropping a repeated header can open a hoist the first pass could not make,
so run it until it reports nothing. Where a site is
comes from `blanklines.py`, which `verify.py` counts by too, so a finding
names this script only for what it mends.

Run it after every merge, beside fix-depth.py.

Usage:  python3 _scripts/fix-tablebreaks.py <KB> [more KBs...] [--dry-run]
"""
import sys

import blanklines
from bundle import discover
from tableorder import SEP


def rejoin(lines):
    """Hoist an appended table row back into the table it continues.

    merge-appends.py appends a row after a paragraph that was itself
    appended, so the row sits below prose and renders as literal pipes. The
    row belongs to the table above it. Moving it there restores the table
    and moves nothing else; the prose stays where it is, now below the whole
    table instead of inside it.

    Guarded three ways. It never crosses a heading, because a row under a
    different heading is a different table. It requires the same column
    count, because two tables in one section with different shapes are two
    tables. And it moves the whole contiguous run of orphan rows, not the
    first one.
    """
    out, ls = list(lines), blanklines.unfenced(lines)
    moved = 0
    held = 0
    i = 0
    while i < len(ls):
        what = blanklines.table_break(ls, i)
        if what in (None, 'blank'):     # a real table start is spaced below
            i += 1
            continue
        end = i
        while end + 1 < len(ls) and ls[end + 1].startswith('|'):
            end += 1
        if what == 'hoist':
            j = blanklines.home(ls, i)
            # no moved line is fenced, so both lists take the same move
            for x in (out, ls):
                run = x[i:end + 1]
                del x[i:end + 1]
                x[j + 1:j + 1] = run
            moved += len(run)
        else:
            held += 1
        i = end + 1
    return out, moved, held


def dedupe_headers(lines):
    """Drop a header row an append carried into a table that already had one.

    The third face of the same merge. An APPEND block that begins with its own
    ``| Date | Event |`` header lands directly under the last row of the table
    it extends, and the header plus its delimiter then render as two spurious
    rows in the middle of the table. There were 118 in Alpha_kb.

    The test is exact equality with the header of the table the row sits in,
    not a column count. Two-column tables are common and a ``| Section | ... |``
    table followed by a ``| Date | Event |`` table is two tables that happen to
    have the same shape; merging them would be worse than the defect. So an
    identical header is dropped as the duplicate it is, and any other repeated
    header is separated with a blank line, which makes it a table of its own.
    """
    ls = blanklines.unfenced(lines) + ['']
    out = []
    dropped = 0
    split = 0
    header = None
    i = 0
    while i < len(lines):
        ln = ls[i]
        if not ln.startswith('|'):
            header = None
        elif SEP.match(ls[i + 1]):
            if header is not None and ln.strip() == header.strip():
                dropped += 1                      # the same header again
                i += 2
                continue
            if header is not None:
                out.append('')                    # a different table
                split += 1
            header = ln
        out.append(lines[i])
        i += 1
    return out, dropped, split


def fix(lines):
    lines, moved, held = rejoin(lines)
    lines, dropped, split = dedupe_headers(lines)
    ls = blanklines.unfenced(lines)
    # a table header glued to the paragraph above it, and a paragraph glued
    # to the last row of a table
    at = [i for i in range(len(ls))
          if blanklines.table_break(ls, i) == 'blank']
    at += blanklines.gaps(ls, blanklines.under_table)
    return blanklines.spaced(lines, at), len(at) + split, moved, held, dropped


def main():
    dry = '--dry-run' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')] or discover()
    widths = '--widths' in sys.argv
    for kb in kbs:
        n = files = orphans = rejoined = headers = 0
        for p, head, lines in blanklines.bodies(kb):
            if widths:
                (new, ins), mv, held, drop = blanklines.fold(lines), 0, 0, 0
            else:
                new, ins, mv, held, drop = fix(lines)
            orphans += held
            rejoined += mv
            headers += drop
            if ins or mv or drop:
                n += ins
                files += 1
                if not dry:
                    open(p, 'w', encoding='utf-8').write(head + '\n'.join(new))
        if widths:
            print('%-12s %4d stray footnote column(s) folded back across '
                  '%d concept(s)%s'
                  % (kb, n, files, '  (dry run)' if dry else ''))
            continue
        print('%-12s %4d blank line(s) inserted, %d orphan row(s) rejoined, '
              '%d repeated header(s) dropped, across %d concept(s)%s; '
              '%d row(s) held, not repaired'
              % (kb, n, rejoined, headers, files,
                 '  (dry run)' if dry else '', orphans))


if __name__ == '__main__':
    main()
