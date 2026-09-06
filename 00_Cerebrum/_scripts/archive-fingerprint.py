#!/usr/bin/env python3
"""Fingerprint an archive layer by content, so a replacement can be remapped.

`archive-snapshot.sh` records a whole-file md5. That answers "did this file
change" and nothing else, and it is the wrong tool the moment an archive is
re-exported: a fresh export rewrites the frontmatter timestamps of every page,
so every md5 differs even where the text is word for word identical. The
snapshot then says "10'561 pages changed", which is true and useless.

What a replacement actually needs answering is "which page in the new export
is this old page", because 875 citations across 98 concepts name old paths and
the coupling in this vault is the path. So fingerprint the *content*:

  body_md5    aggressive normalisation — frontmatter, image markers, asset
              links, URLs and GUIDs removed, whitespace collapsed. Two pages
              with the same body_md5 are the same page even if exported by a
              different tool under a different filename. This is the join key.
  strict_md5  whitespace-collapsed only. Same body_md5 but a different
              strict_md5 means the text is the same and the links or images
              changed — which is exactly what gaining the missing attachments
              looks like.
  head_md5    md5 of the first 120 characters of the normalised body.

              This column held that text in clear until 22.08.2026, so a human
              could eyeball a proposed match without opening two files. That
              was a hole straight through the boundary the vault relies on:
              `OneNote/` is gitignored precisely because the archive is
              sensitive, and this file is tracked, so 2'592 rows of 120
              characters of raw page text went into git and on to GitHub with
              every snapshot. It was found when a page headed `Mail
              Zertifikate` turned out to carry a certificate passphrase in
              its first 120 characters, and therefore in commit ee0a390.
              The token was the thing noticed, not the thing that was there.

              A hash serves the purpose the column exists for. Remapping a
              re-export asks whether two pages have the same opening, which
              is an equality test, and equality survives hashing. Reading the
              opening was a convenience, and the convenience is what leaked.

Written 15.08.2026, before replacing the Alpha archive: 10'561 pages, 1'192 of
them with a byte-identical twin in 529 groups, 3'335 unresolved image markers
and no `_assets/` at all.

Usage:
  python3 _scripts/archive-fingerprint.py <KB>
      Writes <KB>/_snapshots/<layer>-<date>.fingerprint.tsv and .citations.tsv

  python3 _scripts/archive-fingerprint.py <KB> --match <old.fingerprint.tsv> <new dir>
      Matches the old fingerprint against a new export and prints, per old
      page: SAME / MOVED / EDITED / GONE / SPLIT, with the new path. Cited
      pages are reported first and marked, because those are the ones whose
      loss breaks a concept.
"""
import collections
import datetime
import glob
import hashlib
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
IMG_MARKER = re.compile(r'🖼\s*image:\s*`[^`]*`')
MD_IMAGE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
MD_LINK = re.compile(r'\[([^\]]{1,120})\]\([^)]*\)')
URL = re.compile(r'https?://\S+')
GUID = re.compile(r'\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                  r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?')
ASSET = re.compile(r'_assets/\S+')
# A page with less than this much normalised text is too thin to identify by
# content: dozens of year dividers and empty agendas would all collide on one
# hash and every one of them would look like a match for every other.
MIN_BODY = 40


def field(fm, key):
    m = re.search(r'^%s:\s*(.+)$' % key, fm, re.M)
    return m.group(1).strip().strip('"\'') if m else ''


