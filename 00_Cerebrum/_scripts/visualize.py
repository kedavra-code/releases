#!/usr/bin/env python3
"""The vault's data and its map, for specula, the viewer app (see README.md):

    python3 _scripts/visualize.py --json

prints every concept with its place on the map, its links and its body as
HTML, the knowledge bases' halos and blocks, the build facts and the mark, as
one JSON object. specula runs it, and runs it again when a concept changes.
Template builds up to 31 shipped a one-file viewer that this script built;
specula replaced it from build 33."""
import collections
import datetime
import html
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    sys.exit('needs PyYAML: python3 -m pip install --user pyyaml')

import bundle
from bundle import VAULT, FM, discover

if '--json' not in sys.argv[1:] and '--cases' not in sys.argv[1:]:
    sys.exit('this prints the data specula draws: python3 _scripts/visualize.py --json')

def esc(s): return html.escape(str(s), quote=False)

def inline(s, cid, ids):
    # A code span is set aside before bold, italics and links are made, and
    # put back last, so nothing inside it is formatted (RENDER_CASES 3 to 5).
    codes = []
    def keep(m):
        codes.append('<code>%s</code>' % m.group(1))
        return '\x00%d\x00' % (len(codes) - 1)
    s = re.sub(r'`([^`]+)`', keep, s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<i>\1</i>', s)
    # The text is already escaped with quote=False, so & < > are done; only
    # the quotes are left, and a quote would close the attribute (RENDER_CASES 8, 9).
    def attr(v): return v.replace('"', '&quot;').replace("'", '&#x27;')
    def link(m):
        t, u = m.group(1), m.group(2)
        # Only a web address opens, and the tab it opens gets no handle back
        # to specula's page (RENDER_CASES 10, 11).
        if u.startswith(('http://', 'https://')):
            return '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (attr(u), t)
        if u.endswith('.md'):
            tgt = os.path.normpath(os.path.join(os.path.dirname(cid), u)).replace(os.sep, '/')
            if tgt in ids:
                return '<a class="nav" data-t="%s">%s</a>' % (attr(tgt), t)
            return '<a class="dead" title="not written yet — legitimate under OKF">%s</a>' % t
        return t
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    s = re.sub(r'\[\^([^\]]+)\]', r'<sup class="fn">\1</sup>', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: codes[int(m.group(1))], s)

def md2html(text, cid, ids):
    out, lines = [], text.split('\n')
    para, ul, tbl, fns = [], [], [], []
    def flushp():
        if para: out.append('<p>' + inline(esc(' '.join(para)), cid, ids) + '</p>'); para.clear()
    def flushu():
        if ul: out.append('<ul>' + ''.join('<li>%s</li>' % inline(esc(x), cid, ids) for x in ul) + '</ul>'); ul.clear()
    def flusht():
        if tbl:
            rows = [r for r in tbl if not re.match(r'^\|[\s\-:|]+\|$', r)]
            h = '<table>'
            for k, r in enumerate(rows):
                # `\|` is a bar inside the cell, also in a code span, as GFM
                # reads it (RENDER_CASES 1 and 2).
                cells = [c.strip().replace('\\|', '|')
                         for c in re.split(r'(?<!\\)\|', r.strip().strip('|'))]
                tag = 'th' if k == 0 else 'td'
                h += '<tr>' + ''.join('<%s>%s</%s>' % (tag, inline(esc(c), cid, ids), tag) for c in cells) + '</tr>'
            out.append(h + '</table>'); tbl.clear()
    for ln in lines:
        s = ln.rstrip()
        m = re.match(r'^\[\^([^\]]+)\]:\s*(.*)$', s)
        if m: fns.append((m.group(1), m.group(2))); continue
        if s.startswith('|'): flushp(); flushu(); tbl.append(s); continue
        flusht()
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            flushp(); flushu()
            out.append('<h%d>%s</h%d>' % (len(m.group(1)) + 1, inline(esc(m.group(2)), cid, ids), len(m.group(1)) + 1)); continue
        m = re.match(r'^\s*[-*]\s+(.*)$', s)
        if m: flushp(); ul.append(m.group(1)); continue
        if re.match(r'^>\s?', s):
            flushp(); flushu()
            out.append('<blockquote>%s</blockquote>' % inline(esc(re.sub(r'^>\s?', '', s)), cid, ids)); continue
        if not s: flushp(); flushu(); continue
        para.append(s)
    flushp(); flushu(); flusht()
    if fns:
        out.append('<div class="fns"><b>Footnotes</b>'
                   + ''.join('<div><sup>%s</sup> %s</div>' % (esc(a), inline(esc(b), cid, ids)) for a, b in fns) + '</div>')
    return ''.join(out)

# The renderer's kept cases, run by verify.py's vault pass. Two faults the
# specula session found on 05.11.2026, measuring all 1169 concept pages: an
# escaped bar `\|` in a table cell split the cell, as it does not in GFM, and
# bold, italics and links were applied inside a code span. Each case is an
# input, words its HTML must hold, and words it must not.
RENDER_CASES = [
    ('| A | B |\n|---|---|\n| x \\| y | b |', ['<td>x | y</td><td>b</td>'], ['<td>y</td>']),
    ('| A | B |\n|---|---|\n| `a\\|b` | c |', ['<td><code>a|b</code></td><td>c</td>'], []),
    ('Files `*.md` or `*.txt` here.', ['<code>*.md</code> or <code>*.txt</code>'], ['<i>']),
    ('See `**x**` and `~~y~~` here.', ['<code>**x**</code>', '<code>~~y~~</code>'], ['<b>', '<s>']),
    ('See `[x](y.md)` and `[^z]` here.', ['<code>[x](y.md)</code>', '<code>[^z]</code>'], ['<a', '<sup']),
    ('A *word* and **two** and [x](https://e.ch) outside code.', ['<i>word</i>', '<b>two</b>', '<a href="https://e.ch"'], []),
    ('| A | B |\n|---|---|\n| 1 | 2 |', ['<tr><td>1</td><td>2</td></tr>'], []),
    # A quote in a link's URL must not close the href and open an attribute.
    ('[x](http://a"onmouseover="alert(1))', ['href="http://a&quot;onmouseover=&quot;alert(1"'], ['" onmouseover', '"onmouseover="']),
    ('[x](https://e.ch/?a=1&b=2)', ['href="https://e.ch/?a=1&amp;b=2"'], ['&amp;amp;']),
    # A link that opens a tab gives that tab no way back to this page.
    ('[x](https://e.ch)', ['target="_blank" rel="noopener noreferrer"'], []),
    # A scheme that only starts with "http" is no web address and is not linked.
    ('[x](httpx:alert(1))', ['x'], ['<a', 'href']),
]

if '--cases' in sys.argv[1:]:
    bad = 0
    for n, (text, want, never) in enumerate(RENDER_CASES, 1):
        got = md2html(text, 'K_kb/Wiki/x.md', set())
        miss = [w for w in want if w not in got] + ['(must not) ' + w for w in never if w in got]
        if miss:
            bad += 1
            print('render case %d fails: %s; got %s' % (n, miss, got))
    sys.exit(1 if bad else 0)

concepts, order = {}, []
for kb in discover():
    root = os.path.join(VAULT, kb, 'Wiki')
    for dp, dn, fn in os.walk(root):
        if '_to_delete' in dp: continue
        for f in sorted(fn):
            if not f.endswith('.md') or f in ('index.md', 'log.md'): continue
            p = os.path.join(dp, f)
            cid = (kb + '/' + os.path.relpath(p, os.path.join(VAULT, kb))).replace(os.sep, '/')
            raw = open(p, encoding='utf-8').read()
            m = FM.match(raw)
            if not m: continue
            try: fm = bundle.mapping(m.group(1))
            except Exception: fm = {}
            v = fm.get('verified') or {}
            tier = ('human-reviewed' if str(v.get('by', '')).startswith('human:')
                    else 'machine-confirmed' if v else 'unverified')
            concepts[cid] = dict(kb=kb, fm=fm, body=raw[m.end():], tier=tier)
            order.append(cid)

# Each body is searched for links once: what a concept links to, and from
# that what links to it. Until the review of 04.10.2026 the same pattern ran
# over every body twice, once for each direction. The generated page was
# byte-identical from both forms that day.
outbound = {cid: sorted({os.path.normpath(os.path.join(os.path.dirname(cid), m.group(1))).replace(os.sep, '/')
                         for m in re.finditer(r'\]\(([^)#\s]+\.md)\)', c['body'])} & set(concepts))
            for cid, c in concepts.items()}
inbound = collections.defaultdict(list)
for cid, outs in outbound.items():
    for t in outs: inbound[t].append(cid)

# The film, 07.10.2026: a concept comes into the picture at the date of its
# oldest dated source. That is when its subject first shows in the notes, not
# when the concept was written, which for every concept here is 2026. One
# number a concept: the date counted in days with every month 31 long, so the
# page gets the month by dividing by 31 and the day keeps the order inside a
# month. A concept with no dated source has none.
_DATED = re.compile(r'(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?')
def _born(srcs):
    days = []
    for s in srcs:
        m = _DATED.match(str(s.get('last_modified', '')))
        if not m: continue
        y, mo, d = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
        if 1 <= mo <= 12 and 1 <= d <= 31: days.append(y * 372 + (mo - 1) * 31 + d - 1)
    return min(days) if days else None

data = {}
for cid, c in concepts.items():
    fm = c['fm']
    srcs = [s for s in (fm.get('sources') or []) if isinstance(s, dict)]
    data[cid] = dict(b=_born(srcs),
        t=fm.get('title') or os.path.basename(cid)[:-3],
        d=fm.get('description') or '', ty=fm.get('type') or '?',
        st=fm.get('status') or 'stable', tr=c['tier'], kb=c['kb'],
        tags=[str(x) for x in (fm.get('tags') or [])], ns=len(srcs),
        srcs=[[s.get('title') or s.get('resource', ''), str(s.get('last_modified', ''))] for s in srcs[:40]],
        inb=sorted(inbound[cid]), out=outbound[cid],
        html=md2html(c['body'], cid, concepts))

# Guard against the escaping bug of 10.08.2026 returning. These fields are drawn
# on the canvas and set with textContent as well as injected as HTML, so they
# must hold raw text; an entity here means something escaped them too early and
# "Beta Technologie & IT" would render as "Beta Technologie &amp; IT".
_ENT = re.compile(r'&(amp|lt|gt|quot|#\d+);')
_bad = [(cid, f, v) for cid, d in data.items() for f in ('t', 'd', 'ty', 'st')
        for v in [d[f]] if isinstance(v, str) and _ENT.search(v)]
_bad += [(cid, 'tags', t) for cid, d in data.items() for t in d['tags'] if _ENT.search(t)]
if _bad:
    for cid, f, v in _bad[:10]:
        print('HTML entity in raw field %s.%s: %r' % (cid, f, v), file=sys.stderr)
    sys.exit('escaped text reached the data layer; escape at the injection point instead')


# ---- precomputed layout: anchored per knowledge base, ships settled ----
#
# Until 15.08.2026 this packed connected components on a spiral, which put the
# largest component at the origin and everything else wherever it fitted. Once
# Combined_kb became three knowledge bases that stopped saying anything: the
# cross-KB links to the career concepts fused all three employers into one
# component, so the spiral drew one undifferentiated blob.
#
# The arrangement below is the owner's, and it carries meaning the force
# simulation cannot invent: Gamma top left, Beta bottom left, Alpha to the
# right, the two career concepts in the middle of that triangle, and Zeta
# below it because the private knowledge base is not part of the work story
# and shares no links with it.
#
# Each group is laid out on its own intra-group edges, so an employer's shape
# is its own structure rather than a compromise with its neighbours. Nodes
# with no intra-group edge are not special-cased: repulsion pushes them into a
# halo around their own knowledge base, which is where they belong and where
# the old global isolate ring could not put them.
import math
try:
    import numpy as np
except ImportError:
    sys.exit('visualize.py needs numpy for the graph layout, which this Python\n'
             'does not have. Install it with:\n'
             '    python3 -m pip install --user numpy\n'
             'If pip refuses with "externally-managed-environment", add\n'
             '--break-system-packages. Do not reach for that flag first: it is\n'
             'pip 23.0+, and the Command Line Tools pip on the owner Mac predates\n'
             'it and fails with "no such option". Learned 15.08.2026.')

_ids = list(data)
_ix = {c: i for i, c in enumerate(_ids)}
_edges = sorted({(_ix[a], _ix[b]) for a in _ids for b in data[a]['out'] if b in _ix and _ix[a] != _ix[b]})
_n = len(_ids)
_deg = [0] * _n
for a, b in _edges: _deg[a] += 1; _deg[b] += 1

# Concepts belonging to no single knowledge base: a person two bases both
# describe, a timeline spanning them. They get the middle rather than one
# corner, because putting a shared subject inside one bundle says it belongs
# there.
#
# The test is whether the *subject* spans the bases, not whether the concept
# happens to cite more than one. A system deployed at one employer and being
# replaced at another is a concept about a system, and it belongs in the
# bundle whose story it is; put it in PIN_INWARD instead to hold it at that
# bundle's inner rim, beside the centre without claiming to be part of it.
CENTRE = set()

# Concepts to hold in the middle, belonging to no single knowledge base. Empty
# by default. Put a concept id here when two or more bases genuinely share its
# subject — a person who appears across all of them, a timeline that spans
# them — and it will sit at the centroid of the corners rather than inside one.

# Every knowledge base gets a corner, spaced evenly on a unit circle and
# ordered by name so the picture does not shuffle between runs. A vault with a
# shape worth stating replaces this with a hand-placed arrangement carrying
# meaning the simulation cannot invent; if you do, keep the centroid at the
# origin so `_centre` lands in the actual middle.
ANCHOR = {'_centre': (0.0, 0.0)}          # filled in below, once groups are known
GAP = 130.0


def _group_of(i):
    """Every knowledge base is its own group, whether or not it has a corner."""
    cid = _ids[i]
    return '_centre' if cid in CENTRE else data[cid]['kb']

_groups = {}
for i in range(_n):
    _groups.setdefault(_group_of(i), []).append(i)

# Corners, one per knowledge base, evenly spaced and ordered by name. The
# centroid of a regular polygon is its centre, so `_centre` lands in the actual
# middle of them rather than merely between two. With one knowledge base the
# circle degenerates to a single point at the origin, which is correct: there
# is nothing to separate it from.
_corners_all = sorted(k for k in _groups if k != '_centre')
for _i, _k in enumerate(_corners_all):
    _a = 2 * math.pi * _i / len(_corners_all) - math.pi / 2
    ANCHOR[_k] = (0.0, 0.0) if len(_corners_all) == 1 else (math.cos(_a),
                                                            math.sin(_a))

ROUND = 1.35   # the longest a group may be against its width before its gravity rises

def _layout(members, floor=0.0):
    """Fruchterman-Reingold over one group's own edges. Returns positions and radius."""
    m = len(members)
    sub = {g: j for j, g in enumerate(members)}
    E = np.array([[sub[a], sub[b]] for a, b in _edges if a in sub and b in sub] or [[0, 0]], int)
    has_e = any(a in sub and b in sub for a, b in _edges)
    ang = np.arange(m) * 2.399963
    P0 = np.stack([np.cos(ang), np.sin(ang)], 1) * (14 * np.sqrt(np.arange(m) + 1))[:, None]
    K = 46.0

    def relax(grav):
        P = P0.copy()
        for it in range(420):
            tmp = 60.0 * (1 - it / 420) + 2.0
            # Repulsion between every pair, as two m-by-m planes, x and y.
            # Until the review of 04.10.2026 this built one m-by-m-by-2 array
            # and summed over its 2-long axis, 420 times a run, and a build
            # took 14 seconds; it takes 8.5 now. The force on a node is the
            # row sum; the planes are antisymmetric, so it is taken as the
            # negated column sum, which is the form that adds the same
            # numbers in the same order: the positions came out bit for bit
            # the same that day, and the plain row sum did not. It leans on
            # numpy's order of summation, so another numpy build could move
            # the picture once in the last bit.
            dx = P[:, 0][:, None] - P[:, 0][None, :]
            dy = P[:, 1][:, None] - P[:, 1][None, :]
            dist = np.sqrt(dx ** 2 + dy ** 2) + 1e-6
            w = K * K / dist
            disp = np.empty_like(P)
            disp[:, 0] = -((dx / dist) * w).sum(0)
            disp[:, 1] = -((dy / dist) * w).sum(0)
            if has_e:
                ev = P[E[:, 1]] - P[E[:, 0]]
                el = np.sqrt((ev ** 2).sum(-1)) + 1e-6
                fa = (ev / el[:, None]) * (el * el / K)[:, None]
                np.add.at(disp, E[:, 0], fa); np.add.at(disp, E[:, 1], -fa)
            disp -= P * grav
            ln = np.sqrt((disp ** 2).sum(-1)) + 1e-6
            P += (disp / ln[:, None]) * np.minimum(ln, tmp)[:, None]
        return P

    def aspect(P):
        """How much longer the cluster is than it is wide, from its covariance."""
        if m < 3:
            return 1.0
        ev = np.linalg.eigvalsh(np.cov((P - P.mean(0)).T))
        return float(np.sqrt(ev[-1] / max(ev[0], 1e-9)))

    # Gravity toward the group's own middle. Stronger for small groups:
    # with a dozen nodes and few edges the simulation settles into two or
    # three sub-clumps with nothing pulling them together, which is what
    # made Zeta read as scattered rather than as one knowledge base.
    #
    # And stronger again where the result comes out stretched. A group whose
    # sub-clumps link to one another in a chain, as Zeta's shelves do, is
    # drawn by the forces as a line: on 29.09.2026 Zeta, 35 concepts in five
    # shelves, came out 3.3 times as long as it was wide, where every other
    # knowledge base measured 1.1 to 1.4, and the owner asked for it to be
    # circle-shaped. So the layout is measured, and while it is longer than
    # ROUND times its width the gravity doubles and the simulation runs again
    # from the same start. Strong gravity folds a chain into a ball without
    # breaking its links apart. A group that is already round runs once and is
    # untouched, so no knowledge base is a special case.
    grav = 0.03 + 0.22 / math.sqrt(m)
    P = relax(grav)
    for _ in range(6):
        if aspect(P) <= ROUND:
            break
        grav *= 2
        P = relax(grav)
    P -= P.mean(0)
    # The exponent, not the constant, is what sets a cluster's density: it
    # decides how much more room 435 concepts get than 25. It was 0.55 until
    # 20.09.2026, when the owner asked for the Alpha cluster to be less dense.
    # Raised to 0.57, which gives Alpha about 13 per cent more radius and the
    # small bundles about 6 — the big cluster gains most, which is where the
    # crowding is. Changing the exponent rather than adding a factor for one
    # knowledge base keeps a single rule: no bundle is a special case, and Alpha
    # stops being dense because it is large, not because it is Alpha.
    #
    # Nothing below needs adjusting for it. The triangle scale `_T` is solved
    # from the clusters' own extents plus GAP, the halo walk clears the glows,
    # and the Delta/Epsilon pair is placed by its own walk — so every other
    # cluster moves outward on its own and the separations hold by
    # construction rather than by a number kept in step by hand.
    Rt = 26.0 * m ** 0.57 if m > 1 else 26.0
    # A floor under the rule, for the small bases: at 19 concepts the rule
    # gave Zeta a radius of 139, its name at the fixed label size covered
    # the whole cluster, and the owner found it cramped and unimportant
    # (27.09.2026). The floor is the same for every knowledge base, so no base
    # is a special case; the centre group passes none.
    Rt = max(Rt, floor)

    # A node with no intra-group edge is placed by repulsion alone, so its
    # position carries no structure: it is simply as far from everything as it
    # can get. Those two facts have to be handled separately, and conflating
    # them is what wrecked the Alpha layout (22.08.2026).
    linked = np.zeros(m, bool)
    for a, b in _edges:
        if a in sub and b in sub and a != b:
            linked[sub[a]] = linked[sub[b]] = True

    # Normalise on the 90th percentile radius, not the maximum — scaling by the
    # single furthest node stretches every gap in the group to accommodate one
    # outlier, which is half of why twelve concepts filled a disc sized for a
    # hundred. **Take that percentile over the linked nodes only.** One bundle
    # measured here had 47 unlinked concepts in 345, more than a tenth, so the
    # 90th percentile of *all* radii landed out among them: Rc came back 647
    # against a connected body whose median radius was 47, the factor was ~1, and
    # 298 concepts stayed crammed into two per cent of the area they had been
    # given while Beta and Gamma — with no unlinked nodes — were scaled up
    # correctly. The dense middle was not Alpha being denser. It was Alpha being
    # measured with a ruler its own isolates had bent.
    rad = np.sqrt((P ** 2).sum(-1))
    body = rad[linked] if linked.any() else rad
    Rc = float(np.percentile(body, 90)) or float(body.max()) or 1.0
    P *= Rt / Rc

    # Now the unlinked ones. The previous code clamped everything past
    # 1.25 * Rt to exactly 1.25 * Rt, which for two stragglers reads as "on the
    # rim" and for forty-seven draws a literal circle around the knowledge
    # base — the ring the owner asked about. It was an artefact of the clamp,
    # not a fact about the corpus.
    #
    # They do belong outside the body: not citing anything and not being cited
    # is worth seeing, and at Alpha it is worth seeing forty-seven times, because
    # it is the mark left by eight agents compiling concurrently — none of them
    # could link to a concept another was still writing. So keep them outside
    # and make them legible as a halo rather than a wire: golden-angle around
    # the circle so they never collide, and radii walked across a band so no
    # two neighbours share one. Their simulated direction is discarded on
    # purpose; it was never anything but noise.
    if linked.any() and (~linked).any():
        idx = np.flatnonzero(~linked)
        ang = idx * 2.399963 + 0.7
        band = 1.14 + 0.30 * ((np.arange(len(idx)) * 0.6180339887) % 1.0)
        P[idx] = np.stack([np.cos(ang), np.sin(ang)], 1) * (band * Rt)[:, None]

    # Linked nodes flung far by repulsion still get pulled back to the rim,
    # keeping their direction, which for them is real: the two Citrix concepts
    # at Alpha link to Beta and to each other, and sitting on the rim says that.
    rad = np.sqrt((P ** 2).sum(-1))
    cap = 1.10 * Rt
    far = linked & (rad > cap)
    if far.any():
        P[far] *= (cap / rad[far])[:, None]
    return P, Rt, float(np.sqrt((P ** 2).sum(-1)).max()), sub

RT_MIN = 330.0
_lay = {g: _layout(mem, 0.0 if g == '_centre' else RT_MIN) for g, mem in _groups.items()}

# Concepts held at the inner edge of their own group — the side facing the
# centre of the triangle. Owner's instruction of 22.08.2026, for two Alpha
# concepts he wanted near the vault owner without taking the middle itself.
#
# This is deliberately not the same thing as CENTRE. A pinned concept keeps its
# knowledge base, its colour and its place in that group's sidebar; only its
# position is overridden. So it reads as "Alpha, nearest the person" rather than
# as "belongs to no corner", which is what the origin means.
#
# The force simulation is not asked to produce this. A spring pulling two nodes
# inward would drag their neighbours with them and quietly restate the whole
# group's shape, and the position would still depend on how the run happened to
# settle. Overriding after the solve costs the two nodes their simulated
# position — which is the point, since a pin is an instruction about where a
# thing goes, not a hypothesis about where it wants to be.
PIN_INWARD = set()          # concept ids to hold at their group's inner rim

def _pin_inward(lay):
    """Move pinned concepts to the inner rim of their group, fanned so two never collide."""
    for g, (P, Rt, _e, sub) in lay.items():
        ax, ay = ANCHOR.get(g, (0.0, 0.0))
        norm = math.hypot(ax, ay)
        if norm < 1e-9:                       # the centre group has no inward direction
            continue
        ux, uy = -ax / norm, -ay / norm       # unit vector pointing at the origin
        base = math.atan2(uy, ux)
        pin = [i for i in sub if _ids[i] in PIN_INWARD]
        pin.sort(key=lambda i: _ids[i])       # stable across runs, so the picture does not shuffle
        if not pin:
            continue
        # Measure how far the group already reaches toward the centre, and put
        # the pins a little past it. A fixed fraction of Rt does not do this:
        # at Alpha it left ten concepts nearer the middle than the pinned pair,
        # because the unlinked halo reaches 1.44*Rt and some of it lands on the
        # inward side. A pin that is not the closest thing to the centre has
        # failed at the one job it has.
        others = [j for j in range(len(P)) if j not in {sub[i] for i in pin}]
        reach = max((P[j, 0] * ux + P[j, 1] * uy) for j in others) if others else 0.82 * Rt
        r = reach + 0.06 * Rt
        for k, i in enumerate(pin):
            ang = base + (k - (len(pin) - 1) / 2.0) * (60.0 / max(r, 1.0))
            P[sub[i]] = (math.cos(ang) * r, math.sin(ang) * r)
    # extents can only shrink under a pin, but recompute rather than assume
    return {g: (P, Rt, float(np.sqrt((P ** 2).sum(-1)).max()), sub)
            for g, (P, Rt, _e, sub) in lay.items()}

_lay = _pin_inward(_lay)

# separation uses the real extent, so an outlier cannot poke into a neighbour
_ext = {g: max(v[1], v[2]) for g, v in _lay.items()}

# Scale the anchor directions until no two groups can touch. Solved rather than
# tuned, so adding concepts to one knowledge base pushes the others out instead
# of overlapping them.
_T = 1.0
_keys = [k for k in _groups if k in ANCHOR]
for a in _keys:
    for b in _keys:
        if a >= b: continue
        ax, ay = ANCHOR[a]; bx, by = ANCHOR[b]
        sep = math.hypot(ax - bx, ay - by)
        if sep < 1e-9: continue
        _T = max(_T, (_ext[a] + _ext[b] + GAP) / sep)

# The halo the page draws round each knowledge base, measured here and handed to
# the page, so the layout can clear what the page paints. Until 14.09.2026 the
# page measured it for itself, and the layout, which cannot see the page,
# cleared only the clusters' extents. The edge is the 90th-percentile distance
# from the knowledge base's centroid, not the farthest concept: the farthest
# made the glow inconsistent, because Beta is dense right up to its rim and its
# halo stopped at the outer nodes, while Alpha's sparse outliers inflated its
# radius and the glow reached far past the dense mass. One robust edge, 30 past
# it and at least 60, and every halo reaches out from it by the same 1.3.
def _halo(points):
    """Centre and drawn radius of the halo round a set of (x, y) positions."""
    pts = np.asarray(points, float)
    cx, cy = pts.mean(0)
    d = np.sort(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy))
    return float(cx), float(cy), max(60.0, float(d[int(math.floor(0.9 * (len(d) - 1)))]) + 30.0) * 1.3

