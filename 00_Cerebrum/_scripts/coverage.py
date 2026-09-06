#!/usr/bin/env python3
"""Archive coverage, measured rather than asserted.

Until 15.08.2026 coverage was reported as "is there a concept for this
scope", which is a question about the bundle, not about the archive. It said
Alpha was fully compiled while 10'122 of 10'561 pages had never been cited by
anything. A scope can hold a concept and still be unread; the only honest
measure is the fraction of its pages that some concept actually cites,
because in this vault an uncited page contributed nothing to the wiki.

This script writes <KB>/COVERAGE.md, a generated table of pages against
cited pages per archive scope, and records the bundle state it was measured
from so verify.py can tell when it has gone stale.

A page counts as covered when it is either
  cited      — some concept lists it in sources[].resource, or
  read-nil   — listed in <KB>/_COMPILE-LEDGER.md as read with nothing citable
so a compile pass that reads an empty agenda page is not punished for it,
and the ledger stays the honest record of what was actually opened.

Usage:  python3 _scripts/coverage.py [KnowledgeBase ...]   (default: all)
        python3 _scripts/coverage.py --check               (exit 1 if stale)
"""
import glob
import json
import os
import re
import sys
import collections
import datetime

try:
    import yaml
except ImportError:
    sys.exit('coverage.py needs PyYAML: python3 -m pip install --user pyyaml')

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
FENCE = re.compile(r'```.*?```', re.S)
LEDGER_PAGE = re.compile(r'^\s*[-*]\s+`([^`]+)`', re.M)


def discover():
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))


def archive_layer(kb):
    """The KB's archive-layer directory name.

    `OneNote` for the three employer bundles, which is where the name came
    from. A knowledge base whose bulk corpus arrived from somewhere else says
    so in its own `assertions.yaml` — `Epsilon_kb` declares `Raw`, because its
    corpus is a Confluence space export the owner dropped into the drop zone
    rather than a OneNote export. Hardcoding `OneNote` meant this script and
    `plan-batches.py` could not see such a bundle at all, so its coverage was
    unmeasurable and "compiled" could only ever be asserted — which is the one
    thing this script exists to prevent.
    """
    p = os.path.join(VAULT, kb, 'assertions.yaml')
    if os.path.exists(p):
        try:
            A = yaml.safe_load(open(p, encoding='utf-8')) or {}
            if A.get('archive_layer'):
                return str(A['archive_layer'])
        except Exception:
            pass
    return 'OneNote'


def archive_roots(kb):
    """Every immediate subfolder of the KB's archive layer is a chapter."""
    base = os.path.join(VAULT, kb, archive_layer(kb))
    if not os.path.isdir(base):
        return []
    return [os.path.join(base, d) for d in sorted(os.listdir(base))
            if os.path.isdir(os.path.join(base, d))
            and not d.startswith('_')]


def pages(root):
    out = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '_assets']
        for n in fn:
            if n.endswith('.md') and n != '_index.md':
                out.add(os.path.abspath(os.path.join(dp, n)))
    return out


def cited(kb):
    """Parse frontmatter with YAML, exactly as verify.py does.

    A regex over resource: lines disagreed with verify.py by one citation on
    its first run (15.08.2026), because fenced illustrative examples look
    like real entries. Two measurements of the same quantity that disagree
    is the drift this vault forbids, so both now count the same way and the
    staleness check in verify.py can compare them directly.
    """
    out, n_concepts, n_cites = set(), 0, 0
    for f in sorted(glob.glob(os.path.join(VAULT, kb, 'Wiki', '**', '*.md'),
                              recursive=True)):
        if os.path.basename(f) in ('index.md', 'log.md') or '_to_delete' in f:
            continue
        text = FENCE.sub('', open(f, encoding='utf-8').read())
        m = FM.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            continue
        n_concepts += 1
        d = os.path.dirname(f)
        for src in (fm.get('sources') or []):
            if not isinstance(src, dict):
                continue
            r = src.get('resource')
            if not r:
                continue
            n_cites += 1
            out.add(os.path.abspath(os.path.normpath(os.path.join(d, str(r)))))
    return out, n_concepts, n_cites


def ledger(kb):
    """Pages recorded as read with nothing citable."""
    p = os.path.join(VAULT, kb, '_COMPILE-LEDGER.md')
    if not os.path.exists(p):
        return set()
    base = os.path.join(VAULT, kb)
    return {os.path.abspath(os.path.join(base, m))
            for m in LEDGER_PAGE.findall(open(p, encoding='utf-8').read())}


def scope_of(page, root):
    rel = os.path.relpath(page, root).split(os.sep)
    return rel[0] if len(rel) > 1 else '(root)'


def measure(kb):
    cit, n_concepts, n_cites = cited(kb)
    nil = ledger(kb)
    chapters = {}
    for root in archive_roots(kb):
        allp = pages(root)
        if not allp:
            continue
        tot = collections.Counter()
        hit = collections.Counter()
        red = collections.Counter()
        for p in allp:
            s = scope_of(p, root)
            tot[s] += 1
            if p in cit:
                hit[s] += 1
            elif p in nil:
                red[s] += 1
        chapters[os.path.basename(root)] = (tot, hit, red)
    return chapters, n_concepts, n_cites