def fingerprint(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    m = FM.match(raw)
    fm, body = (m.group(1), raw[m.end():]) if m else ('', raw)
    strict = re.sub(r'\s+', ' ', body).strip()
    soft = MD_IMAGE.sub('', body)
    soft = IMG_MARKER.sub('', soft)
    soft = ASSET.sub('', soft)
    soft = MD_LINK.sub(r'\1', soft)
    soft = URL.sub('', soft)
    soft = GUID.sub('', soft)
    soft = re.sub(r'\s+', ' ', soft).strip()
    return {
        'body_md5': hashlib.md5(soft.encode()).hexdigest() if len(soft) >= MIN_BODY else '',
        'strict_md5': hashlib.md5(strict.encode()).hexdigest(),
        'chars': len(soft),
        'bytes': os.path.getsize(path),
        'title': field(fm, 'title').replace('\t', ' '),
        'date': (field(fm, 'Meeting Date') or field(fm, 'created')
                 or field(fm, 'modified'))[:10],
        'head_md5': hashlib.md5(soft[:120].encode('utf-8')).hexdigest(),
    }


def pages(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '_assets']
        for n in sorted(fn):
            if n.endswith('.md') and n != '_index.md':
                out.append(os.path.join(dp, n))
    return sorted(out)


def citations(kb):
    """Every citation into this KB's archive: concept, source id, path."""
    root = os.path.join(VAULT, kb)
    arch = os.path.abspath(os.path.join(root, 'OneNote'))
    out = []
    for f in sorted(glob.glob(os.path.join(VAULT, '*_kb', 'Wiki', '**', '*.md'),
                              recursive=True)):
        if os.path.basename(f) in ('index.md', 'log.md') or '_to_delete' in f:
            continue
        m = FM.match(open(f, encoding='utf-8').read())
        if not m:
            continue
        for entry in re.finditer(
                r'^\s*- id:\s*(\S+)\s*\n(?:\s+\w+:.*\n)*?\s*resource:\s*\'?([^\'\n]+?)\'?\s*$',
                m.group(1), re.M):
            sid, res = entry.group(1), entry.group(2)
            p = os.path.abspath(os.path.normpath(
                os.path.join(os.path.dirname(f), res)))
            if p.startswith(arch):
                out.append((os.path.relpath(f, VAULT), sid,
                            os.path.relpath(p, root), res))
    return out


def do_fingerprint(kb):
    root = os.path.join(VAULT, kb)
    snaps = os.path.join(root, '_snapshots')
    os.makedirs(snaps, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    layers = [d for d in sorted(os.listdir(os.path.join(root, 'OneNote')))
              if os.path.isdir(os.path.join(root, 'OneNote', d))]
    cites = citations(kb)
    cited_paths = collections.Counter(c[2] for c in cites)

    cpath = os.path.join(snaps, '%s.citations.tsv' % stamp)
    with open(cpath, 'w', encoding='utf-8') as fh:
        fh.write('concept\tsource_id\tarchive_path\tresource_as_written\n')
        for c in cites:
            fh.write('\t'.join(c) + '\n')

    total = 0
    for layer in layers:
        ps = pages(os.path.join(root, 'OneNote', layer))
        out = os.path.join(snaps, '%s-%s.fingerprint.tsv'
                           % (re.sub(r'\W+', '-', layer).strip('-').lower(), stamp))
        dupes = collections.defaultdict(list)
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write('path\tbody_md5\tstrict_md5\tchars\tbytes\tcited\t'
                     'date\ttitle\thead_md5\n')
            for p in ps:
                fp = fingerprint(p)
                rel = os.path.relpath(p, root)
                if fp['body_md5']:
                    dupes[fp['body_md5']].append(rel)
                fh.write('%s\t%s\t%s\t%d\t%d\t%d\t%s\t%s\t%s\n'
                         % (rel, fp['body_md5'], fp['strict_md5'], fp['chars'],
                            fp['bytes'], cited_paths.get(rel, 0), fp['date'],
                            fp['title'], fp['head_md5']))
        d = {k: v for k, v in dupes.items() if len(v) > 1}
        print('%-22s %5d pages  %4d cited  %4d in %3d duplicate groups  -> %s'
              % (layer, len(ps), sum(cited_paths.get(os.path.relpath(p, root), 0) > 0
                                     for p in ps),
                 sum(len(v) for v in d.values()), len(d), os.path.basename(out)))
        total += len(ps)
    print('%s: %d pages fingerprinted, %d citations recorded -> %s'
          % (kb, total, len(cites), os.path.basename(cpath)))


def do_match(kb, oldfile, newdir):
    """Match an old fingerprint against a new export, key by key.

    The first version of this reported 1'217 SPLIT and 422 GONE against the
    archive it had just fingerprinted — a self-test that should have been
    100 per cent SAME. Both were the matcher's fault, not the archive's, and
    both would have been read as damage on the real swap:

    SPLIT was the duplicate groups. A body hash held by thirteen pages cannot
    identify one of them, but if the old path is itself among the holders the
    answer is not ambiguous at all — it is that page. And when a re-export
    deduplicates, every member of the old group legitimately maps to the one
    survivor. Ambiguity only remains when the old path is gone *and* several
    candidates survive.

    GONE was the pages below the 40-character floor: year dividers, empty
    agendas, title-only stubs. They have no content to hash, so they need a
    different key — the path, then the title and date. A thin page that keeps
    its name is not missing.
    """
    root = os.path.join(VAULT, kb)
    old = []
    with open(oldfile, encoding='utf-8') as fh:
        hdr = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            old.append(dict(zip(hdr, line.rstrip('\n').split('\t'))))
    new_by_body = collections.defaultdict(list)
    new_by_titledate = collections.defaultdict(list)
    new_strict, new_paths = {}, set()
    for p in pages(newdir):
        fp = fingerprint(p)
        rel = os.path.relpath(p, root)
        if fp['body_md5']:
            new_by_body[fp['body_md5']].append(rel)
        if fp['title'] or fp['date']:
            new_by_titledate[(fp['title'], fp['date'])].append(rel)
        new_strict[rel] = fp['strict_md5']
        new_paths.add(rel)
    print('# old pages: %d, new pages: %d' % (len(old), len(new_paths)))
    print('# status\tcited\told_path\tnew_path')
    tally = collections.Counter()
    for o in sorted(old, key=lambda r: (-int(r.get('cited') or 0), r['path'])):
        cited = o.get('cited') or '0'
        hits = new_by_body.get(o['body_md5'], []) if o['body_md5'] else []
        if o['path'] in (hits or new_paths):
            # the path survived; only the text can have changed
            st = ('SAME' if new_strict[o['path']] == o['strict_md5']
                  else 'EDITED')
            tgt = o['path']
        elif len(hits) == 1:
            st, tgt = 'MOVED', hits[0]
        elif len(hits) > 1:
            st, tgt = 'AMBIGUOUS', ' | '.join(sorted(hits)[:4])
        else:
            td = new_by_titledate.get((o.get('title', ''), o.get('date', '')), [])
            if len(td) == 1:
                st, tgt = 'MOVED', td[0]
            elif len(td) > 1:
                st, tgt = 'AMBIGUOUS', ' | '.join(sorted(td)[:4])
            else:
                st, tgt = 'GONE', ''
        tally[(st, cited != '0')] += 1
        print('%s\t%s\t%s\t%s' % (st, cited, o['path'], tgt))
    added = new_paths - {o['path'] for o in old}
    print('\n# summary (cited pages are the ones that break a concept)')
    for st in ('SAME', 'EDITED', 'MOVED', 'AMBIGUOUS', 'GONE'):
        c, u = tally[(st, True)], tally[(st, False)]
        if c or u:
            print('#   %-9s %5d total, %4d of them cited' % (st, c + u, c))
    print('#   %-9s %5d' % ('NEW', len(added)))


def main():
    kb = sys.argv[1]
    if '--match' in sys.argv:
        i = sys.argv.index('--match')
        do_match(kb, sys.argv[i + 1], sys.argv[i + 2])
    else:
        do_fingerprint(kb)


if __name__ == '__main__':
    main()