def _kb_points(kb, centres):
    """One knowledge base's concepts where they land, given each placed group's centre."""
    return [(float(P[sub[i], 0]) + centres[g][0], float(P[sub[i], 1]) + centres[g][1])
            for g, (P, _Rt, _e, sub) in _lay.items() if g in centres
            for i in _groups[g] if data[_ids[i]]['kb'] == kb]

# The least room between two halos: the 40 units Gamma's halo already kept
# from Alpha's when the owner asked for Delta and Epsilon to be moved out of it.
HALO_GAP = 40.0

# One rule for keeping halos apart, and one walk. Until 04.10.2026 the rule
# stood here four times, each copy written after one overlap: for the corners,
# for the Alpha pair, for Zeta and, on extents alone, for a base nobody has
# placed. A change to the clearance needed four edits, and the fourth copy had
# never learnt about halos. They were joined in a review, from a prototype
# that gave the same x, y and z for every concept and the same halos. What
# each placement needs is said where it is called, with what it was born from.
def _short(moving, extents=False):
    """How far the halos of `moving` fall short of clearing every placed halo
    by HALO_GAP. With `extents`, also how far their extents fall short of
    every placed group's by GAP, which is the older rule and the wider gap."""
    cent = {g: (ANCHOR[g][0] * _T, ANCHOR[g][1] * _T) for g in ANCHOR if g in _groups}
    h = {kb: _halo(_kb_points(kb, cent)) for kb in {data[_ids[i]]['kb'] for g in cent for i in _groups[g]}}
    s = max([0.0] + [h[a][2] + h[b][2] + HALO_GAP - math.hypot(h[a][0] - h[b][0], h[a][1] - h[b][1])
                     for a in moving for b in h if a != b])
    if extents:
        s = max([s] + [_ext[a] + _ext[g] + GAP - math.hypot(cent[a][0] - cent[g][0], cent[a][1] - cent[g][1])
                       for a in moving for g in cent if g != a])
    return s

