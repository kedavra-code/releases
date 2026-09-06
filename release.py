#!/usr/bin/env python3
"""Package a tree-shipped component and keep its manifest honest.

Most things here ship as a release asset and nothing else: unus and murmur are
DMGs, and their appcast.json records a URL and a checksum. `00_Cerebrum` is
different — it is text, so the files live in the tree as well, and the archives
are that same tree packaged.

Two copies of one thing drift. That is the whole reason this script exists:

    python3 release.py check 00_Cerebrum      before pushing, and after any edit
    python3 release.py build 00_Cerebrum --build N --commit SHA
    python3 release.py publish 00_Cerebrum --build N --commit SHA

`check` repacks the tree in memory and compares the result against the sha256
the manifest advertises. If someone edits a file in the tree and pushes without
rebuilding, the manifest now describes an archive that no longer matches what a
reader can browse, and `check` is what says so. It exits 1 on drift and prints
what moved.

**The archive is the tree minus `manifest.json`.** The manifest is this
repository's record of the component, not part of the component: a reader who
unpacks the tarball should get the thing itself, with no bookkeeping file
describing where they got it. `check` enforces that rule in both directions —
a tree file missing from the archive, or an archive entry not in the tree, is a
failure whichever way it points.

Deterministic, the same way `_scripts/build-skill.py` is inside the template:
fixed timestamps, sorted entries, no uid, gid or username, and gzip's own mtime
zeroed. Repacking an unchanged tree produces byte-identical archives, so
`check` can compare checksums rather than contents, and a rebuild that changes
nothing shows up as no change at all.

Build numbers follow the same convention as the apps: a monotonic integer with
no version string to parse. Here it is **this repository's** commit count for
the component directory, so it needs no argument and cannot be typed wrong.

That count has an off-by-one to be honest about. `build` names the state being
published, and at build time the commit carrying it does not exist yet — so the
count is taken at HEAD and one is added when the component has uncommitted
changes. The dirty check ignores `manifest.json`, the same file the archive
excludes, because bookkeeping about a release is not a change to the component.
Build N is therefore the Nth commit to touch this component, which is exactly
what the tag `<component>-N` points at.

`commit` is this repository's short hash at build time. `source_commit` is
optional and records the upstream a component was extracted from — for
`00_Cerebrum` that is the private vault, which cannot be reached from here and
so cannot be computed, only passed with `--source-commit`.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
STAMP = (1980, 1, 1, 0, 0, 0)          # zip's own epoch; nothing older is representable
EPOCH = 315532800                      # 1980-01-01Z, the same instant for tar
EXCLUDE = {'manifest.json'}            # this repo's bookkeeping, not the component
SKIP = ('.DS_Store', '__pycache__', '.git', 'node_modules',
        'okf-viewer.html', 'verify-state.json')


def entries(root):
    """[(relative path, absolute path)] for every file and symlink, sorted.

    Symlinked directories are entries in their own right and are never walked
    into: the template's `.claude/skills/*` point at `_skills/*`, so following
    them would pack every skill twice and turn a two-line link into a copy.
    """
    out = []
    for dirp, dirs, files in os.walk(root):
        links = [d for d in dirs if os.path.islink(os.path.join(dirp, d))]
        dirs[:] = sorted(d for d in dirs if d not in links and d not in SKIP)
        for name in sorted(files + links):
            p = os.path.join(dirp, name)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            if any(s in rel.split('/') or rel.endswith(s) for s in SKIP):
                continue
            if rel in EXCLUDE:
                continue
            out.append((rel, p))
    return sorted(out)


def _mode(p):
    """0755 for anything the filesystem calls executable, 0644 otherwise.

    Read from the file rather than fixed, because `_scripts/*.sh` are meant to
    be runnable and git tracks exactly this one bit — so it is stable across
    clones and the archive stays deterministic.
    """
    return 0o755 if os.access(p, os.X_OK) and not os.path.islink(p) else 0o644


def build_tar(root, prefix):
    """The component as .tar.gz bytes. Symlinks stay symlinks."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.GNU_FORMAT) as t:
        for rel, p in entries(root):
            ti = t.gettarinfo(p, arcname='%s/%s' % (prefix, rel))
            ti.mtime, ti.uid, ti.gid = EPOCH, 0, 0
            ti.uname = ti.gname = ''
            if ti.issym():
                t.addfile(ti)
            else:
                ti.mode = _mode(p)
                with open(p, 'rb') as f:
                    t.addfile(ti, f)
    out = io.BytesIO()
    # mtime=0, or gzip stamps the header with now and no two builds ever match
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as g:
        g.write(raw.getvalue())
    return out.getvalue()


