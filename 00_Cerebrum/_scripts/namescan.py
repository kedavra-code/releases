#!/usr/bin/env python3
"""Calibrated name scan for the 00_Cerebrum vault.

The mentioned-but-never-written scan was wrong by an order of magnitude
twice: Alex Fischer reported at 153 archive pages and standing on 198
(AI-2026-08-09-22), Mila Roth reported at 11 and standing on 200+
(AI-2026-08-10-1). Each fix taught the scan one more spelling family, and
each family revealed the next. This script replaces the enumeration with a
measurement.

The rule it encodes: an estimator that feeds decisions gets calibrated
against knowns before its numbers are trusted. The knowns are the people who
already have concepts. For each, the archive is scanned under every spelling
family, and the gap between the full-name count and the union is the
measured undercount. Counts for unknown names are then presented as a floor
times the calibrated multiplier, never as a scope.

Spelling families, per person:
  full      "Firstname Lastname" (what the old scan counted; the floor)
  outlook   "Lastname, Firstname"
  initial   "F. Lastname"
  first     "Firstname" alone; counted only when the first name is unique
            among known people of the same chapter, and labelled ambiguous
            regardless, because unknown people share first names too
  alias     nicknames and Kuerzel from assertions.yaml only. An unmapped
            shorthand is an interview question, never a count. That is the
            proven-Kuerzel rule of AI-2026-08-10-1.

Usage:
  python3 _scripts/namescan.py --tree Gamma_kb --cache          # pass 1
  python3 _scripts/namescan.py --tree Beta_kb --cache --report    # pass 2
  python3 _scripts/namescan.py --candidates "Alfred Brunner, Sam Weber"

--tree limits one invocation to one knowledge base so a pass fits inside a
bridge session's 45-second command cap; --cache accumulates passes in
_scripts/.namescan-cache.json (derived, gitignored). Run without --tree to
scan every knowledge base that has an archive. Alpha was excluded from the
default until 15.08.2026 on the grounds that it had no people concepts; it
now has 29, and leaving it out made the calibration blind to the largest
archive in the vault. It is 10'561 files, so a bridge session should still
pass --tree Alpha_kb --cache on its own.

The trees are named for the knowledge bases and are discovered on disk. They
were named for the pre-split chapters until 15.08.2026, which is how
Zeta_kb came to be unscannable.

Since the three-way split of 15.08.2026 each tree is a separate knowledge
base with its own Wiki, its own assertions.yaml and its own alias map. The
calibration still pools them, because a multiplier measured on 83 people
is worth more than three measured on 30, and the spelling families behave the
same way whichever employer the person worked for. What does not pool is the
alias map: 'Beni' is three different people across the employer bases, so an
alias is only ever applied inside the knowledge base that declares it.
"""
import argparse
import json
import os
import re
import importlib.util as _ilu
import statistics
import sys

try:
    import yaml
except ImportError:
    sys.exit('namescan.py needs PyYAML: python3 -m pip install --user pyyaml')

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_coverage():
    """`coverage.py` as a module, so `archive_layer` has one definition.

    Same loader as `verify.py`'s, deliberately: copying the key's default
    would give a vault two places that decide where a bundle's archive lives,
    and the next edit would land in only one of them.
    """
    spec = _ilu.spec_from_file_location(
        'cerebrum_coverage', os.path.join(VAULT, '_scripts', 'coverage.py'))
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def discover():
    """{knowledge base: archive root}, found on disk rather than hard-coded.

    This was once a literal map keyed on chapter names. Those were the
    chapter directories inside a combined bundle,
    and they outlived the three-way split by a day: the map still named them
    after the folder was gone, which meant Zeta_kb could not be scanned at
    all and the health check fell back to hand-counting. That fallback moved
    two counts on an unchanged bundle, which is the third hand-rolled count in
    this vault to come out wrong (AI-2026-08-15-5).

    The old keys are not kept as aliases. A dead name kept alive for
    convenience is exactly what left `Combined_kb` standing in six live
    places through two green health checks; the rename is the whole point.

    A knowledge base is a directory with a CLAUDE.md and an archive layer. The
    layer's folder name comes from `coverage.py`'s `archive_layer`, which reads
    the knowledge base's own `assertions.yaml` and falls back to `OneNote`, so
    the two scripts cannot disagree about where an archive lives. Hardcoding
    the folder name here is how a bundle whose corpus arrived from somewhere
    else becomes invisible to one script while another measures it fine.

    Its archive root is the single directory inside that layer, or the layer
    itself if it holds more than one.
    """
    cov = _load_coverage()
    out = {}
    for kb in sorted(os.listdir(VAULT)):
        base = os.path.join(VAULT, kb)
        layer = cov.archive_layer(kb)
        arch = os.path.join(base, layer)
        if not (os.path.exists(os.path.join(base, 'CLAUDE.md'))
                and os.path.isdir(arch)):
            continue
        subs = [d for d in sorted(os.listdir(arch))
                if os.path.isdir(os.path.join(arch, d))]
        out[kb] = ('%s/%s/%s' % (kb, layer, subs[0])) if len(subs) == 1 \
            else '%s/%s' % (kb, layer)
    return out