def _walk(moving, put, d, extents=False):
    """Place `moving` with put(d), d being how far out, and step out until it clears."""
    for _ in range(400):
        put(d)
        s = _short(moving, extents)
        if s <= 0:
            return
        d += s + 1.0
    print('warning: %s did not clear in 400 steps' % ' and '.join(moving), file=sys.stderr)

def _along(kb, ux, uy):
    """put() for one base on one ray from the origin."""
    ul = math.hypot(ux, uy)
    def put(d):
        ANCHOR[kb] = (ux / ul * d / _T, uy / ul * d / _T)
    return put

# The corners clear each other's halos, not only their extents. Owner's
# instruction of 14.09.2026, after Delta and Epsilon were moved out of Alpha's halo:
# "also move Beta slightly out". Beta's halo reached 92 units into Alpha's. A corner
# whose halo reaches into another's steps out along its own ray, keeping its
# angle, until the two clear by HALO_GAP. The smaller halo steps, so Alpha, the
# largest, stays where the solve put it. The corners then no longer stand at one
# distance from the centre, the property the unit circle was chosen for, and
# that is the trade the instruction makes: the angles hold, and the career
# concepts keep the middle.
#
# Every corner but the largest walks, the larger of them first. Where the two
# smaller corners' halos touched each other this would step the larger of the
# two where the old loop stepped the smaller; they stood 447 units clear on
# the day the copies were joined.
_corners = [k for k in _corners_all if k in _groups]
_cent0 = {g: (ANCHOR[g][0] * _T, ANCHOR[g][1] * _T) for g in ANCHOR if g in _groups}
_r0 = {k: _halo(_kb_points(k, _cent0))[2] for k in _corners}
for k in sorted(_corners, key=_r0.get, reverse=True)[1:]:
    _walk([k], _along(k, *ANCHOR[k]), math.hypot(*ANCHOR[k]) * _T)

