#!/usr/bin/env python3
"""Generates 00_Cerebrum_viewer.html — a static, self-contained browser for the
vault's OKF bundles. Derived output, never hand-edited; regenerate with:

    python3 _scripts/visualize.py

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

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)

def kbs():
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))

def esc(s): return html.escape(str(s), quote=False)

def inline(s, cid, ids):
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<i>\1</i>', s)
    def link(m):
        t, u = m.group(1), m.group(2)
        if u.startswith('http'):
            return '<a href="%s" target="_blank">%s</a>' % (u, t)
        if u.endswith('.md'):
            tgt = os.path.normpath(os.path.join(os.path.dirname(cid), u)).replace(os.sep, '/')
            if tgt in ids:
                return '<a class="nav" data-t="%s">%s</a>' % (tgt, t)
            return '<a class="dead" title="not written yet — legitimate under OKF">%s</a>' % t
        return t
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    s = re.sub(r'\[\^([^\]]+)\]', r'<sup class="fn">\1</sup>', s)
    return s

def md2html(text, cid, ids):
    out, lines = [], text.split('\n')
    i, para, ul, tbl, fns = 0, [], [], [], []
    def flushp():
        if para: out.append('<p>' + inline(esc(' '.join(para)), cid, ids) + '</p>'); para.clear()
    def flushu():
        if ul: out.append('<ul>' + ''.join('<li>%s</li>' % inline(esc(x), cid, ids) for x in ul) + '</ul>'); ul.clear()
    def flusht():
        if tbl:
            rows = [r for r in tbl if not re.match(r'^\|[\s\-:|]+\|$', r)]
            h = '<table>'
            for k, r in enumerate(rows):
                cells = [c.strip() for c in r.strip('|').split('|')]
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

concepts, order = {}, []
for kb in kbs():
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
            try: fm = yaml.safe_load(m.group(1)) or {}
            except Exception: fm = {}
            v = fm.get('verified') or {}
            tier = ('human-reviewed' if str((v or {}).get('by', '')).startswith('human:')
                    else 'machine-confirmed' if v else 'unverified')
            concepts[cid] = dict(kb=kb, fm=fm, body=raw[m.end():], tier=tier)
            order.append(cid)

inbound = collections.defaultdict(list)
for cid, c in concepts.items():
    for m in re.finditer(r'\]\(([^)#\s]+\.md)\)', c['body']):
        t = os.path.normpath(os.path.join(os.path.dirname(cid), m.group(1))).replace(os.sep, '/')
        if t in concepts and cid not in inbound[t]: inbound[t].append(cid)

data = {}
for cid, c in concepts.items():
    fm = c['fm']
    srcs = [s for s in (fm.get('sources') or []) if isinstance(s, dict)]
    out_links = sorted({os.path.normpath(os.path.join(os.path.dirname(cid), m.group(1))).replace(os.sep, '/')
                        for m in re.finditer(r'\]\(([^)#\s]+\.md)\)', c['body'])} & set(concepts))
    data[cid] = dict(
        t=fm.get('title') or os.path.basename(cid)[:-3],
        d=fm.get('description') or '', ty=fm.get('type') or '?',
        st=fm.get('status') or 'stable', tr=c['tier'], kb=c['kb'],
        tags=[str(x) for x in (fm.get('tags') or [])], ns=len(srcs),
        srcs=[[s.get('title') or s.get('resource', ''), str(s.get('last_modified', ''))] for s in srcs[:40]],
        inb=sorted(inbound[cid]), out=out_links,
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

def _layout(members):
    """Fruchterman-Reingold over one group's own edges. Returns positions and radius."""
    m = len(members)
    sub = {g: j for j, g in enumerate(members)}
    E = np.array([[sub[a], sub[b]] for a, b in _edges if a in sub and b in sub] or [[0, 0]], int)
    has_e = any(a in sub and b in sub for a, b in _edges)
    ang = np.arange(m) * 2.399963
    P = np.stack([np.cos(ang), np.sin(ang)], 1) * (14 * np.sqrt(np.arange(m) + 1))[:, None]
    K = 46.0
    for it in range(420):
        tmp = 60.0 * (1 - it / 420) + 2.0
        d = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1)) + 1e-6
        F = (d / dist[..., None]) * (K * K / dist)[..., None]
        disp = F.sum(1)
        if has_e:
            ev = P[E[:, 1]] - P[E[:, 0]]
            el = np.sqrt((ev ** 2).sum(-1)) + 1e-6
            fa = (ev / el[:, None]) * (el * el / K)[:, None]
            np.add.at(disp, E[:, 0], fa); np.add.at(disp, E[:, 1], -fa)
        # Gravity toward the group's own middle. Stronger for small groups:
        # with a dozen nodes and few edges the simulation settles into two or
        # three sub-clumps with nothing pulling them together, which is what
        # made Zeta read as scattered rather than as one knowledge base.
        disp -= P * (0.03 + 0.22 / math.sqrt(m))
        ln = np.sqrt((disp ** 2).sum(-1)) + 1e-6
        P += (disp / ln[:, None]) * np.minimum(ln, tmp)[:, None]
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

_lay = {g: _layout(mem) for g, mem in _groups.items()}

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

# The corners clear each other's halos, not only their extents. Owner's
# instruction of 14.09.2026, after Delta and Epsilon were moved out of Alpha's halo:
# "also move Beta slightly out". Beta's halo reached 92 units into Alpha's. A corner
# whose halo reaches into another's steps out along its own ray, keeping its
# angle, until the two clear by HALO_GAP. The smaller halo steps, so Alpha, the
# largest, stays where the solve put it. The corners then no longer stand at one
# distance from the centre, the property the unit circle was chosen for, and
# that is the trade the instruction makes: the angles hold, and the career
# concepts keep the middle.
_corners = [k for k in _corners_all if k in _groups]
for _ in range(400):
    _cent = {g: (ANCHOR[g][0] * _T, ANCHOR[g][1] * _T) for g in ANCHOR if g in _groups}
    _stepped = False
    for _i, _a in enumerate(_corners):
        for _b in _corners[_i + 1:]:
            _ha, _hb = _halo(_kb_points(_a, _cent)), _halo(_kb_points(_b, _cent))
            _short = _ha[2] + _hb[2] + HALO_GAP - math.hypot(_ha[0] - _hb[0], _ha[1] - _hb[1])
            if _short > 0:
                _g = _a if _ha[2] < _hb[2] else _b
                _ux, _uy = ANCHOR[_g]
                _ul = math.hypot(_ux, _uy)
                ANCHOR[_g] = (_ux + _ux / _ul * (_short + 1.0) / _T, _uy + _uy / _ul * (_short + 1.0) / _T)
                _stepped = True
                _cent = {g: (ANCHOR[g][0] * _T, ANCHOR[g][1] * _T) for g in ANCHOR if g in _groups}
    if not _stepped:
        break
else:
    print('warning: the corners\' halos did not clear in 400 steps', file=sys.stderr)

# The two Alpha knowledge bases hang off Alpha's corner rather than being given
# corners of their own: they are that side's own bundles, not a fourth and
# fifth employer, and a corner would claim otherwise. Both stay out of the
# triangle's separation solve for the reason Zeta does — an extra anchor
# would inflate the triangle to clear something that is not one of its corners.
#
# **They are stacked vertically, one above the other.** Epsilon sits up and to
# the right of Alpha, on the mirror of Gamma's own offset; Delta sits directly
# below it, level with Alpha. Owner's instruction of 31.08.2026.
#
# That leaves exactly one free number — how far out along its ray Epsilon goes —
# because Delta's x is then Epsilon's x and its y is Alpha's. So the placement is a
# single walk on that number, pushed out until all three pairs clear each other
# by their extents plus the gap. Solving it as one quantity is the point: an
# earlier version placed Delta first and Epsilon second, and aligning them
# afterwards put the pair 5 units inside their own clearance with nothing to
# notice it.
#
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
    z = zn * np.sqrt(np.maximum((1.10 * Rt) ** 2 - r2, (0.25 * Rt) ** 2))
    if (~linked).any():
        k = np.arange(int((~linked).sum()))
        z[~linked] = (((k * 0.6180339887) % 1.0) * 2 - 1) * np.sqrt(np.maximum((1.55 * Rt) ** 2 - r2[~linked], 0.0))
    return z

