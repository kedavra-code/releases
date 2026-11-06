#!/usr/bin/env python3
"""Generates 00_Cerebrum_viewer.html — a static, self-contained browser for the
vault's OKF bundles. Derived output, never hand-edited; regenerate with:

    python3 _scripts/visualize.py
    python3 _scripts/visualize.py --json   # the page's data only, for a viewer of your own

No server, no network, no dependencies in the page: open the file in any
browser. The viewer renders every concept, resolves concept links in-app,
marks dead links (legitimate under OKF), derives trust tiers, and shows
inbound as well as outbound links per concept. SPEC.md defines no viewer;
this one follows the house profile."""
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
        # to this page (RENDER_CASES 10, 11).
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
# means: viewer-check.js asks for more than 0.75 of every base with 100
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
    # and viewer-check.js fails under 0.75. So where the spread in depth falls
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
# No such check had ever been written. `viewer-check.js` now compares the mark
# with the page's own data, which is what that comment had been promising.
GLOW = 0.80   # of the graph's halo: at 95% the glow took the room the clusters need at 58px

def _mark(p, pulse=False):
    """The mark as SVG. `p` prefixes its ids; `pulse` adds About's moving light."""
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

# The header's controls are icons, as j4k's top bar is, each named by its
# tooltip. Drawn here in one line weight rather than taken from an icon set, so
# the page stays a single file with nothing to fetch. The graph icon's strokes
# stop at the circles' edges, which takes arithmetic rather than typed numbers.
def _icon(body):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>' % body)

