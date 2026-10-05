#!/usr/bin/env python3
"""Repair resource paths whose only fault is the number of ../ steps.

merge-appends.py re-resolves depth for the citations it merges, but a concept
an agent writes *directly* never passes through it. Every wave produces a few:
an agent writes `../../OneNote/...`, which is right from Wiki/<group>/x.md and
wrong from Wiki/references/digests/x.md one level deeper. verify.py catches
them as defects; nothing repaired them, so they were fixed by hand twice and
came back a third time on the Alpha rebuild of 21.08.2026.

Run after every merge. Only touches a citation that does not resolve, and only
where re-anchoring on the path from OneNote/ onward finds the file.

Usage:  python3 _scripts/fix-depth.py <KB> [--dry-run]
"""
import os, re, sys
import bundle
VAULT = bundle.VAULT
ma = bundle.script('merge-appends.py')
RES = r'^(\s*(?:-\s+)?resource:\s*)(.+)$'

def main():
    kb = sys.argv[1]; dry = '--dry-run' in sys.argv
    root = os.path.join(VAULT, kb); n = files = 0
    for f in bundle.concept_files(kb):
        t = open(f, encoding='utf-8').read()
        m = re.match(r'^(---\n)(.*?)(\n---\n)', t, re.S)
        if not m:
            continue
        # What each `resource:` line holds is read by the bundle's YAML reader
        # since 04.10.2026, in the order the lines stand in. Read as text, a
        # path in double quotes kept its quotes and one holding an apostrophe
        # kept the doubled one, so neither resolved and neither could be
        # repaired: 13 citations in Alpha_kb and 11 in Zeta_kb that day, all of
        # which resolve. Where the two counts differ the old reading stands.
        written = [str(s['resource']) for s in bundle.entries(m.group(2))
                   if s.get('resource')]
        # A line that opens its entry, `- resource: …`, is a line too: the
        # pattern did not see those until that day, twelve of them in Alpha_kb.
        if len(written) != len(re.findall(RES, m.group(2), re.M)):
            written = None
        c, k = [0], [0]
        def sub(mm):
            old = mm.group(2).strip().strip("'")
            v = written[k[0]] if written else old
            k[0] += 1
            if os.path.isfile(os.path.normpath(
                    os.path.join(os.path.dirname(f), v))):
                return mm.group(0)
            # `resolve_resource` walks `<kb_root>/OneNote` in its last-resort
            # basename branch, so it needs the path and not the name. Passing
            # `kb` made that branch walk a relative directory that never
            # exists, silently reducing the script to depth-only repair.
            nv = ma.resolve_resource(root, f, v)
            if nv != v:
                c[0] += 1
                # A value the old reading got right is written as it always
                # was. One it got wrong was quoted, and stays quoted.
                return mm.group(1) + (nv if old == v
                                      else "'%s'" % nv.replace("'", "''"))
            return mm.group(0)
        fm = re.sub(RES, sub, m.group(2), flags=re.M)
        if c[0]:
            files += 1; n += c[0]
            print('   %-52s %d repaired' % (os.path.relpath(f, root), c[0]))
            if not dry:
                open(f, 'w', encoding='utf-8').write(
                    '---\n' + fm + '\n---\n' + t[m.end():])
    print('%s: %d citations in %d concepts%s' % (kb, n, files,
          ' (dry run)' if dry else ''))

if __name__ == '__main__':
    main()
