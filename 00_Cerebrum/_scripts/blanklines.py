"""Where a blank line is missing between two blocks: the check and the repair
read it here.

A markdown block ends at a blank line. Where the line is missing the second
block renders inside the first: two claims read as one paragraph, a table
shows as literal pipes, a footnote never defines. Nothing is wrong in the
file and the page is wrong, so the class piles up unseen: 222 run-ons stood
in one base on 16.08.2026 before any check counted one.

Until 05.10.2026 each shape stood twice, as a check in `verify.py` and as a
repair in a `fix-*.py`, with seven lists between them of what counts as a
list, table or heading line. All six bases counted 0 on both sides that day,
and on made-up cases the copies parted: a repair wrote inside fenced blocks
the check never reads, and the check sent five table shapes to a repair that
mends none of them. Three rules were settled that day and hold here:

  - A fenced block is read by nobody. `unfenced()` blanks it, and every rule
    below is handed lines that went through it.
  - The check says where a site is: a repair finds its places with the
    function the check counts with.
  - A repair writes a blank line only beside an ordinary paragraph line,
    `para()`. Anywhere else the site is held for a reader, and `verify.py`
    names no script for it.

Each check counts what it counted before, so the lists are one base list with
three stated additions and not one list: `runon` still takes a `+` item or a
numbered item for a paragraph, and `under_note` a line opening on `**`.

No base holds one of these faults, so the corpus cannot say when a rule here
breaks. `blanklines-cases.py` holds a made-up body for each shape, and
`verify.py` runs them on every commit.
"""
import collections
import re

from bundle import FM, concept_files
from tableorder import SEP

BLOCK = ('|', '#', '>')              # a table row, a heading, a block quote
NOTE = BLOCK + ('[^',)               # and a footnote definition
MARK = r'(?:[-*+]|\d+\.)'
ITEM = re.compile(MARK + r'\s')      # a list item, bulleted or numbered
DEFN = re.compile(r'\[\^[^\]]+\]:')
REF_END = re.compile(r'\[\^[^\]\s]+\]\s*$')
ONLY_FOOTNOTES = re.compile(r'^\s*(\[\^[^\]]+\])+\s*$')


def fence(l):
    """Opens or closes a fenced block. A line that closes its own span,
    ```x``` and then text, is inline code: read as a fence it would blank
    every line down to the next one."""
    s = l.lstrip()
    return s.startswith('```') and '```' not in s.lstrip('`')


def unfenced(lines):
    """The lines as the rules read them: every fenced block blanked, its two
    fence lines with it. Line numbers stay, so a repair writes to the lines
    it was handed."""
    out, inside = [], False
    for l in lines:
        mark = fence(l)
        out.append('' if inside or mark else l)
        if mark:
            inside = not inside
    return out


def flush(l):
    """Carries text and starts at the margin."""
    return bool(l[:1].strip())


def para(l):
    """An ordinary paragraph line, the only neighbour a repair writes a blank
    line beside: beside anything with block semantics of its own, a blank
    line changes meaning. A line opening on `-`, `*` or `+` is taken for a
    list item whatever follows, which holds a paragraph that opens in bold."""
    return (flush(l) and not l.startswith(NOTE + ('-', '*', '+'))
            and not ITEM.match(l))


# The pair rules: `a` is a line and `b` the line under it.

def runon(a, b):
    """A paragraph ending in a footnote reference, then a new sentence: two
    claims with two sources render as one. `fix-runons.py` separates them."""
    return bool(REF_END.search(a) and flush(a) and flush(b)
                and not a.startswith(NOTE + ('*', '-'))
                and (b[:1].isupper() or b[:1] == '"'
                     or re.match(r'\[[^\^\]]+\]\(', b)))


def under_item(a, b):
    """A list item, then a paragraph: it renders inside the bullet."""
    return bool(re.match(r'\s*' + MARK + r'\s+\S', a) and flush(b)
                and (b[:1].isupper() or b[:2] == '**' or b[:1] == '"'))


def under_note(a, b):
    """A footnote definition, then a paragraph: it renders inside the note."""
    return (a.startswith('[^') and ']:' in a and flush(b)
            and not b.startswith(NOTE) and not ITEM.match(b))


def note_under(a, b):
    """Text, then a footnote definition: the text swallows it and the marker
    renders as brackets. `fix-footnote-gaps.py` separates them."""
    return bool(DEFN.match(b) and a.strip() and not DEFN.match(a))


def under_table(a, b):
    """A table row, then a paragraph: it renders as one more row. Written by
    `fix-tablebreaks.py`; no check counts it."""
    return a.startswith('|') and para(b)


def gaps(ls, rule):
    """The line numbers a rule wants a blank line above."""
    return [i for i in range(1, len(ls)) if rule(ls[i - 1], ls[i])]


def spaced(lines, at):
    """The lines with a blank line written above each line number in `at`."""
    at = set(at)
    return [x for i, l in enumerate(lines)
            for x in (('', l) if i in at else (l,))]


def bodies(kb, indexes=False):
    """Each concept of a base as (path, frontmatter block, body lines). A
    file with no frontmatter is left out: the audit reads no body there."""
    for f in concept_files(kb, indexes):
        raw = open(f, encoding='utf-8').read()
        m = FM.match(raw)
        if m:
            yield f, raw[:m.end()], raw[m.end():].split('\n')


def separate(kb, rule, dry, indexes=False):
    """Write the blank lines a pair rule finds missing in one base, and
    yield (path, how many) for each concept that had any."""
    for f, head, lines in bodies(kb, indexes):
        at = gaps(unfenced(lines), rule)
        if at and not dry:
            open(f, 'w', encoding='utf-8').write(
                head + '\n'.join(spaced(lines, at)))
        if at:
            yield f, len(at)