def _spoke(a, b, r):
    """A line between two circles of radius r, from edge to edge."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return 'M%.2f %.2f L%.2f %.2f' % (a[0] + ux * r, a[1] + uy * r, b[0] - ux * r, b[1] - uy * r)

# The gear is j4k's, owner's request of 24.10.2026: "please use the settings
# icon from j4k as well". j4k takes it from Lucide, folia's choice: `Settings`
# from lucide-react 0.468.0, ISC licence, (c) Lucide Contributors 2022, portions
# (c) Cole Bemis 2013-2022 as part of Feather (MIT). Drawn in the header's own
# line weight. Until then a gear of eight flat teeth was drawn here.
LUCIDE_SETTINGS = ('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
                   '<circle cx="12" cy="12" r="3"/>')

_nodes = ((6.0, 7.0), (18.0, 6.0), (12.0, 18.0))
icon_graph = _icon(''.join('<circle cx="%g" cy="%g" r="2.6"/>' % p for p in _nodes)
                   + '<path d="%s"/>' % ' '.join(_spoke(_nodes[i], _nodes[j], 2.6)
                                                 for i, j in ((0, 1), (0, 2), (1, 2))))
# the Concept view's own shape: the list on the left, the page beside it
icon_concepts = _icon('<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
                      '<path d="M9 4v16M12.5 9h5M12.5 12.5h5M12.5 16h3"/>')
# the 3D view's own shape: a cube, the one solid everyone reads as depth
icon_3d = _icon('<path d="M12 3 20 7.5v9L12 21 4 16.5v-9Z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>')
icon_gear = _icon(LUCIDE_SETTINGS)
icon_search = _icon('<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20.5 20.5"/>')
# Settings' parts and About's rows, drawn like the rest: info, layers, an open
# book and a megaphone (24.10.2026).
icon_info = _icon('<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.6v.01"/>')
icon_layers = _icon('<path d="M12 3.5 21 8l-9 4.5L3 8Z"/><path d="m3 12.5 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/>')
icon_book = _icon('<path d="M3 5h6a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H3Z"/><path d="M21 5h-6a3 3 0 0 0-3 3v12a2.5 2.5 0 0 1 2.5-2.5H21Z"/>')
icon_news = _icon('<path d="M3 10.5v3l14 5V5.5Z"/><path d="M17 9h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M7 15.2V19a1.5 1.5 0 0 0 3 0v-2.7"/>')
# Ask Claude and the report list, the pair j4k puts in its own search box: a
# sparkle for the model and a document list for what it has written. The
# sparkle is drawn as three four-pointed stars rather than a glyph, so it keeps
# this page's one line weight and needs nothing fetched.
def _star(cx, cy, r, w=None):
    w = w or r * 0.34
    return ('<path d="M%g %g C%g %g %g %g %g %g C%g %g %g %g %g %g '
            'C%g %g %g %g %g %g C%g %g %g %g %g %g Z"/>'
            % (cx, cy - r, cx, cy - w, cx + w, cy, cx + r, cy,
               cx + w, cy, cx, cy + w, cx, cy + r,
               cx, cy + w, cx - w, cy, cx - r, cy,
               cx - w, cy, cx, cy - w, cx, cy - r))
icon_spark = _icon(_star(10, 9.6, 6.1) + _star(18.2, 6.4, 3.0)
                   + _star(17.6, 17.2, 3.6))
icon_reports = _icon('<rect x="4" y="3" width="16" height="18" rx="2.4"/>'
                     '<path d="M8 8h8M8 12h8M8 16h5"/>')
# Collapse all and Expand all: two chevrons closing on the middle, or opening away from it
icon_collapse = _icon('<path d="m7 4 5 5 5-5"/><path d="m7 20 5-5 5 5"/>')
icon_expand = _icon('<path d="m7 9 5-5 5 5"/><path d="m7 15 5 5 5-5"/>')

# The 3D view, 23.09.2026. Owner's request: "a 3D graph, which is intuitive,
# fast and efficient. make it look really good." Decided with the owner: a third
# view beside Graph and Concepts, and WebGL2 written here rather than a library,
# so the page still fetches nothing and carries no dependency.
#
# It is the 2D map with depth, not a second map. x and y are the owner's layout;
# z comes from _depth above. It shares the selection, the card, the search, the
# category and knowledge-base filters and fitting with the 2D graph, so every
# control means what it means there. With motion allowed it draws every frame,
# for the moving light on the links and for the slow drift that starts after
# six idle seconds and runs for as long as the view is left alone: until
# 23.09.2026 the drift stopped after two minutes, to spare a still picture, and
# the owner asked for it to go on once the light made the picture move anyway.
# For a reader who has asked for less motion it draws only when something
# changed — the camera, the selection, a filter.
#
# Four draw calls a frame, each one instanced from buffers uploaded once:
# faint dust for parallax, the knowledge bases' halos, the links as
# anti-aliased screen-space strips, and the concepts as camera-facing quads.
# A concept's mark is its legend shape, drawn once by shp() into a texture, so
# the 3D view cannot drift from the legend. Its glow is added in the same pass
# with zero alpha, which reads as bloom and costs nothing extra. Concepts are
# sorted back to front each frame, 1,114 of them, which is what makes a near
# concept cover a far one.
#
# Raw string, spliced into the page as __G3__: the page string is not raw, and
# a shader's newline escape would not survive it.
G3_JS = r'''/* ---- The 3D view. See G3_JS in visualize.py for why it is built this way. */
const g3=document.getElementById('g3'),g3l=document.getElementById('g3lbl');
let hov3=-1;
const G3={ok:false,frames:0,drawn:0,enter(){},fit(){},focus(){},project(){return null}};
(function(){
/* Opaque, and the ground is painted here rather than by CSS behind a
   see-through canvas. The glow and the links are added light: colour with no
   alpha. On a see-through canvas that is not a valid pixel, and Chrome shows
   it one way in a headless test and another on screen, where the owner saw
   the links vanish and a coloured square round every mark (23.09.2026). On
   an opaque canvas the alpha is never read, so neither can happen. */
const gl=g3.getContext('webgl2',{antialias:true,alpha:false});
if(!gl){b3.disabled=true;b3.title='3D view: needs WebGL2, which this browser does not offer';
 return}
G3.ok=true;G3.opaque=gl.getContextAttributes().alpha===false;
const RM=matchMedia('(prefers-reduced-motion: reduce)');RM.addEventListener('change',()=>{need=true});
const FOV=38*Math.PI/180,NN=N.length,MARGIN=36;let nearW=1;
const hex=h=>{h=h.trim().replace('#','');if(h.length===3)h=h.split('').map(c=>c+c).join('');
 const v=parseInt(h.slice(0,6),16);return[(v>>16&255)/255,(v>>8&255)/255,(v&255)/255]};
/* canvas y points down, GL y points up: flipping y here is what makes the
   front view the 2D map the right way up */
const PX=new Float32Array(NN),PY=new Float32Array(NN),PZ=new Float32Array(NN),RR=new Float32Array(NN);
N.forEach((n,i)=>{PX[i]=n.x;PY[i]=-n.y;PZ[i]=D[n.id].z||0;RR[i]=n.r});
const C3=N.map(n=>hex(COL[n.c]));
/* The film's clock, 07.10.2026. A concept is born at the date of its oldest
   source, D[id].b, here in months from the film's first month. The film begins
   where the dates begin to follow one another: a lone early date with more
   than a year of nothing after it would open on an empty sky for that long, so
   such a concept is born with the first month, and a concept with no date with
   the last. fp is the playhead in months, null while no film shows, and a
   concept is gone from the picture until the playhead has passed its birth. */
const BD=N.map(n=>D[n.id].b),MO=[...new Set(BD.filter(b=>b!=null).map(b=>Math.floor(b/31)))].sort((a,b)=>a-b);
let m0=0;while(m0<MO.length-1&&MO[m0+1]-MO[m0]>12)m0++;
const T0=MO.length?MO[m0]:0,TOT=MO.length?MO[MO.length-1]-T0+1:1;
const R=BD.map((b,i)=>b!=null?Math.max(0,b/31-T0):TOT-1+(i*.6180339887)%1*.9);
/* The most-linked concept of the vault is there from the film's first month, whatever
   its date. Owner's words of 08.10.2026, whose own concept that is: "make it such
   that you are showing me from the beginning on". The links to it still come as
   their other ends do. */
R[N.reduce((m,n,i)=>D[n.id].inb.length>D[N[m].id].inb.length?i:m,0)]=0;
let fp=null;const gone=i=>hid(N[i])||(fp!==null&&R[i]>=fp);
/* a month of film takes MSM milliseconds, 450 until the Timelapse of 24.10.2026;
   a concept's flash lasts FLASH months and a link draws itself in GROW */
const MSM=180,FLASH=1.6,GROW=1.2;

function prog(vs,fs){const p=gl.createProgram();
 for(const[t,s]of[[gl.VERTEX_SHADER,vs],[gl.FRAGMENT_SHADER,fs]]){const sh=gl.createShader(t);
  gl.shaderSource(sh,'#version 300 es\nprecision highp float;\n'+s);gl.compileShader(sh);
  if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw new Error('3D shader: '+gl.getShaderInfoLog(sh));gl.attachShader(p,sh)}
 gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error('3D link: '+gl.getProgramInfoLog(p));
 const u={};for(let i=0,k=gl.getProgramParameter(p,gl.ACTIVE_UNIFORMS);i<k;i++){const a=gl.getActiveUniform(p,i);u[a.name]=gl.getUniformLocation(p,a.name)}
 return{p,u}}
function buf(data,usage){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,data,usage||gl.STATIC_DRAW);return b}
function attr(loc,b,size,stride,off,div){gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(loc);
 gl.vertexAttribPointer(loc,size,gl.FLOAT,false,stride*4,off*4);gl.vertexAttribDivisor(loc,div)}

/* ---- concepts: one quad each, the legend shape in its core and a glow round it */
const FOG='uniform float uF0,uF1;float fog(float w){return 1.-.72*smoothstep(uF0,uF1,w);}';
const PN=prog(FOG+`
layout(location=0)in vec2 aQ;layout(location=1)in vec4 aP;layout(location=2)in vec4 aC;layout(location=3)in float aS;
uniform mat4 uM;uniform vec2 uV;uniform float uPx,uZs,uMin,uMax;
out vec2 vQ;out vec3 vC;out float vShape,vS,vF;
void main(){vec4 c=uM*vec4(aP.x,aP.y,aP.z*uZs,1.);
 float rp=clamp(aP.w*sqrt(uPx/max(c.w,1e-3)),uMin,uMax);
 const float G=3.2;vQ=aQ*G;vC=aC.rgb;vShape=aC.a;vS=aS;vF=fog(c.w);
 gl_Position=c+vec4(aQ*G*rp*2./uV*c.w,0.,0.);}`,`
uniform sampler2D uT;uniform vec3 uBg,uAcc;uniform float uCell;
in vec2 vQ;in vec3 vC;in float vShape,vS,vF;out vec4 o;
void main(){float d=length(vQ);
 vec2 lc=vec2(.5+vQ.x*uCell,.5-vQ.y*uCell),cell=vec2(mod(vShape,4.),floor(vShape/4.));
 vec4 t=texture(uT,(cell+clamp(lc,0.,1.))/vec2(4.,5.))*(1.-smoothstep(1.38,1.56,d));
 float fill=t.r,edge=max(t.g,fill),ghost=(vS>.5&&vS<1.5)?1.:0.;
 vec3 rgb=vC*fill+uBg*(edge-fill);float a=edge;
 if(vS>1.5){float rr=vS>2.5?1.5:1.38,w=vS>2.5?.13:.08;
  float ring=(1.-smoothstep(w,w+.07,abs(d-rr)))*(1.-edge);rgb+=uAcc*ring;a+=ring;}
 vec3 glow=vC*exp(-d*d*.6)*(ghost>0.?0.:(vS>2.5?.7:.4));
 float k=vF*(ghost>0.?.13:1.);o=vec4((rgb+glow)*k,a*k);if(o.a<.003&&dot(o.rgb,o.rgb)<1e-5)discard;}`);
const NS=9,nodeArr=new Float32Array((NN+12)*NS),quad=buf(new Float32Array([-1,-1,1,-1,-1,1,1,1]));
const nodeBuf=buf(nodeArr.byteLength,gl.DYNAMIC_DRAW);
const vaoN=gl.createVertexArray();gl.bindVertexArray(vaoN);
attr(0,quad,2,2,0,0);attr(1,nodeBuf,4,NS,0,1);attr(2,nodeBuf,4,NS,4,1);attr(3,nodeBuf,1,NS,8,1);
/* the shapes, drawn by the legend's own shp(): red is the mark, green the mark
   with the dark rim the 2D graph strokes round every node.
   The owner saw a faint square round each mark on this Mac's GPU, the size of
   a mark's cell on this sheet, which no headless browser showed (23.09.2026).
   The shader read the sheet inside an if, where the GPU cannot tell how large
   the mark is on screen and may pick a blurred copy that smears the shape over
   its whole cell. So the sheet is read unconditionally, the copies stop at an
   eighth of the size, where each shape still sits inside its cell, and what is
   read is faded out just past the widest shape. */
const CELL=128,SR_=40,tex=gl.createTexture();
(function(){const a=document.createElement('canvas');a.width=CELL*4;a.height=CELL*5;const c=a.getContext('2d');
 const layer=(stroke)=>{c.clearRect(0,0,a.width,a.height);c.fillStyle='#fff';c.strokeStyle='#fff';c.lineWidth=SR_*.34;c.lineJoin='round';
  SHAPES.forEach((s,k)=>{c.save();c.translate((k%4+.5)*CELL,(Math.floor(k/4)+.5)*CELL);shp(c,SR_,k);c.fill();if(stroke)c.stroke();c.restore()});
  return c.getImageData(0,0,a.width,a.height).data};
 const f=layer(false),e=layer(true),px=new Uint8Array(f.length);
 for(let i=0;i<f.length;i+=4){px[i]=f[i+3];px[i+1]=e[i+3];px[i+3]=255}
 gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,a.width,a.height,0,gl.RGBA,gl.UNSIGNED_BYTE,px);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAX_LEVEL,3);
 gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR)})();

/* ---- links: one strip each, cut in screen space so a link is the same width
   near and far, with a soft edge instead of the GPU's jagged one-pixel line */
const PE=prog(FOG+`
layout(location=0)in vec2 aQ;layout(location=1)in vec3 aA;layout(location=2)in vec3 aB;
layout(location=3)in vec3 aCa;layout(location=4)in vec3 aCb;layout(location=5)in vec4 aW;
uniform mat4 uM;uniform vec2 uV;uniform float uZs,uN;
out vec3 vC;out float vA,vD,vH,vF,vS,vSW,vWW,vL,vFg,vAl;
void main(){vec4 a=uM*vec4(aA.xy,aA.z*uZs,1.),b=uM*vec4(aB.xy,aB.z*uZs,1.);
 if(aW.x<.001||(a.w<=uN&&b.w<=uN)){gl_Position=vec4(2.,2.,2.,1.);return;}
 /* an end behind the eye is brought to the near plane along the link, so a link
    that passes the camera is drawn as far as it can be seen. Until 08.10.2026
    such a link was not drawn at all, which the flight along the links met at
    once: the link it flies is one. */
 if(a.w<uN){float t=(b.w-uN)/(b.w-a.w);a=mix(b,a,t);}else if(b.w<uN){float t=(a.w-uN)/(a.w-b.w);b=mix(a,b,t);}
 vec2 sa=a.xy/a.w*uV,sb=b.xy/b.w*uV,dd=sb-sa;float l=length(dd);vec2 dir=l>1e-4?dd/l:vec2(1.,0.);
 vec4 p=mix(a,b,aQ.x);float h=aW.y*.5+1.;if(aW.z!=0.)h=max(h,abs(aW.z)>5.?4.4:2.6);
 gl_Position=p+vec4(vec2(-dir.y,dir.x)*aQ.y*h*2./uV*p.w,0.,0.);
 vC=mix(aCa,aCb,aQ.x);vD=aQ.y*h;vH=aW.y*.5;vFg=1.-.85*smoothstep(uF0,uF1,p.w);vA=aW.x*vFg;vF=aW.z;vS=aW.w;vAl=aW.x;
 /* the distance along the link in screen pixels, interpolated linearly on
    screen: GLSL ES 3.00 has no noperspective, so it travels multiplied by w
    and is divided by the interpolated w in the fragment shader */
 vL=l*.5;vSW=aQ.x*vL*p.w;vWW=p.w;}`,`
in vec3 vC;in float vA,vD,vH,vF,vS,vSW,vWW,vL,vFg,vAl;uniform float uTime;uniform vec3 uFg;out vec4 o;
/* A bead is a round dot of a fixed size on screen, whatever the link's length,
   as the 2D graph draws it: owner's choice of 23.09.2026, after the first cut
   drew a streak whose length was a share of the link's. */
float disc(float s,float c,float r){return 1.-smoothstep(r-.6,r+.6,length(vec2(s-c,vD)));}
void main(){float cov=clamp(vH+.5-abs(vD),0.,1.);vec3 c=vC*vA*cov;
 if(vF!=0.){bool f=abs(vF)>5.;float d=f?vF/10.:vF,s=vSW/vWW,ph=fract(uTime*(f?.45:.15)+vS)*(f?1.:3.);
  float ca=ph*vL,cb=(1.-ph)*vL;
  if(f){float ring=0.,core=0.;
   if(d>0.){ring=disc(s,ca,3.4);core=disc(s,ca,1.5);}
   if(d<0.||d>1.5){ring=max(ring,disc(s,cb,3.4));core=max(core,disc(s,cb,1.5));}
   c+=(vC*ring*(1.-core)+vec3(core))*vFg;}
  else{float b=d>0.?disc(s,ca,1.6):disc(s,cb,1.6);if(d>1.5)b=max(b,disc(s,ca,1.6));
   c+=uFg*b*.45*min(1.,vAl/.12)*vFg;}}
 o=vec4(c,0.);}`);
const pairs=new Map();L.forEach(([a,b])=>{const k=a<b?a*NN+b:b*NN+a;if(!pairs.has(k))pairs.set(k,[Math.min(a,b),Math.max(a,b)])});
const E3=[...pairs.values()],NE=E3.length,MUT=hex(css('--mut'));
const eArr=new Float32Array(NE*12);
E3.forEach(([a,b],j)=>{const o=j*12,ca=C3[a],cb=C3[b];
 eArr.set([PX[a],PY[a],PZ[a],PX[b],PY[b],PZ[b]],o);
 for(let k=0;k<3;k++){eArr[o+6+k]=ca[k]*.6+MUT[k]*.4;eArr[o+9+k]=cb[k]*.6+MUT[k]*.4}});
const eBase=eArr.slice(),OUTS=N.map(n=>new Set(D[n.id].out.map(o=>idx[o]).filter(j=>j!==undefined)));
const eBuf=buf(eArr,gl.DYNAMIC_DRAW),wArr=new Float32Array(NE*4),wBuf=buf(wArr.byteLength,gl.DYNAMIC_DRAW);
/* The focused concept's links in their direction's colour, the selection's or
   else the hovered one's: see #gcard .lk. A pair linked both ways runs orange
   from the focus to blue at the other end. */
let eFocus=-2;
function dirCols(f,o){const LI=hex(css('--lin')),LO=hex(css('--lout')),out=OUTS[f].has(o),inn=OUTS[o].has(f);
 return out&&inn?[LO,LI]:out?[LO,LO]:[LI,LI]}
function recolour(f){if(f===eFocus)return;eFocus=f;eArr.set(eBase);
 if(f>=0)E3.forEach(([a,b],j)=>{if(a!==f&&b!==f)return;const[cf,co]=dirCols(f,a===f?b:a);
  eArr.set(a===f?cf:co,j*12+6);eArr.set(a===f?co:cf,j*12+9)});
 gl.bindBuffer(gl.ARRAY_BUFFER,eBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,eArr)}
G3.flow=o=>{const f=sel>=0?sel:hov3,j=E3.findIndex(([a,b])=>(a===f&&b===o)||(a===o&&b===f));if(j<0)return null;
 const fl=wArr[j*4+2]/10,fromFocus=E3[j][0]===f?fl===1:fl===-1;return fl===2?'both':fl===0?'none':fromFocus?'out':'in'};
/* viewer-check stops the clock to read a bead's shape from a still frame */
let T3=null;G3.freeze=t=>{T3=t;need=true};
G3.age=ms=>{idle-=ms};
G3.flowing=()=>{let n=0;for(let j=0;j<NE;j++)if(wArr[j*4+2])n++;return n};
G3.linkCols=o=>{const f=eFocus,j=E3.findIndex(([a,b])=>(a===f&&b===o)||(a===o&&b===f));if(j<0)return null;
 const at=k=>[...eArr.slice(j*12+k,j*12+k+3)].map(v=>Math.round(v*255));
 return E3[j][0]===f?{focus:at(6),other:at(9)}:{focus:at(9),other:at(6)}};
const vaoE=gl.createVertexArray();gl.bindVertexArray(vaoE);
attr(0,buf(new Float32Array([0,-1,1,-1,0,1,1,1])),2,2,0,0);
attr(1,eBuf,3,12,0,1);attr(2,eBuf,3,12,3,1);attr(3,eBuf,3,12,6,1);attr(4,eBuf,3,12,9,1);attr(5,wBuf,4,4,0,1);

/* ---- halos: each knowledge base in its block hue, as the 2D graph draws it,
   a soft disc that always faces the camera */
const PH=prog(`
layout(location=0)in vec2 aQ;layout(location=1)in vec4 aP;layout(location=2)in vec3 aC;
uniform mat4 uM;uniform vec3 uR,uU;uniform float uZs,uA;out vec2 vQ;out vec3 vC;
void main(){vQ=aQ;vC=aC;vec3 c=vec3(aP.xy,aP.z*uZs)+(uR*aQ.x+uU*aQ.y)*aP.w;gl_Position=uM*vec4(c,1.);}`,`
in vec2 vQ;in vec3 vC;uniform float uA;out vec4 o;
void main(){float d=dot(vQ,vQ);if(d>1.)discard;o=vec4(vC*uA*(exp(-d*2.6)-.074)*1.08,0.);}`);
const KBS=Object.keys(KBC).filter(k=>HUE[k]),KBZ={},KBN={};let KBB=null;
KBS.forEach(k=>{let s=0,c=0;N.forEach((n,i)=>{if(n.kb===k){s+=PZ[i];c++}});KBZ[k]=c?s/c:0;KBN[k]=c||1});
const hArr=new Float32Array(KBS.length*7),hBuf=buf(hArr.byteLength,gl.DYNAMIC_DRAW);let nH=0;
const vaoH=gl.createVertexArray();gl.bindVertexArray(vaoH);attr(0,quad,2,2,0,0);attr(1,hBuf,4,7,0,1);attr(2,hBuf,3,7,4,1);

/* ---- dust: a few hundred faint motes far behind and around the map. They
   carry nothing; they are there so that turning the view reads as moving
   through space, which is most of what makes depth legible on a screen */
const PD=prog(`
layout(location=0)in vec3 aP;uniform mat4 uM;uniform float uDpr;out float vA;
void main(){gl_Position=uM*vec4(aP,1.);gl_PointSize=(1.2+fract(aP.x*.013)*1.4)*uDpr;vA=.1+fract(aP.y*.017)*.22;}`,`
in float vA;uniform vec3 uCol;out vec4 o;
void main(){vec2 q=gl_PointCoord*2.-1.;float d=dot(q,q);if(d>1.)discard;o=vec4(uCol*vA*(1.-d),0.);}`);
let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;for(let i=0;i<NN;i++){x0=Math.min(x0,PX[i]);x1=Math.max(x1,PX[i]);y0=Math.min(y0,PY[i]);y1=Math.max(y1,PY[i])}
const SCX=(x0+x1)/2,SCY=(y0+y1)/2,SCR=Math.max(x1-x0,y1-y0)/2,ND=900,dArr=new Float32Array(ND*3);
let seed=20260923;const rnd=()=>(seed=(seed*1664525+1013904223)>>>0)/4294967296;
for(let i=0;i<ND;i++){const u=rnd()*2-1,t=rnd()*Math.PI*2,r=SCR*(1.5+rnd()*2.2),s=Math.sqrt(1-u*u);
 dArr.set([SCX+r*s*Math.cos(t),SCY+r*s*Math.sin(t),r*u],i*3)}
const vaoD=gl.createVertexArray();gl.bindVertexArray(vaoD);attr(0,buf(dArr),3,3,0,0);gl.bindVertexArray(null);

/* ---- the ground: the vignette #g3pane's CSS describes, drawn in the canvas
   because the canvas is opaque. A triangle over the whole view, and a
   one-level dither so the dark gradient does not band. */
const PB=prog(`out vec2 vU;void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));vU=p;gl_Position=vec4(p*2.-1.,0.,1.);}`,`
in vec2 vU;uniform vec3 uA,uB,uC;out vec4 o;
void main(){float t=length(vec2((vU.x-.5)/1.2,(.58-vU.y)/.95));
 vec3 c=t<.52?mix(uA,uB,t/.52):mix(uB,uC,min(1.,(t-.52)/.48));
 c+=(fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)-.5)/255.;o=vec4(c,1.);}`);
const vaoB=gl.createVertexArray();

/* ---- camera: an orbit round a target point. The orientation is a
   quaternion rather than yaw and pitch, so a turn never meets a pole: the view
   goes over the top and on round, in any direction, for as long as the reader
   drags. Owner's request of 23.09.2026, "let me rotate endlessly". Yaw and
   pitch had to stop short of straight up, where they flip. */
const qmul=(a,b)=>[a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
 a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
const qax=(x,y,z,a)=>{const s=Math.sin(a/2);return[x*s,y*s,z*s,Math.cos(a/2)]};
const qnorm=q=>{const l=Math.hypot(q[0],q[1],q[2],q[3])||1;return q.map(v=>v/l)};
function qrot(q,v){const[x,y,z,w]=q,t=[2*(y*v[2]-z*v[1]),2*(z*v[0]-x*v[2]),2*(x*v[1]-y*v[0])];
 return[v[0]+w*t[0]+y*t[2]-z*t[1],v[1]+w*t[1]+z*t[0]-x*t[2],v[2]+w*t[2]+x*t[1]-y*t[0]]}
const qYP=(yaw,pitch)=>qmul(qax(0,1,0,yaw),qax(1,0,0,-pitch));
function slerp(a,b,t){let d=a[0]*b[0]+a[1]*b[1]+a[2]*b[2]+a[3]*b[3];if(d<0){b=b.map(v=>-v);d=-d}
 if(d>.9995)return qnorm(a.map((v,i)=>v+(b[i]-v)*t));
 const th=Math.acos(d),s=Math.sin(th);return a.map((v,i)=>(v*Math.sin((1-t)*th)+b[i]*Math.sin(t*th))/s)}
const cam={t:[SCX,SCY,0],d:SCR*3,q:qYP(0,0),zs:1};
/* a turn is about the camera's own axes: sideways about its up, up and down
   about its right, which is what makes it endless both ways */
function turn(a,b){cam.q=qnorm(qmul(cam.q,qmul(qax(0,1,0,a),qax(1,0,0,-b))))}
/* The roll: the picture turned in its own plane, clockwise by a, about the
   line of sight. It is the 2D graph's turn, and comes the same two ways: the
   Option key with a two-finger swipe, and Safari's two-finger turn. */
function roll(a){cam.q=qnorm(qmul(cam.q,qax(0,0,1,a)))}
let W=1,H=1,dpr3=1,M=null,pxs=1,right=[1,0,0],up=[0,1,0],back=[0,0,1],anim=null,entered=false,
 vy=0,vp=0,drag3=null,last=performance.now(),idle=last,need=true,skey='',GH=new Uint8Array(NN),
 F0=0,F1=1,BR={c:[SCX,SCY,0],r:SCR};
const SX=new Float32Array(NN),SY=new Float32Array(NN),SW=new Float32Array(NN),SRp=new Float32Array(NN),order=[];
const basis=q=>[qrot(q,[1,0,0]),qrot(q,[0,1,0]),qrot(q,[0,0,1])];
function matrix(){[right,up,back]=basis(cam.q);
 const e=[0,1,2].map(k=>cam.t[k]+cam.d*back[k]),dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 const V=[right[0],up[0],back[0],0,right[1],up[1],back[1],0,right[2],up[2],back[2],0,-dot(right,e),-dot(up,e),-dot(back,e),1];
 const n=nearW=Math.max(1,cam.d*.02),f=cam.d+SCR*8,t=1/Math.tan(FOV/2),a=W/H,nf=1/(n-f);
 const P=[t/a,0,0,0,0,t,0,0,0,0,(f+n)*nf,-1,0,0,2*f*n*nf,0];M=new Float32Array(16);
 for(let c=0;c<4;c++)for(let r=0;r<4;r++){let s=0;for(let k=0;k<4;k++)s+=P[k*4+r]*V[c*4+k];M[c*4+r]=s}
 pxs=(H/2)*t}
function resize3(){const w=g3.clientWidth,h=g3.clientHeight;if(!w||!h)return;W=w;H=h;dpr3=Math.min(devicePixelRatio||1,2);
 for(const c of[g3,g3l]){c.width=Math.round(w*dpr3);c.height=Math.round(h*dpr3)}need=true;
 if(cine==='film')planFilm()}   // the film's frames are planned for the window's shape
new ResizeObserver(resize3).observe(g3);

/* What is showing decides the frame: the bounds Fit uses and the fog range. */
function bounds(zs,keep){let a=[1e9,1e9,1e9],b=[-1e9,-1e9,-1e9],any=false;
 for(let i=0;i<NN;i++){if(keep?!keep(i):gone(i))continue;any=true;const p=[PX[i],PY[i],PZ[i]*zs];
  for(let k=0;k<3;k++){a[k]=Math.min(a[k],p[k]);b[k]=Math.max(b[k],p[k])}}
 if(!any)return null;const c=[0,1,2].map(k=>(a[k]+b[k])/2);
 return{c,r:Math.max(1,Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2])/2)}}
/* Fit is solved, not guessed: for the camera's direction, the distance at
   which every showing concept's centre lands inside the canvas, margins
   included, with the target moved to the middle of what the camera sees. */
function fitFor(q,zs,keep,cap){const[r,u,b]=basis(q),bb=bounds(zs,keep);if(!bb)return null;
 /* in the cinema the frame is what the two bars leave, less `cap` pixels above
    the lower one where the film's caption stands: the picture is fitted into
    that and moved up by half the difference */
 const top=MARGIN+(cine?Math.max(.09*H,58):0),bot=top+(cap||0);
 const tx=Math.tan(FOV/2)*(W/H)*(W-2*MARGIN)/W,ty=Math.tan(FOV/2)*(H-top-bot)/H;
 let xa=1e9,xb=-1e9,ya=1e9,yb=-1e9;const pts=[];
 for(let i=0;i<NN;i++){if(keep?!keep(i):gone(i))continue;const p=[PX[i]-bb.c[0],PY[i]-bb.c[1],PZ[i]*zs-bb.c[2]];
  const x=p[0]*r[0]+p[1]*r[1]+p[2]*r[2],y=p[0]*u[0]+p[1]*u[1]+p[2]*u[2],z=p[0]*b[0]+p[1]*b[1]+p[2]*b[2];
  pts.push([x,y,z]);xa=Math.min(xa,x);xb=Math.max(xb,x);ya=Math.min(ya,y);yb=Math.max(yb,y)}
 const mx=(xa+xb)/2,my=(ya+yb)/2;let d=1;
 for(const[x,y,z]of pts)d=Math.max(d,z+Math.abs(x-mx)/tx,z+Math.abs(y-my)/ty);
 d*=1.01;const dn=(bot-top)*d*Math.tan(FOV/2)/H;
 return{t:[0,1,2].map(k=>bb.c[k]+r[k]*mx+u[k]*(my-dn)),d,q:q.slice(),zs}}
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
function tween(g,ms){if(RM.matches||ms<=0){Object.assign(cam,g,{t:g.t?g.t.slice():cam.t,q:g.q?g.q.slice():cam.q});anim=null;need=true;return}
 anim={f:{t:cam.t.slice(),d:cam.d,q:cam.q.slice(),zs:cam.zs},g:Object.assign({t:cam.t.slice(),d:cam.d,q:cam.q.slice(),zs:cam.zs},g),t0:performance.now(),ms}}
function step(now){const a=anim,k=ease(Math.min(1,(now-a.t0)/a.ms)),f=a.f,g=a.g;
 for(let j=0;j<3;j++)cam.t[j]=f.t[j]+(g.t[j]-f.t[j])*k;
 cam.d=Math.exp(Math.log(f.d)+(Math.log(g.d)-Math.log(f.d))*k);
 cam.q=slerp(f.q,g.q,k);cam.zs=f.zs+(g.zs-f.zs)*k;
 if(k>=1)anim=null}
/* The first visit starts on the flat map, exactly as the Graph view shows it,
   and lifts it into depth while the camera tips, so the reader sees that this
   is the same map before being asked to read it in three dimensions. */
const HOME=qYP(.34,-.46);
G3.enter=()=>{resize3();if(entered){need=true;return}entered=true;
 const flat=fitFor(qYP(0,0),0);if(flat)Object.assign(cam,flat);
 const g=fitFor(HOME,1);if(g)tween(g,1500);idle=performance.now();need=true};
G3.fit=()=>{const g=fitFor(cam.q,1);if(g)tween(g,450);idle=performance.now()};
G3.focus=i=>{const bb=bounds(1)||BR;tween({t:[PX[i],PY[i],PZ[i]],d:Math.min(cam.d,Math.max(bb.r*.5,480)),zs:1},650);idle=performance.now()};
G3.project=i=>{for(const j of order)if(j===i)return[SX[i],SY[i]];return null};
G3.cam=cam;G3.pick=(x,y)=>pick3(x,y);
/* for viewer-check: set a direction, read the turn since a saved one, where
   the camera's up points, and where the eye is */
G3.orient=(y,p)=>{cam.q=qYP(y,p);need=true};G3.q=()=>cam.q.slice();
G3.angle=q0=>2*Math.acos(Math.min(1,Math.abs(q0[0]*cam.q[0]+q0[1]*cam.q[1]+q0[2]*cam.q[2]+q0[3]*cam.q[3])));
G3.up=()=>qrot(cam.q,[0,1,0]);G3.eye=()=>{const b=qrot(cam.q,[0,0,1]);return[0,1,2].map(k=>cam.t[k]+cam.d*b[k])};

/* In the film a link draws itself, from the younger of its two concepts to the
   older, in GROW months: the end at the older concept is moved along the link,
   and put back when the link is whole or the film is over. */
const growing=new Set();
function grow(){let ch=growing.size>0;for(const j of growing)eArr.set(eBase.subarray(j*12,j*12+6),j*12);growing.clear();
 if(fp!==null)E3.forEach(([a,b],j)=>{const k=(fp-Math.max(R[a],R[b]))/GROW;if(k<=0||k>=1)return;
  const y=R[a]>R[b]?a:b,o=y===a?b:a,at=j*12+(o===a?0:3);
  eArr[at]=PX[y]+(PX[o]-PX[y])*k;eArr[at+1]=PY[y]+(PY[o]-PY[y])*k;eArr[at+2]=PZ[y]+(PZ[o]-PZ[y])*k;growing.add(j);ch=true});
 if(ch){gl.bindBuffer(gl.ARRAY_BUFFER,eBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,eArr)}}

/* ---- state: what the search, the selection, hover and the filters decide.
   Recomputed when any of them changes, never per frame. */
function restate(){const anySel=sel>=0;
 for(let i=0;i<NN;i++)GH[i]=ghost(N[i])?1:0;
 const fo=anySel?sel:hov3;
 E3.forEach(([a,b],j)=>{let al=0,w=1.1,fl=0;
  if(!gone(a)&&!gone(b)){
   if(anySel&&(a===sel||b===sel)){al=.55;w=2.4}
   else if(!anySel&&hov3>=0&&(a===hov3||b===hov3)){al=.45;w=2}
   else if(anySel)al=.02;
   else if(qv)al=GH[a]||GH[b]?.015:.34;
   else al=.12;
   /* the flow, as the logo's light runs along its strands, on every link:
      which way the bead travels, from the first end to the second (1), back
      (-1) or both (2); times ten on the focus's links, whose beads run
      brighter and without pause. Owner's requests of 23.09.2026. */
   if(!RM.matches){const ab=OUTS[a].has(b),ba=OUTS[b].has(a);fl=(ab&&ba?2:ab?1:-1)*(fo>=0&&(a===fo||b===fo)?10:1)}}
  wArr[j*4]=al;wArr[j*4+1]=w;wArr[j*4+2]=fl;wArr[j*4+3]=(j*.6180339887)%1});
 gl.bindBuffer(gl.ARRAY_BUFFER,wBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,wArr);grow();
 /* in the film a knowledge base's halo and name come up with its concepts,
    and the halo is whole when a quarter of them are there */
 KBB=null;if(fp!==null){KBB={};for(let i=0;i<NN;i++)if(!gone(i))KBB[N[i].kb]=(KBB[N[i].kb]||0)+1;
  for(const k in KBB)KBB[k]=Math.min(1,KBB[k]/((KBN[k]||1)*.25))}
 nH=0;KBS.forEach(k=>{if(offKB.has(k))return;const c=KBC[k],s=KBB?KBB[k]||0:1,h=hex(HUE[k]).map(v=>v*s);
  if(!s)return;hArr.set([c.cx,-c.cy,KBZ[k],c.halo*1.12,h[0],h[1],h[2]],nH*7);nH++});
 gl.bindBuffer(gl.ARRAY_BUFFER,hBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,hArr);
 BR=bounds(1)||BR;recolour(sel>=0?sel:hov3)}

function draw3(){G3.frames++;
 const key=sel+'|'+hov3+'|'+qv+'|'+[...off].join()+'|'+[...offKB].join()+'|'+RM.matches+'|'+fp+'|'+cine;if(key!==skey){skey=key;restate()}
 matrix();const anySel=sel>=0;
 const dc=Math.hypot(cam.t[0]+cam.d*back[0]-BR.c[0],cam.t[1]+cam.d*back[1]-BR.c[1],cam.t[2]+cam.d*back[2]-BR.c[2]);
 F0=dc-BR.r*.55;F1=dc+BR.r*1.05;
 order.length=0;const umin=3.2;
 for(let i=0;i<NN;i++){if(gone(i))continue;const x=PX[i],y=PY[i],z=PZ[i]*cam.zs;
  const w=M[3]*x+M[7]*y+M[11]*z+M[15];if(w<=cam.d*.03)continue;
  SX[i]=((M[0]*x+M[4]*y+M[8]*z+M[12])/w*.5+.5)*W;SY[i]=(.5-(M[1]*x+M[5]*y+M[9]*z+M[13])/w*.5)*H;
  SW[i]=w;SRp[i]=Math.min(30,Math.max(umin,RR[i]*Math.sqrt(pxs/w)));order.push(i)}
 order.sort((a,b)=>SW[b]-SW[a]);
 /* in the film a concept arrives larger and brighter than it stays */
 order.forEach((i,k)=>{const o=k*NS,c=C3[i],f=fp!==null?Math.max(0,1-(fp-R[i])/FLASH):0,u=1+2.5*f;
  nodeArr[o]=PX[i];nodeArr[o+1]=PY[i];nodeArr[o+2]=PZ[i];nodeArr[o+3]=RR[i]*(1+1.8*f);
  nodeArr[o+4]=c[0]*u;nodeArr[o+5]=c[1]*u;nodeArr[o+6]=c[2]*u;nodeArr[o+7]=N[i].c;
  nodeArr[o+8]=i===sel?3:(i===hov3&&!GH[i])?2:GH[i]?1:0});
 gl.bindBuffer(gl.ARRAY_BUFFER,nodeBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,nodeArr,0,order.length*NS);
 gl.viewport(0,0,g3.width,g3.height);gl.disable(gl.BLEND);
 gl.useProgram(PB.p);gl.uniform3fv(PB.u.uA,hex('#2e2d2a'));gl.uniform3fv(PB.u.uB,hex(css('--bg')));gl.uniform3fv(PB.u.uC,hex('#1b1b1b'));
 gl.bindVertexArray(vaoB);gl.drawArrays(gl.TRIANGLES,0,3);
 gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE);
 gl.useProgram(PD.p);gl.uniformMatrix4fv(PD.u.uM,false,M);gl.uniform1f(PD.u.uDpr,dpr3);gl.uniform3fv(PD.u.uCol,hex(css('--fg')));
 gl.bindVertexArray(vaoD);gl.drawArrays(gl.POINTS,0,ND);
 gl.useProgram(PH.p);gl.uniformMatrix4fv(PH.u.uM,false,M);gl.uniform3fv(PH.u.uR,right);gl.uniform3fv(PH.u.uU,up);
 gl.uniform1f(PH.u.uZs,cam.zs);gl.uniform1f(PH.u.uA,anySel||qv?.1:.22);gl.bindVertexArray(vaoH);gl.drawArraysInstanced(gl.TRIANGLE_STRIP,0,4,nH);
 gl.useProgram(PE.p);gl.uniformMatrix4fv(PE.u.uM,false,M);gl.uniform2f(PE.u.uV,W,H);gl.uniform1f(PE.u.uZs,cam.zs);gl.uniform1f(PE.u.uN,nearW);
 gl.uniform1f(PE.u.uF0,F0);gl.uniform1f(PE.u.uF1,F1);gl.uniform1f(PE.u.uTime,T3!==null?T3:performance.now()/1000);gl.uniform3fv(PE.u.uFg,hex(css('--fg')));gl.bindVertexArray(vaoE);gl.drawArraysInstanced(gl.TRIANGLE_STRIP,0,4,NE);
 gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
 gl.useProgram(PN.p);gl.uniformMatrix4fv(PN.u.uM,false,M);gl.uniform2f(PN.u.uV,W,H);gl.uniform1f(PN.u.uPx,pxs);
 gl.uniform1f(PN.u.uZs,cam.zs);gl.uniform1f(PN.u.uMin,umin);gl.uniform1f(PN.u.uMax,30);gl.uniform1f(PN.u.uF0,F0);gl.uniform1f(PN.u.uF1,F1);
 gl.uniform3fv(PN.u.uBg,hex(css('--bg')));gl.uniform3fv(PN.u.uAcc,hex(css('--acc')));gl.uniform1f(PN.u.uCell,SR_/CELL);
 gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,tex);gl.uniform1i(PN.u.uT,0);
 gl.bindVertexArray(vaoN);gl.drawArraysInstanced(gl.TRIANGLE_STRIP,0,4,order.length);gl.bindVertexArray(null);
 G3.drawn=order.length;labels(anySel)}

/* Labels on their own canvas, in screen space: the knowledge-base names in
   their hue, then concept names by the 2D graph's rule — the selection, what
   it links to, what is hovered, and the most-linked concepts the zoom allows,
   greedily, so no two overlap. Far labels fade with the fog. */
function fogAt(w){const t=Math.max(0,Math.min(1,(w-F0)/(F1-F0)));return 1-.72*t*t*(3-2*t)}
function labels(anySel){const x2=g3l.getContext('2d');x2.setTransform(dpr3,0,0,dpr3,0,0);x2.clearRect(0,0,W,H);
 x2.textAlign='center';x2.textBaseline='middle';x2.font='700 19px system-ui,-apple-system,sans-serif';x2.lineJoin='round';
 const bg=css('--bg');
 for(const k of KBS){if(offKB.has(k)||(KBB&&!KBB[k]))continue;const c=KBC[k],x=c.cx,y=-c.cy,z=KBZ[k]*cam.zs;
  const w=M[3]*x+M[7]*y+M[11]*z+M[15];if(w<=cam.d*.03)continue;
  const sx=((M[0]*x+M[4]*y+M[8]*z+M[12])/w*.5+.5)*W,sy=(.5-(M[1]*x+M[5]*y+M[9]*z+M[13])/w*.5)*H;
  x2.globalAlpha=(anySel||qv?.25:.85)*fogAt(w)*(KBB?KBB[k]:1);x2.lineWidth=5;x2.strokeStyle=bg;x2.strokeText(kbName(k),sx,sy);
  x2.fillStyle=HUE[k];x2.fillText(kbName(k),sx,sy)}
 x2.textAlign='start';x2.font='600 12px system-ui,-apple-system,sans-serif';x2.lineWidth=3;
 const s=pxs/cam.d,thr=s<.28?7:s<.55?4:s<.95?2:0,placed=[];
 const pri=i=>i===sel?1e6:i===hov3?1e5:(anySel&&NB[sel].has(i))?1e4+D[N[i].id].inb.length:D[N[i].id].inb.length;
 const cand=order.filter(i=>!GH[i]&&(i===sel||i===hov3||(anySel&&NB[sel].has(i))||D[N[i].id].inb.length>=thr)).sort((a,b)=>pri(b)-pri(a));
 for(const i of cand){const sx=SX[i],sy=SY[i];if(sx<-40||sy<0||sx>W+40||sy>H)continue;
  const t=D[N[i].id].t,wd=x2.measureText(t).width,bx=sx+SRp[i]+6,box=[bx-2,sy-9,bx+wd+2,sy+9];
  if(placed.some(p=>box[0]<p[2]&&box[2]>p[0]&&box[1]<p[3]&&box[3]>p[1]))continue;placed.push(box);
  x2.globalAlpha=i===sel||i===hov3?1:Math.max(.4,fogAt(SW[i]));
  x2.strokeStyle=bg;x2.strokeText(t,bx,sy);x2.fillStyle=i===sel?css('--fg'):css('--mut');x2.fillText(t,bx,sy)}
 x2.globalAlpha=1}

/* ---- input. Drag turns the map, Shift-drag or the right button moves it,
   the wheel zooms toward the pointer; a click that did not move selects, as
   in the 2D graph, and a second click lets go. The view keeps a little
   momentum after a turn, so it feels like an object rather than a slider. */
function pick3(mx,my){let best=-1,bw=1e18;
 for(const i of order){const r=SRp[i]+4,dx=SX[i]-mx,dy=SY[i]-my;if(dx*dx+dy*dy<r*r&&SW[i]<bw){bw=SW[i];best=i}}return best}
function local(e){const b=g3.getBoundingClientRect();return[e.clientX-b.left,e.clientY-b.top]}
function settle(){if(anim&&anim.ms>1000){Object.assign(cam,anim.g,{t:anim.g.t.slice()})}anim=null}
g3.addEventListener('contextmenu',e=>e.preventDefault());
g3.addEventListener('pointerdown',e=>{g3.setPointerCapture(e.pointerId);settle();vy=vp=0;
 drag3={x:e.clientX,y:e.clientY,m:0,t:performance.now(),pan:e.button!==0||e.shiftKey};idle=performance.now()});
g3.addEventListener('pointermove',e=>{const[mx,my]=local(e);
 if(drag3){const dx=e.clientX-drag3.x,dy=e.clientY-drag3.y,now=performance.now(),dt=Math.max(8,now-drag3.t);
  drag3.x=e.clientX;drag3.y=e.clientY;drag3.t=now;drag3.m+=Math.abs(dx)+Math.abs(dy);idle=now;
  if(drag3.m<5)return;g3.style.cursor='grabbing';
  if(drag3.pan){const k=cam.d/pxs;for(let j=0;j<3;j++)cam.t[j]+=(-dx*right[j]+dy*up[j])*k}
  else{const a=-dx*.0055,b=dy*.0055;turn(a,b);vy=a/dt;vp=b/dt}
  need=true;return}
 const h=cine?-1:pick3(mx,my);if(h!==hov3){hov3=h;need=true}g3.style.cursor=h>=0?'pointer':'grab'});
g3.addEventListener('pointerup',e=>{if(!drag3)return;const d=drag3;drag3=null;g3.style.cursor='grab';
 if(performance.now()-d.t>70)vy=vp=0;
 if(d.m<5){vy=vp=0;if(cine)return;const[mx,my]=local(e),h=pick3(mx,my);if(h>=0){if(sel===h)clearSel();else select(h)}}});
g3.addEventListener('pointerleave',()=>{if(hov3>=0&&!drag3){hov3=-1;need=true}});
g3.addEventListener('dblclick',e=>{if(cine)return;const[mx,my]=local(e),h=pick3(mx,my);if(h>=0){select(h);show(N[h].id)}else G3.fit()});
/* Safari's two-finger turn rolls the view and its pinch zooms, about the middle of the picture */
let ges3=null;
g3.addEventListener('gesturestart',e=>{e.preventDefault();settle();vy=vp=0;ges3={q:cam.q.slice(),d:cam.d}});
g3.addEventListener('gesturechange',e=>{e.preventDefault();if(!ges3)return;idle=performance.now();
 cam.q=qnorm(qmul(ges3.q,qax(0,0,1,(e.rotation||0)*Math.PI/180)));cam.d=Math.min(1e6,Math.max(DMIN,ges3.d/(e.scale||1)));need=true});
g3.addEventListener('gestureend',e=>{e.preventDefault();ges3=null});
/* The wheel zooms toward the pointer, and does not stop when it arrives:
   closer than DMIN it flies on, carrying the orbit point ahead of it along
   the pointer's ray, through the clusters and out the other side. Owner's
   requests of 23.09.2026, "move endlessly" and "zoom endlessly". Outward the
   one bound is a million units, some three hundred times the whole map, there
   only to keep the arithmetic finite. */
const DMIN=40;
g3.addEventListener('wheel',e=>{e.preventDefault();settle();vy=vp=0;idle=performance.now();
 if(e.altKey){roll(swipe(e));need=true;return}
 const[mx,my]=local(e),f=Math.exp(e.deltaY*(e.ctrlKey?.01:.0015));
 const want=Math.min(1e6,cam.d*f),nd=Math.max(DMIN,want),k=cam.d/pxs,r=nd/cam.d;
 for(let j=0;j<3;j++){const p=cam.t[j]+right[j]*(mx-W/2)*k+up[j]*(H/2-my)*k;cam.t[j]=p+(cam.t[j]-p)*r}
 cam.d=nd;
 if(want<DMIN){const ray=[0,1,2].map(j=>-back[j]+right[j]*(mx-W/2)/pxs+up[j]*(H/2-my)/pxs),l=Math.hypot(...ray),go=(DMIN-want)*3;
  for(let j=0;j<3;j++)cam.t[j]+=ray[j]/l*go}
 need=true},{passive:false});

/* ---- The Timelapse: this view with a director, the same canvas, marks, links
   and camera, and a clock that decides what shows and where the camera looks.
   It plays the vault's years. The playhead fp runs from 0 to TOT months; a
   concept is in the picture once fp has passed its birth, arrives with a
   flash, and a link draws itself when both its ends are there. The camera
   starts close in the first cluster and draws back as the bases begin.

   It was the Film, one of two cinema modes of 07.10.2026, on the owner's "i
   want more cinema, more spectacle"; the other, Flight, toured the concepts
   along the links. His words of 24.10.2026: "get rid of the flight", "name the
   film timelapse", "make the timelaps more cinematic. and also faster". So it
   lasts about thirty seconds, where the Film lasted 68: INTRO for the title and
   MSM for a month. It opens on a title, the vault's name and its years, which
   fades as the first cluster comes; the camera turns round the vault in one
   direction while it draws back; the year changes behind a fade; and at the
   end the caption names the vault and its totals. In the code, and in the
   address GLaDOS sends, `cine=film`, it keeps its first name. */
const el=id=>document.getElementById(id),box=el('cine'),cap=el('cineCap'),big=el('cineBig'),sub=el('cineSub'),title=el('cineTitle'),
 bar=el('cineTime'),bPlay=el('cinePlay'),bSpeed=el('cineSpeed');
const INB=N.map(n=>D[n.id].inb.length),INTRO=1800,FADE=1000,YF=180,LEAD=INTRO/MSM;
let cine=null,playing=false,speed=1,barDrag=false,wakeT=0,wentFull=false,ti=0,tf=0,TOTALS='';
el('cineYears').textContent=Math.floor(T0/12)+'–'+Math.floor((T0+TOT-1)/12);

/* The film's camera, second cut, 08.10.2026. The first looked at the concepts of
   the last year of film time, stood as far off as their spread asked, and
   turned slowly. Owner's words on it: "dont zoom in and out so much. this looks
   hectic and you loose sight", "start small inside the first cluster, then
   zoom out over time", "make sure to have an angle/view that you see all the
   important stuff of the whole universe". So the view keeps one direction,
   HOME, the one the 3D view opens on, and the frames are planned for the whole
   film before it plays. A month's frame is the fit of every knowledge base
   that has begun, a tenth of its concepts being there, or of the largest one
   while none has, and of the vault's most-linked concept, which is there
   from the first month and stands between the bases: without it in the fit it
   sat on the picture's lower edge, half behind the bar; as it will be a year
   on: the camera has drawn back before a
   base begins, not after. The distance is never let fall from one month to the
   next, and the frames are averaged over the months around, so the camera
   starts close in the first cluster and draws back slowly, and only back.

   And it is never still. Owner's words on the second cut, the same day: "keep
   the camera always slightly in motion. especially at the beginning it was to
   static and towards the end". Until 24.10.2026 the view swayed a few degrees
   about HOME. The Timelapse turns it round the vault instead, about the
   picture's upright: by ORBIT at the title's start, in one direction, slower
   the nearer the end, and on HOME at the last month. u is the playhead, and
   before it the title's time in months, so the camera turns under the title
   too. A time of the film has one view, and each month's frame is fitted for
   the view that month has. */
const CAP=130,ORBIT=.9;let plan=[];
const look=u=>{const x=Math.min(1,Math.max(0,(u+LEAD)/(TOT+LEAD)));return qnorm(qmul(HOME,qax(0,1,0,ORBIT*(1-x)*(1-x))))};
function planFilm(){const tot={};let hub=-1,l=0;for(let i=0;i<NN;i++)if(!hid(N[i])){tot[N[i].kb]=(tot[N[i].kb]||0)+1;if(hub<0||INB[i]>INB[hub])hub=i}
 const raw=[];for(let m=1;m<=TOT;m++){const n={};for(let i=0;i<NN;i++)if(!hid(N[i])&&R[i]<m)n[N[i].kb]=(n[N[i].kb]||0)+1;
  let on=Object.keys(n).filter(k=>n[k]>=tot[k]*.1);if(!on.length)on=Object.keys(n).sort((x,y)=>n[y]-n[x]).slice(0,1);
  raw.push(fitFor(look(m),1,i=>!hid(N[i])&&R[i]<m&&(i===hub||on.includes(N[i].kb)),CAP)||raw[raw.length-1]||{t:cam.t.slice(),d:cam.d})}
 for(let m=1;m<raw.length;m++)if(raw[m].d<raw[m-1].d)raw[m]={t:raw[m].t,d:raw[m-1].d};
 plan=raw.map((_,m)=>raw[Math.min(raw.length-1,m+12)]);
 for(let pass=0;pass<2;pass++)plan=plan.map((_,m)=>{const t=[0,0,0];let l=0,c=0;
  for(let j=Math.max(0,m-10);j<=Math.min(plan.length-1,m+10);j++,c++){for(let k=0;k<3;k++)t[k]+=plan[j].t[k];l+=Math.log(plan[j].d)}
  return{t:t.map(v=>v/c),d:Math.exp(l/c)}});
 /* what the end names: the vault as the film has shown it */
 E3.forEach(([a,b])=>{if(!hid(N[a])&&!hid(N[b]))l++});const n=Object.values(tot).reduce((a,b)=>a+b,0),k=Object.keys(tot).length;
 TOTALS=sw(n)+(n===1?' concept':' concepts')+' · '+sw(l)+(l===1?' link':' links')+' · '+k+(k===1?' knowledge base':' knowledge bases')}
function framed(p){const x=Math.max(0,Math.min(plan.length-1,p-1)),a=plan[Math.floor(x)],b=plan[Math.ceil(x)],f=x-Math.floor(x);
 return{t:a.t.map((v,k)=>v+(b.t[k]-v)*f),d:Math.exp(Math.log(a.d)+(Math.log(b.d)-Math.log(a.d))*f)}}
/* The caption: the year, and below it the count of concepts; at the end the
   vault's name and its totals. Its words change behind a fade, out and in in
   YF each, so the year changes softly; the count goes on under a year without
   one. The title stands in its place while the film begins, and gives way to
   it over FADE of the film's time. */
let shown='',due='',fa=1;
function words(){if(fp>=TOT){big.textContent='00_Cerebrum';sub.textContent=TOTALS;return}
 let n=0;for(let i=0;i<NN;i++)if(!gone(i))n++;const s=sw(n)+(n===1?' concept':' concepts');
 if(big.textContent!==shown)big.textContent=shown;if(sub.textContent!==s)sub.textContent=s}
function filmUI(){due=fp>=TOT?'end':String(Math.floor((T0+Math.min(TOT-1,Math.floor(fp)))/12));
 if(due===shown&&fp<TOT)words();
 if(!barDrag)bar.value=Math.round(fp/TOT*1000)}
function fade(dt){if(due!==shown){fa=RM.matches||!shown?0:fa-dt/YF;if(fa<=0){shown=due;words();fa=RM.matches?1:0}}
 else if(fa<1)fa=Math.min(1,fa+dt/YF);
 const ta=ti>0?1:tf/FADE;title.style.opacity=ta;cap.style.opacity=fa*(1-ta)}
function seek(p){if(!cine)return;fp=Math.max(0,Math.min(TOT,p));ti=tf=0;
 if(!playing){const g=fp>=TOT?fitFor(cam.q,1,null,CAP):Object.assign(framed(fp),{q:RM.matches?cam.q.slice():look(fp)});if(g)tween(g,700)}
 filmUI();need=true}

const ICON={play:'<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',pause:'<svg viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>'};
function ui(){box.classList.toggle('paused',!playing);bPlay.innerHTML=playing?ICON.pause:ICON.play;
 bPlay.setAttribute('aria-label',playing?'Pause':'Play');bPlay.title=(playing?'Pause':'Play')+' (Space)';bSpeed.textContent=speed+'×';
 if(cine)filmUI()}
function wake(){box.classList.add('awake');clearTimeout(wakeT);wakeT=setTimeout(()=>box.classList.remove('awake'),2600)}
/* the film's first frame, set and not glided to: at its start, and when Play begins it again at its end */
function first(){const a=framed(0);cam.t=a.t.slice();cam.d=a.d;cam.q=look(-LEAD);anim=null}
function play(on){if(!cine)return;playing=on;if(on&&fp>=TOT){fp=0;ti=INTRO;tf=0;first()}ui();need=true}
/* One step of the director, dt milliseconds of the frame loop's time: the
   title's time first, then the film's. */
function cineStep(dt){let ms=playing?dt*speed:0;
 if(ms&&ti>0){const u=Math.min(ti,ms);ti-=u;ms-=u;if(!ti)tf=FADE;if(!RM.matches&&!drag3)cam.q=look(-ti/MSM)}
 if(ms&&tf>0)tf=Math.max(0,tf-ms);
 if(ms&&fp<TOT){fp=Math.min(TOT,fp+ms/MSM);
  if(fp>=TOT){playing=false;const g=fitFor(cam.q,1,null,CAP);if(g)tween(g,2600);ui()}
  else if(!drag3){const a=framed(fp),k=RM.matches?1:1-Math.exp(-dt/600);
   for(let j=0;j<3;j++)cam.t[j]+=(a.t[j]-cam.t[j])*k;cam.d=Math.exp(Math.log(cam.d)+(Math.log(a.d)-Math.log(cam.d))*k);
   if(!RM.matches)cam.q=look(fp)}}
 filmUI();fade(dt)}
function cineStart(){if(view!=='3d')setView('3d');if(cine)cineStop();
 cine='film';playing=!RM.matches;speed=1;clearSel();hov3=-1;anim=null;vy=vp=0;cam.zs=1;
 document.body.classList.add('cine');box.hidden=false;box.className='';resize3();
 fp=0;ti=INTRO;tf=0;shown=due=big.textContent=sub.textContent='';cam.q=HOME.slice();planFilm();first();
 wake();ui();need=true}
function cineStop(){if(!cine)return;cine=null;fp=null;playing=false;anim=null;ti=tf=0;
 document.body.classList.remove('cine');box.hidden=true;resize3();
 if(wentFull&&document.fullscreenElement)document.exitFullscreen();wentFull=false;
 clearSel();need=true;G3.fit()}
bPlay.onclick=()=>{play(!playing);bPlay.blur()};
bSpeed.onclick=()=>{speed=speed>=4?1:speed*2;ui();bSpeed.blur()};
el('cineX').onclick=cineStop;el('bFilm').onclick=()=>cineStart();
el('cineFull').onclick=e=>{e.currentTarget.blur();if(document.fullscreenElement)document.exitFullscreen();
 else{wentFull=true;document.documentElement.requestFullscreen().catch(()=>{wentFull=false})}};
bar.addEventListener('pointerdown',()=>{barDrag=true});addEventListener('pointerup',()=>{barDrag=false});
bar.addEventListener('input',()=>seek(bar.value/1000*TOT));
box.parentNode.addEventListener('pointermove',()=>{if(cine)wake()});
/* Space plays and pauses, as in any player; not while a field has the keys */
addEventListener('keydown',e=>{if(!cine||e.key!==' '||e.metaKey||e.ctrlKey||e.altKey)return;const t=e.target;
 if(t&&(t.tagName==='SELECT'||(t.tagName==='INPUT'&&t.type!=='range')))return;e.preventDefault();play(!playing)});
G3.cine={on:()=>!!cine,start:cineStart,stop:cineStop,play,seek,
 state:()=>({kind:cine,playing,speed,fp,total:TOT,t0:T0,intro:ti}),
 /* viewer-check lets the director's clock run by a stated time, in the frame loop's own steps */
 advance:ms=>{for(;ms>0&&cine;ms-=50)cineStep(Math.min(50,ms));need=true}};
/* and reads a link and a mark as the last frame uploaded them */
G3.link=(a,b)=>{const j=E3.findIndex(e=>e[0]===Math.min(a,b)&&e[1]===Math.max(a,b));if(j<0)return null;
 return{lo:[...eArr.slice(j*12,j*12+3)],hi:[...eArr.slice(j*12+3,j*12+6)],alpha:wArr[j*4]}};
G3.at=p=>{matrix();const w=M[3]*p[0]+M[7]*p[1]+M[11]*p[2]+M[15];return w<=nearW?null:[((M[0]*p[0]+M[4]*p[1]+M[8]*p[2]+M[12])/w*.5+.5)*W,(.5-(M[1]*p[0]+M[5]*p[1]+M[9]*p[2]+M[13])/w*.5)*H]};
G3.mark=i=>{const k=order.indexOf(i);return k<0?null:{r:nodeArr[k*NS+3],rgb:[...nodeArr.slice(k*NS+4,k*NS+7)],s:nodeArr[k*NS+8]}};

(function loop3(now){requestAnimationFrame(loop3);if(view!=='3d')return;
 const dt=Math.min(64,now-last);last=now;let moved=false;
 if(anim){step(now);moved=true}
 if(cine){cineStep(dt);moved=true}
 if(!drag3&&(Math.abs(vy)+Math.abs(vp))>1e-6){turn(vy*dt,vp*dt);
  const k=Math.pow(.9,dt/16);vy*=k;vp*=k;if(Math.abs(vy)+Math.abs(vp)<2e-6)vy=vp=0;moved=true}
 const still=now-idle;
 if(!cine&&!RM.matches&&!drag3&&!anim&&hov3<0&&still>6000){turn(dt*4e-5,0);moved=true}
 if(!RM.matches)moved=true;   // the flow along the links
 if(moved||dirty||need){dirty=false;need=false;draw3()}})(last);
})();
'''

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
# What's new, owner's request of 24.10.2026: "why does cerebrum not have a
# whats new. please build"; and the same day, in folia's shape: "make in
# settings whats new look like the one from folia". As folia's, the list is
# written by hand for the reader, `_scripts/whats-new.json`, newest first: each
# commit that changed this page, by its heading, with a title and a line on
# what it does. A change no reader can see has no title, says why, and is not
# shown. verify.py fails a commit of this page whose heading it does not name.
news = [{'k': n['change'], 'd': n['date'], 't': n['title'], 'x': n['detail']}
        for n in json.load(open(os.path.join(VAULT, '_scripts', 'whats-new.json'), encoding='utf-8'))
        if n['title']]
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
# viewer-check.js reads this list and holds the stamp to it.
PAGE_INPUTS = [':(glob)*/Wiki/**', '_scripts/visualize.py', '_scripts/whats-new.json']
if _git('status', '--porcelain', '--', *PAGE_INPUTS):
    git_id += ' · uncommitted'
# --json: the data the page carries, and only that, as one JSON object on
# stdout, for a viewer of your own; no page is built. Everything above is the
# same for both, so the two cannot disagree.
if '--json' in sys.argv[1:]:
    json.dump({'concepts': data, 'halos': halos, 'blocks': KB_BLOCKS,
               'build': {'git': git_id, 'stamp': stamp, 'number': build_no, 'started': started},
               'news': news, 'mark': {'header': _mark('h'), 'about': _mark('a', pulse=True)}},
              sys.stdout, ensure_ascii=False)
    sys.exit(0)

page = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="cerebrum-address" content="view q cine"><title>00_Cerebrum — OKF viewer</title><style>
:root{color-scheme:dark;--bg:#242424;--fg:#f9f2d9;--mut:#a49a85;--line:#3a3733;--acc:#f0c755;--h3:#e5d5a1;--side:#191919;--card:#2b2b2b;--item:#bbaf96;--ph:#757575;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;--s9:#38b2c3;--s10:#9fae2f;--s11:#c08b52;--s12:#8ecae6;--s13:#b0b7c3;--s14:#7fd1ae;--s15:#cb54d6;--s16:#e0c04d;--s17:#5ec8f2;--lin:#5aa9ff;--lout:#ff9f43;--edge:#4a4640}
*{box-sizing:border-box}[hidden]{display:none!important}
/* One header over two full-screen views. Owner's instruction of 14.09.2026: the
   mark on the left, the categories to its right, and below that either the
   Graph view or the Concept view with the whole window to itself. The page is a
   column, so the header keeps its own height and the view takes the rest. The
   body never scrolls; each view scrolls inside itself. */
body{margin:0;font:16px/1.6 -apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;height:100vh;overflow:hidden}
#top{flex:0 0 auto;position:relative;z-index:20;display:flex;align-items:center;gap:16px;padding:10px 16px 10px 10px;background:var(--side);border-bottom:1px solid var(--line)}
#stage{flex:1;min-height:0;display:flex;position:relative}
#gpane,#cpane,#g3pane{flex:1;min-width:0;position:relative;display:flex}
#gpane{flex-direction:column}
/* The view is a body class, so one switch decides both panes and nothing can
   leave the two showing together. */
body.vg #cpane,body.vc #gpane,body.v3 #gpane,body.v3 #cpane,body.vg #g3pane,body.vc #g3pane{display:none}
/* The card and Fit float over whichever graph is showing, 2D or 3D, so they sit
   in the stage rather than in one pane, and the Concept view hides them. */
body.vc #gcard{display:none!important}
/* The 3D view: a faint vignette of the page's own ground, so the clusters seem
   to float in a room rather than on a sheet. The canvas is opaque and paints
   the same vignette itself; this one shows only before its first frame. The
   labels are a second canvas over it that takes no pointer. */
#g3pane{background:radial-gradient(120% 95% at 50% 42%,#2e2d2a 0%,var(--bg) 52%,#1b1b1b 100%)}
#g3,#g3lbl{position:absolute;inset:0;width:100%;height:100%;display:block}
#g3{cursor:grab;touch-action:none}#g3lbl{pointer-events:none}
/* The Timelapse, 24.10.2026, until then the Film, 07.10.2026: the 3D view as a
   cinema. Its button sits in the 3D pane and not in the header, where a third
   view button once wrapped the category row at 1440px. In the cinema
   everything but the picture leaves: the header, the search bar, the card. Two
   black bars frame it, the lower one holds the controls, and those fade while
   the pointer is still. Its words are set as the page sets its own: the year
   and the vault's name as a page's h1, the count below as the card's
   description, the years under the opening title as the small grey label of
   the card and the list, and the controls in the colours of the page's
   controls. Owner's instruction of 07.10.2026, "please use the same font and
   font color", after the first cut set the film's date thin, off-white and
   78px high. The title stands in the middle of the picture, which is dark
   while it shows; the page sets the opacity of it and of the caption. */
#cineGo{position:absolute;left:16px;top:44px;z-index:2;display:flex;gap:6px}
#cineGo button{height:28px;padding:0 12px 0 10px;border-radius:14px;border:1px solid var(--line);background:var(--side);color:var(--item);font-size:12px;letter-spacing:.02em;display:inline-flex;align-items:center;gap:7px}
#cineGo button::before{content:"";border-left:7px solid currentColor;border-top:4.5px solid transparent;border-bottom:4.5px solid transparent}
#cineGo button:hover{color:var(--fg);border-color:var(--acc)}
body.cine #top,body.cine #askbar,body.cine #gcard,body.cine #g3stat,body.cine #g3hint,body.cine #cineGo{display:none!important}
#cine{position:absolute;inset:0;z-index:4;pointer-events:none;--bar:max(9vh,58px)}
#cine[hidden]{display:none}
#cine .bar{position:absolute;left:0;right:0;height:var(--bar);background:#000}
#cine .bar.top{top:0}#cine .bar.bot{bottom:0}
#cine::before{content:"";position:absolute;left:0;right:0;bottom:var(--bar);height:36vh;background:linear-gradient(#0000,#000b)}
#cineCap{position:absolute;left:8vw;right:8vw;bottom:calc(var(--bar) + 26px);text-align:center;text-shadow:0 0 3px #000,0 2px 22px #000}
#cineTitle{position:absolute;left:8vw;right:8vw;top:50%;transform:translateY(-50%);text-align:center;opacity:0;text-shadow:0 0 3px #000,0 2px 22px #000}
#cineYears{margin-top:.4em}
#cineBig,#cineName{color:var(--acc);font-size:1.75em;font-weight:700;letter-spacing:-.01em;line-height:1.3;font-variant-numeric:tabular-nums}
#cineSub{margin:.3em auto 0;max-width:74ch;font-size:.95em;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
#cineCtl{position:absolute;left:0;right:0;bottom:0;height:var(--bar);display:flex;align-items:center;justify-content:center;gap:10px;padding:0 16px;pointer-events:auto;opacity:0;transition:opacity .35s}
#cine.awake #cineCtl,#cine.paused #cineCtl,#cineCtl:focus-within{opacity:1}
#cineCtl button{height:34px;border-radius:17px;border:1px solid var(--line);background:var(--side);color:var(--item);font-family:inherit;font-size:.9em;padding:0 14px}
#cineCtl button:hover{color:var(--fg);border-color:var(--acc)}
#cinePlay,#cineFull,#cineX{width:34px;padding:0!important;display:inline-grid;place-items:center}
#cineCtl svg{width:16px;height:16px;fill:currentColor}
#cineX{font-size:18px!important;line-height:1}
/* The time bar takes none of the page's padding for inputs: with it the knob
   stopped ten pixels before the end of the bar, and the owner saw a film that
   "does not go to the end" (07.10.2026). */
#cineTime{flex:0 1 46vw;accent-color:var(--acc);padding:0;border:0;background:none}
#cineTime{margin-bottom:0}   /* the page's inputs carry a margin below, which would lift this one off the row */
/* One help line per graph, bottom left, in the same words where the control
   is the same. The 2D one joined on 23.09.2026, on the owner's request, and the
   same day the Fit button went, on the owner's instruction: a double-click on
   empty space does what it did, and the line says so. `f` still fits. */
#g2hint,#g3hint,.gstat{position:absolute;left:16px;bottom:18px;z-index:2;color:var(--mut);font-size:12px;letter-spacing:.02em;pointer-events:none;opacity:.8}
#g2hint b,#g3hint b,.gstat b{color:var(--item);font-weight:600}
/* The vault's figures, top left of each graph in the hints' own style: the
   hints say how to drive the map at its foot, the figures say what is on it
   at its head, the same distance from the edge. Owner's instruction of
   27.09.2026; they stood under the logo that morning. */
.gstat{top:18px;bottom:auto;font-variant-numeric:tabular-nums}
/* The list scrolls and the controls above it do not: the search box moved into
   this column, and a search box that scrolls away with the list is gone exactly
   when the list is long enough to need it. Both parts reserve the same scrollbar
   gutter, so the box and the rows under it share a right edge. */
#side{width:var(--sidew,450px);min-width:220px;max-width:60vw}
#side{flex:0 0 auto;background:var(--side);display:flex;flex-direction:column;min-height:0}
#sidetop{flex:0 0 auto;overflow:hidden;scrollbar-gutter:stable;padding:14px 8px 9px 14px;border-bottom:1px solid var(--line)}
#tree{flex:1;min-height:0;overflow-y:auto;scrollbar-gutter:stable;padding:9px 8px 14px 14px}
#splitter{flex:0 0 6px;position:relative;cursor:col-resize;background:transparent}
#splitter::before{content:'';position:absolute;top:0;bottom:0;left:-6px;right:-6px}
#splitter::after{content:'';position:absolute;top:0;bottom:0;left:2px;width:2px;background:var(--line)}
#splitter:hover::after,#splitter.on::after{left:0;width:6px;background:var(--acc)}
/* The page is one column centred in what the list leaves. Centring each child
   instead, which full screen did, put a 72ch paragraph and a 980px table on two
   different left edges. */
#main{flex:1;min-width:0;overflow-y:auto;scrollbar-gutter:stable;padding:30px 46px}#main .doc{max-width:980px;margin:0 auto}#main p,#main ul,#main ol,#main blockquote{max-width:72ch;line-height:1.7}#main li{margin:.15em 0}
h1,h2{color:var(--acc)}h3,h4,h5{color:var(--h3)}h1{font-size:1.75em;margin:.2em 0;letter-spacing:-.01em}h2{font-size:1.35em;border-bottom:1px solid var(--line);padding-bottom:5px;margin-top:1.9em}h3{font-size:1.15em;margin-top:1.5em}
/* One control surface. Buttons and inputs do not inherit font-family, so every
   control on this page rendered in the UA's Arial beside the page's own
   -apple-system — which is what "the sidebar is a different font" was. The
   sizes had drifted with it: 13.33px on the toggles and the search box against
   13.6px on Collapse all and the About actions, two values close enough to look
   like a mistake and far enough apart to be one. Six rules declared the same
   border, radius, background and colour; they now declare what differs. */
button,input{font-family:inherit;font-size:.9em;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}
input{width:100%;padding:8px 10px;margin-bottom:10px;cursor:text}
/* The house label: a group header in the list, a section head on the graph
   card, the eyebrows and card labels in About and Settings. Six rules carried
   these five properties, and one of the six carried them wrong — `#gcard .sec`
   had no font-weight, so the graph card's headings rendered lighter than the
   identical-looking headers a few hundred pixels to their left. */
.grp,#gcard .sec,#aboutBtn .eyebrow,#cineYears{color:var(--mut);font-size:.78em;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
.grp{margin:12px 0 2px;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;padding:2px 4px;border-radius:5px}
.grp:hover{color:var(--fg);background:var(--line)}.grp .gn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grp .cv{display:inline-block;width:9px;transition:transform .12s;font-size:.9em}.grp.shut .cv{transform:rotate(-90deg)}
.gitems{padding-left:15px;border-left:1px solid var(--line);margin-left:8px}
.grp small{font-weight:400;opacity:.75;font-size:.95em}.grp.flat{cursor:default}.grp.flat:hover{background:none;color:var(--mut)}.grp.flat .cv{visibility:hidden}
#tree .kbh:first-child{margin-top:0}
.kbh{display:flex;align-items:center;gap:6px;width:100%;margin:10px 0 4px;padding:6px 8px;text-align:left;font-size:13px;font-weight:700}
.kbh small{font-weight:400}
.kbh .gn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kbh small{opacity:.7;font-size:.85em;color:inherit;margin-left:-1px}
.kbh .cv{display:inline-block;width:9px;transition:transform .12s;font-size:.9em}.kbh.shut .cv{transform:rotate(-90deg)}.kbh.flat{cursor:default}.kbh.flat .cv{visibility:hidden}
.kbbody .grp:first-child{margin-top:6px}
/* The search bar spans the window. Until 16.09.2026 it sat in a 450px column
   above the list and was re-parented on every view switch; the owner asked for
   the full width, and Ask Claude needs the room. The shape is j4k's
   `.overviewSearchBox`: a grid of auto tracks around one `minmax(0,1fr)`, the
   mode buttons at the left, so the input takes whatever the buttons leave and
   nothing wraps at any width. */
#askbar{flex:0 0 auto;position:relative;z-index:19;background:var(--side);
 border-bottom:1px solid var(--line);padding:9px 16px 10px}
#qwrap{display:grid;grid-template-columns:auto auto minmax(0,1fr) auto auto;
 align-items:center;gap:6px;position:relative}
/* j4k's mode pair, not a toggle: the magnifier and the sparkle stand side by
   side and the active one is lit, so the box always says which of the two it
   is. Its buttons are 30px square at 6px radius and carry no hover rule of
   their own — state is the `.on` class and nothing else. */
#qwrap .mb{width:30px;height:30px;padding:0;display:inline-flex;align-items:center;
 justify-content:center;border:1px solid var(--line);border-radius:6px;
 background:transparent;color:var(--item)}
#qwrap .mb svg{width:16px;height:16px}
#qwrap .mb.on{border-color:var(--acc);color:var(--fg);background:var(--line)}
/* Ask is j4k's bronze, the one colour on this page that is not a token: the
   two search bars are meant to feel like the same control, and this half of it
   is the half that costs money. `#c8901d` border on `#f7edd6`, `#8a5c00` text
   in j4k's light theme; here the fill is the dark-theme pair it ships,
   `#302811` under `#e3aa3c`. */
#mAsk.on{border-color:#c8901d;background:#f7edd6;color:#8a5c00}
/* The login is running out. A tooltip nobody hovers is not a warning, so the
   button carries it: the page's warn colour on its border, and a dot in the
   corner that stays whichever mode is lit. */
#mAsk.warn{border-color:var(--s2)}
#mAsk.warn::before{content:'';position:absolute;top:-3px;right:-3px;width:7px;
 height:7px;border-radius:50%;background:var(--s2)}
#mAsk{position:relative}
#qwrap .mb:disabled{opacity:.42;cursor:default}
#askbar.ask #q{border-color:#c8901d}
#askbar.ask #q::placeholder{color:#8a5c00;opacity:.85;font-style:italic}
@media (prefers-color-scheme:dark){#mAsk.on{border-color:#e3aa3c;background:#302811;color:#e3aa3c}
 #askbar.ask #q{border-color:#e3aa3c}#askbar.ask #q::placeholder{color:#e3aa3c;opacity:.8}}
/* One grammar for every control, and it is the concept row's: a control rests
   in --item on no fill behind a transparent border, hovers to --fg on --line,
   and marks itself active with the accent border. Identical to `.it`, `.it:hover`
   and `.it.on` below — the transparent border is what keeps a row from shifting
   a pixel when it activates. Owner's instruction of 01.09.2026, after three
   passes that moved the concept row toward the buttons; this moves the buttons
   to the row, which is the direction the list wanted all along. The header's
   icon buttons and the graph's Fit joined it on 14.09.2026, so the switch that
   says which view is showing speaks the same language as the row that says
   which concept is. */
.ib,#ball,#q{background:transparent;border:1px solid transparent;border-radius:5px;color:var(--item);font-size:.95em;padding:4px 7px}
.ib:hover,#ball:hover,#q:hover{background:var(--line);color:var(--fg)}
.ib.on{border-color:var(--acc);color:var(--fg)}
#q{margin-bottom:0;min-width:0;padding-right:30px;position:relative}#q::placeholder{color:var(--ph)}
/* The progress bar. A report takes minutes and the page has to say so, but
   nothing here knows how long the librarian will take, so the bar is not a
   guess against a clock: it steps when the helper reports a real milestone —
   the run starting, each tool the librarian picks up, the report filed. The
   steps shrink as they go (1/2 of what is left, then 1/3, then 1/4), so it
   always advances and never reaches the end before the end does.
   **It fills the search box itself.** Until 16.09.2026 it was a 2px line under
   the bar, and the owner read that as a hairline rather than a bar. The input
   is already the right shape and already carries the running commentary in its
   placeholder, so the fill goes behind that text: the question's progress and
   the question's box are one control rather than two. It is placed in the
   input's own grid cell, so it matches the input at every width with no pixel
   arithmetic, and both are stretched to the row so the cell is the input.
   The input is static and the fill is not positioned, so the input's text
   paints above it whatever the DOM order. */
#q,#qbar{grid-column:3;grid-row:1;align-self:stretch}
#qbar{margin:1px;border-radius:4px;overflow:hidden;pointer-events:none}
#qbar i{display:block;height:100%;width:0;background:rgba(200,144,29,.26);
 transition:width .45s ease-out}
#qbar.done i{width:100%;background:rgba(200,144,29,.42)}
@media (prefers-color-scheme:dark){#qbar i{background:rgba(227,170,60,.2)}
 #qbar.done i{background:rgba(227,170,60,.32)}}
/* Thinking: j4k twinkles its sparkle button while the model works. One
   pseudo-element carries the whole starfield, each star a box-shadow with its
   own colour, so the keyframes fade them out of step and no two wink together. */
#mAsk.busy::after{content:'';position:absolute;left:50%;top:50%;width:1.5px;height:1.5px;
 border-radius:50%;pointer-events:none;
 animation:spark 2.6s linear infinite}
@keyframes spark{
 0%,100%{box-shadow:-9px -6px 0 .4px rgba(200,144,29,.85),7px -8px 0 .2px rgba(200,144,29,.15),
  10px 5px 0 .4px rgba(200,144,29,.55),-6px 8px 0 .2px rgba(200,144,29,.2),0px -11px 0 .3px rgba(200,144,29,.35)}
 33%{box-shadow:-9px -6px 0 .2px rgba(200,144,29,.2),7px -8px 0 .4px rgba(200,144,29,.8),
  10px 5px 0 .2px rgba(200,144,29,.15),-6px 8px 0 .4px rgba(200,144,29,.6),0px -11px 0 .2px rgba(200,144,29,.8)}
 66%{box-shadow:-9px -6px 0 .4px rgba(200,144,29,.55),7px -8px 0 .2px rgba(200,144,29,.25),
  10px 5px 0 .4px rgba(200,144,29,.85),-6px 8px 0 .2px rgba(200,144,29,.15),0px -11px 0 .4px rgba(200,144,29,.3)}}
@media (prefers-reduced-motion:reduce){#mAsk.busy::after{animation:none}}
#q:focus{border-color:var(--acc);color:var(--fg);outline:none}
/* Buttons carried no focus style, so they showed the UA's blue ring — and it
   appeared at a confusing moment: clicking a button sets :focus without
   :focus-visible, and the *first keystroke afterwards* switches the browser to
   keyboard modality, so pressing Escape lit up the button that had been
   clicked minutes earlier. The ring is not removed, because a control reachable
   by Tab has to show where you are; it is given the page's own accent. */
button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
#qwrap.has #q{border-color:var(--acc);color:var(--fg)}
/* The icon takes the button's own colour rather than --mut: the label is the
   placeholder's grey and the two sat a shade apart, which was invisible while
   the search icon above it was --mut too and obvious once the bar moved. */
#ball .qi{position:absolute;left:10px;top:50%;transform:translateY(-50%);display:flex;color:inherit;pointer-events:none}#ball .qi svg{width:16px;height:16px}
#qx{position:absolute;right:58px;top:50%;transform:translateY(-50%);display:none;border:0;background:none;padding:0 6px;line-height:1;font-size:1.15em;color:var(--mut);border-radius:5px}
#qx:hover{color:var(--fg);background:var(--line)}
#qwrap.has #qx{display:block}
/* Collapse all is the search bar's second row: its icon under the search icon,
   its label where the search text starts, in the placeholder's grey. Owner's
   instruction of 14.09.2026. That grey was a default each browser picks for
   itself until then, so the page sets it now, for both. The icon stands at
   9px, not 10: the button has a border and the search bar's wrapper has none. */
#ball{width:100%;position:relative;text-align:left;padding-left:32px;color:var(--ph)}#ball .qi{left:9px}#ball:disabled{opacity:.45;cursor:default;background:transparent;border-color:transparent;color:var(--ph)}
/* The transparent border at rest is what keeps the row from shifting by a
   pixel when it is selected; every item carries it, so nothing moves. */
.it{display:block;padding:3px 7px;border:1px solid transparent;border-radius:5px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.95em}
/* Selection is the activated fold button: accent border, full text colour, no
   fill. The amber fill it replaced was the loudest thing in the sidebar and
   said "active" in a second grammar of its own. Hover keeps the grey fill, so
   the two states stay distinguishable and a hovered selection shows both. */
.it{color:var(--item)}.it:hover{background:var(--line);color:var(--fg)}.it.on{border-color:var(--acc);color:var(--fg)}
.badge{display:inline-block;font-size:.72em;padding:1px 8px;border-radius:9px;border:1px solid var(--line);color:var(--mut);margin-right:6px}
.badge.hu{border-color:#0ca30c;color:#0ca30c}.badge.dr{border-color:#fab219;color:#fab219}
a.nav{color:var(--acc);cursor:pointer;text-decoration:underline}a.dead{color:var(--mut);border-bottom:1px dashed var(--mut);cursor:help}
table{border-collapse:collapse;margin:.9em 0;font-size:.95em}td,th{border:1px solid var(--acc);padding:6px 11px;text-align:left;vertical-align:top}th{background:var(--side)}
code{background:var(--side);border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:.9em}
blockquote{border-left:3px solid var(--acc);margin:.6em 0;padding:.1em 1em;color:var(--mut)}
.fns{border-top:1px solid var(--line);margin-top:1.8em;padding-top:.7em;font-size:.9em;color:var(--mut);max-width:72ch;line-height:1.55}
.meta{color:var(--mut);font-size:.92em;margin:.4em 0 1.3em}.gbtns{float:right;display:flex;gap:2px;margin:6px 0 10px 18px}sup.fn{color:var(--mut)}
.links{font-size:.88em;color:var(--mut);margin:.8em 0}
/* The header, left to right: the mark, the categories, the controls. */
/* The brand is the About control. It repeats the dialog's own header — eyebrow
   over the name — so pressing it opens something that looks like what was
   pressed, and the mark carries the identity in both places. The border stays
   declared and transparent so the hover outline costs no layout shift. */
#aboutBtn{flex:0 0 auto;display:flex;align-items:center;gap:14px;padding:6px 10px 6px 8px;border:1px solid transparent;border-radius:8px;background:transparent;cursor:pointer}
/* Hover is the outline alone. Filling the cell put back the surface the row
   had just been relieved of, a moment after it was taken away. */
#aboutBtn:hover{border-color:var(--acc)}
#aboutBtn svg{width:69px;height:60px;flex:0 0 auto}
#aboutBtn .tx{display:grid;gap:2px;min-width:0;text-align:left}
#aboutBtn .wm{color:var(--acc);font-size:1.3em;font-weight:700;line-height:1.1;white-space:nowrap}
/* The categories. 12px rather than the old legend's .8em: at .8em the employer
   row measured 1107px, and it has to share a 1440px window with the mark and
   the controls without wrapping. At 12px it measures 991px. */
#legend{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--mut)}
#legend .lrow{display:flex;flex-wrap:wrap;gap:5px 6px;align-items:center}
.chip{display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 8px 0 6px;border:1px solid var(--line);border-radius:12px;cursor:pointer;user-select:none;white-space:nowrap}
.chip:hover{background:var(--line)}
.chip.off{opacity:.32}.chip b{font-weight:600;color:var(--fg)}.chip small{color:var(--mut);font-variant-numeric:tabular-nums}
/* A row or a chip with nothing showing keeps its place, invisible: the header
   does not change height and no chip slides sideways when a knowledge base is
   hidden. Owner's instruction of 27.09.2026. */
#legend .void{visibility:hidden}
/* The controls are icons, as j4k's top bar is: each is named by its tooltip.
   Views first, then Settings, set a little apart because it opens something
   rather than switching something. */
/* Three view buttons since 23.09.2026, when 3D joined. The extra 42px made the
   employer row of categories wrap at 1440px, so the header gave back 22px from
   its gaps and the brand's right padding; viewer-check holds the row to one line. */
#tools{flex:0 0 auto;display:flex;align-items:center;gap:8px}
#views{display:flex;gap:2px}
.ib{position:relative;display:inline-grid;place-items:center;width:38px;height:38px;padding:0;border-radius:8px}
.ib svg{width:20px;height:20px}
/* The count of hidden knowledge bases, on the button that can bring them
   back. A setting is kept between visits, and Chrome keeps one store for every
   file:// page, so a selection made weeks ago can greet a fresh load. A graph
   missing two clusters with nothing to say why reads as lost data. */
#bSet .dot{position:absolute;top:-5px;right:-5px;min-width:17px;height:17px;padding:0 4px;border:2px solid var(--side);border-radius:9px;background:var(--acc);color:var(--bg);font-size:10px;font-weight:700;line-height:13px;text-align:center}
/* Settings, in the shape of j4k's Settings window since 24.10.2026, on the
   owner's "please build settings and about this app like j4k": a window over
   the page, its parts listed down the left with About 00_Cerebrum first, the
   part shown on the right under its title and one line on what it holds, and
   a foot with the build and Done. j4k took that shape from folia on
   23.10.2026. The viewer's own type and colours, as everything new in it.
   Every part is stacked in one grid cell and only the shown one is visible, so
   the window is as tall as its tallest part and keeps its size when you switch.
   Its head drags it, as j4k's does. Until 24.10.2026 Settings was a panel
   hanging under the header in the shape of j4k's old Options menu (27.09.2026),
   with three tabs (08.10.2026), and About was a box of its own. */
#setWrap{position:fixed;inset:0;z-index:60;display:none;place-items:center;padding:16px;background:rgba(10,9,7,.58)}
#setWrap.on{display:grid}
/* The side is 240px so that "About 00_Cerebrum" stays on one line with the
   count of unread changes beside it: the name needs 138px and has 146px. In
   224px it had 129px and broke in two (owner, 24.10.2026: "fix the about line
   too"). The window grew by the same 16px, so the parts keep their width and
   About still fits without scrolling. */
#setWin{display:grid;grid-template-columns:240px minmax(0,1fr);grid-template-rows:minmax(0,1fr);width:min(956px,100%);max-height:calc(100vh - 32px);overflow:hidden;border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--fg);box-shadow:0 24px 80px rgba(0,0,0,.55)}
.setSide{display:flex;flex-direction:column;gap:2px;min-height:0;padding:18px 10px 12px;border-right:1px solid var(--line);background:var(--side)}
.setBrand{margin:0 10px 12px;font-size:1.15em;font-weight:700;color:var(--fg)}
.setBrand,.winHead{cursor:grab;user-select:none;touch-action:none}
.setTab{display:flex;align-items:center;gap:10px;width:100%;min-height:34px;padding:0 10px;border:0;border-radius:7px;background:transparent;color:var(--item);font-weight:600;text-align:left}
.setTab svg{flex:none;width:16px;height:16px;color:var(--mut)}
.setTab[aria-current="page"]{background:var(--card);color:var(--fg)}
.setTab[aria-current="page"] svg{color:var(--acc)}
.setTab:hover:not([aria-current="page"]){background:var(--line);color:var(--fg)}
.setMain{display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0;min-height:0}
.winHead{display:flex;align-items:flex-start;gap:12px;padding:20px 14px 14px 24px;border-bottom:1px solid var(--line)}
.winHeadText{flex:1;min-width:0}
.winHead h2{margin:0;padding:0;border:none;font-size:1.35em;font-weight:700;color:var(--fg)}
.winHead p{margin:4px 0 0;color:var(--mut);font-size:.9em;line-height:1.45}
#setX{flex:none;width:30px;height:30px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--mut);font-size:16px;cursor:pointer}
#setX:hover{background:var(--line);color:var(--fg)}
.winBody{min-height:0;overflow-y:auto;padding:16px 24px 18px}
.setParts{display:grid}
.setPart{grid-area:1/1;display:grid;align-content:start;gap:12px;min-width:0}
.setPart[inert]{visibility:hidden}
.setPart>*{margin:0}
.winFoot{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:12px 20px;border-top:1px solid var(--line)}
#setBuild{margin:0 auto 0 0;color:var(--ph);font-size:.82em}
/* One control surface in the window, as in the panel before it: one height,
   --card with an --edge line, the line --acc under the pointer. Done is the
   one filled button, as in j4k. */
#setWin .setPart button,#setWin .setPart select,#setWin a.btn{min-height:32px;min-width:0;border:1px solid var(--edge);border-radius:6px;background:var(--card);color:var(--fg);font:inherit;font-weight:700}
#setWin .setPart button,#setWin a.btn{padding:0 12px}
#setWin a.btn{display:inline-flex;align-items:center;text-decoration:none}
#setWin .setPart select{padding:0 10px}
#setWin .setPart button:hover:not(:disabled):not([aria-disabled="true"]),#setWin .setPart select:hover,#setWin a.btn:hover{border-color:var(--acc)}
#setWin .setPart select:focus{border-color:var(--acc);outline:none}
#setWin .setPart button:disabled{opacity:.42;cursor:default}
#setDone{min-height:32px;padding:0 18px;border:1px solid var(--acc);border-radius:6px;background:var(--acc);color:var(--bg);font:inherit;font-weight:700}
#setWin .hint{color:var(--mut);font-size:11px;line-height:1.4}
#setWin .hint b{color:var(--s2);font-weight:600}
/* A part's rows, in j4k's grammar: a group's title in small capitals, a card
   of rows, a row's name and what it does on the left and its value or control
   on the right. */
.setGroup{display:grid;gap:8px;min-width:0}
.setGroup>h4{margin:0 2px;color:var(--mut);font-size:.78em;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.setCard{display:grid;min-width:0;overflow:hidden;border:1px solid var(--edge);border-radius:10px;background:var(--card)}
.setRow{display:flex;align-items:center;gap:12px;min-width:0;min-height:44px;padding:7px 14px}
.setRow+.setRow{border-top:1px solid var(--line)}
.setRowIcon{display:inline-grid;flex:none;place-items:center;width:30px;height:30px;border:1px solid var(--edge);border-radius:8px;background:var(--bg);color:var(--item)}
.setRowIcon svg{width:16px;height:16px}
.setRowText{display:grid;flex:1;gap:2px;min-width:0}
.setRowTitle{color:var(--fg);font-weight:600}
.setRowDetail{color:var(--mut);font-size:.85em;line-height:1.4;overflow-wrap:anywhere}
.setRowControl{display:flex;flex:none;align-items:center;justify-content:flex-end;gap:8px;max-width:50%}
/* The facts as a strip of figures, as j4k's Account counts its tasks: the
   fact's name, its figure, and a few words on what it counts, side by side.
   The words are on the strip, not in a tooltip: the owner asked three times
   what the two link figures mean (27.09.2026). */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:1px;overflow:hidden;border:1px solid var(--edge);border-radius:10px;background:var(--line)}
.stat{display:grid;align-content:start;gap:3px;min-width:0;padding:10px 14px 11px;background:var(--card)}
.stat .sn{color:var(--mut);font-size:.72em;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.stat b{color:var(--fg);font-size:1.12em;font-weight:700;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.stat b a{color:var(--acc);text-decoration:none}.stat b a:hover{text-decoration:underline}
.stat .sd{color:var(--mut);font-size:.8em;line-height:1.35}
.setNote{margin:0 2px;color:var(--mut);font-size:.82em;line-height:1.45}
/* About's card, as j4k's: the mark, then the name and one line on what it is,
   on a band tinted with the accent. */
.aboutCard{display:flex;align-items:center;gap:16px;padding:13px 18px;border:1px solid var(--edge);border-radius:12px;background:linear-gradient(135deg,rgba(240,199,85,.13),var(--card) 72%)}
.aboutCardText{display:grid;flex:1;gap:3px;min-width:0}
.aboutCardName{color:var(--acc);font-size:1.35em;font-weight:700;line-height:1.1}
.aboutCardLine{color:var(--item);font-size:.9em;line-height:1.5}
/* What's new in folia's window (owner, 24.10.2026: "make in settings whats new
   look like the one from folia", then "use the style of folia as well"): its
   dark colours, type and spacing, 520px wide and at most 86% of the page high.
   It takes Settings' place, as folia's does, and Done closes both. A day a
   card, a change a row: its title, and a line on what it does. */
#newsWrap{position:fixed;inset:0;z-index:61;display:none;place-items:center;padding:24px;background:rgb(20 16 8/.28)}
#newsWrap.on{display:grid}
#newsWin{--nwCard:#1e1e1e;--nwSoft:#232323;--nwLine:#3a3a3a;--nwFg:#e8e5de;--nwMut:#a5a198;--nwAcc:#d99b26;--nwInk:#221a06;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr) auto;width:min(520px,100%);max-height:86vh;overflow:hidden;border:1px solid var(--nwLine);border-radius:14px;background:var(--nwCard);color:var(--nwFg);box-shadow:0 16px 48px rgb(0 0 0/.38);line-height:normal;-webkit-font-smoothing:antialiased}
.nwHead{padding:20px 24px 14px;border-bottom:1px solid var(--nwLine)}
.nwHead h2{margin:0;padding:0;border:none;font-size:20px;font-weight:800;letter-spacing:-.015em;color:var(--nwFg)}
.nwHead p{margin:4px 0 0;font-size:13px;line-height:1.5;color:var(--nwMut)}
.nwBody{display:grid;align-content:start;gap:16px;min-height:0;overflow-y:auto;padding:18px 24px 20px}
.nwDay{display:grid;gap:8px}
.nwDay h4{margin:0 2px;font-size:11.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--nwMut)}
.nwCard{display:grid;overflow:hidden;border:1px solid var(--nwLine);border-radius:12px;background:var(--nwSoft)}
.nwRow{display:grid;align-content:center;gap:2px;min-height:50px;padding:9px 14px}
.nwRow+.nwRow{border-top:1px solid var(--nwLine)}
.nwTitle{font-size:13.5px;font-weight:650;color:var(--nwFg)}
.nwDetail{font-size:12.5px;line-height:1.45;color:var(--nwMut)}
.nwFoot{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:8px;padding:12px 20px;border-top:1px solid var(--nwLine)}
#newsCount{margin:0 auto 0 0;font-size:12px;color:var(--nwMut)}
#newsDone{min-height:34px;padding:0 18px;border:1px solid var(--nwAcc);border-radius:6px;background:var(--nwAcc);color:var(--nwInk);font:inherit;font-weight:700}
.pill{display:inline-block;padding:0 7px;border-radius:999px;background:var(--acc);color:var(--bg);font-size:.72em;font-weight:800;line-height:17px;vertical-align:1px}
.setTabCount{margin-left:auto;min-width:18px;padding:0 5px;border-radius:999px;background:var(--acc);color:var(--bg);font-size:.72em;font-weight:800;line-height:18px;text-align:center}
@media (max-width:640px){#setWrap{padding:12px}#setWin{grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr);height:calc(100vh - 24px)}.setSide{flex-direction:row;overflow-x:auto;padding:8px;border-right:0;border-bottom:1px solid var(--line)}.setBrand{display:none}.setTab{flex:none;width:auto}.setRow{flex-wrap:wrap}.setRowControl{max-width:none}}
/* Brain. The model and the effort for the next question, then what stays on
   this Mac. Its controls are one width, owner's request of 24.10.2026: "please
   make the buttons in settings brain equal width". As wide as Download with
   its size, which is also what a local model's name needs in the Model menu;
   a local model's button ends on the same line as the controls above it. */
#brain{display:grid}
#brainAsk,#bModel,#bEffort,#bWeights .wr button{width:184px;max-width:100%}
/* Their words are centred, as in a button (owner, 24.10.2026: "make the text
   in the buttons in brain consistent, all centered"). A menu's arrow takes
   12px on its right, so the left gets 12px more and the words stand in the
   middle of the whole control, not of what the arrow leaves. */
#setWin #bModel,#setWin #bEffort{padding-left:22px;text-align:center;text-align-last:center}
/* A local model's card: a name over one quiet line on the left, the state or
   the action on the right. */
#bWeights{display:grid;gap:8px}
#bWeights .wr{display:grid;align-items:center;gap:4px 12px;padding:8px 14px 8px 10px;border:1px solid var(--edge);border-radius:6px;background:var(--card)}
#bWeights .wr{grid-template-columns:minmax(0,1fr) auto}
#bWeights .wt{display:block;font-weight:700}
#bWeights .ws{display:block;color:var(--mut);font-size:11px}
/* Installed reads as a tick and its size on disk; missing as where the bytes
   come from. Delete asks first, because it takes an instant and costs the whole
   download to undo: the confirmation replaces the status line, so the price is
   read where the row was just describing it. */
#bWeights .tick{color:var(--s3);margin-right:4px;font-weight:700}
#bWeights .no{color:var(--s2)}
#bWeights .wr.arm .ws{color:var(--s2)}
#bWeights .wr button.del:hover:not(:disabled){border-color:var(--s2);color:var(--s2)}
#bWeights .pb{grid-column:1/-1;height:3px;border-radius:2px;background:var(--line);overflow:hidden}
#bWeights .pb i{display:block;height:100%;width:0;background:#c8901d;transition:width .3s ease-out}
/* Two rows of three, every button the same width: owner's instruction of
   27.09.2026, replacing the 3 / 2 / 1 rows of 01.09.2026. The hue still says
   which block a base belongs to. */
#kbbar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}#kbbar button{padding:0 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#kbbar button.on{background:var(--acc);color:var(--bg);border-color:var(--acc)}/* fallback for a KB no block names; the three known blocks override inline */#kbbar button small{opacity:.7;margin-left:5px;font-size:.9em;font-weight:400;color:inherit}#kbbar button[aria-disabled="true"]{cursor:not-allowed}
#gc{flex:1;cursor:grab;touch-action:none;min-height:0}
/* The card is docked, see below. The search box
   does not: it stands exactly where it stands in the Concept view, in a box
   cut from the top of the list, with the list's width, ground, padding and
   divider, and the list's width follows the splitter in both. Owner's
   instructions of 14.09.2026. Its right-hand line is the splitter's, 2px of
   the page's ground and then 2px of line, so the line does not step sideways
   when the view switches. Both are shadows: a border takes its pixel from the
   search box, 412px against the list's 413. */
/* The concept card is a segment of the page, not a window over it. Owner's
   instruction of 23.09.2026: the floating card, with its radius and shadow,
   read as a different style from everything else. It now docks to the right
   edge at full height in the search bar's grammar — the --side ground, a
   1px --line divider on its open side, and the same divider between its parts.
   It still lies over the graph rather than narrowing it, so a click does not
   move the concept under the pointer. Its open
   action is the header's Concept view icon, as the concept page carries the
   graph icons. */
#stage{--cardw:340px}
#gcard{position:absolute;z-index:3;top:0;right:0;bottom:0;width:var(--cardw);overflow-y:auto;background:var(--side);border-left:1px solid var(--line);display:none}
#gcard .cs{padding:12px 16px;border-bottom:1px solid var(--line)}
#gcard .hd{display:flex;align-items:flex-start;gap:6px;margin-bottom:6px}
#gcard .hd .ib{flex:0 0 auto;width:32px;height:32px}#gcard .hd .ib svg{width:18px;height:18px}
#gcard h3{flex:1;min-width:0;margin:.25em 0 0;font-size:1.08em;line-height:1.35}#gcard .desc{font-size:.95em;margin:.5em 0 0;line-height:1.55}
#gcard .sec{margin:0 0 .3em}
/* The selected concept's links wear their direction in both graphs: blue for
   a link that arrives, orange for one that leaves, blue to orange for a pair
   that link both ways. Owner's request of 23.09.2026. The bar before each list
   heading in the card is the legend. Blue and orange, because the pair stays
   apart for the commonest colour blindness. */
#gcard .lk{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin:0 7px 2px 0}
#gcard .lk.in{background:var(--lin)}#gcard .lk.out{background:var(--lout)}
#gcard .nb{display:block;font-size:.92em;padding:1px 0;color:var(--acc);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#gcard .x{font-size:1.2em;line-height:1}
/* A narrow window takes the brand down before it squeezes the categories, the
   way j4k steps its logo down at breakpoints. */
@media (max-width:1200px){#top{gap:14px}#aboutBtn{gap:10px}#aboutBtn svg{width:58px;height:50px}#aboutBtn .wm{font-size:1.1em}}
@media (max-width:860px){#aboutBtn .tx{display:none}}
/* The shape is j4k's About dialog: eyebrow over the name, the logo as the real
   heading, one story line, then label/value facts in two columns, a built-with
   line and an actions row. Its light palette maps onto this viewer's tokens —
   card `#282828` on `#242424` becomes `--card` on `--bg`, and its `#3d3d3d`
   borders are already what `--line` is. */
/* The reports window, on the About dialog's shell: same backdrop, same card,
   same header grammar. It lists what `Outputs/_REPORTS.md` holds, because that
   register is the vault's own record of every report and carries what a
   directory scan cannot — the scope, the question as asked, and whether the
   report is an audit. Grouped by folder, since 16.09.2026 put the audits in
   `Outputs/HealthChecks/` and left the question reports at the root. */
#repWrap{position:fixed;inset:0;z-index:60;display:none;place-items:center;padding:18px;background:rgba(10,9,7,.58)}
#repWrap.on{display:grid}
/* j4k's assistant window, shape for shape: `min(560px, 100%)` wide,
   `min(640px, 100vh - 36px)` tall, a header row over one scrolling column, and
   rows on a 10px radius. The one scrollbar is the vertical one on the list, and
   there is none anywhere else: a row wraps rather than being cut with an
   ellipsis, because a question you cannot read is a row you cannot choose.
   Owner's instruction of 16.09.2026, on both counts. */
#repBox{display:grid;gap:14px;grid-template-rows:auto 1fr auto;width:min(880px,94vw);
 height:min(860px,calc(100vh - 36px));border:1px solid var(--line);border-radius:8px;
 background:var(--bg);padding:18px 20px;box-shadow:0 24px 80px rgba(0,0,0,.55)}
#repList{overflow-y:auto;overflow-x:hidden;min-height:0}
/* A row is two wrapped lines, so without a rule between them the list reads
   as one block of text. The hairline is the page's own --line, and it sits
   between rows rather than around them, so a hovered row is a single filled
   shape and not a box inside a box.
   **The date and the knowledge base share the first line.** They were two
   lines of their own until 16.09.2026, which cost a line per row for two short
   strings that answer the same question — which report is this. The owner asked
   for the space back. They are one flex line that wraps rather than scrolling,
   so a narrow window drops the scope under the date instead of cutting it. */
#repList .rr{display:block;padding:7px 10px;border:1px solid transparent;
 border-radius:10px;cursor:pointer}
#repList .rr + .rr{border-top-color:var(--line);border-top-left-radius:0;
 border-top-right-radius:0}
#repList .rr:hover{background:var(--line);color:var(--fg);border-color:transparent}
#repList .rr:hover .rq{color:var(--acc)}
#repList .rr .rm{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 7px;
 color:var(--mut);font-size:.84em}
#repList .rr .rd{font-variant-numeric:tabular-nums;letter-spacing:.04em}
#repList .rr .rs{overflow-wrap:anywhere}
#repList .rr .rs::before{content:'·';margin-right:7px}
#repList .rr .rq{display:block;margin:1px 0 0;overflow-wrap:anywhere;
 word-break:break-word;white-space:normal;color:var(--fg)}
#repList .rr.gone{opacity:.45;cursor:default}
#repBox .hint{color:var(--mut);font-size:.82em;line-height:1.5;margin:0}
#repBox header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-bottom:12px}
#repBox h2,#repBox p{margin:0}
#repBox h2{font-size:1.35em;color:var(--fg);font-weight:700;border:none;padding:0;margin:0}
#repBox .x{background:none;border:none;color:var(--mut);cursor:pointer;font-size:1.1em;line-height:1;padding:0 6px;border-radius:5px}
#repBox .x:hover{color:var(--fg);background:var(--line)}
.aboutLogo{flex:none;display:grid}
.aboutLogo svg{width:74px;height:64px;display:block}
/* The light that runs along the mark's strands in About: a bead a twenty-fifth
   of a strand long, out and fading, one strand after another. Never in the
   header, and never for a reader who has asked for less motion. */
.aboutLogo .pulse path{fill:none;stroke:var(--fg);stroke-width:26;stroke-linecap:round;stroke-dasharray:4 96;stroke-dashoffset:4;opacity:0;animation:markpulse 6.4s ease-in-out var(--d) infinite}
@keyframes markpulse{0%{stroke-dashoffset:4;opacity:0}6%{opacity:.8}48%{stroke-dashoffset:-96;opacity:.8}54%,100%{stroke-dashoffset:-96;opacity:0}}
@media (prefers-reduced-motion:reduce){.aboutLogo .pulse{display:none}}
</style></head><body class="vg">
<header id="top">
<button id="aboutBtn" title="What this vault is, and the facts to quote when something looks wrong">__LOGO__<span class="tx"><span class="eyebrow">About</span><span class="wm">00_Cerebrum</span></span></button>
<div id="legend" role="group" aria-label="Categories"></div>
<div id="tools"><div id="views" role="group" aria-label="View"><button id="bGraph" class="ib on" title="Graph view: the whole vault as one map" aria-label="Graph view" aria-pressed="true">__IGRAPH__</button><button id="b3d" class="ib" title="3D view: the same map with depth. Drag to turn it" aria-label="3D view" aria-pressed="false">__I3D__</button><button id="bList" class="ib" title="Concept view: the list of concepts, and the concept page beside it" aria-label="Concept view" aria-pressed="false">__ICONCEPTS__</button></div><button id="bSet" class="ib" title="Settings" aria-label="Settings" aria-haspopup="dialog" aria-expanded="false">__IGEAR__</button></div>
</header>
<div id="askbar"><div id="qwrap"><button id="mSearch" class="mb on" type="button" title="Search the vault" aria-label="Search the vault" aria-pressed="true">__ISEARCH__</button><button id="mAsk" class="mb" type="button" title="Ask Claude for a report instead of searching" aria-label="Ask Claude" aria-pressed="false">__ISPARK__</button><div id="qbar" hidden><i></i></div><input id="q" placeholder="Search title, description, tags…" aria-label="Search concepts"><button id="qx" type="button" title="Clear the search" aria-label="Clear the search">×</button><button id="bRep" class="mb" type="button" title="The reports in Outputs/" aria-label="Reports" aria-haspopup="dialog" aria-expanded="false">__IREPORTS__</button></div></div>
<div id="stage">
<div id="gpane"><canvas id="gc"></canvas><div class="gstat" id="g2stat"></div><div id="g2hint"><b>Drag</b> to move · <b>Scroll</b> to zoom · <span class="howturn"></span> to turn · <b>Click</b> to select · <b>Double-click</b> to open · <b>Double-click empty space</b> to fit</div></div>
<div id="g3pane"><canvas id="g3"></canvas><canvas id="g3lbl"></canvas><div class="gstat" id="g3stat"></div><div id="cineGo"><button id="bFilm" type="button" title="Timelapse: the vault's years in about thirty seconds. Each concept appears at the date of its oldest source">Timelapse</button></div><div id="g3hint"><b>Drag</b> to turn · <b>Shift-drag</b> to move · <b>Scroll</b> to zoom · <span class="howturn"></span> to roll · <b>Click</b> to select · <b>Double-click</b> to open · <b>Double-click empty space</b> to fit</div>
<div id="cine" hidden><div class="bar top"></div><div class="bar bot"></div>
<div id="cineTitle"><div id="cineName">00_Cerebrum</div><div id="cineYears"></div></div>
<div id="cineCap"><div id="cineBig"></div><div id="cineSub"></div></div>
<div id="cineCtl"><button id="cinePlay" type="button"></button><input id="cineTime" type="range" min="0" max="1000" value="0" aria-label="Where the timelapse is"><button id="cineSpeed" type="button" title="Speed"></button><button id="cineFull" type="button" title="Full screen" aria-label="Full screen"><svg viewBox="0 0 24 24"><path d="M4 4h6v2H6v4H4zM14 4h6v6h-2V6h-4zM4 14h2v4h4v2H4zM18 14h2v6h-6v-2h4z"/></svg></button><button id="cineX" type="button" title="Leave (Esc)" aria-label="Leave">&#215;</button></div></div></div>
<div id="gcard"></div>
<div id="cpane"><div id="side"><div id="sidetop"><button id="ball" title="Fold or unfold every group in the list">Collapse all</button></div><div id="tree"></div></div><div id="splitter" title="drag to resize"></div><div id="main"><div class="doc"><div class="meta">Pick a concept, or search. Dashed links point at concepts not written yet — legitimate under OKF.</div></div></div></div>
</div>
<div id="repWrap"><div id="repBox">
<header><div><p class="eyebrow">Outputs</p><h2>Reports</h2></div><button class="x" id="repX" title="Close reports (Esc)">&#215;</button></header>
<div id="repList"></div>
<p class="hint" id="repHint"></p>
</div></div>
<div id="setWrap"><section id="setWin" role="dialog" aria-modal="true" aria-label="Settings">
<aside class="setSide"><p class="setBrand">Settings</p>
<nav class="setNav" aria-label="Parts of the settings"><button type="button" class="setTab" data-part="partAbout">__IINFO__<span>About 00_Cerebrum</span><span class="setTabCount" id="newsTab" hidden title="Changes you have not read yet"></span></button><button type="button" class="setTab" data-part="paneKb">__ILAYERS__<span>Knowledge bases</span></button><button type="button" class="setTab" data-part="paneBrain">__ISPARK__<span>Brain</span></button></nav></aside>
<section class="setMain">
<header class="winHead"><div class="winHeadText"><h2 id="setTitle"></h2><p id="setLine"></p></div><button id="setX" type="button" title="Close settings (Esc)" aria-label="Close settings">&#215;</button></header>
<div class="winBody"><div class="setParts">
<div class="setPart" id="partAbout" data-part="partAbout">
<div class="aboutCard"><div class="aboutLogo">__LOGO__</div><span class="aboutCardText"><span class="aboutCardName">00_Cerebrum</span><span class="aboutCardLine">A knowledge base that reads its own sources and cites every claim back to the page it came from, and the machinery that keeps it honest. <i>Cerebrum</i> is the Latin for brain. Built by your-account with Claude Code.</span></span></div>
<div class="setGroup"><h4>Read</h4><div class="setCard"><div class="setRow"><span class="setRowIcon">__IBOOK__</span><span class="setRowText"><span class="setRowTitle">Docs</span><span class="setRowDetail">Your manual for the vault, where FIELD_MANUAL names one.</span></span><span class="setRowControl"><a class="btn" id="setDocs" target="_blank" rel="noopener" title="Open your manual for the vault in a new tab">Open</a></span></div><div class="setRow"><span class="setRowIcon">__INEWS__</span><span class="setRowText"><span class="setRowTitle">What&#8217;s new</span><span class="setRowDetail" id="newsLine">What changed in the viewer, newest first.</span></span><span class="setRowControl"><span class="pill" id="newsPill" hidden></span><button type="button" id="setNews" title="What changed in the viewer, newest first">Open</button></span></div></div></div>
<div class="setGroup"><h4>This version</h4><div class="stats" id="setVersion"></div></div>
<div class="setGroup"><h4>00_Cerebrum</h4><div class="stats" id="setVault"></div><p class="setNote">Markdown and YAML in an Obsidian vault, Open Knowledge Format v0.2 for the bundles, Python for the checks, GitHub for the code.</p></div>
</div>
<div class="setPart" id="paneKb" data-part="paneKb">
<div id="kbbar"></div>
<p class="hint"><span id="kbN"></span>. A hidden knowledge base leaves the graph, the concept list and the category counts. The choice is kept for the next visit.</p>
</div>
<div class="setPart" id="paneBrain" data-part="paneBrain">
<div class="setGroup" id="brain"><h4>Claude</h4><div class="setCard">
<div class="setRow"><span class="setRowIcon">__ISPARK__</span><span class="setRowText"><span class="setRowTitle">Ask Claude</span><span class="setRowDetail">A question about the vault, answered as a report. The sparkle in the search bar does the same.</span></span><span class="setRowControl"><button type="button" id="brainAsk" title="Close Settings and ask in the search bar">Open</button></span></div>
<div class="setRow"><span class="setRowText"><span class="setRowTitle">Model</span><span class="setRowDetail" id="brainWhere"></span></span><span class="setRowControl"><select id="bModel" aria-label="Which model answers"></select></span></div>
<div class="setRow"><span class="setRowText"><span class="setRowTitle">Effort</span><span class="setRowDetail" id="brainEffort"></span></span><span class="setRowControl"><select id="bEffort" aria-label="How much Claude thinks"></select></span></div>
</div><p class="setNote">Both choices are kept in this browser and apply to the next question.</p></div>
<p class="setNote" id="brainOff" hidden></p>
<div class="setGroup" id="brainLocal"><h4>On this Mac</h4><div id="bWeights"></div><p class="setNote" id="brainDisk"></p></div>
</div>
</div></div>
<footer class="winFoot"><p id="setBuild"></p><button id="setDone" type="button">Done</button></footer>
</section></section></div>
<div id="newsWrap"><section id="newsWin" role="dialog" aria-modal="true" aria-label="What&#8217;s new">
<header class="nwHead"><h2>What&#8217;s new</h2><p>What changed in the viewer, newest first. Docs is the fuller reference for how each part works.</p></header>
<div class="nwBody" id="newsList"></div>
<footer class="nwFoot"><p id="newsCount"></p><button id="newsDone" type="button">Done</button></footer>
</section></div>
<script>const D=__DATA__;const GIT='__GIT__';const STAMP='__STAMP__';const BUILDNO='__BUILDNO__';const STARTED='__STARTED__';const NEWS=__NEWS__;
/* One pinned order for the whole viewer: the knowledge-base buttons two per
   row (Alpha and Beta, then Gamma and Zeta) and the sidebar groups in the
   same sequence. Pinned rather than sorted so a rename cannot reshuffle
   either, and so the two never disagree. Anything not listed sorts after. */
/* The blocks are the vault's real structure — the three employer archives,
   the two Alpha documentation bundles, the private base — and they are the one
   source of the ordering. The selector in Settings draws them in that order,
   three to a row at one width, each wearing its block's hue, and the concept
   tree reads them flat in the same sequence. A knowledge base no block names
   comes last in both.

   `KB_ORDER` is derived rather than written out. It was a second hand-kept
   list until 01.09.2026 and it had already drifted: it still carried the
   order of 29.08.2026, Delta and Epsilon directly after Alpha, while the blocks
   introduced that morning put them in their own row after the employers. So
   the buttons read Alpha, Beta, Gamma, Delta, Epsilon, Zeta and the concept
   tree read Alpha, Delta, Epsilon, Beta, Gamma, Zeta. The comment on the old
   list promised the two could never disagree; deriving one from the other is
   what actually keeps that promise. */
const KB_BLOCKS=__KB_BLOCKS__;
const HUE={};KB_BLOCKS.forEach(b=>b.kbs.forEach(k=>HUE[k]=b.hue));
const KB_ORDER=KB_BLOCKS.flatMap(b=>b.kbs);
const tree=document.getElementById('tree'),main=document.getElementById('main'),q=document.getElementById('q');
const side=document.getElementById('side'),sidetop=document.getElementById('sidetop'),qwrap=document.getElementById('qwrap');
const KB_LABEL={};        /* display names where the folder name is not the one you want */
function kbOf(id){return id.split('/')[0]}
function kbName(k){return KB_LABEL[k]||k.replace('_kb','')}
function group(id){const p=id.split('/'),sub=p.slice(2,-1).join('/');
/* A concept at the bundle root — questions.md — has no subpath, and the
   old expression relied on ||, which never fired because the left side was
   already truthy. It rendered as 'Alpha / ' with a dangling separator. */
return sub?kbName(p[0])+' / '+sub:kbName(p[0])}
/* Order the sidebar by knowledge base first, using the same pinned order as
   the buttons, then by group inside it. localeCompare on the group label is
   case-insensitive, which put Zeta between Alpha and Beta purely because of
   its lowercase name — an ordering that meant nothing and read as an
   accident. Owner's request of 15.08.2026: Zeta sits below Gamma. */
function kbRank(id){const i=KB_ORDER.indexOf(kbOf(id));return i<0?KB_ORDER.length:i}
/* Which knowledge bases are shown is a setting, and a setting is kept between
   visits, as j4k keeps what its Options menu sets and nothing else. Two ways a
   kept value turns into a dead page, both taken seriously because Chrome shares
   one store between every file:// page: a name no knowledge base carries any
   more is dropped, and a store that hides every knowledge base is ignored,
   since a page showing nothing looks broken rather than configured. */
const KB_ALL=[...new Set(Object.values(D).map(c=>c.kb))];
var offKB=new Set();
try{const s=JSON.parse(localStorage.getItem('okf.kbOff')||'[]');
 if(Array.isArray(s))offKB=new Set(s.filter(k=>KB_ALL.includes(k)))}catch(e){}
if(offKB.size>=KB_ALL.length)offKB.clear();
function saveKb(){try{localStorage.setItem('okf.kbOff',JSON.stringify([...offKB]))}catch(e){}}
/* Full screen, 09.09.2026 to 14.09.2026, kept its choice under this name. Both
   views are full screen now, so nothing reads it; clear it rather than leave a
   dead value in the store Chrome shares with every other file:// page. */
try{localStorage.removeItem('okf.fs')}catch(e){}
/* Categories switched off in the header. A working selection, not a setting:
   it lasts while the page is open, as j4k's tag scope and search text do. It
   filters both views, because the header sits over both. */
const off=new Set();
let view='graph';
/* Collapsible groups. 223 concepts in one scroll is the length problem;
   folding is per group, persisted, and never allowed to hide a search hit.
   Items stay in the DOM when folded — the container is what hides — so
   viewer-check's "sidebar lists every concept" stays a true statement and
   show() can still highlight into a folded group. */
const ball=document.getElementById('ball');
var collapsed=new Set(),foldKb=new Set(),curGroups=[],curKbs=[],cur=null;
/* Two levels since 27.09.2026, owner's instruction: a knowledge base above its
   categories, so the list can fold down to one line per base without losing
   the categories inside it. Each level keeps its own folds. */
try{collapsed=new Set(JSON.parse(localStorage.getItem('okf.collapsed')||'[]'))}catch(e){}
try{foldKb=new Set(JSON.parse(localStorage.getItem('okf.foldKb')||'[]'))}catch(e){}
function saveFold(){try{localStorage.setItem('okf.collapsed',JSON.stringify([...collapsed]));localStorage.setItem('okf.foldKb',JSON.stringify([...foldKb]))}catch(e){}}
function markSel(){if(!cur)return;document.querySelectorAll('.it').forEach(e=>e.classList.toggle('on',e.dataset.t===cur))}
function item(id){const c=D[id];const e=document.createElement('a');e.className='it';e.dataset.t=id;e.textContent=c.t;e.title=c.d;e.onclick=()=>show(id);return e}
function build(filter){tree.innerHTML='';const kbs=new Map();
Object.keys(D).sort((a,b)=>{const ra=kbRank(a),rb=kbRank(b);if(ra!==rb)return ra-rb;
const ga=group(a),gb=group(b);return ga===gb?D[a].t.localeCompare(D[b].t):ga.localeCompare(gb)}).forEach(id=>{const c=D[id];if(offKB.has(c.kb)||off.has(CATS.indexOf(cat(id))))return;
if(filter){const hay=(c.t+' '+c.d+' '+c.tags.join(' ')+' '+id).toLowerCase();if(!hay.includes(filter))return}
const kb=kbOf(id),g=group(id);if(!kbs.has(kb))kbs.set(kb,new Map());const gm=kbs.get(kb);if(!gm.has(g))gm.set(g,[]);gm.get(g).push(id)});
curGroups=[];curKbs=[...kbs.keys()];
kbs.forEach((gm,kb)=>{const kopen=!!filter||!foldKb.has(kb);
/* The base wears the button Settings gives it: filled with the block hue,
   the count in small type after the name. */
const kh=document.createElement('button');kh.type='button';kh.className='kbh'+(kopen?'':' shut')+(filter?' flat':'');kh.dataset.kb=kb;
if(HUE[kb]){kh.style.background=HUE[kb];kh.style.borderColor=HUE[kb];kh.style.color='var(--bg)'}
kh.setAttribute('aria-expanded',String(kopen));
const kc=document.createElement('span');kc.className='cv';kc.textContent='▾';kh.appendChild(kc);
const kn=document.createElement('span');kn.className='gn';kn.textContent=kbName(kb);kh.appendChild(kn);
const ks=document.createElement('small');ks.textContent=[...gm.values()].reduce((a,x)=>a+x.length,0);kh.appendChild(ks);
kh.title=filter?'showing search results':(kopen?'click to fold this knowledge base':'click to unfold this knowledge base');
const kbox=document.createElement('div');kbox.className='kbbody';if(!kopen)kbox.style.display='none';
gm.forEach((ids,g)=>{
/* A concept at the bundle root, questions.md, has no category: it sits
   directly under its base. */
if(g===kbName(kb)){const rb=document.createElement('div');rb.className='gitems';ids.forEach(id=>rb.appendChild(item(id)));kbox.appendChild(rb);return}
curGroups.push(g);const open=!!filter||!collapsed.has(g);
const h=document.createElement('div');h.className='grp'+(open?'':' shut')+(filter?' flat':'');
const cv=document.createElement('span');cv.className='cv';cv.textContent='▾';h.appendChild(cv);
const gn=document.createElement('span');gn.className='gn';gn.textContent=g.slice(kbName(kb).length+3);h.appendChild(gn);
const ct=document.createElement('small');ct.textContent=ids.length;h.appendChild(ct);
h.title=filter?'showing search results':(open?'click to fold this group':'click to unfold this group');
const box=document.createElement('div');box.className='gitems';if(!open)box.style.display='none';
ids.forEach(id=>box.appendChild(item(id)));
if(!filter)h.onclick=()=>{collapsed.has(g)?collapsed.delete(g):collapsed.add(g);saveFold();build(q.value.toLowerCase())};
kbox.appendChild(h);kbox.appendChild(box)});
if(!filter)kh.onclick=()=>{foldKb.has(kb)?foldKb.delete(kb):foldKb.add(kb);saveFold();build(q.value.toLowerCase())};
tree.appendChild(kh);tree.appendChild(kbox)});
/* Collapse all folds the bases and every category inside them, so a base
   opened afterwards shows its categories closed (owner's instruction of
   27.09.2026); Expand all opens bases and categories alike. */
const anyOpen=curKbs.some(k=>!foldKb.has(k));
ball.innerHTML='<span class="qi" aria-hidden="true">'+(anyOpen?'__ICOLLAPSE__':'__IEXPAND__')+'</span>'+(anyOpen?'Collapse all':'Expand all');ball.disabled=!!filter||!curKbs.length;
ball.title=filter?'the list is showing search results':'Fold or unfold every knowledge base in the list';
markSel()}
ball.onclick=()=>{const anyOpen=curKbs.some(k=>!foldKb.has(k));
if(anyOpen){curKbs.forEach(k=>foldKb.add(k));curGroups.forEach(g=>collapsed.add(g))}else{curKbs.forEach(k=>foldKb.delete(k));curGroups.forEach(g=>collapsed.delete(g))}
saveFold();build(q.value.toLowerCase())};
function E(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function chip(txt,cls){return '<span class="badge '+(cls||'')+'">'+E(txt)+'</span>'}
/* Opening a concept is what the Concept view is for, so it switches there from
   wherever it was asked: the list, a link in a page, the graph card. */
function show(id){const c=D[id];if(!c)return;cur=id;setView('concepts');
/* A concept reached from a body link may sit in a folded group; leaving it
   folded loses the highlight and the reader's place in the tree. */
if(!q.value&&(collapsed.has(group(id))||foldKb.has(kbOf(id)))){collapsed.delete(group(id));foldKb.delete(kbOf(id));saveFold();build('')}
/* Out of sight, the row comes to the middle of the list; in sight, it stays
   put. 'nearest' left a concept opened from the graph on the list's bottom
   edge, and centring every time would jump the list under the pointer that
   had just clicked a visible row. */
markSel();const selEl=tree.querySelector('.it.on');
if(selEl){const tb=tree.getBoundingClientRect(),rb=selEl.getBoundingClientRect();
if(rb.top<tb.top||rb.bottom>tb.bottom)selEl.scrollIntoView({block:'center'})}
let h='<div class="doc">'+(idx[id]===undefined?'':'<span class="gbtns"><button class="ib g2" title="Show this concept in the Graph view" aria-label="Show in the Graph view">__IGRAPH__</button>'+(G3.ok?'<button class="ib g3" title="Show this concept in the 3D view" aria-label="Show in the 3D view">__I3D__</button>':'')+'</span>')+'<h1>'+E(c.t)+'</h1><div class="meta">'+chip(c.ty)+chip(c.st,c.st==='draft'?'dr':'')+chip(c.tr,c.tr==='human-reviewed'?'hu':'')+chip(c.ns+' sources')+' '+c.tags.map(t=>'#'+E(t)).join(' ')+'<br>'+E(c.d)+'</div>';
if(c.inb.length)h+='<div class="links">← linked from: '+c.inb.map(x=>'<a class="nav" data-t="'+x+'">'+E(D[x].t)+'</a>').join(' · ')+'</div>';
h+=c.html;
if(c.srcs.length){h+='<h2>Sources</h2><table><tr><th>Source</th><th>last_modified</th></tr>'+c.srcs.map(s=>'<tr><td>'+E(s[0])+'</td><td>'+E(s[1])+'</td></tr>').join('')+'</table>'}
main.innerHTML=h+'</div>';main.scrollTop=0;
main.querySelectorAll('a.nav').forEach(a=>a.onclick=()=>show(a.dataset.t));
/* The two view icons from the header, so each says which graph it opens.
   Owner's instruction of 23.09.2026, replacing the one "Show in graph". */
for(const[c,v]of[['.g2','graph'],['.g3','3d']]){const b=main.querySelector(c);if(b)b.onclick=()=>{setView(v);select(idx[id]);centerOn(idx[id])}}}
const qx=document.getElementById('qx');
q.addEventListener('input',()=>qwrap.classList.toggle('has',!!q.value));
qx.onclick=()=>{q.value='';q.dispatchEvent(new Event('input'));q.focus()};

/* ---- The other half of the box: Ask Claude, and the reports it writes.
   The page is one file opened from disk, so it can reach nothing by itself.
   `_scripts/viewer-server.py` on 127.0.0.1 is what serves the two things it
   cannot do: run the librarian over the vault, and read `Outputs/`. The helper
   is started by hand and is usually not running, so everything below is built
   to be absent: the page searches exactly as before, and the two buttons say
   plainly that the helper is off rather than failing when pressed. */
const HELPER='http://127.0.0.1:8760';
const mSearch=document.getElementById('mSearch'),mAsk=document.getElementById('mAsk'),
 bRep=document.getElementById('bRep'),askbar=document.getElementById('askbar'),
 qbar=document.getElementById('qbar'),qbarFill=qbar.firstElementChild,
 repWrap=document.getElementById('repWrap'),repList=document.getElementById('repList'),
 repHint=document.getElementById('repHint'),repX=document.getElementById('repX');
const SEARCH_PH='Search title, description, tags…',
 ASK_PH='Ask Claude for a report on the vault — Enter to send';
let helper=null,asking=false,askMode=false;
/* The blank line that ends one event. Built rather than written: this
   whole page is one Python string, so a backslash escape is resolved when
   the generator is parsed and never reaches the browser. */
const EVSEP=String.fromCharCode(10,10);

/* Whether the helper is there at all. One call at load, and again whenever the
   Ask side is pressed: it is started and stopped by hand, so the answer at load
   is often out of date by the time it is wanted. */
async function pingHelper(){
 try{const r=await fetch(HELPER+'/health',{cache:'no-store'});helper=r.ok?await r.json():null}
 catch(e){helper=null}
 const off=!helper;
 mAsk.disabled=off;bRep.disabled=off;
 /* The command-line login dies after about a month and says nothing. macOS
    notifications do not reach this Mac, so the two places that do are the
    launcher and here, on the button the question is asked from. */
 const L=(helper&&helper.login)||null;
 let warn=null;
 /* Both say where the sign-in is: the launcher asks, one Return and one click
    in the browser. Until 05.10.2026 the close expiry named the day and no way
    out, and the dead one a command to type into a Terminal. */
 if(L&&L.state==='expired')warn=' — the Claude Code login expired on '+L.when+'. Double-click "Open 00_Cerebrum.command" to sign in again';
 else if(L&&L.state==='soon')warn=' — the Claude Code login expires in '+L.days+' day(s), on '+L.when+'. Double-click "Open 00_Cerebrum.command" to sign in again';
 mAsk.title=off?'Ask Claude — open the vault with "Open 00_Cerebrum.command" to use this'
  :('Ask Claude for a report instead of searching ('+askWho()+')'+(warn||''));
 mAsk.classList.toggle('warn',!!warn);
 bRep.title=off?'Reports — open the vault with "Open 00_Cerebrum.command" to use this'
  :('The reports in Outputs/ ('+helper.reports+')');
 if(off&&askMode)setMode(false);
 return helper}

/* What answers the next question, as the Ask button says it: the model and
   effort chosen in Brain, or the helper's own while no choice is known yet. */
function askWho(){const m=MODELS.find(x=>x.id===picked),id=m?m.label:(picked||helper.model),
 e=m?(m.effort?effort:null):(effort||helper.effort);return id+(e?', '+(EFFORT_LABEL[e]||e).toLowerCase()+' effort':'')}
function setMode(ask){askMode=!!ask&&!!helper;
 mSearch.classList.toggle('on',!askMode);mAsk.classList.toggle('on',askMode);
 mSearch.setAttribute('aria-pressed',String(!askMode));
 mAsk.setAttribute('aria-pressed',String(askMode));
 askbar.classList.toggle('ask',askMode);
 q.setAttribute('aria-label',askMode?'Ask Claude':'Search concepts');
 q.placeholder=askMode?ASK_PH:SEARCH_PH;
 /* Leaving Ask mode must not leave the list filtered by a question nobody
    searched for, and entering it must not filter by one either. */
 if(q.value){q.value='';q.dispatchEvent(new Event('input'))}
 q.focus()}
mSearch.onclick=()=>setMode(false);
mAsk.onclick=async()=>{if(!helper)await pingHelper();setMode(true)};

/* The bar advances on real milestones, never on a timer. Each step closes half
   the remaining gap, then a third, then a quarter, so it always moves and never
   arrives before the report does. */
let step=0;
function bar(reset){if(reset){step=0;qbar.hidden=false;qbar.classList.remove('done');
  qbarFill.style.width='0%';return}
 step++;let w=0,left=100;for(let i=1;i<=step;i++){const take=left/(i+1);w+=take;left-=take}
 qbarFill.style.width=w.toFixed(1)+'%'}
function barDone(ok){qbar.classList.toggle('done',!!ok);qbarFill.style.width='100%';
 setTimeout(()=>{qbar.hidden=true;qbar.classList.remove('done')},ok?2600:1200)}

async function ask(){
 const text=q.value.trim();if(!text||asking)return;
 if(!await pingHelper()){q.placeholder='the helper is not running';return}
 asking=true;mAsk.classList.add('busy');q.value='';q.blur();
 q.placeholder='asking the librarian…';bar(true);
 let path=null,err=null;
 try{
  const res=await fetch(HELPER+'/ask',{method:'POST',
   headers:{'content-type':'application/json'},body:JSON.stringify(Object.assign({question:text},brainBody()))});
  if(res.status===409){throw new Error('a report is already being written')}
  if(!res.ok){throw new Error('the helper answered '+res.status)}
  /* The body is an event stream read by hand rather than an EventSource,
     because the question has to go up in a POST and EventSource only gets. A
     chunk boundary can fall inside an event, so the tail is kept. */
  const rd=res.body.getReader(),dec=new TextDecoder();let buf='';
  for(;;){const {value,done}=await rd.read();if(done)break;
   buf+=dec.decode(value,{stream:true});let i;
   while((i=buf.indexOf(EVSEP))>-1){
    const raw=buf.slice(0,i).replace(/^data: /,'');buf=buf.slice(i+2);
    if(!raw)continue;let ev;try{ev=JSON.parse(raw)}catch(e){continue}
    if(ev.type==='step'||ev.type==='note'){bar();if(ev.text)q.placeholder=ev.text}
    else if(ev.type==='error'){err=ev.error}
    else if(ev.type==='done'){path=ev.path;
     /* Both languages, every time, since 16.09.2026 — so the box says whether
        the German version is really there rather than letting it be assumed. */
     q.placeholder=path?('report filed in '+ev.seconds+'s, '
       +(ev.de?'EN and DE':'English only — the German version failed')
       +' — opening it')
      :'the librarian finished without filing a report'}}}
 }catch(e){err=e.message}
 asking=false;mAsk.classList.remove('busy');
 if(err){q.placeholder=err;barDone(false);return}
 barDone(true);
 if(path){openReport(path);loadReports()}}

function openReport(rel){window.open(HELPER+'/report/'+rel.split('/').map(encodeURIComponent).join('/'),'_blank')}

/* The list is the register's, not a directory's. `Outputs/_REPORTS.md` is where
   the vault records every report, and it carries the scope and the question as
   asked; a folder listing carries neither. Grouped by folder, because an audit
   lives in `Outputs/HealthChecks/` and a question report at the root. */
async function loadReports(){
 if(!await pingHelper()){repList.innerHTML='';
  repHint.textContent='The helper is not running. Start it with: python3 _scripts/viewer-server.py';return}
 let rows=[];
 try{rows=(await (await fetch(HELPER+'/reports',{cache:'no-store'})).json()).reports||[]}
 catch(e){repHint.textContent='the helper answered nothing';return}
 /* Only the question reports. The audits live in `Outputs/HealthChecks/` since
    16.09.2026 and are 40 of the 50 rows, which is what buried the ten that
    answer a question; this window is for those ten. Owner's instruction. */
 const q1=rows.filter(r=>!r.audit);
 repList.innerHTML=q1.map(r=>
   '<div class="rr'+(r.exists?'':' gone')+'" data-p="'+E(r.path)+'">'+
   '<span class="rm"><span class="rd">'+E(r.date)+'</span>'+
   '<span class="rs">'+E(r.scope)+(r.exists?'':' · missing on disk')+'</span></span>'+
   '<span class="rq">'+E(r.question||r.title)+'</span></div>').join('');
 repHint.textContent=q1.length+' report(s). The health checks are in Outputs/HealthChecks/ and are not listed here. A row opens the report in a new tab.';
 repList.querySelectorAll('.rr').forEach(el=>{if(el.classList.contains('gone'))return;
  el.onclick=()=>openReport(el.dataset.p)})}

/* ---- Brain: which model answers -------------------------------------------
   The page holds the choice and sends it with every request; the helper keeps
   the allowlist and refuses anything it does not name, because an id reaches a
   command line and names a folder on disk. The choice survives a reload, like
   the knowledge-base toggles. The effort level is the page's to choose again
   since 24.10.2026, as in j4k's Assistant: "look at the assistant section of
   j4k. model and effort selector". From 27.09.2026 until then no request
   carried one, on the owner's instruction, and the helper's own, high, applied.
   A model that takes no effort level is sent none. */
const brainEl=document.getElementById('brain'),bModel=document.getElementById('bModel'),
 bWeights=document.getElementById('bWeights'),
 brainWhere=document.getElementById('brainWhere'),
 brainDisk=document.getElementById('brainDisk'),bEffort=document.getElementById('bEffort'),
 brainEffort=document.getElementById('brainEffort'),brainOff=document.getElementById('brainOff'),
 brainLocal=document.getElementById('brainLocal');
let MODELS=[],EFFORTS=[],picked=null,effort=null,defEffort='';
const EFFORT_LABEL={low:'Low',medium:'Medium',high:'High',xhigh:'Extra high',max:'Max'};
function loadPick(){try{picked=localStorage.getItem('okf.model')||null;effort=localStorage.getItem('okf.effort')||null}catch(e){}}
function savePick(){try{if(picked)localStorage.setItem('okf.model',picked);if(effort)localStorage.setItem('okf.effort',effort)}catch(e){}}
loadPick();
/* What every request carries. A model the helper has since stopped naming —
   a registry edited between two visits — falls back to its default rather than
   being sent and refused. */
function brainBody(){const m=MODELS.find(x=>x.id===picked);
 return m?Object.assign({model:m.id},m.effort&&EFFORTS.includes(effort)?{effort}:{}):{}}
function curModel(){return MODELS.find(x=>x.id===picked)||MODELS[0]||null}

async function loadBrain(){
 const off=t=>{brainEl.hidden=brainLocal.hidden=true;bWeights.innerHTML='';brainOff.hidden=false;brainOff.textContent=t};
 if(!helper)return off('Start the helper to choose a model and an effort.');
 let d=null;try{d=await (await fetch(HELPER+'/models',{cache:'no-store'})).json()}
 catch(e){return off('The helper answered nothing.')}
 brainEl.hidden=brainLocal.hidden=false;brainOff.hidden=true;
 MODELS=d.models||[];EFFORTS=d.efforts||[];defEffort=d.defaultEffort||'';
 if(!MODELS.some(m=>m.id===picked))picked=d.default;
 if(!EFFORTS.includes(effort))effort=defEffort;
 bEffort.innerHTML=EFFORTS.map(x=>'<option value="'+E(x)+'"'+(x===effort?' selected':'')+'>'+E(EFFORT_LABEL[x]||x)+'</option>').join('');
 bModel.innerHTML=MODELS.map(m=>'<option value="'+E(m.id)+'"'+
   (m.id===picked?' selected':'')+(m.installed?'':' disabled')+'>'+E(m.label)+
   (m.installed?'':' — not installed')+'</option>').join('');
 paintBrain(d)}

/* The line that says what leaves this Mac, and the one warning worth carrying
   into the window: a local model is a completion and Ask Claude is an agent, so
   picking one here means the Ask button will say so rather than run. */
function paintBrain(d){const m=curModel();if(!m)return;
 brainWhere.innerHTML=(m.provider==='local'
   ? 'Runs here. <b>Nothing leaves this Mac.</b> Translates only; Ask needs a Claude model.'
   : 'Reads the vault at Anthropic.')+' '+E(m.note||'');
 bEffort.disabled=!m.effort;
 brainEffort.textContent=m.effort?'How much Claude thinks before it answers. Low is fastest; Max is the most careful and the slowest.'
   :'This model takes no effort level.';
 const local=MODELS.filter(x=>x.provider==='local');
 bWeights.innerHTML=local.map(row).join('');
 /* "free" alone read as memory, and the owner asked on 16.09.2026 why three
    models would not fit when switching between them frees the RAM. They do
    free it — one model is loaded at a time — and the limit was never RAM.
    Weights sit on disk whether or not they are loaded, so the line says disk. */
 brainDisk.innerHTML=local.length
   ? (d.free/1e9).toFixed(0)+' GB free on disk. Each model stays on disk whether or not it is loaded; only one is in memory at a time.'
     +(d.mlx?'':' <b>mlx-lm is not installed</b> — run: python3 -m pip install --user mlx-lm')
   : '';
 wireWeights()}

/* One card per local model: the name over its status, the action on the right. */
function row(x){
 const gb=n=>(n/1e9).toFixed(1)+' GB';
 const on=x.installed;
 return '<div class="wr" data-m="'+E(x.id)+'" data-gb="'+E(gb(x.bytes||0))+
   '" data-disk="'+E(gb(x.onDisk||0))+'">'+
  /* Every row here is local, so the label's own "(local)" says nothing.
     It stays in the dropdown, where Claude models sit beside these. */
  '<span class="wl"><span class="wt">'+E(x.label.replace(' (local)',''))+'</span><span class="ws">'+
    (on?'<span class="tick">&#10003;</span>Installed, '+gb(x.onDisk||0)+' on disk'
      :'One-time download from Hugging Face'+(x.fits?''
        :' &middot; <span class="no">not enough free disk</span>'))+
  '</span></span>'+
  (on?'<button type="button" class="del">Delete</button>'
     :'<button type="button" class="get"'+(x.fits?'':' disabled')+'>Download '+gb(x.bytes||0)+'</button>')+
  '</div>'}

function wireWeights(){
 bWeights.querySelectorAll('.wr').forEach(r=>{
  const b=r.querySelector('button');if(!b)return;
  if(b.classList.contains('get')){b.onclick=()=>pullModel(r.dataset.m,b);return}
  /* Delete asks first and the question names what saying yes costs, because
     the way out has to come before the action rather than during it. */
  b.onclick=()=>{
   if(!r.classList.contains('arm')){
    r.classList.add('arm');
    r.querySelector('.ws').innerHTML='Frees '+E(r.dataset.disk)+
      '. Getting it back is '+E(r.dataset.gb)+' from Hugging Face.';
    b.textContent='Delete, really';
    setTimeout(()=>{if(r.classList.contains('arm'))loadBrain()},8000);
    return}
   b.disabled=true;b.textContent='…';
   delModel(r.dataset.m,r)}})}

async function delModel(id,r){
 let err=null;
 try{const res=await fetch(HELPER+'/models/delete',{method:'POST',
   headers:{'content-type':'application/json'},body:JSON.stringify({model:id})});
  const j=await res.json().catch(()=>({}));
  if(!res.ok)err=j.error||('the helper answered '+res.status)}
 catch(e){err=e.message}
 /* A failed delete leaves the row installed. GLaDOS's own review found the
    message written only under the not-installed branch, so the reader confirmed
    a destructive action, nothing happened, and nothing said why. */
 await loadBrain();
 if(err){const row=bWeights.querySelector('[data-m="'+CSS.escape(id)+'"] .ws');
  if(row)row.innerHTML='<span class="no">'+E(err)+'</span>'}}

bModel.onchange=()=>{picked=bModel.value;savePick();paintBrain({free:0,dir:'',mlx:true});loadBrain();pingHelper()};
bEffort.onchange=()=>{effort=bEffort.value;savePick();pingHelper()};
document.getElementById('brainAsk').onclick=()=>{setClose();setMode(true);q.focus()};

/* The download. Seventeen gigabytes is minutes of silence otherwise, so the
   helper streams what it has and the row carries a bar. Same event shape as a
   question, so nothing new had to be parsed. */
async function pullModel(id,btn){const row=btn.closest('.wr');
 btn.disabled=true;btn.textContent='…';
 let pb=row.querySelector('.pb');
 if(!pb){pb=document.createElement('div');pb.className='pb';pb.innerHTML='<i></i>';
  row.appendChild(pb)}
 try{
  const res=await fetch(HELPER+'/models/pull',{method:'POST',
   headers:{'content-type':'application/json'},body:JSON.stringify({model:id})});
  if(!res.ok)throw new Error('the helper answered '+res.status);
  const rd=res.body.getReader(),dec=new TextDecoder();let buf='';
  for(;;){const {value,done}=await rd.read();if(done)break;
   buf+=dec.decode(value,{stream:true});let i;
   while((i=buf.indexOf(EVSEP))>-1){
    const raw=buf.slice(0,i).replace(/^data: /,'');buf=buf.slice(i+2);
    if(!raw)continue;let ev;try{ev=JSON.parse(raw)}catch(e){continue}
    if(ev.type==='step'&&ev.total)pb.firstElementChild.style.width=
      (100*ev.received/ev.total).toFixed(1)+'%';
    else if(ev.type==='error'){row.querySelector('.wl').innerHTML+=
      ' <span class="no">'+E(ev.error)+'</span>'}}}
 }catch(e){row.querySelector('.wl').innerHTML+=' <span class="no">'+E(e.message)+'</span>'}
 loadBrain()}

function showReports(on){repWrap.classList.toggle('on',on);
 bRep.setAttribute('aria-expanded',String(on));if(on)loadReports()}
bRep.onclick=()=>showReports(!repWrap.classList.contains('on'));
repX.onclick=()=>showReports(false);
repWrap.onclick=e=>{if(e.target===repWrap)showReports(false)};
/* The Brain is loaded with the first ping rather than when Settings opens, so
   the very first question already carries the chosen model — the owner may
   never open Settings again after picking one. */
pingHelper().then(loadBrain);
/* The helper is started by hand and may come up after the page is open, so one
   check at load would leave the two buttons grey until a reload. Ask again when
   the window is looked at again, which is what happens after starting it, and
   never more than once every few seconds. */
let lastPing=Date.now();
addEventListener('focus',()=>{if(Date.now()-lastPing>3000){lastPing=Date.now();pingHelper()}});
document.addEventListener('visibilitychange',()=>{
 if(!document.hidden&&Date.now()-lastPing>3000){lastPing=Date.now();pingHelper()}});
/* ---- graph view, built on a precomputed layout: opens settled, identical
   every regeneration. Click selects and shows the concept card with its
   neighbourhood lit, and a second click on the same concept lets it go;
   Open (or double-click) goes to the full page. A double-click's own second
   click lets go of the concept, so the open selects it again. Colors
   are the validated palette; identity is never hue alone: shapes + legend +
   labels. ---- */
/* A concept's category is its Wiki subdirectory when that is a name CATS knows,
   and `meta` otherwise — which covers questions.md at a bundle root and any
   shelf this list has not been told about. Add your own group names here and
   they get their own shape, their own legend entry and their own place in the
   sort; leave them out and they collect under meta, which is honest rather
   than wrong. */
const CATS=['people','systems','projects','decisions','meeting-series','organisation','timelines','services','procedures','policies','hardware','tools','references','meta'];
const SHAPES=['circle','square','triangle','diamond','pentagon','hexagon','star','cross','ring','invtriangle','bars','shield','chip','gear','card','stack'];
const LBL={'meeting-series':'meeting series','meta':'meta / references'};
function cat(id){const p=id.split('/');const g=p.length>3?p[2]:'meta';
return CATS.includes(g)?g:'meta'}
const gc=document.getElementById('gc'),card=document.getElementById('gcard'),
bL=document.getElementById('bList'),bG=document.getElementById('bGraph'),b3=document.getElementById('b3d'),legend=document.getElementById('legend');
const ids=Object.keys(D),idx={};ids.forEach((id,i)=>idx[id]=i);
const N=ids.map((id,i)=>({id,i,c:CATS.indexOf(cat(id)),kb:D[id].kb,x:D[id].x,y:D[id].y,r:5.5+2.3*Math.sqrt(D[id].inb.length)}));
const L=[];ids.forEach(id=>D[id].out.forEach(o=>{if(idx[o]!==undefined&&idx[o]!==idx[id])L.push([idx[id],idx[o]])}));
const NB=N.map(()=>new Set());L.forEach(([a,b])=>{NB[a].add(b);NB[b].add(a)});
let tx=0,ty=0,sc=1,hov=-1,sel=-1,drag=null,pan=null,qv='',dirty=true,dpr=devicePixelRatio||1;
/* The map can be turned, in both graphs. Owner's request of 08.10.2026: "i
   want to rotate on the mac with the usual two-finger rotation gesture on the
   trackpad. if this doesnt work, please come up with an idea". It works in
   Safari, which gives that gesture to the page as gesture events. Chrome and
   Firefox keep it from the page, so there the idea is the Option key with a
   two-finger swipe, which is a wheel event with altKey and arrives in every
   browser. rot is the 2D map's turn, in radians, clockwise on the screen: a
   place on the screen is the middle + sc * R(rot) * (place + (tx,ty)). The
   marks and every name stay upright. SPIN is the turn for one pixel of swipe. */
let rot=0;const SPIN=.004,rv=(x,y,a)=>{const c=Math.cos(a),n=Math.sin(a);return[x*c-y*n,x*n+y*c]};
const swipe=e=>-(Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY)*SPIN;
/* one soft halo per knowledge base, in its block's hue, so the clusters in
   the graph visibly belong to the settings block and legend row that share the
   colour. The generator measures each halo and hands it over, because the
   layout has to clear what this draws: see _halo in visualize.py. */
const KBC=__HALO__;
function hid(n){return off.has(n.c)||offKB.has(n.kb)}
function rEff(n){return Math.min(30,Math.max(7,n.r*Math.sqrt(sc)))/sc}
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim()}
let COL=[];function loadCols(){COL=CATS.map((c,i)=>css('--s'+(i+1)));dirty=true}
loadCols();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{loadCols();chips()});
function ghost(n){if(hid(n))return true;
if(qv){const d=D[n.id];if(!(d.t+' '+d.d+' '+d.tags.join(' ')).toLowerCase().includes(qv))return true}
if(sel>=0&&n.i!==sel&&!NB[sel].has(n.i))return true;return false}
/* The two views. The search box no longer moves between them: since
   16.09.2026 it is one bar across the window, above both panes, so its text,
   its clear button and its filter are the same in both without anything being
   re-parented on every switch. Owner's instruction. */
function setView(v){view=v==='graph'||v==='3d'?v:'concepts';const g=view==='graph',t=view==='3d',c=view==='concepts';
document.body.classList.toggle('vg',g);document.body.classList.toggle('vc',c);document.body.classList.toggle('v3',t);
bG.classList.toggle('on',g);bL.classList.toggle('on',c);b3.classList.toggle('on',t);
bG.setAttribute('aria-pressed',String(g));bL.setAttribute('aria-pressed',String(c));b3.setAttribute('aria-pressed',String(t));
if(t)G3.enter();else if(G3.cine)G3.cine.stop();   // the Timelapse is the 3D view's, and ends with it
/* The canvas is sized from its client box, and a hidden canvas measures zero:
   a window resized while the Concept view was showing leaves the graph with no
   backing store until this runs. */
if(g){resize();fit()}}
bL.onclick=()=>setView('concepts');bG.onclick=()=>setView('graph');b3.onclick=()=>setView('3d');
const kbbarEl=document.getElementById('kbbar');
/* The selector mirrors the vault's real structure, one block per ontology:
   the three employer archives, the two Alpha documentation bundles, the private
   base. 3 / 2 / 1 across the panel, so each block is symmetric on its own
   line and the grouping needs no label. A knowledge base this list does not
   know lands in a fourth row rather than nowhere. It moved from the sidebar
   into Settings on 14.09.2026, on the owner's instruction, unchanged. */
function kbbar(){kbbarEl.innerHTML='';
const known=KB_BLOCKS.flatMap(b=>b.kbs);
const blocks=[...KB_BLOCKS.map(b=>({kbs:b.kbs.filter(k=>KB_ALL.includes(k)),hue:b.hue})),
 {kbs:KB_ALL.filter(k=>!known.includes(k)).sort(),hue:''}];
/* the buttons wear the block hue directly — filled when on, a tinted
   outline when off — so the row needs no accent bar. Owner's instruction
   of 01.09.2026, replacing the vertical line of the same morning. */
blocks.forEach((block,bi)=>{if(!block.kbs.length)return;
block.kbs.forEach(kb=>{const on=!offKB.has(kb);
/* The last knowledge base showing stays on. Hiding it would leave both
   views empty, which is the dead page the stored choice is guarded against. */
const last=on&&offKB.size===KB_ALL.length-1;
const s=document.createElement('button');s.className=on?'on':'';s.dataset.block=bi;
if(block.hue){if(!on){s.style.borderColor=block.hue+'66';s.style.color=block.hue}
else{s.style.background=block.hue;s.style.borderColor=block.hue;s.style.color='var(--bg)'}}
s.textContent=kbName(kb);
const sm=document.createElement('small');sm.textContent=Object.values(D).filter(c=>c.kb===kb).length;s.appendChild(sm);
s.title=last?'the last knowledge base showing stays on':'show / hide this knowledge base — graph, list and counts alike';
if(last)s.setAttribute('aria-disabled','true');
s.onclick=()=>{if(last)return;on?offKB.add(kb):offKB.delete(kb);saveKb();kbbar();kbBadge();chips();build(q.value.toLowerCase());if(sel>=0&&hid(N[sel]))clearSel();dirty=true};
kbbarEl.appendChild(s)})})}
/* One legend row per block, counting that block's own concepts, and the
   counts follow what is showing. With a knowledge base hidden in Settings,
   its concepts leave the counts, and a chip or a whole row with nothing left
   in it goes blank, so no chip offers a filter that would change nothing.
   Blank, not gone: the geometry stays fixed. A removed row made the header
   shorter and moved the search bar, the views and Settings with it; a removed
   chip slid the ones after it. Each count also keeps the width of its largest
   value, in figures of one width, so a count going from 120 to 98 moves
   nothing either. */
function chips(){legend.innerHTML='';
KB_BLOCKS.forEach(blk=>{
const inBlk=new Set(blk.kbs);
const cnt=CATS.map(()=>0),all=CATS.map(()=>0);N.forEach(n=>{if(inBlk.has(n.kb)){all[n.c]++;if(!offKB.has(n.kb))cnt[n.c]++}});
const row=document.createElement('div');row.className='lrow';
/* the accent bar alone names the block — a text tag repeated the sidebar
   and pushed each row's chips right by a different width, so the category
   columns never aligned. Owner's instruction of 01.09.2026. */
row.style.borderLeft='3px solid '+blk.hue;row.style.paddingLeft='8px';
let any=false;
for(let i=0;i<CATS.length;i++){const c=CATS[i];if(!all[i])continue;if(cnt[i])any=true;
const s=document.createElement('span');s.className='chip'+(off.has(i)?' off':'')+(cnt[i]?'':' void');
/* drawn at the screen's pixel density: a 16px bitmap blurs on a Retina display,
   and the header is where every category mark is seen first */
const cv=document.createElement('canvas');cv.width=cv.height=Math.round(16*dpr);cv.style.width=cv.style.height='16px';const x2=cv.getContext('2d');
x2.scale(dpr,dpr);x2.translate(8,8);x2.fillStyle=COL[i];shp(x2,5.5,i);x2.fill();
s.appendChild(cv);const bb=document.createElement('b');bb.textContent=LBL[c]||c;s.appendChild(bb);
const sm=document.createElement('small');sm.textContent=cnt[i];sm.style.minWidth=String(all[i]).length+'ch';s.appendChild(sm);
s.title='click to hide / show this category — graph and list alike';
s.onclick=()=>{off.has(i)?off.delete(i):off.add(i);if(sel>=0&&hid(N[sel]))clearSel();chips();build(q.value.toLowerCase());dirty=true};
row.appendChild(s)}
if(!any)row.classList.add('void');legend.appendChild(row)})}
function shp(x2,r,k){x2.beginPath();const s=SHAPES[k];
if(s==='circle')x2.arc(0,0,r,0,7);
else if(s==='square')x2.rect(-r*.9,-r*.9,r*1.8,r*1.8);
else if(s==='triangle'){x2.moveTo(0,-r*1.15);x2.lineTo(r,r*.85);x2.lineTo(-r,r*.85);x2.closePath()}
else if(s==='diamond'){x2.moveTo(0,-r*1.2);x2.lineTo(r*1.2,0);x2.lineTo(0,r*1.2);x2.lineTo(-r*1.2,0);x2.closePath()}
else if(s==='cross'){const w=r*.45;x2.rect(-w,-r*1.1,2*w,2.2*r);x2.rect(-r*1.1,-w,2.2*r,2*w)}
else if(s==='ring'){x2.arc(0,0,r*1.05,0,7);x2.moveTo(r*.55,0);x2.arc(0,0,r*.55,0,7,true)}
else if(s==='invtriangle'){x2.moveTo(0,r*1.15);x2.lineTo(r,-r*.85);x2.lineTo(-r,-r*.85);x2.closePath()}
else if(s==='bars'){x2.rect(-r,-r*.95,2*r,r*.7);x2.rect(-r,r*.25,2*r,r*.7)}
else if(s==='shield'){x2.moveTo(0,-r*1.15);x2.lineTo(r*.95,-r*.65);x2.lineTo(r*.95,r*.1);x2.lineTo(0,r*1.15);x2.lineTo(-r*.95,r*.1);x2.lineTo(-r*.95,-r*.65);x2.closePath()}
else if(s==='chip'){x2.rect(-r*.75,-r*.75,r*1.5,r*1.5);for(let j=-1;j<2;j++){x2.rect(-r*1.15,j*r*.5-r*.11,r*.4,r*.22);x2.rect(r*.75,j*r*.5-r*.11,r*.4,r*.22)}}
else if(s==='gear'){for(let j=0;j<16;j++){const rr=j%2?r*.78:r*1.15;const a=-Math.PI/2+j*Math.PI/8;x2[j?'lineTo':'moveTo'](rr*Math.cos(a),rr*Math.sin(a))}x2.closePath()}
else if(s==='card'){x2.rect(-r*.75,-r*1.05,r*1.5,r*2.1)}
else if(s==='stack'){x2.ellipse(0,-r*.55,r*1.05,r*.5,0,0,7);x2.moveTo(r*1.05,r*.55);x2.ellipse(0,r*.55,r*1.05,r*.5,0,0,7)}
else{const m=s==='pentagon'?5:s==='hexagon'?6:s==='octagon'?8:10;for(let j=0;j<m;j++){const rr=s==='star'?(j%2?r*.5:r*1.15):r*1.05;
const a=-Math.PI/2+j*2*Math.PI/m;x2[j?'lineTo':'moveTo'](rr*Math.cos(a),rr*Math.sin(a))}x2.closePath()}}
function resize(){gc.width=gc.clientWidth*dpr;gc.height=gc.clientHeight*dpr;dirty=true}
addEventListener('resize',resize);
/* Frame the graph clear of what floats on it. The search box holds the top-left
   corner, where Gamma sits, and the old pad of 70 world units came to about
   twenty pixels on screen, so the corner of that cluster was framed underneath
   the box. The margins are in screen pixels, and the top one is the box's
   height with room to spare; the graph is centred in what they leave. */
const FIT_TOP=76,FIT_SIDE=28,FIT_BOTTOM=28;
function fit(){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,any=false;
for(const n of N){if(hid(n))continue;any=true;const[x,y]=rv(n.x,n.y,rot);x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y)}
if(!any)return;
const w=gc.clientWidth-2*FIT_SIDE,h=gc.clientHeight-FIT_TOP-FIT_BOTTOM;
sc=Math.max(.08,Math.min(2.2,Math.min(w/Math.max(x1-x0,1),h/Math.max(y1-y0,1))));
[tx,ty]=rv(-(x0+x1)/2,(FIT_TOP-FIT_BOTTOM)/(2*sc)-(y0+y1)/2,-rot);dirty=true}
function centerOn(i){if(view==='3d'){G3.focus(i);return}const n=N[i];sc=Math.max(sc,1.5);tx=-n.x;ty=-n.y;dirty=true}
function world(e){const b=gc.getBoundingClientRect(),p=rv((e.clientX-b.left-gc.clientWidth/2)/sc,(e.clientY-b.top-gc.clientHeight/2)/sc,-rot);
return[p[0]-tx,p[1]-ty]}
/* put a place of the map under the pointer: what a zoom and a turn both keep still */
function pin(e,wx,wy){const b=gc.getBoundingClientRect(),p=rv((e.clientX-b.left-gc.clientWidth/2)/sc,(e.clientY-b.top-gc.clientHeight/2)/sc,-rot);
tx=p[0]-wx;ty=p[1]-wy;dirty=true}
function pick(wx,wy){let best=-1,bd=1e18;
for(const n of N){if(hid(n))continue;const rr=rEff(n)+5/sc;const d=(n.x-wx)**2+(n.y-wy)**2;
if(d<rr*rr&&d<bd){bd=d;best=n.i}}return best}
function select(i){sel=i;renderCard();dirty=true}
function clearSel(){sel=-1;card.style.display='none';dirty=true}
function renderCard(){if(sel<0){card.style.display='none';return}
const id=N[sel].id,c=D[id];let h='<div class="cs"><div class="hd"><h3>'+E(c.t)+'</h3><button class="ib open" title="Open concept" aria-label="Open concept">__ICONCEPTS__</button><button class="ib x" title="Close (Esc)" aria-label="Close">&#215;</button></div>';
h+='<div>'+'<span class="badge">'+E(c.ty)+'</span><span class="badge">'+E(LBL[cat(id)]||cat(id))+'</span><span class="badge">'+c.ns+' sources</span></div>';
if(c.d)h+='<div class="desc">'+E(c.d)+'</div>';h+='</div>';
if(c.inb.length){h+='<div class="cs"><div class="sec"><i class="lk in"></i>Linked from ('+c.inb.length+')</div>';
c.inb.slice(0,9).forEach(x=>{h+='<span class="nb" data-i="'+idx[x]+'">'+E(D[x].t)+'</span>'});
if(c.inb.length>9)h+='<span class="nb" style="color:var(--mut);cursor:default">… '+(c.inb.length-9)+' more</span>';h+='</div>'}
if(c.out.length){h+='<div class="cs"><div class="sec"><i class="lk out"></i>Links to ('+c.out.length+')</div>';
c.out.slice(0,9).forEach(x=>{h+='<span class="nb" data-i="'+idx[x]+'">'+E(D[x].t)+'</span>'});
if(c.out.length>9)h+='<span class="nb" style="color:var(--mut);cursor:default">… '+(c.out.length-9)+' more</span>';h+='</div>'}
card.innerHTML=h;card.style.display='block';
card.querySelector('.x').onclick=clearSel;
card.querySelector('.open').onclick=()=>show(id);
card.querySelectorAll('.nb[data-i]').forEach(a=>a.onclick=()=>{select(+a.dataset.i);centerOn(+a.dataset.i)})}
gc.addEventListener('mousemove',e=>{const[wx,wy]=world(e);
if(drag){drag.x=wx;drag.y=wy;drag._m=(drag._m||0)+Math.abs(e.movementX||1)+Math.abs(e.movementY||1);dirty=true;return}
if(pan){const p=rv((e.clientX-pan[0])/sc,(e.clientY-pan[1])/sc,-rot);tx+=p[0];ty+=p[1];pan=[e.clientX,e.clientY];dirty=true;return}
const h=pick(wx,wy);if(h!==hov){hov=h;dirty=true}
gc.style.cursor=hov>=0?'pointer':'grab'});
gc.addEventListener('mousedown',e=>{const[wx,wy]=world(e);const h=pick(wx,wy);
if(h>=0){drag=N[h];drag._m=0}else pan=[e.clientX,e.clientY]});
addEventListener('mouseup',()=>{if(drag&&(drag._m||0)<6){if(sel===drag.i)clearSel();else select(drag.i)}drag=null;pan=null});
gc.addEventListener('dblclick',e=>{const[wx,wy]=world(e);const h=pick(wx,wy);
if(h>=0){select(h);show(N[h].id)}else fit()});
/* Zoom has no working limit: the owner asked for endless zoom on
   23.09.2026. The bounds left are there only to keep the arithmetic finite,
   1/500 of the fitted scale out to 500 times in. */
const zoomTo=v=>Math.max(.002,Math.min(500,v));
gc.addEventListener('wheel',e=>{e.preventDefault();const[wx,wy]=world(e);
if(e.altKey)rot+=swipe(e);else sc=zoomTo(sc*Math.exp(-e.deltaY*.0015));
pin(e,wx,wy)},{passive:false});
/* Safari's two-finger turn and pinch. rotation is in degrees since the gesture
   began, clockwise, and scale is the pinch since then; the place under the
   pointer at the start stays under it. */
let ges=null;
gc.addEventListener('gesturestart',e=>{e.preventDefault();const[wx,wy]=world(e);ges={r:rot,s:sc,wx,wy}});
gc.addEventListener('gesturechange',e=>{e.preventDefault();if(!ges)return;
rot=ges.r+(e.rotation||0)*Math.PI/180;sc=zoomTo(ges.s*(e.scale||1));pin(e,ges.wx,ges.wy)});
gc.addEventListener('gestureend',e=>{e.preventDefault();ges=null});
/* the line under each graph says how to turn, in this browser's and this keyboard's words */
const ALTKEY=/Mac|iP/.test(navigator.platform)?'Option':'Alt';
document.querySelectorAll('.howturn').forEach(h=>{h.innerHTML=('ongesturestart' in window?'<b>Two fingers turning</b> or ':'')+'<b>'+ALTKEY+'-scroll</b>'});
/* In Ask mode the box is a question, not a filter: typing one must not empty
   the list behind it, and clearing it must not leave the list filtered by half
   a question. `askMode` is the switch; the filter is fed the empty string. */
q.oninput=()=>{const f=askMode?'':q.value.toLowerCase();build(f);qv=f;dirty=true};
q.addEventListener('keydown',e=>{if(e.key==='Enter'&&askMode){e.preventDefault();ask()}});
function sxy(n){const p=rv(n.x+tx,n.y+ty,rot);return[p[0]*sc+gc.clientWidth/2,p[1]*sc+gc.clientHeight/2]}
function draw(){const x2=gc.getContext('2d');x2.setTransform(dpr,0,0,dpr,0,0);
x2.clearRect(0,0,gc.clientWidth,gc.clientHeight);
x2.save();x2.translate(gc.clientWidth/2,gc.clientHeight/2);x2.scale(sc,sc);x2.rotate(rot);x2.translate(tx,ty);
const anySel=sel>=0;
for(const kb in KBC){if(offKB.has(kb)||!HUE[kb])continue;const c=KBC[kb];
const g=x2.createRadialGradient(c.cx,c.cy,0,c.cx,c.cy,c.halo);
g.addColorStop(0,HUE[kb]+'30');g.addColorStop(.7,HUE[kb]+'1c');g.addColorStop(1,HUE[kb]+'00');
x2.fillStyle=g;x2.beginPath();x2.arc(c.cx,c.cy,c.halo,0,7);x2.fill();
}
x2.lineWidth=1/sc;
const MUT2=css('--mut'),LIN=css('--lin'),LOUT=css('--lout');
/* The focus is the selection, or else the concept under the pointer: its
   links light up in their direction's colours either way, as in the 3D view.
   Hover does not dim the rest; a selection does. Owner's request of 23.09.2026. */
const fo=anySel?sel:hov;
for(const[a,b]of L){const na=N[a],nb2=N[b];if(hid(na)||hid(nb2))continue;
const strong=fo>=0&&(a===fo||b===fo);
if(strong){const o=a===fo?b:a,s0=N[fo],so=N[o],out=D[s0.id].out.includes(so.id),inn=D[so.id].out.includes(s0.id);
 if(out&&inn){const g=x2.createLinearGradient(s0.x,s0.y,so.x,so.y);g.addColorStop(0,LOUT);g.addColorStop(1,LIN);x2.strokeStyle=g}
 else x2.strokeStyle=out?LOUT:LIN}
else x2.strokeStyle=MUT2;
x2.globalAlpha=strong?(anySel?.85:.7):anySel?.05:qv?.08:.28;x2.lineWidth=(strong?1.6:1)/sc;
x2.beginPath();x2.moveTo(na.x,na.y);x2.lineTo(nb2.x,nb2.y);x2.stroke()}
x2.globalAlpha=1;
/* The flow, as the logo's light runs along its strands. Every link carries a
   faint bead now and then, travelling the way it points, a third of them at a
   time; the selection's links carry a bright one without pause, in the link's
   colour with a white core. Owner's requests of 23.09.2026. None for less
   motion. */
if(!RMQ.matches){const T=performance.now()/1000;x2.fillStyle=css('--fg');x2.globalAlpha=anySel?.06:qv?.12:.45;
 for(let k=0;k<L.length;k++){const[a,b]=L[k],na=N[a],nb2=N[b];if(hid(na)||hid(nb2))continue;
  const ph=((T*.15+k*.6180339887)%1)*3;if(ph>1||(fo>=0&&(a===fo||b===fo)))continue;
  x2.beginPath();x2.arc(na.x+(nb2.x-na.x)*ph,na.y+(nb2.y-na.y)*ph,1.6/sc,0,7);x2.fill()}
 x2.globalAlpha=1}
if(fo>=0&&!RMQ.matches){const T=performance.now()/1000,s0=N[fo];
 const bead=(f,t,ph,col)=>{const x=f.x+(t.x-f.x)*ph,y=f.y+(t.y-f.y)*ph;
  x2.fillStyle=col;x2.beginPath();x2.arc(x,y,3.4/sc,0,7);x2.fill();x2.fillStyle='#fff';x2.beginPath();x2.arc(x,y,1.5/sc,0,7);x2.fill()};
 for(const o of NB[fo]){const so=N[o];if(hid(so))continue;const ph=(T*.45+o*.6180339887)%1;
  if(D[s0.id].out.includes(so.id))bead(s0,so,ph,LOUT);if(D[so.id].out.includes(s0.id))bead(so,s0,ph,LIN)}}
for(const n of N){if(hid(n))continue;const g=ghost(n);
x2.save();x2.translate(n.x,n.y);x2.rotate(-rot);x2.globalAlpha=g?.13:1;
x2.fillStyle=COL[n.c];x2.strokeStyle=css('--bg');x2.lineWidth=2/sc;
shp(x2,rEff(n),n.c);x2.fill();x2.stroke();
if(n.i===sel){x2.strokeStyle=css('--acc');x2.lineWidth=3/sc;shp(x2,rEff(n)+5/sc,n.c);x2.stroke()}
else if(n.i===hov&&!g){x2.strokeStyle=css('--acc');x2.lineWidth=2/sc;shp(x2,rEff(n)+3/sc,n.c);x2.stroke()}
x2.restore()}
/* the bundle names ride above the nodes, map-label style, in the block hue
   with a dark halo. Two placements tried first: above the cluster (drifts
   off-canvas for a big radius, Gamma lost its name) and a centroid
   watermark under the nodes (invisible exactly where the cluster is dense —
   only Zeta's fifteen sparse nodes let its through). */
for(const kb in KBC){if(offKB.has(kb)||!HUE[kb])continue;const c=KBC[kb];
/* one size for every name — scaling by radius made Alpha shout and Zeta
   whisper, and the six names are peers. Owner: symmetry and consistency. */
const fs=80;
x2.font='700 '+fs+'px system-ui,-apple-system,sans-serif';x2.textAlign='center';x2.textBaseline='middle';
x2.globalAlpha=anySel||qv?.25:.8;
x2.save();x2.translate(c.cx,c.cy);x2.rotate(-rot);
x2.lineWidth=fs*.14;x2.strokeStyle=css('--bg');x2.strokeText(kbName(kb),0,0);
x2.fillStyle=HUE[kb];x2.fillText(kbName(kb),0,0);x2.restore();
x2.globalAlpha=1;x2.textAlign='start'}
x2.restore();
/* labels in screen space: constant size, halo, greedy anti-collision */
x2.font='600 12px system-ui,-apple-system,sans-serif';x2.textBaseline='middle';
const thr=sc<.28?7:sc<.55?4:sc<.95?2:0;
const placed=[];
const cand=N.filter(n=>!hid(n)&&!ghost(n)&&(n.i===sel||n.i===hov||(sel>=0&&NB[sel].has(n.i))||D[n.id].inb.length>=thr));
cand.sort((a,b)=>D[b.id].inb.length-D[a.id].inb.length);
for(const n of cand){const[sx,sy]=sxy(n);if(sx<-40||sy<0||sx>gc.clientWidth+40||sy>gc.clientHeight)continue;
const txt=D[n.id].t,w=x2.measureText(txt).width,r=rEff(n)*sc;
const bx=sx+r+6,by=sy,box=[bx-2,by-9,bx+w+2,by+9];
if(placed.some(p=>box[0]<p[2]&&box[2]>p[0]&&box[1]<p[3]&&box[3]>p[1]))continue;placed.push(box);
x2.lineWidth=3;x2.strokeStyle=css('--bg');x2.strokeText(txt,bx,by);
x2.fillStyle=n.i===sel?css('--fg'):css('--mut');x2.fillText(txt,bx,by)}
}
const RMQ=matchMedia('(prefers-reduced-motion: reduce)');RMQ.addEventListener('change',()=>{dirty=true});
(function loop(){if(view==='graph'&&(dirty||drag||!RMQ.matches)){dirty=false;draw()}requestAnimationFrame(loop)})();
const split=document.getElementById('splitter');
let sdrag=false;
split.addEventListener('mousedown',e=>{sdrag=true;split.classList.add('on');document.body.style.userSelect='none';e.preventDefault()});
addEventListener('mousemove',e=>{if(!sdrag)return;const w=Math.max(220,Math.min(innerWidth*.6,e.clientX));document.documentElement.style.setProperty('--sidew',w+'px')});
addEventListener('mouseup',()=>{if(sdrag){sdrag=false;split.classList.remove('on');document.body.style.userSelect=''}});
// About: every number is derived from D at open time, so the panel cannot
// drift from the page it describes the way a baked-in count would. The
// knowledge-base breakdown is deliberately absent — the selectors in Settings
// already carry a count each, and a second copy is this vault's oldest
// recurring fault.
const setWrap=document.getElementById('setWrap'),setWin=document.getElementById('setWin'),bSet=document.getElementById('bSet');
const REPO='';   /* your repository URL, or '' to hide the link */
/* A manual of your own for the vault, as a web address, or '' to hide the Docs row. */
const FIELD_MANUAL='';
if(FIELD_MANUAL)document.getElementById('setDocs').href=FIELD_MANUAL;
else document.getElementById('setDocs').closest('.setRow').hidden=true;
/* What's new, as folia's: Settings › About › What's new opens it in Settings'
   place, and Done closes both. NEWS is `_scripts/whats-new.json`, written for
   the reader: a change a title and a line, newest first. The changes not read
   yet are counted on About and on its row until it is opened. "Read up to
   here" is the newest change's heading, kept in this browser; on a first visit
   the changes of the last week before the newest count as new, not every
   change since August. */
const newsWrap=document.getElementById('newsWrap'),newsTab=document.getElementById('newsTab'),newsPill=document.getElementById('newsPill');
const newsMark=()=>{try{return localStorage.getItem('okf.newsSeen')||''}catch(e){return ''}};
function unseenNews(){const i=NEWS.findIndex(n=>n.k===newsMark());if(i>=0)return NEWS.slice(0,i);if(!NEWS.length)return [];
 const lim=new Date(NEWS[0].d);lim.setDate(lim.getDate()-7);return NEWS.filter(n=>new Date(n.d)>=lim)}
function paintNews(){const u=unseenNews().length;newsTab.hidden=newsPill.hidden=!u;newsTab.textContent=u;newsPill.textContent=u+' new';
 document.getElementById('newsLine').textContent=u?u+(u===1?' change':' changes')+' you have not read yet.':'What changed in the viewer, newest first.'}
const dayName=d=>new Date(d+'T12:00').toLocaleDateString(undefined,{dateStyle:'medium'});
function newsOpen(){const days=[],list=document.getElementById('newsList');
 for(const n of NEWS){if(!days.length||days[days.length-1].d!==n.d)days.push({d:n.d,ns:[]});days[days.length-1].ns.push(n)}
 list.innerHTML=days.map(g=>'<section class="nwDay"><h4>'+dayName(g.d)+'</h4><div class="nwCard">'+
  g.ns.map(n=>'<div class="nwRow"><span class="nwTitle">'+E(n.t)+'</span><span class="nwDetail">'+E(n.x)+'</span></div>').join('')+'</div></section>').join('');
 document.getElementById('newsCount').textContent=NEWS.length+(NEWS.length===1?' change':' changes')+' listed.';
 setClose();newsWrap.classList.add('on');list.scrollTop=0;
 try{if(NEWS.length)localStorage.setItem('okf.newsSeen',NEWS[0].k)}catch(e){}paintNews()}
function newsClose(){newsWrap.classList.remove('on')}
document.getElementById('setNews').onclick=newsOpen;
document.getElementById('newsDone').onclick=newsClose;
newsWrap.addEventListener('pointerdown',e=>{if(e.target===newsWrap)newsClose()});
paintNews();
/* One figure of a strip: the fact's name, its value, and a few words on what
   it counts. The longer sentence, where one is needed, is the cell's tooltip. */
function fact(strip,k,detail,v,ttl,href){const c=document.createElement('div');c.className='stat';if(ttl)c.title=ttl;
const n=document.createElement('span');n.className='sn';n.textContent=k;
const b=document.createElement('b');
if(href){const a=document.createElement('a');a.href=href;a.target='_blank';a.rel='noopener';a.textContent=v;b.appendChild(a)}else b.textContent=v;
const d=document.createElement('span');d.className='sd';d.textContent=detail;c.append(n,b,d);strip.appendChild(c)}
function aboutFill(){
 const cs=Object.values(D),ver=document.getElementById('setVersion'),vt=document.getElementById('setVault');ver.innerHTML='';vt.innerHTML='';
 // The build facts lead, as in j4k's About: what this page is, before what the corpus in it holds.
 fact(ver,'Build code','the commit this page was made from',GIT,'Linked to the commit where REPO is set. ’uncommitted’ means the vault held edits that were in no commit when it ran, so the page matches no commit exactly and there is nothing to link to. Set REPO above to link the hash to your own repository.',
  REPO&&/^[0-9a-f]{7,40}$/.test(GIT)?REPO+'/commit/'+GIT:null);
 fact(ver,'Build number','commits on main then',BUILDNO);
 fact(ver,'Build date','when this page was made',STAMP,'When _scripts/visualize.py last ran, in this Mac’s time zone');
 const st=STARTED.split(' · ');
 fact(vt,'Started','first commit '+st[0],st[1]||STARTED,'The vault’s first commit, and which day of building this is');
 fact(vt,'Concepts','in '+new Set(cs.map(c=>c.kb)).size+' knowledge bases',sw(cs.length),'Every concept of every knowledge base, whatever Settings hides');
 fact(vt,'Citations','sources the concepts cite',sw(cs.reduce((a,c)=>a+(c.ns||0),0)));
 fact(vt,'Links','between concepts, counted where they land',sw(cs.reduce((a,c)=>a+(c.inb||[]).length,0)),'A link is one concept pointing at another. Every link arrives somewhere, so this counts all links between concepts, where they land. Higher means better connected; a bundle that is a list rather than a graph shows up here first.');
 fact(vt,'Unlinked','concepts nothing links to',sw(cs.filter(c=>!(c.inb||[]).length).length),'Concepts that no other concept links to. Not an error, but usually a link is missing.');
}
/* The parts, down the window's left side, About first as in j4k; each says
   under its title what it holds. */
const PARTS={partAbout:['About 00_Cerebrum','Which build this page is, and where to read how the vault works.'],
 paneKb:['Knowledge bases','Which knowledge bases the map, the list and the counts show. Kept for the next visit.'],
 paneBrain:['Brain','Which model answers a question, and what leaves this Mac.']};
const setTabs=[...document.querySelectorAll('.setTab')];
function setTab(id){setTabs.forEach(t=>{if(t.dataset.part===id)t.setAttribute('aria-current','page');else t.removeAttribute('aria-current')});
 document.querySelectorAll('.setPart').forEach(p=>{if(p.id===id)p.removeAttribute('inert');else p.setAttribute('inert','')});
 document.getElementById('setTitle').textContent=PARTS[id][0];document.getElementById('setLine').textContent=PARTS[id][1]}
setTabs.forEach(t=>t.onclick=()=>{setTab(t.dataset.part);t.blur()});
const setShown=()=>setWrap.classList.contains('on');
let dragAt=[0,0];
async function setOpen(id){aboutFill();setTab(id);dragAt=[0,0];setWin.style.transform='';
 setWrap.classList.add('on');bSet.classList.add('on');bSet.setAttribute('aria-expanded','true');
 await pingHelper();loadBrain()}
function setClose(){setWrap.classList.remove('on');bSet.classList.remove('on');bSet.setAttribute('aria-expanded','false')}
/* The gear opens on Knowledge bases, which is what it is pressed for; the
   mark in the header opens on About, as About j4k sits first. A press on the
   dimmed page outside the window closes it, on pointerdown, so a drag that
   ends outside does not. */
bSet.onclick=()=>{if(setShown())setClose();else setOpen('paneKb')};
document.getElementById('aboutBtn').onclick=()=>setOpen('partAbout');
document.getElementById('setX').onclick=setClose;
document.getElementById('setDone').onclick=setClose;
setWrap.addEventListener('pointerdown',e=>{if(e.target===setWrap)setClose()});
document.getElementById('setBuild').textContent='Build '+BUILDNO+' · '+GIT;
/* Moved by its head or the word Settings, as j4k's window, and kept 8px inside
   the page; it opens centred again. */
setWin.addEventListener('pointerdown',e=>{if(e.button!==0||!e.target.closest('.winHead,.setBrand')||e.target.closest('button,a,select,input'))return;
 e.preventDefault();const b=setWin.getBoundingClientRect(),x0=e.clientX,y0=e.clientY,s0=dragAt.slice(),M=8;
 const lim=[M-b.left,innerWidth-M-b.right,M-b.top,innerHeight-M-b.bottom],cl=(v,l,h)=>l>h?0:Math.min(Math.max(v,l),h);
 const mv=m=>{dragAt=[s0[0]+cl(m.clientX-x0,lim[0],lim[1]),s0[1]+cl(m.clientY-y0,lim[2],lim[3])];setWin.style.transform='translate('+dragAt[0]+'px,'+dragAt[1]+'px)'};
 const up=()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up);removeEventListener('pointercancel',up)};
 addEventListener('pointermove',mv);addEventListener('pointerup',up);addEventListener('pointercancel',up)});
function kbBadge(){const n=offKB.size;let d=bSet.querySelector('.dot');
if(n){if(!d){d=document.createElement('span');d.className='dot';bSet.appendChild(d)}d.textContent=n}
else if(d)d.remove();
bSet.title=n?'Settings · '+n+(n>1?' knowledge bases':' knowledge base')+' hidden':'Settings';
document.getElementById('kbN').textContent=(KB_ALL.length-n)+' of '+KB_ALL.length+' showing'}
/* One keyboard handler for the page. Escape closes the nearest thing open —
   About, then Settings, then the Timelapse, then the graph card — and then
   lets go of any button
   still holding focus. The owner reported the reason on 09.09.2026, on the
   full-screen button: a button keeps focus after a click, the first keystroke
   afterwards switches the browser to keyboard modality, and Escape itself
   draws the ring. Every button can be the last one clicked, so every button
   is let go of. Reports is first in the chain, because it is the thing most
   recently opened when it is open at all. `f` frames the graph, and never
   while typing: a search for "fokus" framed it. */
addEventListener('keydown',e=>{
if(e.key==='Escape'){
if(repWrap.classList.contains('on'))showReports(false);
else if(newsWrap.classList.contains('on'))newsClose();
else if(setShown())setClose();
else if(G3.cine&&G3.cine.on())G3.cine.stop();
else if(view==='graph'||view==='3d')clearSel();
const a=document.activeElement;if(a&&a.tagName==='BUTTON')a.blur();
return}
const t=e.target;if(e.metaKey||e.ctrlKey||e.altKey||(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA')))return;
if(e.key==='f'||e.key==='F'){if(view==='graph')fit();else if(view==='3d')G3.fit()}});
__G3__
/* The page opens on the graph: the Graph view is the first of the two, and a
   working selection like the view is not kept between visits. */
/* The vault's figures, owner's request of 27.09.2026, in one line at the top
   left of each graph. The whole vault, as the About box counts it, whatever
   the Settings hide. A link runs from one concept to another, so the vault's
   outbound and inbound totals are one number, counted from either end, and
   the line gives it once. */
function sw(n){return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,"'")}
(()=>{const cs=Object.values(D);
const html='<b>'+new Set(cs.map(c=>c.kb)).size+'</b> bases · <b>'+sw(cs.length)+'</b> concepts · <b>'+
 sw(cs.reduce((a,c)=>a+c.inb.length,0))+'</b> links · <b>'+sw(cs.reduce((a,c)=>a+(c.ns||0),0))+'</b> citations';
document.querySelectorAll('.gstat').forEach(el=>el.innerHTML=html)})();
/* The address can name a view and a search, 27.09.2026, for GLaDOS, the owner's
   voice assistant: "switch to concepts, 2D view and 3D view", "search for
   something using the search bar (not ask for Claude)", "this should work in all
   views". `#view=concepts|graph|2d|3d&q=…` is read on load and on every change of
   the fragment, which is how she steers this tab without reloading 16 MB. A part
   the fragment does not name is left as it is, an empty `q` clears the search, and
   the search is always Search, never Ask: it goes through the box's own `input`
   event, as typing does, so it filters every view alike. `n` is hers, to make
   each address new, and means nothing here. The meta tag in the head says the
   page does this; she looks for it before telling anyone the page followed her.
   viewer-check.js holds it.

   And it can start the Film, 08.10.2026. The owner's words, in her session and
   passed on by it: "in Cerebrum, in 3D view, can you teach glados to start the
   film?"; his yes to the change was given here. `cine=film` does what the Film
   button did, and the Timelapse button does since 24.10.2026, after the view
   and the search: so the same address with a new `n` starts the film again
   from its beginning, as a second press does, and
   with Reduce Motion the film opens and waits for Play. An address without
   `cine` leaves what plays as it is; an address that names another view ends
   it, as that view's button does. Only `film` is read. The tag's third word
   says the page does this, and she sends `cine` only when the word is there. */
function fromAddress(){const a=new URLSearchParams(location.hash.slice(1)),v=a.get('view');
 if(v==='concepts'||v==='graph'||v==='3d'||v==='2d')setView(v==='2d'?'graph':v);
 if(a.has('q')){if(askMode)setMode(false);q.value=a.get('q');q.dispatchEvent(new Event('input'))}
 if(a.get('cine')==='film'&&G3.cine)G3.cine.start('film')}
addEventListener('hashchange',fromAddress);
build('');kbbar();kbBadge();chips();setView('graph');fromAddress();
</script></body></html>"""
page = (page.replace('__G3__', G3_JS).replace('__I3D__', icon_3d).replace('__LOGO__', _mark('h'), 1).replace('__LOGO__', _mark('a', pulse=True), 1)
        .replace('__KB_BLOCKS__', json.dumps(KB_BLOCKS, ensure_ascii=False)).replace('__GIT__', git_id)
        .replace('__IGRAPH__', icon_graph).replace('__ICONCEPTS__', icon_concepts)
        .replace('__IGEAR__', icon_gear).replace('__ISEARCH__', icon_search)
        .replace('__ICOLLAPSE__', icon_collapse).replace('__IEXPAND__', icon_expand)
        .replace('__ISPARK__', icon_spark).replace('__IREPORTS__', icon_reports)
        .replace('__IINFO__', icon_info).replace('__ILAYERS__', icon_layers)
        .replace('__IBOOK__', icon_book).replace('__INEWS__', icon_news)
        .replace('__HALO__', json.dumps(halos))
        .replace('__BUILDNO__', build_no).replace('__STARTED__', started).replace('__NEWS__', json.dumps(news, ensure_ascii=False))).replace('__STAMP__', stamp).replace('__DATA__', json.dumps(data, ensure_ascii=False))
out = os.path.join(VAULT, '00_Cerebrum_viewer.html')
# Written whole or not at all. This used to write straight over the file, which
# was safe while a session ran it by hand and waited; since 16.09.2026 the
# post-commit hook runs it, so it can land while the owner has the viewer open
# and a browser reload could otherwise read a 16 MB file mid-write. `os.replace`
# is atomic on the same filesystem, so a reader sees the old page or the new one.
tmp = out + '.tmp'
open(tmp, 'w', encoding='utf-8').write(page)
os.replace(tmp, out)
print('wrote %s  (%d concepts, %.1f MB)' % (out, len(concepts), os.path.getsize(out) / 1e6))