_pos = {}
for g, members in _groups.items():
    P, Rt, _e, sub = _lay[g]
    cx, cy = ANCHOR[g][0] * _T, ANCHOR[g][1] * _T
    for i in members:
        _pos[i] = (float(P[sub[i], 0]) + cx, float(P[sub[i], 1]) + cy)

# Depth, for the 3D view only. Owner's request of 23.09.2026: a 3D graph that
# is intuitive. The x/y above are the owner's arrangement and stay exactly as
# they are, so the 3D view is the 2D map with one more dimension rather than a
# second map to learn. z is solved per group, in the group's own frame:
#   * a spring toward the mean depth of linked neighbours, so what links
#     together sits together in depth as well;
#   * a push apart in depth between concepts that sit close in x/y, which is
#     what 3D is for here — the dense Alpha core opens up instead of overlapping;
#   * a weak pull to the group's plane, which keeps the solve from running off.
# The solved depths then only order the concepts: each is placed within the
# depth a ball of the group's size has at its x/y, most in the middle and none
# at the rim, so every knowledge base is a sphere from any side and still the
# flat map from the front. Owner's request of 23.09.2026; it was a lens a third
# as thick as it was wide until then.
# Unlinked concepts carry no structure in x/y (see _layout), so they get none
# in z either: a golden-ratio spread within a larger ball, which turns their
# ring into a loose outer shell.
# Deterministic, like the layout: no random numbers, so a rebuild draws the
# same picture.
# How deep a large knowledge base has to be for its width, and what large
# means: specula's viewer check asks for more than 0.75 of every base with 100
# concepts or more, and DEEP leaves it a margin, as ROUND does for the layout.
DEEP = 0.85
BALL_MIN = 100

