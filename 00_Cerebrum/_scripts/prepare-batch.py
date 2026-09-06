#!/usr/bin/env python3
"""Mechanical pre-filter for a compile batch, with novelty collapsing.

Reading the archive was never the expensive part of a compile: in the opus
batch of 15.08.2026, 55 pages were 35k tokens of the 275k spent. The rest
went on per-agent orientation and the concept-writing loop. So the way to
compile 10'561 pages affordably is to strip what no model needs to read,
pack many pages into one extraction pass, and keep the expensive model for
synthesis.

This script emits one packed text file per batch: every page in the batch,
frontmatter reduced to what matters, Teams and OneNote boilerplate removed,
byte-identical bodies collapsed to one copy with the duplicates named. Each
page keeps an explicit PAGE header carrying the path a concept must cite, so
the extractor can never invent a citation and never lose one.

Novelty collapsing is the second saving and the larger one. These archives
are rolling notes: measured 15.08.2026, only 14 per cent of lines in the Alpha
notebook and 36 per cent in the remaining Beta and Gamma pages had never
appeared anywhere before. Reading every page whole means reading the same
line an average of three to seven times. So a page is emitted with its novel
lines in full and its carried lines collapsed to a marker naming where they
came from. The extractor still sees every page and still sees what is new on
it, and the marker preserves the one thing the repetition actually carries:
that an item was carried forward again.

Lines already cited by a concept count as seen, so a compile pass never
re-reads what the bundle already holds.

Usage:  python3 _scripts/prepare-batch.py <KB> <batch-id> [more ids...]
        python3 _scripts/prepare-batch.py <KB> --all
        python3 _scripts/prepare-batch.py <KB> --all --no-collapse
"""
import hashlib
import json
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOILER = re.compile(
    r'(Microsoft Teams|Join the meeting|Meeting-?ID|Passcode|Kenncode|dial-?in|'
    r'teams\.microsoft\.com|Besprechung beitreten|An Besprechung teilnehmen|'
    r'Weitere Infos|Learn More|Help|Options|Anruf-ID|Für Organisatoren|'
    r'Datenschutz|Legal|^\s*_{4,}\s*$|^\s*-{4,}\s*$|^\s*\|?\s*$)', re.I)
KEEP_FM = ('title', 'date', 'created', 'modified', 'author')
# A SharePoint URL or a OneNote GUID is 100-200 characters that no concept
# ever quotes, and they drag the whole file to ~2.2 characters per token.
# The fact that a link was present is worth keeping; its target is not.
URL = re.compile(r'https?://\S+')
# Below this many characters of genuinely novel text, a collapsed page is
# not worth the risk: it is emitted whole instead. See the note in main().
NOVEL_FLOOR = 60
GUID = re.compile(r'\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                  r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?')
MDLINK = re.compile(r'\[([^\]]{1,80})\]\(https?://[^)]+\)')


def clean(path, kb_root):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    m = re.match(r'^---\n(.*?)\n---\n', raw, re.S)
    fm, body = ({}, raw)
    if m:
        body = raw[m.end():]
        for line in m.group(1).split('\n'):
            k, _, v = line.partition(':')
            if k.strip() in KEEP_FM and v.strip():
                fm[k.strip()] = v.strip().strip('"')
    body = MDLINK.sub(r'\1<link>', body)
    body = URL.sub('<link>', body)
    body = GUID.sub('<id>', body)
    lines = [l.rstrip() for l in body.split('\n') if not BOILER.search(l)]
    out, blank = [], 0
    for l in lines:
        if not l.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(l)
    return fm, '\n'.join(out).strip()


def seen_from_cited(kb_root):
    """Lines already inside the bundle's cited pages: never re-read them."""
    import glob as _g
    fmre = re.compile(r'^---\n(.*?)\n---\n', re.S)
    fence = re.compile(r'```.*?```', re.S)
    cited, seen = set(), {}
    for f in _g.glob(os.path.join(kb_root, 'Wiki', '**', '*.md'), recursive=True):
        if os.path.basename(f) in ('index.md', 'log.md') or '_to_delete' in f:
            continue
        t = fence.sub('', open(f, encoding='utf-8').read())
        m = fmre.match(t)
        if not m:
            continue
        for mm in re.finditer(r"resource:\s*'?([^'\n]+?)'?\s*$", m.group(1), re.M):
            cited.add(os.path.abspath(os.path.normpath(
                os.path.join(os.path.dirname(f), mm.group(1)))))
    for p in cited:
        if not os.path.isfile(p):
            continue  # a citation may point at a directory; only files hold lines
        b = re.sub(r'^---\n.*?\n---\n', '', open(p, encoding='utf-8',
                   errors='ignore').read(), flags=re.S)
        for l in b.split('\n'):
            l = l.strip()
            if l and not BOILER.search(l):
                seen.setdefault(hashlib.md5(l.encode()).hexdigest(),
                                os.path.basename(p))
    return seen