_depths = {}
for g, members in _groups.items():
    P, Rt, _e, sub = _lay[g]
    Pm = np.array([P[sub[i]] for i in members])
    for i, zz in zip(members, _depth(Pm, Rt, members)):
        _depths[i] = float(zz)

# Centre the picture on the middle of the work triangle, not on the mean of
# every node: the mean is dragged around by whichever knowledge base grew last,
# and Zeta sitting below would push the career concepts off centre.
_mx = _my = 0.0
for i, c in enumerate(_ids):
    x, y = _pos[i]
    data[c]['x'] = round(x - _mx, 1); data[c]['y'] = round(y - _my, 1); data[c]['z'] = round(_depths[i], 1)
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

def _gear(teeth=8, outer=9.3, root=6.9, hole=2.9):
    """Eight flat-topped teeth: each is two points on the root circle and two on the outer."""
    pts = []
    for k in range(teeth):
        a = 2 * math.pi * k / teeth - math.pi / 2
        for da, r in ((-0.31, root), (-0.17, outer), (0.17, outer), (0.31, root)):
            pts.append('%.2f %.2f' % (12 + r * math.cos(a + da), 12 + r * math.sin(a + da)))
    return '<path d="M%s Z"/><circle cx="12" cy="12" r="%g"/>' % (' L'.join(pts), hole)

_nodes = ((6.0, 7.0), (18.0, 6.0), (12.0, 18.0))
icon_graph = _icon(''.join('<circle cx="%g" cy="%g" r="2.6"/>' % p for p in _nodes)
                   + '<path d="%s"/>' % ' '.join(_spoke(_nodes[i], _nodes[j], 2.6)
                                                 for i, j in ((0, 1), (0, 2), (1, 2))))
# the Concept view's own shape: the list on the left, the page beside it
icon_concepts = _icon('<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
                      '<path d="M9 4v16M12.5 9h5M12.5 12.5h5M12.5 16h3"/>')
# the 3D view's own shape: a cube, the one solid everyone reads as depth
icon_3d = _icon('<path d="M12 3 20 7.5v9L12 21 4 16.5v-9Z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>')
icon_gear = _icon(_gear())
icon_search = _icon('<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20.5 20.5"/>')
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
 document.getElementById('about3d').disabled=true;return}
G3.ok=true;G3.opaque=gl.getContextAttributes().alpha===false;
const RM=matchMedia('(prefers-reduced-motion: reduce)');RM.addEventListener('change',()=>{need=true});
const FOV=38*Math.PI/180,NN=N.length,MARGIN=36;
const hex=h=>{h=h.trim().replace('#','');if(h.length===3)h=h.split('').map(c=>c+c).join('');
 const v=parseInt(h.slice(0,6),16);return[(v>>16&255)/255,(v>>8&255)/255,(v&255)/255]};
/* canvas y points down, GL y points up: flipping y here is what makes the
   front view the 2D map the right way up */
const PX=new Float32Array(NN),PY=new Float32Array(NN),PZ=new Float32Array(NN),RR=new Float32Array(NN);
N.forEach((n,i)=>{PX[i]=n.x;PY[i]=-n.y;PZ[i]=D[n.id].z||0;RR[i]=n.r});
const C3=N.map(n=>hex(COL[n.c]));

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
uniform mat4 uM;uniform vec2 uV;uniform float uPx,uZs,uMin;
out vec2 vQ;out vec3 vC;out float vShape,vS,vF;
void main(){vec4 c=uM*vec4(aP.x,aP.y,aP.z*uZs,1.);
 float rp=clamp(aP.w*sqrt(uPx/max(c.w,1e-3)),uMin,30.);
 const float G=3.2;vQ=aQ*G;vC=aC.rgb;vShape=aC.a;vS=aS;vF=fog(c.w);
 gl_Position=c+vec4(aQ*G*rp*2./uV*c.w,0.,0.);}`,`
