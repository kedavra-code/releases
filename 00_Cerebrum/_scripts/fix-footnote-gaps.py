#!/usr/bin/env python3
"""Insert the blank line a footnote definition is missing above it.

The mirror of `fix-runons.py`, and of the check built for Gamma_kb
AI-2026-09-14-10. That one catches a paragraph starting on the line under a
footnote definition, where the paragraph is swallowed into the footnote. This
catches the other direction: a definition written on the line directly under a
paragraph, with no blank line between them.

Under lazy continuation the definition is read as more of the paragraph. The
footnote then never defines, so its marker renders as literal bracket text and
the source the reader is chasing is not there. Nothing caught it until
20.09.2026, when eight readers working the whole Gamma_kb bundle kept
reporting the same shape from different concepts; the scan then found 47 cases
across 33 concepts here and 64 across 49 in Alpha_kb.

Same cause as the run-on: `merge-appends.py` joining an appended chunk to what
precedes it with a single newline. That is fixed at the source; this repairs
what the old behaviour already wrote.

The rule is `blanklines.note_under`, the one `verify.py` counts by, so the
two cannot part. A footnote definition at the start of a line, whose previous
line carries text and is not itself a definition. Fenced blocks are skipped on
both sides, so an illustrative example in `references/` is left as written.

Usage:  python3 _scripts/fix-footnote-gaps.py <KB> [more KBs...] [--dry-run]
"""
import os
import sys

import blanklines
from bundle import VAULT


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    if not args:
        print(__doc__.strip().split('\n')[-1])
        return 1
    total, touched = 0, 0
    for kb in args:
        for f, n in blanklines.separate(kb, blanklines.note_under, dry):
            total += n
            touched += 1
            print('%s: %d' % (os.path.relpath(f, VAULT), n))
    print('%s%d blank line(s) across %d file(s)'
          % ('would insert ' if dry else 'inserted ', total, touched))
    return 0


if __name__ == '__main__':
    sys.exit(main())