def _depth(P, Rt, members):
    m = len(members)
    if m < 3:
        return np.zeros(m)
    sub = {g: j for j, g in enumerate(members)}
    E = np.array([[sub[a], sub[b]] for a, b in _edges if a in sub and b in sub], int).reshape(-1, 2)
    deg = np.zeros(m)
    np.add.at(deg, E[:, 0], 1); np.add.at(deg, E[:, 1], 1)
    linked = deg > 0
    z = (((np.arange(m) * 0.6180339887) % 1.0) - 0.5) * Rt * 0.5
    s = 1.6 * Rt * math.sqrt(math.pi / m)          # about two node spacings
    d2 = ((P[:, None, :] - P[None, :, :]) ** 2).sum(-1)
    near = np.exp(-d2 / (2 * s * s))
    np.fill_diagonal(near, 0.0)
    for it in range(240):
        spring = np.zeros(m)
        if len(E):
            np.add.at(spring, E[:, 0], z[E[:, 1]] - z[E[:, 0]])
            np.add.at(spring, E[:, 1], z[E[:, 0]] - z[E[:, 1]])
            spring /= np.maximum(deg, 1)
        dz = z[:, None] - z[None, :]
        rep = (near * np.tanh(dz / s) * np.exp(-(dz * dz) / (2 * (2 * s) ** 2))).sum(1)
        step = s * 0.12 * (1 - it / 240) + s * 0.01
        z += np.clip(0.35 * spring + 1.2 * s * rep - 0.015 * z, -step, step)
    body = np.abs(z[linked]) if linked.any() else np.abs(z)
    zn = np.clip(z / (float(np.percentile(body, 95)) or 1.0), -1.0, 1.0)
    r2 = (P ** 2).sum(-1)
    # 1.10 * Rt is where _layout caps the linked body, 1.55 * Rt clears the
    # unlinked halo's outer edge at 1.44. The rim keeps a little depth, a
    # quarter of Rt, or concepts crowded at the edge of a small base would
    # overlap again there: Epsilon went from one overlapping pair to nine.
    env = np.sqrt(np.maximum((1.10 * Rt) ** 2 - r2, (0.25 * Rt) ** 2))
    # The same order in depth, spaced evenly: what the relaxed depths are
    # blended towards when they come out too flat, below.
    n = int(linked.sum())
    even = np.zeros(m)
    if n > 1:
        even[linked] = z[linked].argsort(kind='stable').argsort() / (n - 1) * 2 - 1
    halo = (((np.arange(m - n) * 0.6180339887) % 1.0) * 2 - 1) * np.sqrt(
        np.maximum((1.55 * Rt) ** 2 - r2[~linked], 0.0))
    across = float(P.std(0).mean()) or 1.0

    # A large knowledge base is a ball, not a disc, whatever its links do.
    # Nothing in the solve ties the spread in depth to the spread across: the
    # one is scaled on the 95th percentile of the depths, the other on the
    # 90th percentile of the radii, and the ratio moves with every change of
    # links. Epsilon_kb measured 0.64 as deep as it is wide after the health
    # check of 04.10.2026 and 0.96 after the action sitting of the same day,
    # and specula's viewer check fails under 0.75. So where the spread in depth falls
    # short of DEEP times the spread across, the depths move a quarter at a
    # time towards even spacing in the same order, and stop at the first step
    # that reaches it. A base that is already a ball is not touched.
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        out = ((1 - t) * zn + t * even) * env
        out[~linked] = halo
        if m < BALL_MIN or float(out.std()) / across >= DEEP:
            break
    return out