def build_zip(root, prefix):
    """The component as .zip bytes, for people who would rather not use tar."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, p in entries(root):
            zi = zipfile.ZipInfo('%s/%s' % (prefix, rel), STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            if os.path.islink(p):
                # Unix mode in the high half, with S_IFLNK set: unzip restores a
                # link, and the unzippers that do not get a small text file
                # holding the target, which is at least legible.
                zi.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(zi, os.readlink(p))
            else:
                zi.external_attr = _mode(p) << 16
                with open(p, 'rb') as f:
                    z.writestr(zi, f.read())
    return out.getvalue()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args],
                          capture_output=True, text=True).stdout.strip()


def next_build(component):
    """This repository's commit count for the component, counting the one coming.

    `git rev-list --count` sees only commits that exist, and the commit carrying
    this build is not one of them yet. So a component with uncommitted changes
    is one ahead of its own history — and manifest.json is excluded from that
    test for the reason it is excluded from the archive: it records the release
    rather than being part of what is released, so a rebuild that only rewrites
    checksums must not push the number up again.
    """
    n = int(git('rev-list', '--count', 'HEAD', '--', component + '/') or 0)
    dirty = [l for l in git('status', '--porcelain', '--', component + '/').splitlines()
             if not l.endswith('/manifest.json')]
    return n + 1 if dirty else n


def manifest_path(component):
    return os.path.join(ROOT, component, 'manifest.json')


def load(component):
    with open(manifest_path(component), encoding='utf-8') as f:
        return json.load(f)


def check(component):
    """Does the manifest still describe the tree? Exit 1 with the difference."""
    root = os.path.join(ROOT, component)
    if not os.path.isdir(root):
        sys.exit('no such component: %s' % component)
    m = load(component)
    bad = []

    # -z and split on NUL, not whitespace: `About me/writing-rules.md` has a
    # space in it, and splitting on whitespace reported it as two files that
    # were each missing from the other side. Found by this check's first run.
    # Tracked *and* untracked-but-not-ignored, because `git ls-files` alone
    # cannot see a stray until it has already been committed — which is how
    # `_scripts/verify-state.json`, written into the tree by a verify run and
    # swept up by `git add -A`, got past this check once and was only caught on
    # the pass after. A file that is present and not ignored will be committed
    # by the next `add -A`, so it counts as being in the tree now.
    present = set()
    for args in (['ls-files', '-z', component],
                 ['ls-files', '-z', '--others', '--exclude-standard', component]):
        for p in subprocess.run(['git', '-C', ROOT, *args],
                                capture_output=True, text=True).stdout.split('\0'):
            if p.startswith(component + '/'):
                present.add(p[len(component) + 1:])
    tracked = present
    packed = {rel for rel, _ in entries(root)}
    for rel in sorted(tracked - packed - EXCLUDE):
        bad.append('in the tree but not in the archive: %s' % rel)
    for rel in sorted(packed - tracked):
        bad.append('in the archive but not tracked in the tree: %s' % rel)

    prefix = component
    for label, data, want in (
            ('tar.gz', build_tar(root, prefix), m.get('sha256')),
            ('zip', build_zip(root, prefix), (m.get('zip') or {}).get('sha256'))):
        got = sha(data)
        if got != want:
            bad.append('%s: manifest says %s, the tree packs to %s'
                       % (label, (want or 'nothing')[:16], got[:16]))

    if bad:
        print('%s: manifest and tree disagree\n' % component)
        for b in bad:
            print('  ' + b)
        print('\nRebuild with: python3 release.py build %s' % component)
        return 1
    print('%s: manifest matches the tree (%d files, build %s)'
          % (component, len(packed), m.get('build')))
    return 0


def build(component, build_no, commit, outdir, source_commit=None):
    """Pack the tree, write both archives, and rewrite the manifest to match."""
    root = os.path.join(ROOT, component)
    if not os.path.isdir(root):
        sys.exit('no such component: %s' % component)
    m = load(component)
    build_no = build_no if build_no is not None else next_build(component)
    commit = commit or git('rev-parse', '--short', 'HEAD')

    os.makedirs(outdir, exist_ok=True)
    base = '%s-template-%s' % (component, build_no)
    tgz, zp = build_tar(root, component), build_zip(root, component)
    paths = {}
    for name, data in (('%s.tar.gz' % base, tgz), ('%s.zip' % base, zp)):
        p = os.path.join(outdir, name)
        with open(p, 'wb') as f:
            f.write(data)
        paths[name] = p

    dl = 'https://github.com/kedavra-code/releases/releases/download/%s-%s/' % (component, build_no)
    m['build'], m['commit'] = build_no, commit
    if source_commit:
        m['source_commit'] = source_commit
    m['url'], m['sha256'] = dl + '%s.tar.gz' % base, sha(tgz)
    m['zip'] = {'url': dl + '%s.zip' % base, 'sha256': sha(zp)}
    with open(manifest_path(component), 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=2)
        f.write('\n')

    print('%s build %s — %d files' % (component, build_no, len(entries(root))))
    for name, p in paths.items():
        print('  %-40s %8d bytes  %s' % (name, os.path.getsize(p), sha(open(p, 'rb').read())[:16]))
    print('  manifest.json rewritten')
    return paths


def publish(component, build_no, commit, outdir, notes, source_commit=None):
    paths = build(component, build_no, commit, outdir, source_commit)
    m = load(component)
    if check(component):
        sys.exit('refusing to publish: the manifest does not match the tree')
    tag = '%s-%s' % (component, m['build'])
    cmd = ['gh', 'release', 'create', tag, *sorted(paths.values()),
           '--repo', 'kedavra-code/releases',
           '--title', '%s template — build %s' % (component, m['build'])]
    cmd += ['--notes-file', notes] if notes else ['--notes', m.get('notes', '')]
    print('\n$ ' + ' '.join(cmd))
    subprocess.run(cmd, check=True)
    print('\nCommit the manifest and the tree together; the tag points at assets '
          'built from exactly this tree.')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('action', choices=('check', 'build', 'publish'))
    ap.add_argument('component')
    ap.add_argument('--build', type=int,
                    help='override the self-computed build number; rarely wanted')
    ap.add_argument('--commit', help="override this repo's short hash")
    ap.add_argument('--source-commit', help='upstream commit the component was cut from')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    ap.add_argument('--notes', help='path to a release-notes file, for publish')
    a = ap.parse_args()

    if a.action == 'check':
        sys.exit(check(a.component))
    if a.action == 'build':
        build(a.component, a.build, a.commit, a.out, a.source_commit)
        sys.exit(check(a.component))
    publish(a.component, a.build, a.commit, a.out, a.notes, a.source_commit)


if __name__ == '__main__':
    main()
