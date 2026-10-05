"""Made-up bodies that hold the blank-line rules in place.

Every base counts 0 for these findings, so the corpus cannot say when a rule
in `blanklines.py` breaks: an edit that stopped a rule counting would pass
the audit until a compile next wrote the fault. The review of 05.10.2026
found three faults in the joined rule that way, each on a shape no base
holds. Each case here is one shape, with what the audit counts in it and
what the repairs leave. `verify.py` runs them in its vault pass, so a rule
that moves fails the commit.

A case is (what it is, the body, what the audit counts, the body after every
repair has run). A count that is not named is 0, and a case with no fourth
item is a body no repair writes to. The counts are the ones `verify.py`
reads: the four pair rules by name, the `table_break` verdicts, `widths` and
`wheld` from `width_breaks`, and `unclosed` for a fence that never closes.
"""
import blanklines
import bundle

CASES = [
    # Two paragraphs, and a paragraph under a list item or a footnote
    ('run-on, prose under prose',
     'First claim.[^a]\nSecond claim, a new sentence.[^b]',
     {'runon': 1},
     'First claim.[^a]\n\nSecond claim, a new sentence.[^b]'),
    ('run-on inside a fenced block',
     'Lead.\n\n```\nFirst claim.[^a]\nSecond claim.\n```',
     {}),
    ('run-on inside a six-backtick fence',
     '``````\nFirst claim.[^a]\nSecond claim.\n``````',
     {}),
    ('run-on under a line that opens with a one-line code span',
     '```x``` is the flag.\n\nFirst claim.[^a]\nSecond claim.[^b]',
     {'runon': 1},
     '```x``` is the flag.\n\nFirst claim.[^a]\n\nSecond claim.[^b]'),
    ('run-on whose reference label holds a space',
     'First claim.[^x y]\nSecond claim.',
     {}),
    ('numbered item ending in a reference, then a sentence',
     '1. A numbered item.[^a]\nA new sentence under it.',
     {'runon': 1, 'under_item': 1},
     '1. A numbered item.[^a]\n\nA new sentence under it.'),
    ('list item ending in a reference, then a sentence',
     '- A list item.[^a]\nA new sentence under it.',
     {'under_item': 1}),
    ('paragraph under a list item',
     '- a list item\nGlued paragraph.',
     {'under_item': 1}),
    ('paragraph under a footnote definition',
     '[^a]: Source A.\nGlued paragraph.',
     {'under_note': 1}),
    ('footnote definition under a paragraph',
     'A claim.[^a]\n[^a]: Source A.',
     {'note_under': 1},
     'A claim.[^a]\n\n[^a]: Source A.'),
    ('footnote definition under a paragraph, in a fence',
     '```\nA claim.[^a]\n[^a]: Source A.\n```',
     {}),
    # A table and the line above it
    ('table between two paragraphs, well formed',
     'Lead.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nMore.',
     {}),
    ('table header under a paragraph',
     'Intro paragraph.\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'blank': 1},
     'Intro paragraph.\n\n| A | B |\n|---|---|\n| 1 | 2 |'),
    ('table header with no closing pipe under a paragraph',
     'Intro paragraph.\n| A | B\n|---|---|\n| 1 | 2 |',
     {'blank': 1},
     'Intro paragraph.\n\n| A | B\n|---|---|\n| 1 | 2 |'),
    ('table header under a paragraph, separator with no closing pipe',
     'Intro paragraph.\n| A | B |\n|---|---\n| 1 | 2 |',
     {'blank': 1},
     'Intro paragraph.\n\n| A | B |\n|---|---\n| 1 | 2 |'),
    ('table header under a paragraph, tabs in the separator',
     'Intro paragraph.\n| A | B |\n|\t---\t|\t---\t|\n| 1 | 2 |',
     {'blank': 1},
     'Intro paragraph.\n\n| A | B |\n|\t---\t|\t---\t|\n| 1 | 2 |'),
    ('table header under a paragraph that opens in bold',
     '**Note.** Intro paragraph.\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'held': 1}),
    ('table header under a closing fence',
     '```\ncode\n```\n| A | B |\n|---|---|\n| 1 | 2 |',
     {}),
    ('table under a list item',
     '- a list item\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'held': 1}),
    ('table under a numbered item',
     '1. a numbered item\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'held': 1}),
    ('table under an indented line',
     'Lead.\n\n    an indented line\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'held': 1}),
    ('table under a footnote definition',
     '[^a]: Source A.\n| A | B |\n|---|---|\n| 1 | 2 |',
     {'held': 1}),
    ('indented table under a paragraph',
     'Intro paragraph.\n  | A | B |\n  |---|---|\n  | 1 | 2 |',
     {'held': 1}),
    ('fenced table that meets its closing fence',
     '```\n| A | B |\n|---|---|\n| 1 | 2 |\n```',
     {}),
    # What a header, a separator and a row are
    ('table that opens on a data row',
     'Lead.\n\n| 1 | 2 |\n| 3 | 4 |',
     {'headerless': 1}),
    ('table whose header row is empty',
     '| | |\n|---|---|\n| Ownership | Public |',
     {}),
    ('data row of single dashes in a table',
     '| A | B |\n|---|---|\n| 1 | 2 |\n| - | - |\n| 3 | 4 |',
     {}),
    # A row a merge left under prose, away from its table
    ('orphan row under a paragraph, its table above',
     '| A | B |\n|---|---|\n| 1 | 2 |\n\nAppended prose.\n| 3 | 4 |',
     {'hoist': 1},
     '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\nAppended prose.'),
    ('orphan row with no closing pipe, its table above',
     '| A | B |\n|---|---|\n| 1 | 2 |\n\nAppended prose.\n| 3 | 4',
     {'hoist': 1},
     '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4\n\nAppended prose.'),
    ('orphan row under a paragraph, no table above',
     'Prose with no table above.\n| 3 | 4 |',
     {'held': 1}),
    ('orphan row, a heading between it and the table above',
     '| A | B |\n|---|---|\n| 1 | 2 |\n\n# Next section\n\nAppended prose.\n| 3 | 4 |',
     {'held': 1}),
    ('orphan row whose only table above is fenced',
     '```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n\nAppended prose.\n| 3 | 4 |',
     {'held': 1}),
    ('orphan row, a fenced # line between it and its table',
     '| A | B |\n|---|---|\n| 1 | 2 |\n\n```\n# a shell comment\n```\n\nAppended prose.\n| 3 | 4 |',
     {'hoist': 1},
     '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n```\n# a shell comment\n```\n\nAppended prose.'),
    ('orphan row holding an escaped pipe, its table above',
     '| Session | Note |\n|---|---|\n| IK 01 | first |\n\nAppended prose.\n| IK 02\\|23 | second |',
     {'hoist': 1},
     '| Session | Note |\n|---|---|\n| IK 01 | first |\n| IK 02\\|23 | second |\n\nAppended prose.'),
    ('two-cell orphan holding an escaped pipe, a three-column table above',
     '| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n\nAppended prose.\n| x\\|y | z |',
     {'held': 1}),
    # What a merge left under a table's last row
    ("paragraph under a table's last row",
     '| A | B |\n|---|---|\n| 1 | 2 |\nA paragraph glued under the last row.',
     {},
     '| A | B |\n|---|---|\n| 1 | 2 |\n\nA paragraph glued under the last row.'),
    ("the table's own header repeated under its last row",
     '| A | B |\n|---|---|\n| 1 | 2 |\n| A | B |\n|---|---|\n| 3 | 4 |',
     {},
     '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |'),
    ("another table's header under a last row",
     '| A | B |\n|---|---|\n| 1 | 2 |\n| C | D |\n|---|---|\n| 3 | 4 |',
     {},
     '| A | B |\n|---|---|\n| 1 | 2 |\n\n| C | D |\n|---|---|\n| 3 | 4 |'),
    # Rows of another width, and a fence that never closes
    ('row with its footnote in a cell of its own',
     '| Year | Event |\n|---|---|\n| 2020 | x[^a] |\n| 2021 | y | [^b] |',
     {'widths': 1},
     '| Year | Event |\n|---|---|\n| 2020 | x[^a] |\n| 2021 | y[^b] |'),
    ('row with its footnote inline under a Source header',
     '| When | Event | Source |\n|---|---|---|\n| 2020 | x[^a] |',
     {'widths': 1},
     '| When | Event | Source |\n|---|---|---|\n| 2020 |  x | [^a] |'),
    ('row one cell wider, the extra cell holding text',
     '| A | B |\n|---|---|\n| 1 | 2 | 3 |',
     {'wheld': 1}),
    ('stray footnote column inside a fence',
     '```\n| Year | Event |\n|---|---|\n| 2021 | y | [^b] |\n```',
     {}),
    ('width mismatch under a fence that never closes',
     'Lead.\n\n```\ncode\n\n| A | B |\n|---|---|\n| 1 | 2 | 3 |',
     {'unclosed': 1}),
]


def counted(lines):
    """What the audit counts in a body, zeros left out."""
    ls = blanklines.unfenced(lines)
    n = {k: len(blanklines.gaps(ls, getattr(blanklines, k)))
         for k in ('runon', 'under_item', 'under_note', 'note_under')}
    n.update(blanklines.table_breaks(ls))
    n['widths'], n['wheld'] = blanklines.width_breaks(ls)
    n['unclosed'] = sum(map(blanklines.fence, lines)) % 2
    return {k: v for k, v in n.items() if v}


def repaired(lines):
    """A body after `fix-runons.py`, `fix-tablebreaks.py`, its `--widths`
    and `fix-footnote-gaps.py` have each run once, in that order."""
    tables = bundle.script('fix-tablebreaks.py')
    for rule in (blanklines.runon, None, blanklines.note_under):
        if rule:
            lines = blanklines.spaced(lines, blanklines.gaps(
                blanklines.unfenced(lines), rule))
        else:
            lines = blanklines.fold(tables.fix(lines)[0])[0]
    return lines


def failures():
    """One line for each case the rules no longer read as it says."""
    out = []
    for what, body, want, *after in CASES:
        lines = body.split('\n')
        got = counted(lines)
        if got != want:
            out.append('blank-line case "%s": the rules count %s where the '
                       'case says %s' % (what, got or 'nothing',
                                         want or 'nothing'))
        end = '\n'.join(repaired(lines))
        if end != (after[0] if after else body):
            out.append('blank-line case "%s": the repairs leave %r'
                       % (what, end))
    return out
