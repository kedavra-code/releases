#!/usr/bin/env python3
"""Build a .skill package from its source under _skills/.

Skills in this vault have two representations and one source of truth:

    _skills/<name>/            the source. Tracked, diffable, edited.
    <name>.skill               the package. Built from it, installed by the app.

The health-check skill spent its first week without the first of those. It
was edited inside an ephemeral session container and only the zip was ever
written back, so the source of a skill the vault depends on lived in scratch
space and inside a binary blob: every change showed in git as a blob of a
different size, and editing it meant unzipping first. The compile skill was
created the right way on 16.08.2026 and this script makes that the rule.

Deterministic: fixed timestamps and sorted entries, so rebuilding an
unchanged source produces a byte-identical package and git sees nothing.

Usage:  python3 _scripts/build-skill.py <name> [more names...]
        python3 _scripts/build-skill.py --all
        python3 _scripts/build-skill.py --check     (verify, write nothing)
"""
import hashlib
import io
import os
import sys
import zipfile

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(VAULT, '_skills')
STAMP = (1980, 1, 1, 0, 0, 0)   # fixed: the mtime is not part of the skill


def files_of(name):
    root = os.path.join(SRC, name)
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if not d.startswith('.'))
        for f in sorted(fn):
            if f.startswith('.'):
                continue
            full = os.path.join(dp, f)
            out.append((full, os.path.relpath(full, SRC).replace(os.sep, '/')))
    return out


def build(name, check=False):
    files = files_of(name)
    if not files:
        return '%-40s NO SOURCE under _skills/' % name
    pkg = os.path.join(VAULT, name + '.skill')
    # Built in memory, never through a temp file: a device-bridge session
    # cannot delete, so a scratch file it writes is one the owner has to
    # clear by hand. --check must leave the disk untouched.
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(name + '/', STAMP)
        zi.external_attr = 0o40755 << 16
        z.writestr(zi, b'')
        for full, arc in files:
            zi = zipfile.ZipInfo(arc, STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, open(full, 'rb').read())
    new = mem.getvalue()
    old = open(pkg, 'rb').read() if os.path.exists(pkg) else b''
    same = hashlib.sha256(new).digest() == hashlib.sha256(old).digest()
    if check:
        # content comparison, not byte comparison: a package built by another
        # tool differs in framing while holding identical files
        drift = []
        if old:
            with zipfile.ZipFile(pkg) as z:
                have = {i.filename: z.read(i) for i in z.infolist()
                        if not i.filename.endswith('/')}
            want = {arc: open(full, 'rb').read() for full, arc in files}
            drift = sorted(set(have) ^ set(want)) + \
                sorted(k for k in set(have) & set(want) if have[k] != want[k])
        return '%-40s %s' % (name, 'in sync' if not drift
                             else 'DRIFTED: ' + ', '.join(drift))
    open(pkg, 'wb').write(new)
    return '%-40s %d files, %d bytes%s' % (
        name, len(files), len(new), '' if not same else ' (unchanged)')


def main():
    check = '--check' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not names or '--all' in sys.argv:
        names = sorted(d for d in os.listdir(SRC)
                       if os.path.isdir(os.path.join(SRC, d)))
    for n in names:
        print(build(n, check))


if __name__ == '__main__':
    main()
