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
which table the row belongs to. It is idempotent.

Run it after every merge, beside fix-depth.py.

Usage:  python3 _scripts/fix-tablebreaks.py <KB> [more KBs...] [--dry-run]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify  # noqa: E402

VAULT = verify.VAULT
ROW = re.compile(r'^\|')
DELIM = re.compile(r'^\s*\|[-: |]+\|\s*$')
# A prose line this script is willing to touch. Anything with its own block
# semantics is left alone, because a blank line beside it changes meaning.
SKIP = re.compile(r'^(\s|[-*+>#]|\d+\.\s|\[\^)')


def plain(line):
    return bool(line.strip()) and not ROW.match(line) and not SKIP.match(line)



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
    out = list(lines)
    moved = 0
    held = 0
    i = 1
    fenced = False
    while i < len(out):
        ln = out[i]
        if ln.lstrip().startswith('```'):
            fenced = not fenced
        if fenced or not ROW.match(ln) or not plain(out[i - 1]):
            i += 1
            continue
        nxt = out[i + 1] if i + 1 < len(out) else ''
        if DELIM.match(nxt):        # a real table start, not an orphan row
            i += 1
            continue
        end = i
        while end + 1 < len(out) and ROW.match(out[end + 1]):
            end += 1
        j = i - 1
        while j >= 0 and not ROW.match(out[j]):
            if out[j].startswith('#'):
                j = -1
                break
            j -= 1
        if j < 0 or out[j].count('|') != ln.count('|'):
            held += 1
            i = end + 1
            continue
        run = out[i:end + 1]
        del out[i:end + 1]
        out[j + 1:j + 1] = run
        moved += len(run)
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
    out = []
    dropped = 0
    split = 0
    fenced = False
    header = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.lstrip().startswith('```'):
            fenced = not fenced
        if fenced or not ROW.match(ln):
            if not ROW.match(ln):
                header = None
            out.append(ln)
            i += 1
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        if DELIM.match(nxt):
            if header is None:                    # this table's own header
                header = ln
                out.append(ln)
                i += 1
                continue
            if ln.strip() == header.strip():      # the same header again
                dropped += 1
                i += 2
                continue
            out.append('')                        # a different table
            split += 1
            header = ln
        out.append(ln)
        i += 1
    return out, dropped, split


def fix(path):
    text = open(path, encoding='utf-8').read()
    lines, moved, held = rejoin(text.split('\n'))
    lines, dropped, split = dedupe_headers(lines)
    out = []
    fenced = False
    inserts = 0
    splits = 0
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('```'):
            fenced = not fenced
        prev = lines[i - 1] if i else ''
        if not fenced and i:
            # a table header glued to the paragraph above it
            if ROW.match(ln) and plain(prev):
                nxt = lines[i + 1] if i + 1 < len(lines) else ''
                if DELIM.match(nxt):
                    out.append('')
                    inserts += 1
            # a paragraph glued to the last row of a table
            elif plain(ln) and ROW.match(prev):
                out.append('')
                inserts += 1
        out.append(ln)
    return '\n'.join(out), inserts + split, moved, held, dropped



SEP = re.compile(r'^\s*\|[\s:|-]+\|\s*$')
ONLY_FOOTNOTES = re.compile(r'^\s*(\[\^[^\]]+\])+\s*$')


