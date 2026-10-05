#!/usr/bin/env python3
"""Insert the blank line a run-on paragraph is missing.

`verify.py` has reported this since it was written: a line ending in a footnote
reference followed immediately by a new sentence renders as one paragraph, so
two claims with two different sources read as one claim. It is a rendering
fault, not a truth fault, which is why it is a finding and not a defect — and
why 147 of them accumulated in Alpha_kb before anyone repaired any.

The cause was `merge-appends.py` joining an appended chunk to the section above
it with a single newline. That is fixed at the source; this repairs what the
old behaviour already wrote. Both are needed: fixing the merger stops new ones,
and only this clears the standing 147.

The rule is `blanklines.runon`, the one `verify.py` counts by, so the two
cannot part: a non-indented line ending in a footnote reference, followed by a
non-indented line that begins a new sentence (capital, quote, or a markdown
link). Tables, headings, block quotes, footnote definitions, fenced blocks and
list items marked `-` or `*` are left alone on both sides.

Usage:  python3 _scripts/fix-runons.py <KB> [more KBs...] [--dry-run]
"""
import sys

import blanklines


def main():
    dry = '--dry-run' in sys.argv
    for kb in [a for a in sys.argv[1:] if not a.startswith('--')]:
        # With each directory's index and the bundle's log: this repair has
        # always read those too, where every other walk leaves them out.
        done = list(blanklines.separate(kb, blanklines.runon, dry,
                                        indexes=True))
        print('%-12s %3d paragraph(s) separated in %d concept(s)%s'
              % (kb, sum(n for _, n in done), len(done),
                 '  (dry run)' if dry else ''))


if __name__ == '__main__':
    main()