TREES = discover()
KBS = {k: k for k in TREES}
CACHE = os.path.join(VAULT, '_scripts', '.namescan-cache.json')
TITLE = re.compile(r'^title:\s*(.+)$', re.M)


def known_people():
    """People with concepts: {stem: (first, last, chapter-or-None)}.

    Since the split of 15.08.2026 the chapter is which knowledge base the
    concept lives in, not which subdirectory it sits in. The three concepts
    that span all three employers live in Alpha_kb but are not Alpha-only, so they
    are marked chapter=None and scanned against every tree; without that,
    the vault owner would be counted in one archive out of three.
    """
    # Concept stems that belong to no single knowledge base and must be
    # scanned against every archive. Without this a person who appears in
    # several archives is counted in only the one their concept lives in.
    SPANNING = set()
    out = {}
    for chapter, kb in KBS.items():
        root = os.path.join(VAULT, kb, 'Wiki', 'people')
        if not os.path.isdir(root):
            continue
        for dirp, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith('.md') or fn == 'index.md':
                    continue
                raw = open(os.path.join(dirp, fn), encoding='utf-8').read()
                m = TITLE.search(raw)
                if not m:
                    continue
                words = m.group(1).strip().split()
                if len(words) < 2:
                    continue
                stem = fn[:-3]
                out[stem] = (words[0], words[-1],
                             None if stem in SPANNING else chapter)
    return out


def alias_map():
    """Aliases from every knowledge base, each scoped to its own chapter.

    The maps are deliberately not pooled. "Beni" is Robin Vogel in
    Gamma_kb, Robin Moser in Beta_kb and Robin Bader in Alpha_kb, so an
    alias declared in one knowledge base may only ever be applied to that
    one's archive. Before the split a single file carried a `chapter:` key per
    entry to say the same thing; now the file's location says it.
    """
    out = []
    for chapter, kb in KBS.items():
        p = os.path.join(VAULT, kb, 'assertions.yaml')
        if not os.path.exists(p):
            continue
        for a in ((yaml.safe_load(open(p, encoding='utf-8')) or {})
                  .get('aliases') or []):
            if not a.get('person'):
                continue                      # not a person, e.g. a role acronym
            out.append(dict(a, chapter=a.get('chapter') or chapter))
    return out


def build_patterns(people, aliases, trees):
    """patterns[tree][stem][family] = compiled regex."""
    firsts = {}
    for first, last, chapter in people.values():
        for t in (trees if chapter is None else [chapter]):
            firsts.setdefault(t, []).append(first)
    pats = {t: {} for t in trees}
    for stem, (first, last, chapter) in people.items():
        for t in (trees if chapter is None else [chapter]):
            if t not in pats:
                continue
            fam = {
                'full': re.compile(r'\b%s\s+%s\b' % (re.escape(first), re.escape(last))),
                'outlook': re.compile(r'\b%s,\s*%s\b' % (re.escape(last), re.escape(first))),
                'initial': re.compile(r'\b%s\.\s*%s\b' % (re.escape(first[0]), re.escape(last))),
            }
            if firsts[t].count(first) == 1:
                fam['first'] = re.compile(r'\b%s\b' % re.escape(first))
            pats[t][stem] = fam
    for a in aliases:
        t, stem = a.get('chapter'), a.get('person')
        if t in pats and stem in pats[t]:
            pats[t][stem]['alias:%s' % a['alias']] = re.compile(
                r'\b%s\b' % re.escape(str(a['alias'])))
    return pats


