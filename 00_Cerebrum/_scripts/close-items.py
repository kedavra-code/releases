#!/usr/bin/env python3
"""Moves what is closed out of a base's Wiki/questions.md into
<KB>/_QUESTIONS-CLOSED.md.

Two things move: every action item `actioned` or `withdrawn`, and every
*Held by …* or *Held from …* section whose rows are all settled (the rows and
the words `queues.py` reads). From the move on, the closed file is the only
place a closed item's state lives, and its id is never used again.

Why: on 08.11.2026 121 of the 122 rows in Alpha_kb's action-item table were
closed, 178'662 bytes, and every action sitting read them again to find the
one that was open.

The closed file sits beside CHANGELOG.md and is not a concept, so the checks
for concepts leave its old text alone. Links in a moved row were written from
`Wiki/`; they are rebased to the knowledge base folder, and so is a
backticked path that starts with `../`.

A base opts in with `questions_closed: true` in its assertions.yaml.
`closeout.sh` runs this first.

Usage:  python3 _scripts/close-items.py [KB ...] [--dry-run]
        no base named: every base that opts in
"""
import os
import re
import sys

import actionitems
import bundle
import queues
from tableorder import SEP

CLOSED = actionitems.CLOSED
HELD = re.compile(r'^## Held (?:by|from)[^\n]*\n.*?(?=^#{1,2} |\Z)', re.S | re.M)
ROWLINE = re.compile(r'^(\| \[|\d+\. )')

HEAD = """# Closed questions — {kb}

What `Wiki/questions.md` has closed: every action item `actioned` or `withdrawn`, and every *Held* section whose rows are all settled. `_scripts/close-items.py` moves them here, so that a sitting reads only what is still open (owner, 08.11.2026). From the move on, this file is the only place a closed item's state lives, and its id is never used again.

Links here are written from this folder, not from `Wiki/`. The newest moves stand first in the table; held sections stand in the order they were moved.

# Action items

{header}

# Held sections, settled
"""


def rebase(text):
    """A link or a `../` path written from Wiki/, rewritten from the base folder."""
    def link(m):
        tgt = m.group(1)
        wrap = tgt.startswith('<') and tgt.endswith('>')
        inner = tgt[1:-1] if wrap else tgt
        path, _, frag = inner.partition('#')
        if not path:
            return m.group(0)
        new = os.path.normpath(os.path.join('Wiki', path)) + ('#' + frag if frag else '')
        return '](%s)' % ('<%s>' % new if wrap else new)
    text = re.sub(r'\]\(((?!https?:|mailto:|#|/)[^)\n]+)\)', link, text)
    return re.sub(r'`(\.\./[^`\n]+)`',
                  lambda m: '`%s`' % os.path.normpath(os.path.join('Wiki', m.group(1))), text)


def split(text):
    """Returns (questions.md as it stays, table header, closed rows, closed sections)."""
    m = re.search(r'^# Action items\n(.*?)(?=^# |\Z)', text, re.S | re.M)
    if not m:
        return text, None, [], []
    sec = m.group(1)
    lines = sec.split('\n')
    # The header is the two lines above the first item row: the section can
    # open with another table, as Alpha_kb's does with *State* and *Meaning*.
    first = next((i for i, l in enumerate(lines) if actionitems.ROW.match(l)), None)
    header = ('\n'.join(lines[first - 2:first])
              if first and first >= 2 and SEP.match(lines[first - 1]) else None)
    keep, rows = [], []
    for l in lines:
        r = actionitems.ROW.match(l)
        if r and actionitems.state_of(r.group(4)) in ('actioned', 'withdrawn'):
            rows.append(l)
        else:
            keep.append(l)
    text = text[:m.start(1)] + '\n'.join(keep) + text[m.end(1):]
    secs = []
    for h in list(HELD.finditer(text))[::-1]:
        rl = [l for l in h.group(0).splitlines() if ROWLINE.match(l)]
        # `queues.held_lines` is the one definition of a row not settled.
        if rl and not queues.held_lines(h.group(0)):
            secs.insert(0, h.group(0))
            text = text[:h.start()] + text[h.end():]
    return text, header, rows, secs


def close(kb, dry):
    qp = os.path.join(bundle.VAULT, kb, 'Wiki', 'questions.md')
    cp = os.path.join(bundle.VAULT, kb, CLOSED)
    text = open(qp, encoding='utf-8').read()
    stays, header, rows, secs = split(text)
    # A table with no item row left gives no header; the vault's five cells stand in.
    header = header or '| Id | Raised | Item | State | Resolution |\n|---|---|---|---|---|'
    if not rows and not secs:
        print('%-10s nothing closed to move' % kb)
        return
    if os.path.exists(cp):
        closed = open(cp, encoding='utf-8').read()
    elif header:
        closed = HEAD.format(kb=kb, header=header)
    else:
        sys.exit('%s: no table header in Wiki/questions.md to start %s from' % (kb, CLOSED))
    if rows:
        # Under the separator row of the item table, found by its header.
        lines = closed.split('\n')
        k = next((i for i, l in enumerate(lines[:-1])
                  if header and l == header.split('\n')[0] and SEP.match(lines[i + 1])), None)
        if k is None:
            sys.exit('%s: %s has no item table headed as in questions.md' % (kb, CLOSED))
        at = sum(len(l) + 1 for l in lines[:k + 2])
        closed = closed[:at] + ''.join(rebase(r) + '\n' for r in rows) + closed[at:]
    for s in secs:
        closed = closed.rstrip('\n') + '\n\n' + rebase(s).rstrip('\n') + '\n'
    # Every id that left questions.md must stand once in the closed file.
    gone = [actionitems.ROW.match(r).group(1).strip() for r in rows]
    for i in gone:
        if closed.count('| %s |' % i) != 1 and closed.count('| %s|' % i) != 1:
            sys.exit('%s: %s would not stand exactly once in %s; nothing written' % (kb, i, CLOSED))
    print('%-10s %d item rows and %d held sections move, %d bytes out of questions.md%s'
          % (kb, len(rows), len(secs), len(text) - len(stays), ' (dry run)' if dry else ''))
    if not dry:
        open(cp, 'w', encoding='utf-8').write(closed)
        open(qp, 'w', encoding='utf-8').write(stays)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    kbs = args or [kb for kb in bundle.discover() if bundle.assertions(kb).get('questions_closed')]
    for kb in kbs:
        if not bundle.assertions(kb).get('questions_closed'):
            print('%-10s does not opt in (questions_closed: true); left alone' % kb)
            continue
        close(kb, dry)


if __name__ == '__main__':
    main()