_depths = {}
for g, members in _groups.items():
    P, Rt, _e, sub = _lay[g]
    Pm = np.array([P[sub[i]] for i in members])
    for i, zz in zip(members, _depth(Pm, Rt, members)):
        _depths[i] = float(zz)

# The picture is centred on the middle of the work triangle, not on the mean of
# every node: the mean is dragged around by whichever knowledge base grew last,
# and Zeta sitting below would push the career concepts off centre. The
# anchors already put the origin there, so no offset is taken. One of zero was
# subtracted from every coordinate until the review of 04.10.2026, which read
# as if the picture were re-centred here.
# ---- Places set by hand. A vault whose owner wants the middle of a knowledge
# base at a place of his own names it here: '<Topic>_kb': (x, y, z).
#
# x to the right, y up and z out of the map's plane toward the reader; the
# middle of the map is 0 0 0. A base named here is moved there whole, as the
# solve above laid it out and with its own depths, so that the middle of its
# concepts stands at the place. A base not named keeps the place the solve gave
# it. The Graph view is the map seen from above: it shows x and y of these
# places, and the 3D view adds z. The table is empty in the template, so every
# base keeps the solve's place and the 40 units between two halos hold.
PLACE = {}
for _kb, (_px, _py, _pz) in PLACE.items():
    _m = _groups.get(_kb, [])
    if not _m:
        continue
    _cx = sum(_pos[i][0] for i in _m) / len(_m)
    _cy = sum(_pos[i][1] for i in _m) / len(_m)
    _cz = sum(_depths[i] for i in _m) / len(_m)
    for i in _m:
        _pos[i] = (_pos[i][0] - _cx + _px, _pos[i][1] - _cy - _py)   # the map's own y runs down the page
        _depths[i] += _pz - _cz