def fix_widths(path):
    """Fold a stray footnote column back into the cell it belongs to.

    The fault: an appended row carries its citation in its own trailing cell,
    `| date | text | [^cite] |`, while the table it lands in carries citations
    inline, `| date | text[^cite] |`. Both are well-formed tables, so neither
    the run-on check nor the header checks can see it; the row simply renders
    with one cell too many and the column headers stop lining up.

    Only the provably safe case is touched: the row is exactly one cell wider
    than its table's first row, and that extra cell holds nothing but footnote
    references. Then folding it into the preceding cell restores the table's
    own convention and changes rendering alone — the same footnote, the same
    claim, the same source. Anything else is left for a human, because
    guessing which table a mismatched run belongs to is what put four
    `Date | Event` rows under a `Story line | Argument` header in the first
    place.
    """
    lines = open(path, encoding='utf-8').read().split('\n')
    out = list(lines)
    folded = 0
    run = []
    blocks = []
    for i, l in enumerate(lines):
        if l.lstrip().startswith('|'):
            run.append(i)
        else:
            if run:
                blocks.append(run)
            run = []
    if run:
        blocks.append(run)

    for b in blocks:
        rows = [i for i in b if not SEP.match(lines[i].replace('\\|', ''))]
        if len(rows) < 2:
            continue
        hdr = lines[rows[0]].replace('\\|', '').count('|')
        for i in rows[1:]:
            l = lines[i]
            if l.replace('\\|', '').count('|') != hdr + 1:
                continue
            if not l.rstrip().endswith('|'):
                continue
            cells = l.rstrip()[1:-1].split('|')
            if len(cells) < 2 or not ONLY_FOOTNOTES.match(cells[-1]):
                continue
            # keep the table's own `...] |` spacing rather than gluing the
            # footnote against the closing pipe
            cells[-2] = cells[-2].rstrip() + cells[-1].strip() + ' '
            out[i] = '|' + '|'.join(cells[:-1]) + '|'
            folded += 1

    # The mirror case, and the commoner one. A table headed
    # `| Date | Event | Source |` whose rows carry the citation inline in the
    # Event cell instead of in the Source cell beside it: three columns
    # declared, two supplied, so every row after it slides one column left.
    #
    # Splitting is only safe under a real header. In a table with no header
    # row at all the first row is data, the two-cell form is the convention,
    # and splitting would break every row to match an accident. So the block
    # must open with a separator row underneath it and its first cell must not
    # be a date. `optimierung-druckerlandschaft.md` was repaired this way by
    # hand on 22.08.2026, which is where the transform comes from.
    for b in blocks:
        rows = [i for i in b if not SEP.match(lines[i].replace('\\|', ''))]
        if len(rows) < 2:
            continue
        h = rows[0]
        if h + 1 >= len(lines) or not SEP.match(lines[h + 1].replace('\\|', '')):
            continue
        first = lines[h].strip('| ').split('|')[0].strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}', first):
            continue
        hdr = lines[h].replace('\\|', '').count('|')
        for i in rows[1:]:
            l = out[i]
            if l.replace('\\|', '').count('|') != hdr - 1:
                continue
            if not l.rstrip().endswith('|'):
                continue
            cells = l.rstrip()[1:-1].split('|')
            m = re.search(r'((?:\[\^[^\]]+\])+)\s*$', cells[-1].rstrip())
            if not m:
                continue
            body_txt = cells[-1].rstrip()[:m.start()].rstrip()
            cells[-1] = ' ' + body_txt + ' '
            cells.append(' ' + m.group(1) + ' ')
            out[i] = '|' + '|'.join(cells) + '|'
            folded += 1

    return '\n'.join(out), folded


def main():
    dry = '--dry-run' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')] or verify.discover()
    if '--widths' in sys.argv:
        for kb in kbs:
            root = os.path.join(VAULT, kb, 'Wiki')
            tot = files = 0
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith('_')]
                for f in sorted(filenames):
                    if not f.endswith('.md') or f in ('index.md', 'log.md'):
                        continue
                    p = os.path.join(dirpath, f)
                    new, k = fix_widths(p)
                    if k:
                        tot += k
                        files += 1
                        if not dry:
                            open(p, 'w', encoding='utf-8').write(new)
            print('%-12s %4d stray footnote column(s) folded back across '
                  '%d concept(s)%s'
                  % (kb, tot, files, '  (dry run)' if dry else ''))
        return

    for kb in kbs:
        root = os.path.join(VAULT, kb, 'Wiki')
        n = files = orphans = rejoined = headers = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith('_')]
            for f in sorted(filenames):
                if not f.endswith('.md') or f in ('index.md', 'log.md'):
                    continue
                p = os.path.join(dirpath, f)
                new, ins, mv, held, drop = fix(p)
                orphans += held
                rejoined += mv
                headers += drop
                if ins or mv or drop:
                    n += ins
                    files += 1
                    if not dry:
                        open(p, 'w', encoding='utf-8').write(new)
        print('%-12s %4d blank line(s) inserted, %d orphan row(s) rejoined, '
              '%d repeated header(s) dropped, across %d concept(s)%s; '
              '%d row(s) held, not repaired'
              % (kb, n, rejoined, headers, files,
                 '  (dry run)' if dry else '', orphans))


if __name__ == '__main__':
    main()
