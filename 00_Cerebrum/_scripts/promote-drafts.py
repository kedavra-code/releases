#!/usr/bin/env python3
"""Promotes the drafts that give no reason to be drafts.

The rule, settled 15.08.2026 and written in the vault `CLAUDE.md`: a concept is
`draft` only while it names something unsettled that would change what it says,
and `stable` once it does not. The three employer bundles held roughly 860
concepts at `draft` from before that rule, none of them giving a reason, which
makes the field decorative — and a decorative field is worse than an absent one
because it looks like information. The owner ruled on 16.09.2026 (`Gamma_kb`
AI-2026-09-15-3): "Promote by script, read the exceptions".

**This script promotes only the clean case, and never judges.** A concept is
promoted when its body carries neither of two things:

  1. the literal string `` `status: draft` ``, which is the marker
     `draft_needs_reason` already looks for and the way a concept states its
     own reason;
  2. a non-empty section headed Open questions, Offene Fragen, Unresolved,
     Contradictions or Uncertain.

Everything else is left alone and listed, because whether an open question
would change what the concept says is a reading, not a pattern. Measured
16.09.2026: 367 clean, 567 with an open-questions section, 16 with the marker.

`--list` prints what would be left for a reader instead of promoting.

Usage:  python3 _scripts/promote-drafts.py <KB> [more KBs...] [--dry-run]
        python3 _scripts/promote-drafts.py <KB> --list
"""
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTION = re.compile(
    r'^#+ *(?:Open questions|Offene Fragen|Unresolved|Contradictions'
    r'|Uncertain)[^\n]*\n(.*?)(?=^#+ |\Z)', re.M | re.S)


def classify(body):
    """'marker', 'openq' or 'clean'."""
    if '`status: draft`' in body:
        return 'marker'
    for m in SECTION.finditer(body):
        if m.group(1).strip():
            return 'openq'
    return 'clean'


def concepts(kb):
    for f in sorted(glob.glob(os.path.join(VAULT, kb, 'Wiki', '**', '*.md'),
                              recursive=True)):
        if '_to_delete' in f or os.path.basename(f) in ('index.md', 'log.md'):
            continue
        text = open(f, encoding='utf-8').read()
        m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        if not m or not re.search(r'^status: *draft *$', m.group(1), re.M):
            continue
        yield f, text, m


def main():
    dry = '--dry-run' in sys.argv
    listing = '--list' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')]
    done = kept = 0
    for kb in kbs:
        for f, text, m in concepts(kb):
            kind = classify(text[m.end():])
            rel = os.path.relpath(f, VAULT)
            if kind != 'clean':
                kept += 1
                if listing:
                    print('%-6s %s' % (kind, rel))
                continue
            done += 1
            if listing:
                continue
            head = re.sub(r'^status: *draft *$', 'status: stable',
                          m.group(1), count=1, flags=re.M)
            if not dry:
                open(f, 'w', encoding='utf-8').write(
                    '---\n' + head + '\n---\n' + text[m.end():])
            print('promoted %s' % rel)
    print('%d promoted, %d left for a reader%s'
          % (done, kept, ' (dry run)' if dry else ''))


if __name__ == '__main__':
    main()
