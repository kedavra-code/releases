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

The rule matches verify.py's own, deliberately: a non-indented line ending in a
footnote reference, followed by a non-indented line that begins a new sentence
(capital, quote, or a markdown link). Tables, lists, headings, block quotes and
footnote definitions are left alone on both sides.

Usage:  python3 _scripts/fix-runons.py <KB> [more KBs...] [--dry-run]
"""
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
SKIP = ('|', '*', '-', '#', '>', '[^', '```')


def fix(text):
    lines = text.split('\n')
    out, n = [], 0
    for i, line in enumerate(lines):
        out.append(line)
        if i + 1 >= len(lines):
            continue
        a, b = line, lines[i + 1]
        if not a.rstrip().endswith(']') or not re.search(r'\[\^[^\]]+\]$', a.rstrip()):
            continue
        if a.lstrip() != a or a.lstrip().startswith(SKIP):
            continue
        if not b.strip() or b.lstrip() != b or b.startswith(SKIP):
            continue
        if b[:1].isupper() or b[:1] == '"' or re.match(r'\[[^\^\]]+\]\(', b):
            out.append('')
            n += 1
    return '\n'.join(out), n


def main():
    dry = '--dry-run' in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')]
    for kb in kbs:
        root = os.path.join(VAULT, kb)
        files = n = 0
        for f in sorted(glob.glob(os.path.join(root, 'Wiki', '**', '*.md'),
                                  recursive=True)):
            if '_to_delete' in f:
                continue
            raw = open(f, encoding='utf-8').read()
            m = FM.match(raw)
            if not m:
                continue
            head, body = raw[:m.end()], raw[m.end():]
            new, k = fix(body)
            if k:
                files += 1
                n += k
                if not dry:
                    open(f, 'w', encoding='utf-8').write(head + new)
        print('%-12s %3d paragraph(s) separated in %d concept(s)%s'
              % (kb, n, files, '  (dry run)' if dry else ''))


if __name__ == '__main__':
    main()