def main():
    kb = sys.argv[1]
    kb_root = os.path.join(VAULT, kb)
    ex = os.path.join(kb_root, '_extractions')
    ids = [a for a in sys.argv[2:] if not a.startswith('--')]
    # Test the flag on argv, not on `ids`. `ids` is built one line above by
    # dropping every `--` argument, so `ids == ['--all']` could never be true:
    # `--all` packed nothing, ran zero iterations and exited 0, which is the
    # worst shape a failure can take. Found 31.08.2026, when it silently
    # packed none of Epsilon_kb's ten batches.
    if '--all' in sys.argv:
        plan = json.load(open(os.path.join(ex, '_BATCHES.json'), encoding='utf-8'))
        ids = [b['id'] for b in plan]
    # A manifest from a superseded plan stays on disk — the bridge forbids
    # deletion — and packing one re-reads pages that are already compiled.
    # It cost a whole batch on 15.08.2026: `BBHO-01` was packed from a stale
    # manifest and 38 of its 55 pages came back "nothing novel", which is the
    # tell. Refuse anything the current plan does not list.
    plan_ids = {b['id'] for b in json.load(
        open(os.path.join(ex, '_BATCHES.json'), encoding='utf-8'))}
    stale = [b for b in ids if b not in plan_ids]
    if stale:
        sys.exit('not in the current _BATCHES.json: %s\n'
                 'Re-run plan-batches.py, or pass --force if you mean it.'
                 % ', '.join(stale) if '--force' not in sys.argv else 0)
    collapse = '--no-collapse' not in sys.argv
    seen = seen_from_cited(kb_root) if collapse else {}
    for bid in ids:
        man = os.path.join(ex, '_batch-%s.txt' % bid)
        files = [l.strip() for l in open(man, encoding='utf-8') if l.strip()]
        chunks, dupes, kept, bytes_in, bytes_out = [], 0, 0, 0, 0
        fully_collapsed = 0
        seen_body = {}
        for rel in files:
            p = os.path.join(kb_root, rel)
            bytes_in += os.path.getsize(p)
            fm, body = clean(p, kb_root)
            h = hashlib.md5(body.encode()).hexdigest()
            if h in seen_body and body:
                dupes += 1
                chunks.append('=== PAGE %s\n=== DUPLICATE-OF %s\n' % (rel, seen_body[h]))
                continue
            seen_body[h] = rel
            seen_bodies_marker = None
            kept += 1
            head = ' | '.join('%s: %s' % (k, v) for k, v in fm.items())
            if collapse and body:
                keep, run, src = [], 0, None
                for l in body.split('\n'):
                    ls = l.strip()
                    h2 = hashlib.md5(ls.encode()).hexdigest() if ls else None
                    if ls and h2 in seen:
                        run += 1
                        src = src or seen[h2]
                        continue
                    if run:
                        keep.append('    [+%d lines carried, first in %s]'
                                    % (run, src))
                        run, src = 0, None
                    keep.append(l)
                    if ls:
                        seen[h2] = os.path.basename(rel)
                if run:
                    keep.append('    [+%d lines carried, first in %s]' % (run, src))
                collapsed = '\n'.join(keep).strip()
                # A page whose every line collapsed arrives as nothing but a
                # marker, and an agent that cannot read a page records it as
                # carrying nothing citable — which the ledger then counts as
                # covered. That is the assertion-for-measurement failure the
                # coverage rewrite existed to kill, reintroduced one layer
                # down. Twenty pages of the wave of 15.08.2026 arrived this
                # way, most of them because seen_from_cited() keys lines by
                # basename and the archive has namesakes in other sections.
                # A page must never arrive empty: below the floor, emit it
                # whole and pay the tokens.
                novel = re.sub(r'\[\+\d+ lines carried[^\]]*\]', '', collapsed)
                if len(novel.strip()) < NOVEL_FLOOR:
                    fully_collapsed += 1
                else:
                    body = collapsed
            bytes_out += len(body)
            chunks.append('=== PAGE %s\n=== META %s\n%s\n'
                          % (rel, head or '(none)', body if body else '(empty)'))
        out = os.path.join(ex, '_packed-%s%s.txt'
                           % (bid, '' if collapse else '-nocollapse'))
        open(out, 'w', encoding='utf-8').write(
            ('# Packed batch %s — %d pages, %d unique, %d duplicates\n'
             '# Cite the path on each PAGE line exactly.\n\n' %
             (bid, len(files), kept, dupes)) + '\n'.join(chunks))
        print('%-12s %3d pages  %3d unique  %3d dup  %6.1f KB -> %6.1f KB  '
              '(%.0f%% saved)%s'
              % (bid, len(files), kept, dupes, bytes_in / 1024, bytes_out / 1024,
                 100 * (1 - bytes_out / max(bytes_in, 1)),
                 '  [%d sent whole: nothing novel]' % fully_collapsed
                 if fully_collapsed else ''))


if __name__ == '__main__':
    main()
