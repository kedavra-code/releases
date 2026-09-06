#!/usr/bin/env python3
"""Connectedness of each bundle, measured rather than eyeballed.

    python3 _scripts/linkcheck.py [KnowledgeBase ...]     (default: all)
    python3 _scripts/linkcheck.py --verbose               (name the isolates)

`coverage.py` answers "how much of the archive did anything read". This answers
the other half: **how much of the bundle is reachable from the rest of it.** A
compile can hit 100 per cent coverage and still produce a list rather than a
graph, and the list is worth less — nothing leads a reader from one concept to
the next, and the viewer draws a wide empty disc because its layout is a force
simulation and edges are what pull structure out of it.

That is not hypothetical. `Epsilon_kb` came out of a ten-batch compile on
31.08.2026 with 100 concepts and 100 edges — 1.0 per concept against 4.4 in
`Delta_kb`, which covers the same institution's Confluence from the other side —
and 21 per cent of its concepts had nothing pointing at them. The compile skill
had never told an agent to link, and the dispatcher had told every agent to skip
cross-KB links "because the dispatcher adds those afterwards" and then had no
checklist entry obliging it to. Both are fixed; this script is what makes the
recurrence visible.

**The thresholds are calibrated against the bundles that were already right,**
not chosen. Measured 31.08.2026, share of concepts with no inbound link: Beta 0
per cent, Delta 0, Zeta 0, Gamma 1, Alpha 2. Every mature bundle sits at or
under 2, so 5 is a floor with room in it rather than a line drawn round today's
numbers. Same rule `namescan.py` encodes: calibrate an estimator against knowns
before trusting what it says about an unknown.

**Components are reported and never thresholded**, deliberately. The share of a
bundle inside its largest component is the sharper signal — `Epsilon_kb` scored 21
per cent on isolates but only 41 per cent inside its largest component, so the
isolate figure understated how broken it was. It is still not a rule, because
`Zeta_kb` sits at 60 per cent and is correct: its two islands are
`ai/system-cards/` and `ai/knowledge-bases/`, two unrelated subjects that share
a bundle, and no honest link joins them. A check that fired there would be
standing noise, and standing noise trains a reader to skip the findings block.
So the number is printed for a human to read and only the isolate share carries
a threshold.

**A dead link inside a bundle is not a fault.** Under OKF a link to a concept
that has not been written is a legitimate way to record knowledge that is
missing, so those are counted and reported, never flagged. A **cross-KB** link
that resolves nowhere is different and `verify.py` already fails the run on it;
this script counts them so the two measurements can be compared.
"""
import collections
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r'\]\(((?!https?://)[^)\s]+\.md)(?:#[^)\s]*)?\)')
RESERVED = ('index.md', 'log.md')

# Share of concepts with no inbound link, above which a linking pass is due.
# See the calibration in the module docstring.
ISOLATE_FLOOR = 0.05


def discover():
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))


def concepts(kb):
    """Every concept in the bundle, as paths relative to the vault root.

    `_to_delete/` is excluded. It is a retirement bin, its contents are
    superseded and unlinked by definition, and counting it is how a first
    pass at this measurement reported `Alpha_kb` as 24 per cent isolated when
    the real figure is 2 — a wrong number that nearly sent an agent to invent
    links into the healthiest bundle in the vault.
    """
    root = os.path.join(VAULT, kb, 'Wiki')
    return sorted(
        os.path.relpath(f, VAULT)
        for f in glob.glob(os.path.join(root, '**', '*.md'), recursive=True)
        if os.path.basename(f) not in RESERVED and '_to_delete' not in f)