for i, c in enumerate(_ids):
    x, y = _pos[i]
    data[c]['x'] = round(x, 1); data[c]['y'] = round(y, 1); data[c]['z'] = round(_depths[i], 1)
    data[c]['deg'] = _deg[i]

# first appearance, the order the page used to meet them in, so the halos still
# overlay each other in the same order
halos = {}
for c in _ids:
    kb = data[c]['kb']
    if kb not in halos:
        hx, hy, hr = _halo([(data[o]['x'], data[o]['y']) for o in _ids if data[o]['kb'] == kb])
        halos[kb] = {'cx': round(hx, 1), 'cy': round(hy, 1), 'halo': round(hr, 1)}

print('graph layout: ' + ', '.join('%s %d (r=%d, extent=%d)' % (g, len(m), _lay[g][1], _ext[g])
                                   for g, m in sorted(_groups.items())), file=sys.stderr)

stamp = datetime.datetime.now().strftime('%d.%m.%Y, %H:%M')

# The block hues, worn by the graph's halos, the Settings buttons and the mark.
# One definition, handed to the page as KB_BLOCKS. It was a literal in the page
# script until 14.09.2026, which the mark, drawn here, could not read.
#
# One block per knowledge base by default, ordered by name so the picture and
# the legend do not shuffle between runs. Group several bundles into one block
# where your vault has a real grouping to say — three employers against two
# reference corpora, say — by writing the blocks out as literals instead; the
# legend, the halo hues, the Settings buttons and the mark all follow whatever
# this list says, and nothing else needs changing.
KB_HUES = ['#e8a14a', '#4fc3d0', '#c76bd4', '#7fbf6a',
           '#e07b7b', '#8e9ae0', '#d9b34a', '#6fb3a8']
KB_BLOCKS = [{'kbs': [k], 'hue': KB_HUES[i % len(KB_HUES)],
              'tag': k[:-3] if k.endswith('_kb') else k}
             for i, k in enumerate(sorted(g for g in _groups if g != '_centre'))]

# The mark, defined once and placed twice — the header brand and the About
# dialog — because two copies of one drawing is the fault this vault keeps
# finding in its own generated files. Size is the caller's, set in CSS. Each
# placement prefixes its own ids, so the two copies' gradients cannot collide.
#
# It is the graph, abstracted, and drawn from the numbers the graph is drawn
# from. Owner's instruction of 14.09.2026: "make it like the abstracted graph.
# use the halo color of the kb's in the graph as colors in the graph. indicate
# the connections somehow. surprise me. make it look good." What each part says:
#   * Each knowledge base stands at the centre of its halo in the graph, in a
#     glow at 80% of that halo's radius, in its block's hue. The mark moves when
#     the layout does, and the viewBox is framed on what is drawn.
#   * Inside the glow, a constellation on a golden-angle spiral, its first and
#     largest dot facing the hub. More concepts make it wider, as the square
#     root, and fuller, as the logarithm, so 435 concepts read larger than 15
#     without drowning them.
#   * The pale hub is whatever CENTRE puts in the middle — concepts belonging
#     to no single knowledge base. Empty CENTRE, no hub.
#   * A strand for about every eleven links between two parts of the graph,
#     drawn for each pair with ten or more, fading from one end's colour to the
#     other's. A bundle sharing no link with any other simply stands alone.
#   * In About only, light runs out along the strands from the end nearer the
#     hub, slowly, unless the reader has asked for less motion.
#
# **Nothing here is hand-placed**, which is the point: the mark is derived from
# the same numbers the graph is, so it follows your vault rather than
# describing someone else's. The drawing it replaced was a layout typed in by
# hand under a comment claiming the generator checked it against the real one.
# No such check had ever been written. specula's viewer check now compares the
# mark with the data, which is what that comment had been promising.
GLOW = 0.80   # of the graph's halo: at 95% the glow took the room the clusters need at 58px

