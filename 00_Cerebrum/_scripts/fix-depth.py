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
import os, re, sys, glob, importlib.util
VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location(
    'ma', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'merge-appends.py'))
ma = importlib.util.module_from_spec(_s); _s.loader.exec_module(ma)

def main():
    kb = sys.argv[1]; dry = '--dry-run' in sys.argv
    root = os.path.join(VAULT, kb); n = files = 0
    for f in sorted(glob.glob(os.path.join(root, 'Wiki', '**', '*.md'),
                              recursive=True)):
        if os.path.basename(f) in ('index.md', 'log.md') or '_to_delete' in f:
            continue
        t = open(f, encoding='utf-8').read()
        m = re.match(r'^(---\n)(.*?)(\n---\n)', t, re.S)
        if not m:
            continue
        c = [0]
        def sub(mm):
            v = mm.group(2).strip().strip("'")
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
                return mm.group(1) + nv
            return mm.group(0)
        fm = re.sub(r'^(\s*resource:\s*)(.+)$', sub, m.group(2), flags=re.M)
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