def scan_tree(tree, pats):
    """One pass over one archive tree. Returns {stem: {family: n, _union: n}}."""
    hits = {stem: {f: 0 for f in fams} for stem, fams in pats.items()}
    union = {stem: 0 for stem in pats}
    root = os.path.join(VAULT, TREES[tree])
    nfiles = 0
    for dirp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != '_assets']
        for fn in files:
            if not fn.endswith('.md'):
                continue
            nfiles += 1
            try:
                text = open(os.path.join(dirp, fn), encoding='utf-8',
                            errors='ignore').read()
            except OSError:
                continue
            for stem, fams in pats.items():
                seen = False
                for fam, rx in fams.items():
                    if rx.search(text):
                        hits[stem][fam] += 1
                        seen = True
                if seen:
                    union[stem] += 1
    for stem in hits:
        hits[stem]['_union'] = union[stem]
    return hits, nfiles


def report(cache, people):
    mults = []
    rows = []
    for stem, (first, last, chapter) in sorted(people.items()):
        fams, un = {}, 0
        for tree, data in cache.items():
            if stem not in data:
                continue
            un += data[stem]['_union']
            for fam, n in data[stem].items():
                if fam != '_union':
                    fams[fam] = fams.get(fam, 0) + n
        full = fams.get('full', 0)
        if un == 0:
            continue
        mult = un / full if full else float('inf')
        if full:
            mults.append(mult)
        extra = {k: v for k, v in fams.items()
                 if k != 'full' and v}
        rows.append((stem, full, un, mult, extra))
    print('## Known-person calibration, %d people with archive presence\n'
          % len(rows))
    print('| Person | full-name pages (the old count) | all families, union '
          '| multiplier | what full-name missed |')
    print('|---|---|---|---|---|')
    for stem, full, un, mult, extra in sorted(rows, key=lambda r: -r[3]):
        m = 'inf' if mult == float('inf') else '%.1f' % mult
        ex = ', '.join('%s %d' % (k, v) for k, v in
                       sorted(extra.items(), key=lambda kv: -kv[1])) or '-'
        print('| %s | %d | %d | %s | %s |' % (stem, full, un, m, ex))
    if mults:
        med = statistics.median(mults)
        p90 = sorted(mults)[max(0, int(len(mults) * .9) - 1)]
        print('\n**Calibration: median multiplier %.1f, p90 %.1f, n=%d.** '
              'A full-name count for an unknown person is a floor; present '
              'it as "N pages (floor; calibrated range N to %.0f x N)". '
              'First-name-only counts are ceilings, not floors: unknown '
              'people share first names too.' % (med, p90, len(mults), p90))
        return med, p90
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', action='append', choices=sorted(TREES),
                    help='limit this pass to one knowledge base')
    ap.add_argument('--cache', action='store_true',
                    help='merge results into %s' % os.path.basename(CACHE))
    ap.add_argument('--report', action='store_true',
                    help='print the calibration report from the cache')
    ap.add_argument('--candidates', default='',
                    help='comma-separated unknown names to count calibrated')
    a = ap.parse_args()

    people = known_people()
    if not TREES:
        sys.exit('No knowledge base in this vault has an archive layer to scan.\n'
                 'namescan reads archives, not Wiki bundles. Add an archive layer,\n'
                 'or declare its folder as archive_layer in the knowledge base\'s\n'
                 'assertions.yaml if it is not called OneNote/.')
    trees = a.tree or sorted(TREES)
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))

    if not (a.report and not a.tree):
        pats = build_patterns(people, alias_map(), trees)
        for t in trees:
            hits, nf = scan_tree(t, pats[t])
            cache[t] = hits
            print('scanned %s: %d files' % (t, nf), file=sys.stderr)
    if a.cache:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), indent=0)

    med = p90 = None
    if a.report or not a.candidates:
        med, p90 = report(cache, people)

    if a.candidates:
        names = [n.strip() for n in a.candidates.split(',') if n.strip()]
        cpeople = {'cand-%d' % i: (n.split()[0], n.split()[-1], None)
                   for i, n in enumerate(names) if len(n.split()) >= 2}
        pats = build_patterns(cpeople, [], trees)
        print('\n## Candidates (no aliases counted: unproven shorthands are '
              'interview questions, not counts)\n')
        print('| Name | floor (full name) | union of families | calibrated range |')
        print('|---|---|---|---|')
        for t in trees:
            h, _ = scan_tree(t, pats[t])
            for i, n in enumerate(names):
                stem = 'cand-%d' % i
                if stem not in h:
                    continue
                full, un = h[stem].get('full', 0), h[stem]['_union']
                rng = ('%d to %d' % (full, round(full * p90))
                       if p90 and full else 'uncalibrated')
                print('| %s (%s) | %d | %d | %s |' % (n, t, full, un, rng))


if __name__ == '__main__':
    main()
