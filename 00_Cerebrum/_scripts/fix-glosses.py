#!/usr/bin/env python3
"""Restores link descriptions truncated by the orphan-linking pass.

On 15.08.2026 the orphan sweep wrote one bullet per orphan into the concept
that names it, glossing each from the orphan's own `description`. The gloss
helper cut at 110 characters, and it cut on a character boundary rather than
a word one, so 29 descriptions in Gamma_kb end mid-word: "copying home-driv",
"as simple as pos", "non-customis", "was spec".

The full text is on disk in every case — the orphan's frontmatter `description`
is the source the gloss was taken from — so this is a restoration rather than
a rewrite. Beta_kb's 62 were repaired by hand during the health check of
22.08.2026; this script exists so the class has a repair rather than a habit,
and so the same sweep run again cannot reintroduce it silently.

It only touches a bullet whose gloss is a strict prefix of the concept's own
description. Anything a human has since edited is left alone.

Usage:  python3 _scripts/fix-glosses.py <KB> [more KBs...] [--dry-run]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify  # noqa: E402

try:
    import yaml
except ImportError:
    sys.exit('fix-glosses.py needs PyYAML')

BULLET = re.compile(r'^(\s*[*-] \[[^\]]+\]\((?!http)([^)\n]+\.md)\) — )(.+)$', re.M)


def description_of(path):
    if not os.path.exists(path):
        return None
    t = verify.FENCE.sub('', open(path, encoding='utf-8').read())
    m = verify.FM.match(t)
    if not m:
        return None
    fm = yaml.safe_load(m.group(1)) or {}
    return ' '.join(str(fm.get('description') or '').split()) or None


def main():
    apply = '--dry-run' not in sys.argv
    kbs = [a for a in sys.argv[1:] if not a.startswith('--')]
    total = files = 0
    for kb in kbs:
        for p in sorted(glob.glob(os.path.join(kb, 'Wiki', '**', '*.md'),
                                  recursive=True)):
            if os.path.basename(p) in ('index.md', 'log.md') \
                    or '_to_delete' in p:
                continue
            s = open(p, encoding='utf-8').read()
            out, n = [], 0
            last = 0
            for m in BULLET.finditer(s):
                gloss = m.group(3).rstrip()
                tgt = os.path.normpath(os.path.join(os.path.dirname(p),
                                                    m.group(2)))
                full = description_of(tgt)
                if not full or gloss == full or not full.startswith(gloss):
                    continue
                out.append((m.start(3), m.end(3), full))
                n += 1
            if not n:
                continue
            for a, b, full in reversed(out):
                s = s[:a] + full + s[b:]
            total += n
            files += 1
            print('  %-58s %d restored' % (os.path.relpath(p, kb), n))
            if apply:
                open(p, 'w', encoding='utf-8').write(s)
    print('%d gloss(es) restored across %d concept(s)%s'
          % (total, files, '' if apply else '  (dry run)'))


if __name__ == '__main__':
    main()