def measure(kb, universe):
    cs = concepts(kb)
    have = set(cs)
    inb = collections.Counter({c: 0 for c in cs})
    outb = collections.Counter({c: 0 for c in cs})
    pairs = set()
    dead, xkb_ok, xkb_bad, xkb_targets = 0, 0, [], collections.Counter()

    for c in cs:
        d = os.path.dirname(os.path.join(VAULT, c))
        for m in LINK.finditer(open(os.path.join(VAULT, c), encoding='utf-8').read()):
            tgt = os.path.normpath(os.path.join(d, m.group(1)))
            rel = os.path.relpath(tgt, VAULT)
            if rel in have:
                if rel != c:
                    pairs.add(tuple(sorted((c, rel))))
                    inb[rel] += 1
                    outb[c] += 1
            elif rel.split(os.sep)[0] != kb:
                # crosses into another knowledge base
                if os.path.isfile(tgt):
                    xkb_ok += 1
                    xkb_targets[rel.split(os.sep)[0]] += 1
                else:
                    xkb_bad.append((c, rel))
            else:
                dead += 1                       # in-bundle, unwritten: legitimate

    # connected components over the undirected graph
    adj = collections.defaultdict(set)
    for a, b in pairs:
        adj[a].add(b)
        adj[b].add(a)
    seen, comps = set(), []
    for c in cs:
        if c in seen:
            continue
        stack, comp = [c], []
        seen.add(c)
        while stack:
            n = stack.pop()
            comp.append(n)
            for m in adj[n] - seen:
                seen.add(m)
                stack.append(m)
        comps.append(comp)
    comps.sort(key=len, reverse=True)

    return {
        'kb': kb, 'n': len(cs), 'edges': len(pairs),
        'no_in': [c for c in cs if inb[c] == 0],
        'no_out': [c for c in cs if outb[c] == 0],
        'isolated': [c for c in cs if inb[c] == 0 and outb[c] == 0],
        'dead': dead, 'xkb_ok': xkb_ok, 'xkb_bad': xkb_bad,
        'xkb_targets': xkb_targets,
        'comps': comps,
        'hubs': [c for c, _ in inb.most_common(3)],
        'inb': inb,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    verbose = '--verbose' in sys.argv
    kbs = args or discover()
    rows = [measure(kb, kbs) for kb in kbs]

    print('%-12s %7s %7s %7s   %-14s %-13s %s'
          % ('bundle', 'concepts', 'edges', 'per', 'no inbound',
             'largest comp', 'cross-KB'))
    print('-' * 88)
    due = []
    for r in rows:
        share = len(r['no_in']) / r['n'] if r['n'] else 0
        big = len(r['comps'][0]) / r['n'] if r['n'] else 0
        flag = '  <-- linking pass due' if share > ISOLATE_FLOOR else ''
        if flag:
            due.append(r['kb'])
        print('%-12s %7d %7d %7.1f   %4d (%3.0f%%)%s %4d (%3.0f%%)  %3d ok, %d broken%s'
              % (r['kb'], r['n'], r['edges'], r['edges'] / r['n'] if r['n'] else 0,
                 len(r['no_in']), 100 * share, ' ' * 4,
                 len(r['comps'][0]), 100 * big,
                 r['xkb_ok'], len(r['xkb_bad']), flag))
    print()
    for r in rows:
        extra = []
        if r['dead']:
            extra.append('%d in-bundle links to concepts not written yet '
                         '(legitimate under OKF)' % r['dead'])
        if len(r['comps']) > 1:
            extra.append('%d components; %d concepts outside the largest'
                         % (len(r['comps']), r['n'] - len(r['comps'][0])))
        if r['xkb_targets']:
            extra.append('cites into ' + ', '.join(
                '%s (%d)' % (k, v) for k, v in sorted(r['xkb_targets'].items())))
        if extra:
            print('%-12s %s' % (r['kb'], '; '.join(extra)))
        for c, rel in r['xkb_bad']:
            print('   BROKEN cross-KB  %s -> %s' % (c, rel))
        if verbose and r['no_in']:
            for c in r['no_in']:
                print('   no inbound  %s' % c)
    if due:
        print('\nLinking pass due: %s' % ', '.join(due))
        print('Threshold is %.0f%% of concepts with no inbound link, calibrated '
              'against the bundles that were already right (0-2%%).'
              % (100 * ISOLATE_FLOOR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