def _mark(p, pulse=False):
    """The mark as SVG. `p` prefixes its ids; `pulse` adds About's moving light."""
    if not halos:          # a vault with no knowledge base yet has no map to draw
        return ''
    hue = {kb: b['hue'] for b in KB_BLOCKS for kb in b['kbs']}
    mid = [c for c in _ids if c in CENTRE]
    hx = sum(data[c]['x'] for c in mid) / len(mid) if mid else 0.0
    hy = sum(data[c]['y'] for c in mid) / len(mid) if mid else 0.0
    hub_r, ga = 140.0, math.pi * (3 - math.sqrt(5))
    defs, glows, dots, dot_at = [], [], [], {}
    for kb, h in halos.items():
        col = hue.get(kb, '#a49a85')
        defs.append('<radialGradient id="%s-halo-%s"><stop offset="0" stop-color="%s" stop-opacity=".72"/>'
                    '<stop offset=".5" stop-color="%s" stop-opacity=".3"/><stop offset="1" stop-color="%s" stop-opacity="0"/>'
                    '</radialGradient>' % (p, kb, col, col, col))
        glows.append('<circle data-kb="%s" cx="%.1f" cy="%.1f" r="%.1f" fill="url(#%s-halo-%s)"/>'
                     % (kb, h['cx'], h['cy'], h['halo'] * GLOW, p, kb))
        n = len(_groups.get(kb, ())) or 1
        m = max(2, round(1.5 + 1.4 * math.log(n)))
        rc = max(120.0, 26.0 * math.sqrt(n))
        face = math.atan2(hy - h['cy'], hx - h['cx'])
        pts = []
        for j in range(m):
            t = j / (m - 1)
            pts.append((h['cx'] + rc * math.sqrt(t) * math.cos(face + j * ga),
                        h['cy'] + rc * math.sqrt(t) * math.sin(face + j * ga),
                        rc * 1.21 * (1 - 0.5 * math.sqrt(t)) / math.sqrt(m)))
        dot_at[kb] = pts
        dots.append('<g data-kb="%s" fill="%s">%s</g>' % (kb, col, ''.join(
            '<circle cx="%.0f" cy="%.0f" r="%.0f"/>' % q for q in pts)))
    dot_at['_centre'] = [(hx, hy, hub_r)]
    links = collections.Counter()
    for a in _ids:
        for b in data[a]['out']:
            if b in _ix and b != a and _group_of(_ix[a]) != _group_of(_ix[b]):
                links[tuple(sorted((_group_of(_ix[a]), _group_of(_ix[b]))))] += 1
    bundles, lights, k_light = [], [], 0
    for i, ((a, b), k) in enumerate(sorted(links.items(), key=lambda t: (t[1], t[0]))):
        if k < 10 or a not in dot_at or b not in dot_at:
            continue
        # the end nearer the hub first, so the light runs outward
        ends = sorted((a, b), key=lambda g: math.hypot(dot_at[g][0][0] - hx, dot_at[g][0][1] - hy) if g != '_centre' else -1.0)
        mids = [(sum(q[0] for q in dot_at[g]) / len(dot_at[g]), sum(q[1] for q in dot_at[g]) / len(dot_at[g])) for g in ends]
        cols = ['style="stop-color:var(--fg)"' if g == '_centre' else 'stop-color="%s"' % hue.get(g, '#a49a85') for g in ends]
        defs.append('<linearGradient id="%s-link-%d" gradientUnits="userSpaceOnUse" x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f">'
                    '<stop offset="0" %s/><stop offset="1" %s/></linearGradient>'
                    % (p, i, mids[0][0], mids[0][1], mids[1][0], mids[1][1], cols[0], cols[1]))
        s_n = max(1, round(k / 11))
        near = [sorted(dot_at[g], key=lambda q: math.hypot(q[0] - o[0], q[1] - o[1]))
                for g, o in ((ends[0], mids[1]), (ends[1], mids[0]))]
        paths = ['M%.0f %.0f L%.0f %.0f' % (near[0][t % len(near[0])][0], near[0][t % len(near[0])][1],
                                            near[1][t % len(near[1])][0], near[1][t % len(near[1])][1]) for t in range(s_n)]
        bundles.append('<g data-link="%s %s" data-n="%d" stroke="url(#%s-link-%d)" stroke-width="24" stroke-opacity=".55" '
                       'stroke-linecap="round">%s</g>' % (a, b, k, p, i, ''.join('<path d="%s"/>' % d for d in paths)))
        for d in paths:
            lights.append('<path d="%s" pathLength="100" style="--d:%.2fs"/>' % (d, (k_light * 0.37) % 6.4))
            k_light += 1
    defs.append('<radialGradient id="%s-hub"><stop offset="0" style="stop-color:var(--fg)" stop-opacity=".55"/>'
                '<stop offset="1" style="stop-color:var(--fg)" stop-opacity="0"/></radialGradient>' % p)
    hub = ('<g data-ids="%s"><circle cx="%.0f" cy="%.0f" r="%.0f" fill="url(#%s-hub)"/>'
           '<circle cx="%.0f" cy="%.0f" r="%.0f" style="fill:var(--fg)"/></g>'
           % (' '.join(mid), hx, hy, hub_r * 3.2, p, hx, hy, hub_r))
    x0 = min(h['cx'] - h['halo'] * GLOW for h in halos.values()) - 30
    x1 = max(h['cx'] + h['halo'] * GLOW for h in halos.values()) + 30
    y0 = min(h['cy'] - h['halo'] * GLOW for h in halos.values()) - 30
    y1 = max(h['cy'] + h['halo'] * GLOW for h in halos.values()) + 30
    return ('<svg viewBox="%.0f %.0f %.0f %.0f" role="img" aria-label=""><defs>%s</defs>%s%s%s%s%s</svg>'
            % (x0, y0, x1 - x0, y1 - y0, ''.join(defs), ''.join(glows), ''.join(bundles),
               '<g class="pulse">%s</g>' % ''.join(lights) if pulse else '', hub, ''.join(dots)))

# The commit the vault sat at when this file was written, and whether the tree
# was clean. This is the viewer's analogue of j4k's build code: the first thing
# to quote when the page shows something that looks wrong, because it says which
# corpus the page was drawn from. `--no-optional-locks` on both calls, for the
# reason `_scripts/git-read.sh` exists — a bare `git status` takes .git/index.lock
# and a session that cannot delete it wedges the next commit.
def _git(*a):
    try:
        r = subprocess.run(('git', '--no-optional-locks') + a, cwd=VAULT,
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:
        return ''
git_id = _git('rev-parse', '--short', 'HEAD') or 'not a git checkout'
# The build number and the project's age, as j4k shows them. Both are computed
# rather than tracked: murmur commits its count because a shallow clone returns
# a confidently wrong one, but this page is only ever generated here, from a
# full checkout, so a tracked counter would be a second copy of an answer git
# already holds.
build_no = _git('rev-list', '--count', 'HEAD') or '?'
# What's new is specula's own since 24.10.2026, so the key stays and is empty.
news = []
_first = (_git('log', '--reverse', '--format=%ad', '--date=short') or '').split('\n')[0]
try:
    _d = datetime.date.fromisoformat(_first)
    started = '%s · day %d' % (_d.strftime('%d.%m.%Y'),
                               (datetime.date.today() - _d).days + 1)
except ValueError:
    started = 'unknown'
# One word, so the card stays on one line and its row stays even — but a word
# a reader knows. It said `dirty` for an hour on 29.08.2026 and the owner had
# to ask what that meant: fixing a layout by reaching for jargon moves the cost
# from the grid to the reader.
#
# **Only the page's own inputs count**: every bundle's Wiki, which is the whole
# of its data, and this script, which is the whole of its code. The test was
# the whole tree until 27.09.2026, and the page said `uncommitted` after every
# commit: the pre-commit hook runs verify.py, verify.py writes its memory to
# _scripts/verify-state.json, and the post-commit rebuild then found the tree
# changed. A file the page never reads cannot make it match no commit.
# specula's checks read this list and hold the stamp to it.
PAGE_INPUTS = [':(glob)*/Wiki/**', '_scripts/visualize.py']
if _git('status', '--porcelain', '--', *PAGE_INPUTS):
    git_id += ' · uncommitted'
# specula draws the vault itself and asks this script for the data, as one
# JSON object on stdout.
json.dump({'concepts': data, 'halos': halos, 'blocks': KB_BLOCKS,
           'build': {'git': git_id, 'stamp': stamp, 'number': build_no, 'started': started},
           'news': news, 'mark': {'header': _mark('h'), 'about': _mark('a', pulse=True)}},
          sys.stdout, ensure_ascii=False)