def render(kb, chapters, n_concepts, n_cites, stamp):
    L = ['# Archive coverage — %s' % kb, '',
         '**Generated, not authored. Do not edit this file.** Written by '
         '`_scripts/coverage.py`; regenerate rather than correct. '
         '`verify.py` fails when it goes stale.', '',
         'Coverage is the share of archive pages that some concept actually '
         'cites, plus pages the compile ledger records as read with nothing '
         'citable. It is not "does a concept exist for this scope" — that '
         'question is about the bundle, and it can report a bundle fully '
         'compiled while most of its pages have never been read.',
         '',
         'Measured **%s** from %d concepts and %d citations.'
         % (stamp, n_concepts, n_cites), '']
    gt = gh = gr = 0
    for chap, (tot, hit, red) in sorted(chapters.items()):
        L += ['## %s' % chap, '',
              '| Scope | Pages | Cited | Read, nothing citable | Covered |',
              '|---|---:|---:|---:|---:|']
        # Break ties on the scope name. Sorting on the count alone left the
        # order of equal-sized scopes to set-iteration order, which Python
        # randomises per process: Alpha_kb/COVERAGE.md swapped two identical
        # rows between runs with no number changing. A derived file that
        # churns teaches a reader to ignore diffs on derived files.
        for s, n in sorted(tot.items(), key=lambda kv: (-kv[1], kv[0])):
            c, r = hit.get(s, 0), red.get(s, 0)
            L.append('| %s | %d | %d | %d | %.1f%% |'
                     % (s, n, c, r, 100.0 * (c + r) / n))
            gt += n
            gh += c
            gr += r
        st, sh, sr = sum(tot.values()), sum(hit.values()), sum(red.values())
        L += ['| **%s total** | **%d** | **%d** | **%d** | **%.1f%%** |'
              % (chap, st, sh, sr, 100.0 * (sh + sr) / st), '']
    if gt:
        L += ['**Knowledge base total: %d pages, %d cited, %d read-nil, '
              '%.1f%% covered.**' % (gt, gh, gr, 100.0 * (gh + gr) / gt), '']
    return '\n'.join(L)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    check = '--check' in sys.argv
    stale = []
    for kb in (args or discover()):
        chapters, n_concepts, n_cites = measure(kb)
        if not chapters:
            # No archive layer at all is a knowledge base that never had one,
            # and it has no coverage table to keep. An archive folder that is
            # present but empty is different: the export has been deleted
            # pending a replacement, and skipping here would leave the last
            # table on disk describing pages that no longer exist while
            # verify.py went on failing it as stale — a stale number nobody
            # can refresh. Write the honest empty table instead. Alpha,
            # 16.08.2026.
            arch = os.path.join(VAULT, kb, archive_layer(kb))
            if not os.path.isdir(arch):
                continue
            out = os.path.join(VAULT, kb, 'COVERAGE.md')
            state = os.path.join(VAULT, kb, '.coverage-state.json')
            now = {'concepts': n_concepts, 'citations': n_cites}
            if check:
                old = {}
                if os.path.exists(state):
                    try:
                        old = json.load(open(state, encoding='utf-8'))
                    except Exception:
                        old = {}
                if not os.path.exists(out) or old != now:
                    stale.append(kb)
                continue
            open(out, 'w', encoding='utf-8').write('\n'.join([
                '# Archive coverage — %s' % kb, '',
                '**Generated, not authored. Do not edit this file.** Written '
                'by `_scripts/coverage.py`; regenerate rather than correct.',
                '',
                '**The archive layer is empty.** The export was deleted '
                'pending a complete replacement, so there is nothing to '
                'measure coverage against. This is not nought per cent of a '
                'corpus; it is the absence of one. Regenerate once the new '
                'export is in place.', '',
                'Measured **%s** from %d concepts and %d citations.'
                % (datetime.datetime.now(datetime.timezone.utc)
                   .strftime('%d.%m.%Y, %H:%M UTC'), n_concepts, n_cites),
                '']))
            json.dump(now, open(state, 'w', encoding='utf-8'))
            print('%-14s archive layer empty; wrote the empty table'
                  % kb)
            continue
        out = os.path.join(VAULT, kb, 'COVERAGE.md')
        state = os.path.join(VAULT, kb, '.coverage-state.json')
        now = {'concepts': n_concepts, 'citations': n_cites}
        if check:
            old = {}
            if os.path.exists(state):
                try:
                    old = json.load(open(state, encoding='utf-8'))
                except Exception:
                    old = {}
            if not os.path.exists(out) or old != now:
                stale.append('%s: COVERAGE.md missing or stale (measured %s, '
                             'bundle now %s)' % (kb, old or 'never', now))
            continue
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            '%d.%m.%Y, %H:%M UTC')
        body = render(kb, chapters, n_concepts, n_cites, stamp)
        # Only rewrite when the measurement itself moved. Re-running on an
        # unchanged bundle used to bump the timestamp alone, which shows up
        # as a modified file with a one-line diff and trains a reader to
        # ignore diffs on derived files. The stamp says when the numbers
        # were last true, not when the script last ran.
        strip = lambda t: re.sub(r'^Measured \*\*.*?\*\* ', '', t, flags=re.M)
        if os.path.exists(out) and strip(open(out, encoding='utf-8').read()) \
                == strip(body):
            print('%-12s unchanged' % kb)
            json.dump(now, open(state, 'w', encoding='utf-8'))
            continue
        open(out, 'w', encoding='utf-8').write(body)
        json.dump(now, open(state, 'w', encoding='utf-8'))
        tot = sum(sum(t.values()) for t, _, _ in chapters.values())
        cov = sum(sum(h.values()) + sum(r.values())
                  for _, h, r in chapters.values())
        print('%-12s %6d pages, %5d covered, %5.1f%%  -> %s'
              % (kb, tot, cov, 100.0 * cov / tot,
                 os.path.relpath(out, VAULT)))
    if check and stale:
        for s in stale:
            print('STALE  ' + s, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