uniform sampler2D uT;uniform vec3 uBg,uAcc;uniform float uCell;
in vec2 vQ;in vec3 vC;in float vShape,vS,vF;out vec4 o;
void main(){float d=length(vQ);
 vec2 lc=vec2(.5+vQ.x*uCell,.5-vQ.y*uCell),cell=vec2(mod(vShape,4.),floor(vShape/4.));
 vec4 t=texture(uT,(cell+clamp(lc,0.,1.))/4.)*(1.-smoothstep(1.38,1.56,d));
 float fill=t.r,edge=max(t.g,fill),ghost=(vS>.5&&vS<1.5)?1.:0.;
 vec3 rgb=vC*fill+uBg*(edge-fill);float a=edge;
 if(vS>1.5){float rr=vS>2.5?1.5:1.38,w=vS>2.5?.13:.08;
  float ring=(1.-smoothstep(w,w+.07,abs(d-rr)))*(1.-edge);rgb+=uAcc*ring;a+=ring;}
 vec3 glow=vC*exp(-d*d*.6)*(ghost>0.?0.:(vS>2.5?.7:.4));
 float k=vF*(ghost>0.?.13:1.);o=vec4((rgb+glow)*k,a*k);if(o.a<.003&&dot(o.rgb,o.rgb)<1e-5)discard;}`);
const NS=9,nodeArr=new Float32Array(NN*NS),quad=buf(new Float32Array([-1,-1,1,-1,-1,1,1,1]));
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
(function(){const a=document.createElement('canvas');a.width=a.height=CELL*4;const c=a.getContext('2d');
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
uniform mat4 uM;uniform vec2 uV;uniform float uZs;
out vec3 vC;out float vA,vD,vH,vF,vS,vSW,vWW,vL,vFg,vAl;
void main(){vec4 a=uM*vec4(aA.xy,aA.z*uZs,1.),b=uM*vec4(aB.xy,aB.z*uZs,1.);
 if(aW.x<.001||a.w<=0.||b.w<=0.){gl_Position=vec4(2.,2.,2.,1.);return;}
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
const KBS=Object.keys(KBC).filter(k=>HUE[k]),KBZ={};
KBS.forEach(k=>{let s=0,c=0;N.forEach((n,i)=>{if(n.kb===k){s+=PZ[i];c++}});KBZ[k]=c?s/c:0});
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
let W=1,H=1,dpr3=1,M=null,pxs=1,right=[1,0,0],up=[0,1,0],back=[0,0,1],anim=null,entered=false,
 vy=0,vp=0,drag3=null,last=performance.now(),idle=last,need=true,skey='',GH=new Uint8Array(NN),
 F0=0,F1=1,BR={c:[SCX,SCY,0],r:SCR};
const SX=new Float32Array(NN),SY=new Float32Array(NN),SW=new Float32Array(NN),SRp=new Float32Array(NN),order=[];
const basis=q=>[qrot(q,[1,0,0]),qrot(q,[0,1,0]),qrot(q,[0,0,1])];
function matrix(){[right,up,back]=basis(cam.q);
 const e=[0,1,2].map(k=>cam.t[k]+cam.d*back[k]),dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 const V=[right[0],up[0],back[0],0,right[1],up[1],back[1],0,right[2],up[2],back[2],0,-dot(right,e),-dot(up,e),-dot(back,e),1];
 const n=Math.max(1,cam.d*.02),f=cam.d+SCR*8,t=1/Math.tan(FOV/2),a=W/H,nf=1/(n-f);
 const P=[t/a,0,0,0,0,t,0,0,0,0,(f+n)*nf,-1,0,0,2*f*n*nf,0];M=new Float32Array(16);
 for(let c=0;c<4;c++)for(let r=0;r<4;r++){let s=0;for(let k=0;k<4;k++)s+=P[k*4+r]*V[c*4+k];M[c*4+r]=s}
 pxs=(H/2)*t}
function resize3(){const w=g3.clientWidth,h=g3.clientHeight;if(!w||!h)return;W=w;H=h;dpr3=Math.min(devicePixelRatio||1,2);
 for(const c of[g3,g3l]){c.width=Math.round(w*dpr3);c.height=Math.round(h*dpr3)}need=true}
new ResizeObserver(resize3).observe(g3);

/* What is showing decides the frame: the bounds Fit uses and the fog range. */
function bounds(zs){let a=[1e9,1e9,1e9],b=[-1e9,-1e9,-1e9],any=false;
 for(let i=0;i<NN;i++){if(hid(N[i]))continue;any=true;const p=[PX[i],PY[i],PZ[i]*zs];
  for(let k=0;k<3;k++){a[k]=Math.min(a[k],p[k]);b[k]=Math.max(b[k],p[k])}}
 if(!any)return null;const c=[0,1,2].map(k=>(a[k]+b[k])/2);
 return{c,r:Math.max(1,Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2])/2)}}
/* Fit is solved, not guessed: for the camera's direction, the distance at
   which every showing concept's centre lands inside the canvas, margins
   included, with the target moved to the middle of what the camera sees. */
function fitFor(q,zs){const[r,u,b]=basis(q),bb=bounds(zs);if(!bb)return null;
 const tx=Math.tan(FOV/2)*(W/H)*(W-2*MARGIN)/W,ty=Math.tan(FOV/2)*(H-2*MARGIN)/H;
 let xa=1e9,xb=-1e9,ya=1e9,yb=-1e9;const pts=[];
 for(let i=0;i<NN;i++){if(hid(N[i]))continue;const p=[PX[i]-bb.c[0],PY[i]-bb.c[1],PZ[i]*zs-bb.c[2]];
  const x=p[0]*r[0]+p[1]*r[1]+p[2]*r[2],y=p[0]*u[0]+p[1]*u[1]+p[2]*u[2],z=p[0]*b[0]+p[1]*b[1]+p[2]*b[2];
  pts.push([x,y,z]);xa=Math.min(xa,x);xb=Math.max(xb,x);ya=Math.min(ya,y);yb=Math.max(yb,y)}
 const mx=(xa+xb)/2,my=(ya+yb)/2;let d=1;
 for(const[x,y,z]of pts)d=Math.max(d,z+Math.abs(x-mx)/tx,z+Math.abs(y-my)/ty);
 return{t:[0,1,2].map(k=>bb.c[k]+r[k]*mx+u[k]*my),d:d*1.01,q:q.slice(),zs}}
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

/* ---- state: what the search, the selection, hover and the filters decide.
   Recomputed when any of them changes, never per frame. */
function restate(){const anySel=sel>=0;
 for(let i=0;i<NN;i++)GH[i]=ghost(N[i])?1:0;
 const fo=anySel?sel:hov3;
 E3.forEach(([a,b],j)=>{let al=0,w=1.1,fl=0;
  if(!hid(N[a])&&!hid(N[b])){
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
 gl.bindBuffer(gl.ARRAY_BUFFER,wBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,wArr);
 nH=0;KBS.forEach(k=>{if(offKB.has(k))return;const c=KBC[k],h=hex(HUE[k]);
  hArr.set([c.cx,-c.cy,KBZ[k],c.halo*1.12,h[0],h[1],h[2]],nH*7);nH++});
 gl.bindBuffer(gl.ARRAY_BUFFER,hBuf);gl.bufferSubData(gl.ARRAY_BUFFER,0,hArr);
 BR=bounds(1)||BR;recolour(sel>=0?sel:hov3)}

function draw3(){G3.frames++;
 const key=sel+'|'+hov3+'|'+qv+'|'+[...off].join()+'|'+[...offKB].join()+'|'+RM.matches;if(key!==skey){skey=key;restate()}
 matrix();const anySel=sel>=0;
 const dc=Math.hypot(cam.t[0]+cam.d*back[0]-BR.c[0],cam.t[1]+cam.d*back[1]-BR.c[1],cam.t[2]+cam.d*back[2]-BR.c[2]);
 F0=dc-BR.r*.55;F1=dc+BR.r*1.05;
 order.length=0;const umin=3.2;
 for(let i=0;i<NN;i++){if(hid(N[i]))continue;const x=PX[i],y=PY[i],z=PZ[i]*cam.zs;
  const w=M[3]*x+M[7]*y+M[11]*z+M[15];if(w<=cam.d*.03)continue;
  SX[i]=((M[0]*x+M[4]*y+M[8]*z+M[12])/w*.5+.5)*W;SY[i]=(.5-(M[1]*x+M[5]*y+M[9]*z+M[13])/w*.5)*H;
  SW[i]=w;SRp[i]=Math.min(30,Math.max(umin,RR[i]*Math.sqrt(pxs/w)));order.push(i)}
 order.sort((a,b)=>SW[b]-SW[a]);
 order.forEach((i,k)=>{const o=k*NS,c=C3[i];nodeArr[o]=PX[i];nodeArr[o+1]=PY[i];nodeArr[o+2]=PZ[i];nodeArr[o+3]=RR[i];
  nodeArr[o+4]=c[0];nodeArr[o+5]=c[1];nodeArr[o+6]=c[2];nodeArr[o+7]=N[i].c;
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
 gl.useProgram(PE.p);gl.uniformMatrix4fv(PE.u.uM,false,M);gl.uniform2f(PE.u.uV,W,H);gl.uniform1f(PE.u.uZs,cam.zs);
 gl.uniform1f(PE.u.uF0,F0);gl.uniform1f(PE.u.uF1,F1);gl.uniform1f(PE.u.uTime,T3!==null?T3:performance.now()/1000);gl.uniform3fv(PE.u.uFg,hex(css('--fg')));gl.bindVertexArray(vaoE);gl.drawArraysInstanced(gl.TRIANGLE_STRIP,0,4,NE);
 gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
 gl.useProgram(PN.p);gl.uniformMatrix4fv(PN.u.uM,false,M);gl.uniform2f(PN.u.uV,W,H);gl.uniform1f(PN.u.uPx,pxs);
 gl.uniform1f(PN.u.uZs,cam.zs);gl.uniform1f(PN.u.uMin,umin);gl.uniform1f(PN.u.uF0,F0);gl.uniform1f(PN.u.uF1,F1);
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
 for(const k of KBS){if(offKB.has(k))continue;const c=KBC[k],x=c.cx,y=-c.cy,z=KBZ[k]*cam.zs;
  const w=M[3]*x+M[7]*y+M[11]*z+M[15];if(w<=cam.d*.03)continue;
  const sx=((M[0]*x+M[4]*y+M[8]*z+M[12])/w*.5+.5)*W,sy=(.5-(M[1]*x+M[5]*y+M[9]*z+M[13])/w*.5)*H;
  x2.globalAlpha=(anySel||qv?.25:.85)*fogAt(w);x2.lineWidth=5;x2.strokeStyle=bg;x2.strokeText(kbName(k),sx,sy);
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
 const h=pick3(mx,my);if(h!==hov3){hov3=h;need=true}g3.style.cursor=h>=0?'pointer':'grab'});
g3.addEventListener('pointerup',e=>{if(!drag3)return;const d=drag3;drag3=null;g3.style.cursor='grab';
 if(performance.now()-d.t>70)vy=vp=0;
 if(d.m<5){vy=vp=0;const[mx,my]=local(e),h=pick3(mx,my);if(h>=0){if(sel===h)clearSel();else select(h)}}});
g3.addEventListener('pointerleave',()=>{if(hov3>=0&&!drag3){hov3=-1;need=true}});
g3.addEventListener('dblclick',e=>{const[mx,my]=local(e),h=pick3(mx,my);if(h>=0){select(h);show(N[h].id)}else G3.fit()});
/* The wheel zooms toward the pointer, and does not stop when it arrives:
   closer than DMIN it flies on, carrying the orbit point ahead of it along
   the pointer's ray, through the clusters and out the other side. Owner's
   requests of 23.09.2026, "move endlessly" and "zoom endlessly". Outward the
   one bound is a million units, some three hundred times the whole map, there
   only to keep the arithmetic finite. */
const DMIN=40;
g3.addEventListener('wheel',e=>{e.preventDefault();settle();vy=vp=0;idle=performance.now();
 const[mx,my]=local(e),f=Math.exp(e.deltaY*(e.ctrlKey?.01:.0015));
 const want=Math.min(1e6,cam.d*f),nd=Math.max(DMIN,want),k=cam.d/pxs,r=nd/cam.d;
 for(let j=0;j<3;j++){const p=cam.t[j]+right[j]*(mx-W/2)*k+up[j]*(H/2-my)*k;cam.t[j]=p+(cam.t[j]-p)*r}
 cam.d=nd;
 if(want<DMIN){const ray=[0,1,2].map(j=>-back[j]+right[j]*(mx-W/2)/pxs+up[j]*(H/2-my)/pxs),l=Math.hypot(...ray),go=(DMIN-want)*3;
  for(let j=0;j<3;j++)cam.t[j]+=ray[j]/l*go}
 need=true},{passive:false});

(function loop3(now){requestAnimationFrame(loop3);if(view!=='3d')return;
 const dt=Math.min(64,now-last);last=now;let moved=false;
 if(anim){step(now);moved=true}
 if(!drag3&&(Math.abs(vy)+Math.abs(vp))>1e-6){turn(vy*dt,vp*dt);
  const k=Math.pow(.9,dt/16);vy*=k;vp*=k;if(Math.abs(vy)+Math.abs(vp)<2e-6)vy=vp=0;moved=true}
 const still=now-idle;
 if(!RM.matches&&!drag3&&!anim&&hov3<0&&still>6000){turn(dt*4e-5,0);moved=true}
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
if _git('status', '--porcelain'):
    git_id += ' · uncommitted'
page = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>00_Cerebrum — OKF viewer</title><style>
:root{color-scheme:dark;--bg:#242424;--fg:#f9f2d9;--mut:#a49a85;--line:#3a3733;--acc:#f0c755;--h3:#e5d5a1;--side:#191919;--card:#2b2b2b;--item:#bbaf96;--ph:#757575;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;--s9:#38b2c3;--s10:#9fae2f;--s11:#c08b52;--s12:#8ecae6;--s13:#b0b7c3;--s14:#7fd1ae;--s15:#cb54d6;--s16:#e0c04d;--lin:#5aa9ff;--lout:#ff9f43}
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
/* One help line per graph, bottom left, in the same words where the control
   is the same. The 2D one joined on 23.09.2026, on the owner's request, and the
   same day the Fit button went, on the owner's instruction: a double-click on
   empty space does what it did, and the line says so. `f` still fits. */
#g2hint,#g3hint{position:absolute;left:16px;bottom:18px;z-index:2;color:var(--mut);font-size:12px;letter-spacing:.02em;pointer-events:none;opacity:.8}
#g2hint b,#g3hint b{color:var(--item);font-weight:600}
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
.grp,#gcard .sec,#aboutBtn .eyebrow,#aboutBox .eyebrow,#setBox .eyebrow,.sgt,#aboutFacts dt,.aboutLogo .tl{color:var(--mut);font-size:.78em;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
.grp{margin:12px 0 2px;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;padding:2px 4px;border-radius:5px}
.grp:hover{color:var(--fg);background:var(--line)}.grp .gn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grp .cv{display:inline-block;width:9px;transition:transform .12s;font-size:.9em}.grp.shut .cv{transform:rotate(-90deg)}
.gitems{padding-left:15px;border-left:1px solid var(--line);margin-left:8px}
.grp small{font-weight:400;opacity:.75;font-size:.95em}.grp.flat{cursor:default}.grp.flat:hover{background:none;color:var(--mut)}.grp.flat .cv{visibility:hidden}
#tree .grp:first-child{margin-top:0}
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
#mAsk.busy{position:relative}
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
#legend .lrow i{font-style:normal;opacity:.7;font-size:.92em;margin-right:2px}
.chip{display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 8px 0 6px;border:1px solid var(--line);border-radius:12px;cursor:pointer;user-select:none;white-space:nowrap}
.chip:hover{background:var(--line)}
.chip.off{opacity:.32}.chip b{font-weight:600;color:var(--fg)}.chip small{color:var(--mut)}
.kbchip{border-width:2px;border-color:var(--fg)}.ldiv{width:1px;align-self:stretch;background:var(--line);margin:0 4px}
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
/* Settings, in the shape of j4k's Options menu: a panel hanging under the
   header rather than a dialog over a dimmed page, closed by its ×, by Escape or
   by a click anywhere else. The frame is About's, border, radius, background
   and shadow alike, so the two read as one family. */
#setBox{position:absolute;top:calc(100% + 8px);right:12px;z-index:40;display:grid;gap:12px;width:min(430px,calc(100vw - 24px));padding:18px;border:1px solid var(--line);border-radius:8px;background:var(--bg);box-shadow:0 24px 80px rgba(0,0,0,.55);cursor:default}
.sgrp{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
#kbN{color:var(--mut);font-size:.8em}
#setBox .hint{color:var(--mut);font-size:.82em;line-height:1.5}
/* Brain. The Settings tab of the owner's GLaDOS is the shape: the model first,
   then what it costs to run, then — because this is where the network rule
   stops being abstract — one line saying what leaves this Mac. Two selects on
   one row, the effort one greying out for a model that takes none rather than
   disappearing, so the row does not jump when the choice changes. */
/* The effort column was `auto`, so it shrank to the widest word in it and
   the model select took everything else. The owner asked for the balance
   the other way on 16.09.2026: a fixed effort column, which also stops the
   row twitching when the label changes from `low` to `medium`. */
#brain{display:grid;grid-template-columns:minmax(0,1fr) 104px;gap:6px}
#brain select{font:inherit;font-size:.95em;padding:5px 7px;border-radius:5px;
 border:1px solid var(--line);background:var(--side);color:var(--fg)}
#brain select:disabled{opacity:.42}
#brainWhere{margin:0}
#brainWhere b{color:var(--s2);font-weight:600}
/* A weights row per local model, in the shape of GLaDOS's `LocalModelRow`:
   a name over one quiet line of detail, and the action on the right. Installed
   reads as a tick, its size on disk and Delete; missing reads as where the
   bytes come from and Download with the cost in the button. The rows sit on
   the panel's own card so three of them read as a list rather than as text. */
#bWeights{display:flex;flex-direction:column;gap:1px;border:1px solid var(--line);
 border-radius:7px;overflow:hidden}
#bWeights .wr{display:flex;align-items:center;gap:10px;padding:8px 10px;
 background:var(--side)}
#bWeights .wl{flex:1;min-width:0}
#bWeights .wt{display:block;color:var(--fg);font-size:.92em}
#bWeights .wt .tick{color:var(--s3);margin-right:5px;font-weight:700}
#bWeights .ws{display:block;color:var(--mut);font-size:.8em;margin-top:1px;
 overflow-wrap:anywhere}
#bWeights .ws .no{color:var(--s2)}
#bWeights .wr button{flex:0 0 auto;font:inherit;font-size:.82em;padding:4px 10px;
 border-radius:5px;border:1px solid var(--line);background:transparent;
 color:var(--item);white-space:nowrap}
#bWeights .wr button:hover:not(:disabled){background:var(--line);color:var(--fg)}
#bWeights .wr button:disabled{opacity:.4}
/* Delete asks first, because it takes an instant and costs the whole download
   to undo — GLaDOS puts the way out before the action rather than during it.
   The confirmation replaces the row's own detail line, so the cost of saying
   yes is read in the place the row was just describing. */
#bWeights .wr.arm{background:var(--card)}
#bWeights .wr.arm .ws{color:var(--s2)}
#bWeights .wr button.del:hover:not(:disabled){border-color:var(--s2);color:var(--s2);
 background:transparent}
#bWeights .pb{height:3px;border-radius:2px;background:var(--line);overflow:hidden;
 margin-top:5px}
#bWeights .pb i{display:block;height:100%;width:0;background:#c8901d;
 transition:width .3s ease-out}
#kbbar{display:flex;flex-direction:column;gap:6px}#kbbar .krow{display:flex;gap:6px}#kbbar .krow button{flex:1;padding:6px;white-space:nowrap;min-width:0}#kbbar button.on{background:var(--acc);color:var(--bg);border-color:var(--acc)}/* fallback for a KB no block names; the three known blocks override inline */#kbbar button small{opacity:.7;margin-left:5px;font-size:.85em;color:inherit}#kbbar button[aria-disabled="true"]{cursor:not-allowed}
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
#aboutWrap{position:fixed;inset:0;z-index:60;display:none;place-items:center;padding:18px;background:rgba(10,9,7,.58)}
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
#aboutWrap.on{display:grid}
#aboutBox{display:grid;gap:14px;width:min(460px,100%);max-height:min(830px,calc(100vh - 36px));overflow:auto;border:1px solid var(--line);border-radius:8px;background:var(--bg);padding:18px;box-shadow:0 24px 80px rgba(0,0,0,.55)}
#aboutBox header,#setBox header,#repBox header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-bottom:12px}
#aboutBox h2,#aboutBox p,#setBox h2,#setBox p,#repBox h2,#repBox p{margin:0}
#aboutBox h2,#setBox h2,#repBox h2{font-size:1.35em;color:var(--fg);font-weight:700;border:none;padding:0;margin:0}
#aboutBox .x,#setBox .x,#repBox .x{background:none;border:none;color:var(--mut);cursor:pointer;font-size:1.1em;line-height:1;padding:0 6px;border-radius:5px}
#aboutBox .x:hover,#setBox .x:hover,#repBox .x:hover{color:var(--fg);background:var(--line)}
#aboutContent{display:grid;gap:10px;justify-items:center;text-align:center}
.aboutLogo{display:grid;justify-items:center;gap:7px;margin-top:4px}
.aboutLogo svg{width:145px;height:126px;display:block}
/* The light that runs along the mark's strands in About: a bead a twenty-fifth
   of a strand long, out and fading, one strand after another. Never in the
   header, and never for a reader who has asked for less motion. */
.aboutLogo .pulse path{fill:none;stroke:var(--fg);stroke-width:26;stroke-linecap:round;stroke-dasharray:4 96;stroke-dashoffset:4;opacity:0;animation:markpulse 6.4s ease-in-out var(--d) infinite}
@keyframes markpulse{0%{stroke-dashoffset:4;opacity:0}6%{opacity:.8}48%{stroke-dashoffset:-96;opacity:.8}54%,100%{stroke-dashoffset:-96;opacity:0}}
@media (prefers-reduced-motion:reduce){.aboutLogo .pulse{display:none}}
.aboutLogo .wm{font-size:1.35em;font-weight:700;color:var(--acc);line-height:1}
#aboutBox .story{max-width:42ch;color:var(--item);font-size:.92em}
#aboutFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 14px;width:100%;margin:4px 0 0;text-align:left}
#aboutFacts>div{display:grid;gap:2px;min-width:0;border:1px solid var(--line);border-radius:6px;padding:6px 9px;background:var(--card)}
#aboutFacts dd{margin:0;color:var(--fg);font-size:.9em;font-weight:600;overflow-wrap:anywhere}
#aboutBox .built{max-width:42ch;color:var(--mut);font-size:.82em}
#aboutActions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;width:100%}
/* the dialog's controls follow the same grammar as the header's, which is the
   concept row's — its close button matches the search box's clear button, the
   same control one layer down. */
#aboutActions button{background:transparent;border:1px solid transparent;border-radius:5px;color:var(--item);font-size:.95em}
#aboutActions button:hover{background:var(--line);color:var(--fg)}
</style></head><body class="vg">
<header id="top">
<button id="aboutBtn" title="What this vault is, and the facts to quote when something looks wrong">__LOGO__<span class="tx"><span class="eyebrow">About</span><span class="wm">00_Cerebrum</span></span></button>
<div id="legend" role="group" aria-label="Categories"></div>
<div id="tools"><div id="views" role="group" aria-label="View"><button id="bGraph" class="ib on" title="Graph view: the whole vault as one map" aria-label="Graph view" aria-pressed="true">__IGRAPH__</button><button id="b3d" class="ib" title="3D view: the same map with depth. Drag to turn it" aria-label="3D view" aria-pressed="false">__I3D__</button><button id="bList" class="ib" title="Concept view: the list of concepts, and the concept page beside it" aria-label="Concept view" aria-pressed="false">__ICONCEPTS__</button></div><button id="bSet" class="ib" title="Settings" aria-label="Settings" aria-haspopup="dialog" aria-expanded="false">__IGEAR__</button></div>
<div id="setBox" role="dialog" aria-label="Settings" hidden>
<header><div><p class="eyebrow">Settings</p><h2>00_Cerebrum</h2></div><button class="x" id="setX" title="Close settings (Esc)">&#215;</button></header>
<div class="sgrp"><span class="sgt">Brain</span><span id="brainN"></span></div>
<div id="brain"><select id="bModel" aria-label="Which model answers"></select><select id="bEffort" aria-label="Effort level"></select></div>
<p class="hint" id="brainWhere"></p>
<div id="bWeights"></div>
<p class="hint" id="brainDisk"></p>
<div class="sgrp"><span class="sgt">Knowledge bases</span><span id="kbN"></span></div>
<div id="kbbar"></div>
<p class="hint">A hidden knowledge base leaves the graph, the concept list and the category counts. The choice is kept for the next visit.</p>
</div>
</header>
<div id="askbar"><div id="qwrap"><button id="mSearch" class="mb on" type="button" title="Search the vault" aria-label="Search the vault" aria-pressed="true">__ISEARCH__</button><button id="mAsk" class="mb" type="button" title="Ask Claude for a report instead of searching" aria-label="Ask Claude" aria-pressed="false">__ISPARK__</button><div id="qbar" hidden><i></i></div><input id="q" placeholder="Search title, description, tags…" aria-label="Search concepts"><button id="qx" type="button" title="Clear the search" aria-label="Clear the search">×</button><button id="bRep" class="mb" type="button" title="The reports in Outputs/" aria-label="Reports" aria-haspopup="dialog" aria-expanded="false">__IREPORTS__</button></div></div>
<div id="stage">
<div id="gpane"><canvas id="gc"></canvas><div id="g2hint"><b>Drag</b> to move · <b>Scroll</b> to zoom · <b>Click</b> to select · <b>Double-click</b> to open · <b>Double-click empty space</b> to fit</div></div>
<div id="g3pane"><canvas id="g3"></canvas><canvas id="g3lbl"></canvas><div id="g3hint"><b>Drag</b> to turn · <b>Shift-drag</b> to move · <b>Scroll</b> to zoom · <b>Click</b> to select · <b>Double-click</b> to open · <b>Double-click empty space</b> to fit</div></div>
<div id="gcard"></div>
<div id="cpane"><div id="side"><div id="sidetop"><button id="ball" title="Fold or unfold every group in the list">Collapse all</button></div><div id="tree"></div></div><div id="splitter" title="drag to resize"></div><div id="main"><div class="doc"><div class="meta">Pick a concept, or search. Dashed links point at concepts not written yet — legitimate under OKF.</div></div></div></div>
</div>
<div id="repWrap"><div id="repBox">
<header><div><p class="eyebrow">Outputs</p><h2>Reports</h2></div><button class="x" id="repX" title="Close reports (Esc)">&#215;</button></header>
<div id="repList"></div>
<p class="hint" id="repHint"></p>
</div></div>
<div id="aboutWrap"><div id="aboutBox">
<header><div><p class="eyebrow">About</p><h2>00_Cerebrum</h2></div><button class="x" id="aboutX" title="Close about">&#215;</button></header>
<div id="aboutContent">
<div class="aboutLogo">__LOGO__
<div class="wm">00_Cerebrum</div><div class="tl">Open Knowledge Format</div>
</div>
<p class="story">A knowledge base that reads its own sources and cites every claim back to the page it came from, and the machinery that keeps it honest. <i>Cerebrum</i> is the Latin for brain. Built by your-account with Claude Code.</p>
<dl id="aboutFacts"></dl>
<p class="built">Markdown and YAML in an Obsidian vault, Open Knowledge Format v0.2 for the bundles, Python for the checks, GitHub for the code.</p>
<div id="aboutActions"><button id="aboutGraph">Graph</button><button id="about3d">3D</button><button id="aboutList">Concepts</button></div>
</div></div></div>
<script>const D=__DATA__;const GIT='__GIT__';const STAMP='__STAMP__';const BUILDNO='__BUILDNO__';const STARTED='__STARTED__';
/* One pinned order for the whole viewer: the knowledge-base buttons two per
   row (Alpha and Beta, then Gamma and Zeta) and the sidebar groups in the
   same sequence. Pinned rather than sorted so a rename cannot reshuffle
   either, and so the two never disagree. Anything not listed sorts after. */
/* The blocks are the vault's real structure — the three employer archives,
   the two Alpha documentation bundles, the private base — and they are the one
   source of the ordering. The selector in Settings draws them 3 / 2 / 1 across
   its width, each block symmetric on its own line, and the concept tree reads
   them flat in the same sequence. A knowledge base no block names lands in a
   fourth selector row and sorts last in the tree.

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
var collapsed=new Set(),curGroups=[],cur=null;
try{collapsed=new Set(JSON.parse(localStorage.getItem('okf.collapsed')||'[]'))}catch(e){}
function saveFold(){try{localStorage.setItem('okf.collapsed',JSON.stringify([...collapsed]))}catch(e){}}
function markSel(){if(!cur)return;document.querySelectorAll('.it').forEach(e=>e.classList.toggle('on',e.dataset.t===cur))}
function build(filter){tree.innerHTML='';const gs=new Map();
Object.keys(D).sort((a,b)=>{const ra=kbRank(a),rb=kbRank(b);if(ra!==rb)return ra-rb;
const ga=group(a),gb=group(b);return ga===gb?D[a].t.localeCompare(D[b].t):ga.localeCompare(gb)}).forEach(id=>{const c=D[id];if(offKB.has(c.kb)||off.has(CATS.indexOf(cat(id))))return;
if(filter){const hay=(c.t+' '+c.d+' '+c.tags.join(' ')+' '+id).toLowerCase();if(!hay.includes(filter))return}
const g=group(id);if(!gs.has(g))gs.set(g,[]);gs.get(g).push(id)});
curGroups=[...gs.keys()];
gs.forEach((ids,g)=>{const open=!!filter||!collapsed.has(g);
const h=document.createElement('div');h.className='grp'+(open?'':' shut')+(filter?' flat':'');
const cv=document.createElement('span');cv.className='cv';cv.textContent='▾';h.appendChild(cv);
const gn=document.createElement('span');gn.className='gn';gn.textContent=g;h.appendChild(gn);
const ct=document.createElement('small');ct.textContent=ids.length;h.appendChild(ct);
h.title=filter?'showing search results':(open?'click to fold this group':'click to unfold this group');
const box=document.createElement('div');box.className='gitems';if(!open)box.style.display='none';
ids.forEach(id=>{const c=D[id];const e=document.createElement('a');e.className='it';e.dataset.t=id;e.textContent=c.t;e.title=c.d;e.onclick=()=>show(id);box.appendChild(e)});
if(!filter)h.onclick=()=>{collapsed.has(g)?collapsed.delete(g):collapsed.add(g);saveFold();build(q.value.toLowerCase())};
tree.appendChild(h);tree.appendChild(box)});
const anyOpen=curGroups.some(g=>!collapsed.has(g));
ball.innerHTML='<span class="qi" aria-hidden="true">'+(anyOpen?'__ICOLLAPSE__':'__IEXPAND__')+'</span>'+(anyOpen?'Collapse all':'Expand all');ball.disabled=!!filter||!curGroups.length;
ball.title=filter?'the list is showing search results':'Fold or unfold every group in the list';
markSel()}
ball.onclick=()=>{const anyOpen=curGroups.some(g=>!collapsed.has(g));
curGroups.forEach(g=>anyOpen?collapsed.add(g):collapsed.delete(g));saveFold();build(q.value.toLowerCase())};
function E(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function chip(txt,cls){return '<span class="badge '+(cls||'')+'">'+E(txt)+'</span>'}
/* Opening a concept is what the Concept view is for, so it switches there from
   wherever it was asked: the list, a link in a page, the graph card. */
function show(id){const c=D[id];if(!c)return;cur=id;setView('concepts');
/* A concept reached from a body link may sit in a folded group; leaving it
   folded loses the highlight and the reader's place in the tree. */
if(!q.value&&collapsed.has(group(id))){collapsed.delete(group(id));saveFold();build('')}
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
 if(L&&L.state==='expired')warn=' — the Claude Code login expired on '+L.when+', run: claude auth login';
 else if(L&&L.state==='soon')warn=' — the Claude Code login expires in '+L.days+' day(s), on '+L.when;
 mAsk.title=off?'Ask Claude — open the vault with "Open 00_Cerebrum.command" to use this'
  :('Ask Claude for a report instead of searching ('+helper.model+', '+helper.effort+' effort)'+(warn||''));
 mAsk.classList.toggle('warn',!!warn);
 bRep.title=off?'Reports — open the vault with "Open 00_Cerebrum.command" to use this'
  :('The reports in Outputs/ ('+helper.reports+')');
 if(off&&askMode)setMode(false);
 return helper}

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

/* ---- Brain: which model answers, and at what effort ----------------------
   The page holds the choice and sends it with every request; the helper keeps
   the allowlist and refuses anything it does not name, because an id reaches a
   command line and names a folder on disk. Two stores, because the two answer
   different questions and a model that takes no effort must not lose the level
   the last one used. Both survive a reload, like the knowledge-base toggles. */
const brainEl=document.getElementById('brain'),bModel=document.getElementById('bModel'),
 bEffort=document.getElementById('bEffort'),bWeights=document.getElementById('bWeights'),
 brainWhere=document.getElementById('brainWhere'),brainN=document.getElementById('brainN'),
 brainDisk=document.getElementById('brainDisk');
let MODELS=[],EFFORTS=[],picked=null,pickedEffort=null;
function loadPick(){try{picked=localStorage.getItem('okf.model')||null;
  pickedEffort=localStorage.getItem('okf.effort')||null}catch(e){}}
function savePick(){try{if(picked)localStorage.setItem('okf.model',picked);
  if(pickedEffort)localStorage.setItem('okf.effort',pickedEffort)}catch(e){}}
loadPick();
/* What every request carries. A model the helper has since stopped naming —
   a registry edited between two visits — falls back to its default rather than
   being sent and refused. */
function brainBody(){const m=MODELS.find(x=>x.id===picked);
 return m?{model:m.id,effort:pickedEffort||undefined}:{}}
function curModel(){return MODELS.find(x=>x.id===picked)||MODELS[0]||null}

async function loadBrain(){
 if(!helper){brainEl.hidden=true;bWeights.innerHTML='';
  brainWhere.textContent='Start the helper to choose a model.';
  brainN.textContent='';return}
 brainEl.hidden=false;
 let d=null;try{d=await (await fetch(HELPER+'/models',{cache:'no-store'})).json()}
 catch(e){brainWhere.textContent='the helper answered nothing';return}
 MODELS=d.models||[];EFFORTS=d.efforts||[];
 /* A stored model the helper no longer names takes the default effort with it:
    the effort was chosen for the model that has gone. */
 if(!MODELS.some(m=>m.id===picked)){picked=d.default;pickedEffort=d.defaultEffort}
 if(EFFORTS.indexOf(pickedEffort)<0)pickedEffort=d.defaultEffort;
 bModel.innerHTML=MODELS.map(m=>'<option value="'+E(m.id)+'"'+
   (m.id===picked?' selected':'')+(m.installed?'':' disabled')+'>'+E(m.label)+
   (m.installed?'':' — not installed')+'</option>').join('');
 bEffort.innerHTML=EFFORTS.map(x=>'<option value="'+E(x)+'"'+
   (x===pickedEffort?' selected':'')+'>'+E(x)+'</option>').join('');
 paintBrain(d)}

/* The line that says what leaves this Mac, and the one warning worth carrying
   into the window: a local model is a completion and Ask Claude is an agent, so
   picking one here means the Ask button will say so rather than run. */
function paintBrain(d){const m=curModel();if(!m)return;
 bEffort.disabled=!m.effort;
 bEffort.title=m.effort?'How hard the model thinks':m.label+' takes no effort level';
 brainN.textContent=m.label;
 brainWhere.innerHTML=(m.provider==='local'
   ? 'Runs here. <b>Nothing leaves this Mac.</b> Translates only; Ask needs a Claude model.'
   : 'Reads the vault at Anthropic.')+' '+E(m.note||'');
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

/* One row, in GLaDOS's two-line shape: the name, one quiet line of detail, and
   the action on the right. */
function row(x){
 const gb=n=>(n/1e9).toFixed(1)+' GB';
 const on=x.installed;
 return '<div class="wr" data-m="'+E(x.id)+'" data-gb="'+E(gb(x.bytes||0))+
   '" data-disk="'+E(gb(x.onDisk||0))+'">'+
  '<span class="wl"><span class="wt">'+(on?'<span class="tick">&#10003;</span>':'')+
    /* Every row here is local, so the label's own "(local)" says nothing.
       It stays in the dropdown, where Claude models sit beside these. */
    E(x.label.replace(' (local)',''))+'</span><span class="ws">'+
    (on?gb(x.onDisk||0)+' on disk'
      :'One-time download from Hugging Face'+(x.fits?''
        :' &middot; <span class="no">not enough free disk</span>'))+
  '</span></span>'+
  (on?'<button type="button" class="del">Delete</button>'
     :'<button type="button" class="get"'+(x.fits?'':' disabled')+'>Download '+
       gb(x.bytes||0)+'</button>')+
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

bModel.onchange=()=>{picked=bModel.value;savePick();paintBrain({free:0,dir:'',mlx:true});loadBrain()};
bEffort.onchange=()=>{pickedEffort=bEffort.value;savePick()};

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
if(t)G3.enter();
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
blocks.forEach(block=>{if(!block.kbs.length)return;
const row=document.createElement('div');row.className='krow';
block.kbs.forEach(kb=>{const on=!offKB.has(kb);
/* The last knowledge base showing stays on. Hiding it would leave both
   views empty, which is the dead page the stored choice is guarded against. */
const last=on&&offKB.size===KB_ALL.length-1;
const s=document.createElement('button');s.className=on?'on':'';
if(block.hue){if(!on){s.style.borderColor=block.hue+'66';s.style.color=block.hue}
else{s.style.background=block.hue;s.style.borderColor=block.hue;s.style.color='var(--bg)'}}
s.textContent=kbName(kb);
const sm=document.createElement('small');sm.textContent=Object.values(D).filter(c=>c.kb===kb).length;s.appendChild(sm);
s.title=last?'the last knowledge base showing stays on':'show / hide this knowledge base — graph, list and counts alike';
if(last)s.setAttribute('aria-disabled','true');
s.onclick=()=>{if(last)return;on?offKB.add(kb):offKB.delete(kb);saveKb();kbbar();kbBadge();chips();build(q.value.toLowerCase());if(sel>=0&&hid(N[sel]))clearSel();dirty=true};
row.appendChild(s)});
kbbarEl.appendChild(row)})}
/* One legend row per block, counting that block's own concepts. The counts
   follow what is showing: with a knowledge base hidden in Settings its
   concepts leave the counts, and a row with nothing left in it leaves the
   header, so no chip offers a filter that would change nothing. */
function chips(){legend.innerHTML='';
KB_BLOCKS.forEach(blk=>{
const inBlk=new Set(blk.kbs);
const cnt=CATS.map(()=>0);N.forEach(n=>{if(inBlk.has(n.kb)&&!offKB.has(n.kb))cnt[n.c]++});
const row=document.createElement('div');row.className='lrow';
/* the accent bar alone names the block — a text tag repeated the sidebar
   and pushed each row's chips right by a different width, so the category
   columns never aligned. Owner's instruction of 01.09.2026. */
row.style.borderLeft='3px solid '+blk.hue;row.style.paddingLeft='8px';
let any=false;
for(let i=0;i<CATS.length;i++){const c=CATS[i];if(!cnt[i])continue;any=true;
const s=document.createElement('span');s.className='chip'+(off.has(i)?' off':'');
/* drawn at the screen's pixel density: a 16px bitmap blurs on a Retina display,
   and the header is where every category mark is seen first */
const cv=document.createElement('canvas');cv.width=cv.height=Math.round(16*dpr);cv.style.width=cv.style.height='16px';const x2=cv.getContext('2d');
x2.scale(dpr,dpr);x2.translate(8,8);x2.fillStyle=COL[i];shp(x2,5.5,i);x2.fill();
s.appendChild(cv);const bb=document.createElement('b');bb.textContent=LBL[c]||c;s.appendChild(bb);
const sm=document.createElement('small');sm.textContent=cnt[i];s.appendChild(sm);
s.title='click to hide / show this category — graph and list alike';
s.onclick=()=>{off.has(i)?off.delete(i):off.add(i);if(sel>=0&&hid(N[sel]))clearSel();chips();build(q.value.toLowerCase());dirty=true};
row.appendChild(s)}
if(any)legend.appendChild(row)})}
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
else{const m=s==='pentagon'?5:s==='hexagon'?6:10;for(let j=0;j<m;j++){const rr=s==='star'?(j%2?r*.5:r*1.15):r*1.05;
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
for(const n of N){if(hid(n))continue;any=true;x0=Math.min(x0,n.x);y0=Math.min(y0,n.y);x1=Math.max(x1,n.x);y1=Math.max(y1,n.y)}
if(!any)return;
const w=gc.clientWidth-2*FIT_SIDE,h=gc.clientHeight-FIT_TOP-FIT_BOTTOM;
sc=Math.max(.08,Math.min(2.2,Math.min(w/Math.max(x1-x0,1),h/Math.max(y1-y0,1))));
tx=-(x0+x1)/2;ty=(FIT_TOP-FIT_BOTTOM)/(2*sc)-(y0+y1)/2;dirty=true}
function centerOn(i){if(view==='3d'){G3.focus(i);return}const n=N[i];sc=Math.max(sc,1.5);tx=-n.x;ty=-n.y;dirty=true}
function world(e){const b=gc.getBoundingClientRect();
return[((e.clientX-b.left)-gc.clientWidth/2)/sc-tx,((e.clientY-b.top)-gc.clientHeight/2)/sc-ty]}
function pick(wx,wy){let best=-1,bd=1e18;
for(const n of N){if(hid(n))continue;const rr=rEff(n)+5/sc;const d=(n.x-wx)**2+(n.y-wy)**2;
if(d<rr*rr&&d<bd){bd=d;best=n.i}}return best}
function select(i){sel=i;renderCard();dirty=true}
function clearSel(){sel=-1;card.style.display='none';dirty=true}
function renderCard(){if(sel<0){card.style.display='none';return}
const id=N[sel].id,c=D[id];let h='<div class="cs"><div class="hd"><h3>'+E(c.t)+'</h3><button class="ib open" title="Open concept" aria-label="Open concept">__ICONCEPTS__</button><button class="ib x" title="Close (Esc)" aria-label="Close">&#215;</button></div>';
h+='<div>'+'<span class="badge">'+E(c.ty)+'</span><span class="badge">'+E(LBL[cat(id)]||cat(id))+'</span><span class="badge">'+c.ns+' sources</span></div>';
if(c.d)h+='<div class="desc">'+E(c.d)+'</div>';h+='</div>';
const nb=[...NB[sel]];
const inb=nb.filter(j=>D[N[j].id].out.includes(id)||c.inb.includes(N[j].id));
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
if(pan){tx+=(e.clientX-pan[0])/sc;ty+=(e.clientY-pan[1])/sc;pan=[e.clientX,e.clientY];dirty=true;return}
const h=pick(wx,wy);if(h!==hov){hov=h;dirty=true}
gc.style.cursor=hov>=0?'pointer':'grab'});
gc.addEventListener('mousedown',e=>{const[wx,wy]=world(e);const h=pick(wx,wy);
if(h>=0){drag=N[h];drag._m=0}else pan=[e.clientX,e.clientY]});
addEventListener('mouseup',()=>{if(drag&&(drag._m||0)<6){if(sel===drag.i)clearSel();else select(drag.i)}drag=null;pan=null});
gc.addEventListener('dblclick',e=>{const[wx,wy]=world(e);const h=pick(wx,wy);
if(h>=0){select(h);show(N[h].id)}else fit()});
gc.addEventListener('wheel',e=>{e.preventDefault();const b=gc.getBoundingClientRect();const[wx,wy]=world(e);
/* Zoom has no working limit: the owner asked for endless zoom on
   23.09.2026. The bounds left are there only to keep the arithmetic finite,
   1/500 of the fitted scale out to 500 times in. */
const ns=Math.max(.002,Math.min(500,sc*Math.exp(-e.deltaY*.0015)));
tx=(e.clientX-b.left-gc.clientWidth/2)/ns-wx;ty=(e.clientY-b.top-gc.clientHeight/2)/ns-wy;sc=ns;dirty=true},{passive:false});
/* In Ask mode the box is a question, not a filter: typing one must not empty
   the list behind it, and clearing it must not leave the list filtered by half
   a question. `askMode` is the switch; the filter is fed the empty string. */
q.oninput=()=>{const f=askMode?'':q.value.toLowerCase();build(f);qv=f;dirty=true};
q.addEventListener('keydown',e=>{if(e.key==='Enter'&&askMode){e.preventDefault();ask()}});
function sxy(n){return[(n.x+tx)*sc+gc.clientWidth/2,(n.y+ty)*sc+gc.clientHeight/2]}
function draw(){const x2=gc.getContext('2d');x2.setTransform(dpr,0,0,dpr,0,0);
x2.clearRect(0,0,gc.clientWidth,gc.clientHeight);
x2.save();x2.translate(gc.clientWidth/2,gc.clientHeight/2);x2.scale(sc,sc);x2.translate(tx,ty);
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
x2.save();x2.translate(n.x,n.y);x2.globalAlpha=g?.13:1;
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
x2.lineWidth=fs*.14;x2.strokeStyle=css('--bg');x2.strokeText(kbName(kb),c.cx,c.cy);
x2.fillStyle=HUE[kb];x2.fillText(kbName(kb),c.cx,c.cy);
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
const aboutWrap=document.getElementById('aboutWrap');
const REPO='';   /* your repository URL, or '' to hide the link */
function fact(dlEl,k,v,ttl,href){const w=document.createElement('div');
const dt=document.createElement('dt');dt.textContent=k;
const dd=document.createElement('dd');
if(href){const a=document.createElement('a');a.href=href;a.target='_blank';a.rel='noopener';
 a.className='nav';a.textContent=v;dd.appendChild(a);}else{dd.textContent=v;}
if(ttl)w.title=ttl;
w.appendChild(dt);w.appendChild(dd);dlEl.appendChild(w)}
function aboutFill(){
 const cs=Object.values(D),f=document.getElementById('aboutFacts');f.innerHTML='';
 // The four build facts lead, as they do in j4k's About: what this page is,
 // before what the corpus in it holds.
 fact(f,'Build code',GIT,'The commit this page was generated from. ’uncommitted’ means the vault held edits that were in no commit when it ran, so the page matches no commit exactly and there is nothing to link to. Set REPO above to link the hash to your own repository.',
  REPO&&/^[0-9a-f]{7,40}$/.test(GIT)?REPO+'/commit/'+GIT:null);
 fact(f,'Build number',BUILDNO,'Commits on main when this page was generated');
 fact(f,'Build date',STAMP,'When _scripts/visualize.py last ran, in this machine’s timezone');
 fact(f,'Started',STARTED,'The vault’s first commit, and which day of building this is');
 fact(f,'Concepts',cs.length+' in '+new Set(cs.map(c=>c.kb)).size+' bases');
 fact(f,'Citations',cs.reduce((a,c)=>a+(c.ns||0),0));
 fact(f,'Inbound links',cs.reduce((a,c)=>a+(c.inb||[]).length,0),'Concept-to-concept links across the whole vault, counted where they land. A bundle that is a list rather than a graph shows up here before it shows up anywhere else.');
 fact(f,'No inbound links',cs.filter(c=>!(c.inb||[]).length).length,'Nothing else in the vault points at these');
}
function aboutOpen(){aboutFill();aboutWrap.classList.add('on')}
function aboutClose(){aboutWrap.classList.remove('on')}
document.getElementById('aboutBtn').onclick=aboutOpen;
document.getElementById('aboutX').onclick=aboutClose;
aboutWrap.onclick=e=>{if(e.target===aboutWrap)aboutClose()};
document.getElementById('aboutList').onclick=()=>{aboutClose();bL.click()};
document.getElementById('aboutGraph').onclick=()=>{aboutClose();bG.click()};
document.getElementById('about3d').onclick=()=>{aboutClose();if(!b3.disabled)b3.click()};
/* Settings. Opened from the gear, closed by its ×, by Escape, or by a press
   anywhere outside it — j4k's house rule for its menus, and on pointerdown in
   the capture phase for j4k's reason: a press that lands on another control
   must close the panel before that control acts. */
const setBox=document.getElementById('setBox'),bSet=document.getElementById('bSet');
function setOpen(){setBox.hidden=false;bSet.classList.add('on');bSet.setAttribute('aria-expanded','true')}
function setClose(){setBox.hidden=true;bSet.classList.remove('on');bSet.setAttribute('aria-expanded','false')}
bSet.onclick=async()=>{if(setBox.hidden){setOpen();await pingHelper();loadBrain()}else setClose()};
document.getElementById('setX').onclick=setClose;
document.addEventListener('pointerdown',e=>{if(setBox.hidden||setBox.contains(e.target)||bSet.contains(e.target))return;setClose()},true);
function kbBadge(){const n=offKB.size;let d=bSet.querySelector('.dot');
if(n){if(!d){d=document.createElement('span');d.className='dot';bSet.appendChild(d)}d.textContent=n}
else if(d)d.remove();
bSet.title=n?'Settings · '+n+(n>1?' knowledge bases':' knowledge base')+' hidden':'Settings';
document.getElementById('kbN').textContent=(KB_ALL.length-n)+' of '+KB_ALL.length+' showing'}
/* One keyboard handler for the page. Escape closes the nearest thing open —
   About, then Settings, then the graph card — and then lets go of any button
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
else if(aboutWrap.classList.contains('on'))aboutClose();
else if(!setBox.hidden)setClose();
else if(view==='graph'||view==='3d')clearSel();
const a=document.activeElement;if(a&&a.tagName==='BUTTON')a.blur();
return}
const t=e.target;if(e.metaKey||e.ctrlKey||e.altKey||(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA')))return;
if(e.key==='f'||e.key==='F'){if(view==='graph')fit();else if(view==='3d')G3.fit()}});
__G3__
/* The page opens on the graph: the Graph view is the first of the two, and a
   working selection like the view is not kept between visits. */
build('');kbbar();kbBadge();chips();setView('graph');
</script></body></html>"""
page = (page.replace('__G3__', G3_JS).replace('__I3D__', icon_3d).replace('__LOGO__', _mark('h'), 1).replace('__LOGO__', _mark('a', pulse=True), 1)
        .replace('__KB_BLOCKS__', json.dumps(KB_BLOCKS, ensure_ascii=False)).replace('__GIT__', git_id)
        .replace('__IGRAPH__', icon_graph).replace('__ICONCEPTS__', icon_concepts)
        .replace('__IGEAR__', icon_gear).replace('__ISEARCH__', icon_search)
        .replace('__ICOLLAPSE__', icon_collapse).replace('__IEXPAND__', icon_expand)
        .replace('__ISPARK__', icon_spark).replace('__IREPORTS__', icon_reports)
        .replace('__HALO__', json.dumps(halos))
        .replace('__BUILDNO__', build_no).replace('__STARTED__', started)).replace('__STAMP__', stamp).replace('__DATA__', json.dumps(data, ensure_ascii=False))
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