# Tables. A table row glued under text needs more than the two lines to
# judge: whether the line under it is a separator, and what stands above.

def home(ls, i):
    """The row an orphan run at line i continues, or None: the nearest table
    line above it, never across a heading and only at the same `width()`,
    because two shapes in one section are two tables."""
    j = i - 1
    while j >= 0 and not ls[j].startswith('|'):
        if ls[j].startswith('#'):
            return None
        j -= 1
    return j if j >= 0 and width(ls[j]) == width(ls[i]) else None


def table_break(ls, i):
    """What is wrong at line i where it is a table row, or None.

    'blank'       a header glued under a paragraph. A blank line mends it.
    'hoist'       a row with no header of its own under a paragraph, and
                  `home()` finds the table it continues. Moving it there
                  mends it; a blank line would make a headerless table.
    'held'        a row under a list item, an indented line or a footnote
                  definition, an indented row, or an orphan with no home.
    'headerless'  a table that opens on a data row. The header stayed with
                  the table it was split from.

    The last two are a reader's: nothing here knows where the row belongs.

    A row is a line that opens on a pipe, with a closing pipe or without
    one, as GFM reads it.
    """
    a, b = ls[i - 1] if i else '', ls[i]
    nxt = ls[i + 1] if i + 1 < len(ls) else ''
    if not b.lstrip().startswith('|'):
        return None
    if not a.strip():
        return ('headerless' if nxt.lstrip().startswith('|')
                and not SEP.match(nxt) else None)
    if a.lstrip().startswith(BLOCK):
        return None
    if not para(a) or b[0] != '|':
        return 'held'
    if SEP.match(nxt):
        return 'blank'
    return 'held' if home(ls, i) is None else 'hoist'


def table_breaks(ls):
    """How many of each `table_break` a body holds."""
    return collections.Counter(
        filter(None, (table_break(ls, i) for i in range(len(ls)))))


def width(l):
    """Cells in a row, with a closing pipe or without one.
    `IK-Session 02\\|23` is one cell holding a pipe."""
    s = l.replace('\\|', '').rstrip()
    return (s[:-1] if s.endswith('|') else s).count('|')


def table_rows(ls):
    """Each run of table lines as the line numbers of its rows. A separator
    row is in the run and is not a row."""
    rows = []
    for i, l in enumerate(ls + ['']):
        if not l.lstrip().startswith('|'):
            if rows:
                yield rows
            rows = []
        elif not SEP.match(l.replace('\\|', '')):
            rows.append(i)


def fold(lines):
    """(the lines with every row `--widths` can mend rewritten, how many).

    Both sides of this fault are well-formed tables, so no blank-line rule
    sees it: the row renders with one cell too many or too few and the
    headers stop lining up. Two provably safe cases are mended, and they
    change rendering alone, the same footnote on the same claim. Anything
    else is a reader's, because guessing which table a mismatched run
    belongs to is what put four `Date | Event` rows under a
    `Story line | Argument` header in the first place.
    """
    ls, out, n = unfenced(lines), list(lines), 0
    for rows in table_rows(ls):
        hdr = width(ls[rows[0]])
        # A row one cell wider than its table's first row, the extra cell
        # holding nothing but footnote references: an appended row carrying
        # its citation in a cell of its own where the table carries it
        # inline. Folded into the cell before it.
        for i in rows[1:]:
            l = ls[i]
            if width(l) != hdr + 1 or not l.rstrip().endswith('|'):
                continue
            cells = l.rstrip()[1:-1].split('|')
            if len(cells) < 2 or not ONLY_FOOTNOTES.match(cells[-1]):
                continue
            # keep the table's own `...] |` spacing rather than gluing the
            # footnote against the closing pipe
            cells[-2] = cells[-2].rstrip() + cells[-1].strip() + ' '
            out[i] = '|' + '|'.join(cells[:-1]) + '|'
            n += 1
        # The mirror case, and the commoner one. A table headed
        # `| Date | Event | Source |` whose rows carry the citation inline in
        # the Event cell: three columns declared, two supplied.
        #
        # Splitting is only safe under a real header. In a table with no
        # header row the first row is data, the two-cell form is the
        # convention, and splitting would break every row to match an
        # accident. So the run must open with a separator row underneath it
        # and its first cell must not be a date.
        # `optimierung-druckerlandschaft.md` was repaired this way by hand
        # on 22.08.2026, which is where the transform comes from.
        h = rows[0]
        under = ls[h + 1] if h + 1 < len(ls) else ''
        if not SEP.match(under.replace('\\|', '')) or re.match(
                r'^\d{4}-\d{2}-\d{2}', ls[h].strip('| ').split('|')[0].strip()):
            continue
        for i in rows[1:]:
            l = out[i]
            if width(l) != hdr - 1 or not l.rstrip().endswith('|'):
                continue
            cells = l.rstrip()[1:-1].split('|')
            m = re.search(r'((?:\[\^[^\]]+\])+)\s*$', cells[-1].rstrip())
            if not m:
                continue
            cells[-1] = ' ' + cells[-1].rstrip()[:m.start()].rstrip() + ' '
            cells.append(' ' + m.group(1) + ' ')
            out[i] = '|' + '|'.join(cells) + '|'
            n += 1
    return out, n


def width_breaks(ls):
    """(mendable, held): rows whose column count differs from the row above
    them in the same table, split by whether `fold()` leaves them standing."""
    def count(x):
        return sum(width(x[a]) != width(x[b]) for rows in table_rows(x)
                   for a, b in zip(rows, rows[1:]))
    n = count(ls)
    left = min(n, count(fold(ls)[0])) if n else 0
    return n - left, left
