#!/usr/bin/env python3
"""Generates okf-viewer.html — a static, self-contained browser for the
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
# "Beta Technology & IT" would render as "Beta Technologie &amp; IT".
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
# An earlier version packed connected components on a spiral, which put the
# largest component at the origin and everything else wherever it fitted. Once
# a vault holds several knowledge bases that stops saying anything: cross-KB
# links fuse them into one component and the spiral draws one blob.
#
# So each knowledge base gets its own corner, and the arrangement is the place
# to put meaning the force simulation cannot invent. The default below spaces
# the corners evenly, which asserts nothing; replace it with a hand-placed
# ANCHOR once your vault has a shape worth stating.
#
# Each group is laid out on its own intra-group edges, so a bundle's shape is
# its own structure rather than a compromise with its neighbours. Nodes
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
             'pip 23.0+, and the macOS Command Line Tools pip predates\n'
             'it and fails with "no such option". Learned 15.08.2026.')

_ids = list(data)
_ix = {c: i for i, c in enumerate(_ids)}
_edges = sorted({(_ix[a], _ix[b]) for a in _ids for b in data[a]['out'] if b in _ix and _ix[a] != _ix[b]})
_n = len(_ids)
_deg = [0] * _n
for a, b in _edges: _deg[a] += 1; _deg[b] += 1

# Concepts that belong to no single knowledge base and should sit in the
# middle of the picture rather than inside one group. Empty by default: fill
# it with concept ids (`<KB>/Wiki/<group>/<name>.md`) if your vault has
# concepts that genuinely span several bundles.
CENTRE = set()

# Every knowledge base gets a corner, spaced evenly on a unit circle and
# ordered by name so the picture does not shuffle between runs. The owner's
# own vault replaced this with a hand-placed arrangement carrying meaning the
# simulation cannot invent; do the same once your vault has a shape worth
# saying something about, and keep the centroid at the origin so `_centre`
# lands in the actual middle.
ANCHOR = {'_centre': (0.0, 0.0)}          # filled in below, once the groups are known
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
_corners = sorted(k for k in _groups if k != '_centre')
for _i, _k in enumerate(_corners):
    _a = 2 * math.pi * _i / len(_corners) - math.pi / 2
    ANCHOR[_k] = (0.0, 0.0) if len(_corners) == 1 else (math.cos(_a), math.sin(_a))

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
        # makes a small bundle read as scattered rather than as one thing.
        disp -= P * (0.03 + 0.22 / math.sqrt(m))
        ln = np.sqrt((disp ** 2).sum(-1)) + 1e-6
        P += (disp / ln[:, None]) * np.minimum(ln, tmp)[:, None]
    P -= P.mean(0)
    Rt = 26.0 * m ** 0.55 if m > 1 else 26.0

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
    # had 47 unlinked concepts in 345, more than a tenth, so the 90th
    # percentile of *all* radii landed out among them: Rc came back 647 against
    # a connected body whose median radius was 47, the scale factor was ~1, and
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
# middle of the picture. Empty by default; fill PIN_INWARD below to place a
# concept near the centre without taking the centre itself.
#
# This is deliberately not the same thing as CENTRE. A pinned concept keeps
# its knowledge base, its colour and its place in that group's sidebar; only
# its position is overridden. So it reads as "this bundle, nearest the
# middle" rather than as "belongs to no corner", which is what the origin
# means.
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

_pos = {}
for g, members in _groups.items():
    P, Rt, _e, sub = _lay[g]
    cx, cy = ANCHOR[g][0] * _T, ANCHOR[g][1] * _T
    for i in members:
        _pos[i] = (float(P[sub[i], 0]) + cx, float(P[sub[i], 1]) + cy)

# Centre the picture on the origin the anchors are built around, not on the
# mean of every node: the mean is dragged around by whichever knowledge base
# grew last, so the middle would move every time one bundle outgrew another.
_mx = _my = 0.0
for i, c in enumerate(_ids):
    x, y = _pos[i]
    data[c]['x'] = round(x - _mx, 1); data[c]['y'] = round(y - _my, 1)
    data[c]['deg'] = _deg[i]

print('graph layout: ' + ', '.join('%s %d (r=%d, extent=%d)' % (g, len(m), _lay[g][1], _ext[g])
                                   for g, m in sorted(_groups.items())), file=sys.stderr)

ncit = sum(len([s for s in (c['fm'].get('sources') or []) if isinstance(s, dict) and s.get('resource')]) for c in concepts.values())
stamp = datetime.datetime.now().strftime('%d.%m.%Y, %H:%M')

# The mark, defined once and placed twice — the sidebar brand and the About
# dialog — because two copies of one drawing is the fault this vault keeps
# finding in its own generated files. Size is the caller's, set in CSS.
#
# Generic by design: three groups on a circle around a centre, which is what
# the layout above computes for a vault that has not been given an
# arrangement of its own. Colours are the same palette tokens the legend and
# the graph use, so the mark cannot drift away from what the page draws.
logo_svg = '''<svg viewBox="0 0 128 128" role="img" aria-label="">
<g stroke="var(--rule)" stroke-width="2" fill="none">
<line x1="64" y1="64" x2="64" y2="26"/><line x1="64" y1="64" x2="97" y2="83"/>
<line x1="64" y1="64" x2="31" y2="83"/>
</g>
<g fill="var(--s1)"><circle cx="64" cy="26" r="11"/></g>
<g fill="var(--s2)"><circle cx="97" cy="83" r="11"/></g>
<g fill="var(--s3)"><circle cx="31" cy="83" r="11"/></g>
<g fill="var(--acc)"><circle cx="64" cy="64" r="7"/></g>
</svg>'''

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
:root{color-scheme:dark;--bg:#242424;--fg:#f9f2d9;--mut:#a49a85;--line:#3a3733;--acc:#f0c755;--h3:#e5d5a1;--side:#191919;--card:#2b2b2b;--item:#bbaf96;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;--s9:#38b2c3;--s10:#9fae2f;--s11:#c08b52;--s12:#8ecae6;--s13:#b0b7c3;--s14:#7fd1ae;--s15:#cb54d6;--s16:#e0c04d}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--fg);display:flex;height:100vh}
#side{container-type:inline-size;width:450px;min-width:220px;max-width:60vw;flex:0 0 auto;background:var(--side);overflow-y:auto;scrollbar-gutter:stable;padding:14px 8px 14px 14px}
#splitter{flex:0 0 6px;position:relative;cursor:col-resize;background:transparent}
#splitter::before{content:'';position:absolute;top:0;bottom:0;left:-6px;right:-6px}
#splitter::after{content:'';position:absolute;top:0;bottom:0;left:2px;width:2px;background:var(--line)}
#splitter:hover::after,#splitter.on::after{left:0;width:6px;background:var(--acc)}
#main{flex:1;overflow-y:auto;scrollbar-gutter:stable;padding:30px 46px}#main>*{max-width:980px}#main p,#main ul,#main ol,#main blockquote{max-width:72ch;line-height:1.7}#main li{margin:.15em 0}
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
   card, the eyebrows and card labels in About. Six rules carried these five
   properties, and one of the six carried them wrong — `#gcard .sec` had no
   font-weight, so the graph card's headings rendered lighter than the
   identical-looking headers a few hundred pixels to their left. */
.grp,#gcard .sec,#aboutBtn .eyebrow,#aboutBox .eyebrow,#aboutFacts dt,.aboutLogo .tl{color:var(--mut);font-size:.78em;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
.grp{margin:12px 0 2px;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;padding:2px 4px;border-radius:5px}
.grp:hover{color:var(--fg);background:var(--line)}.grp .gn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grp .cv{display:inline-block;width:9px;transition:transform .12s;font-size:.9em}.grp.shut .cv{transform:rotate(-90deg)}
.gitems{padding-left:15px;border-left:1px solid var(--line);margin-left:8px}
.grp small{font-weight:400;opacity:.75;font-size:.95em}.grp.flat{cursor:default}.grp.flat:hover{background:none;color:var(--mut)}.grp.flat .cv{visibility:hidden}
#qwrap{position:relative;margin-bottom:9px}#tree .grp:first-child{margin-top:0}
/* One grammar for the whole sidebar, and it is the concept row's: every
   control rests in --item on no fill behind a transparent border, hovers to
   --fg on --line, and marks itself active with the accent border. Identical
   to `.it`, `.it:hover` and `.it.on` below — the transparent border is what
   keeps a row from shifting a pixel when it activates. Owner's instruction
   of 01.09.2026, after three passes that moved the concept row toward the
   buttons; this moves the buttons to the row, which is the direction the
   list wanted all along. */
#views button,#ball,#q{background:transparent;border:1px solid transparent;border-radius:5px;color:var(--item);font-size:.95em;padding:4px 7px}
#views button:hover,#ball:hover,#q:hover{background:var(--line);color:var(--fg)}
#views button.on{border-color:var(--acc);color:var(--fg)}
#q{margin-bottom:0;padding-right:30px}
#q:focus{border-color:var(--acc);color:var(--fg);outline:none}
#qwrap.has #q{border-color:var(--acc);color:var(--fg)}
#qx{position:absolute;right:5px;top:50%;transform:translateY(-50%);display:none;border:0;background:none;padding:0 6px;line-height:1;font-size:1.15em;color:var(--mut);border-radius:5px}
#qx:hover{color:var(--fg);background:var(--line)}
#qwrap.has #qx{display:block}
#ball{width:100%;margin-bottom:9px}#ball:disabled{opacity:.45;cursor:default;background:transparent;border-color:transparent;color:var(--item)}
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
.meta{color:var(--mut);font-size:.92em;margin:.4em 0 1.3em}.gbtn{float:right;margin:6px 0 10px 18px;border-color:var(--acc);color:var(--acc)}.gbtn:hover{background:var(--acc);color:var(--bg)}sup.fn{color:var(--mut)}
.links{font-size:.88em;color:var(--mut);margin:.8em 0}.stat{color:var(--mut);font-size:.82em;margin-bottom:9px}  /* The sidebar is symmetric about its control stack: 9px from the stat text down to the first button row, 6px between the button rows, and 9px either side of the search box down to the first group header. Owner's instruction of 31.08.2026 — symmetry is king. An earlier 22px here was the same instruction read as "push the buttons down", which bought a boundary at the cost of the balance. */
#views{display:flex;gap:6px;margin-bottom:6px}#kbbar{display:flex;flex-direction:column;gap:6px;margin-bottom:6px}#kbbar .krow{display:flex;gap:6px}#kbbar .krow button{flex:1;padding:6px;white-space:nowrap;min-width:0}#kbbar button.on{background:var(--acc);color:var(--bg);border-color:var(--acc)}/* fallback for a KB no block names; the three known blocks override inline */#kbbar button small{opacity:.7;margin-left:5px;font-size:.85em;color:inherit}#views button{flex:1}
#gpane{flex:1;display:none;flex-direction:column;position:relative;min-width:0}
#legend{display:flex;flex-direction:column;gap:4px;padding:9px 14px;border-bottom:1px solid var(--line);font-size:.8em;color:var(--mut)}
#legend .lrow{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}
#legend .lrow i{font-style:normal;opacity:.7;font-size:.92em;margin-right:2px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border:1px solid var(--line);border-radius:12px;cursor:pointer;user-select:none}
.chip.off{opacity:.32}.chip b{font-weight:600;color:var(--fg)}.chip small{color:var(--mut)}
.kbchip{border-width:2px;border-color:var(--fg)}.ldiv{width:1px;align-self:stretch;background:var(--line);margin:0 4px}
#gc{flex:1;cursor:grab;touch-action:none;min-height:0}
#gfit{position:absolute;bottom:18px;right:18px;z-index:2}
#gcard{position:absolute;top:56px;right:14px;width:320px;max-height:calc(100% - 130px);overflow-y:auto;background:var(--bg);border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 26px rgba(0,0,0,.55);padding:14px 16px;display:none;z-index:3}
#gcard h3{margin:.1em 0 .3em;font-size:1.08em}#gcard .desc{font-size:.95em;margin:.5em 0;line-height:1.55}
#gcard .sec{margin:.9em 0 .2em}
#gcard .nb{display:block;font-size:.92em;padding:1px 0;color:var(--acc);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#gcard .open{margin-top:12px;width:100%;border:none;background:var(--acc);color:var(--bg)}
#gcard .x{position:absolute;top:8px;right:12px;cursor:pointer;color:var(--mut);font-size:1.1em}
/* The brand row is the About control. It repeats the dialog's own header —
   eyebrow over the name — so pressing it opens something that looks like what
   was pressed, and the mark carries the identity in both places. */
/* No cell of its own: the brand sits on the sidebar, not in a box on it. The
   border stays declared and transparent so the hover outline costs no layout
   shift, and the hover fill is unchanged. */
#aboutBtn{display:flex;align-items:center;justify-content:center;gap:26px;width:100%;text-align:left;padding:14px 16px;margin-bottom:12px;border:1px solid transparent;border-radius:8px;background:transparent;cursor:pointer}
/* Hover is the outline alone. Filling the cell put back the surface the row
   had just been relieved of, a moment after it was taken away. */
#aboutBtn:hover{border-color:var(--acc)}
#aboutBtn svg{width:131px;height:114px;flex:0 0 auto}
#aboutBtn .tx{display:grid;gap:2px;min-width:0}
#aboutBtn .wm{color:var(--acc);font-size:1.35em;font-weight:700;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* The splitter can take this box to 220px, where a 72px mark and a 26px gap
   leave the name as `00…`. j4k answers the same problem with explicit logo
   breakpoints; these are the same idea against the container rather than the
   viewport, because the width here is dragged and not the window's. */
@container (max-width: 400px){#aboutBtn{gap:16px;padding:12px}#aboutBtn svg{width:106px;height:92px}#aboutBtn .wm{font-size:1.15em}}
@container (max-width: 320px){#aboutBtn{gap:10px;padding:10px}#aboutBtn svg{width:76px;height:66px}#aboutBtn .wm{font-size:.95em}#aboutBtn .eyebrow{font-size:.72em}}
/* The shape is j4k's About dialog: eyebrow over the name, the logo as the real
   heading, one story line, then label/value facts in two columns, a built-with
   line and an actions row. Its light palette maps onto this viewer's tokens —
   card `#282828` on `#242424` becomes `--card` on `--bg`, and its `#3d3d3d`
   borders are already what `--line` is. */
#aboutWrap{position:fixed;inset:0;z-index:60;display:none;place-items:center;padding:18px;background:rgba(10,9,7,.58)}
#aboutWrap.on{display:grid}
#aboutBox{display:grid;gap:14px;width:min(460px,100%);max-height:min(830px,calc(100vh - 36px));overflow:auto;border:1px solid var(--line);border-radius:8px;background:var(--bg);padding:18px;box-shadow:0 24px 80px rgba(0,0,0,.55)}
#aboutBox header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-bottom:12px}
#aboutBox h2,#aboutBox p{margin:0}
#aboutBox h2{font-size:1.35em;color:var(--fg);font-weight:700;border:none;padding:0;margin:0}
#aboutBox .x{background:none;border:none;color:var(--mut);cursor:pointer;font-size:1.1em;line-height:1;padding:0 6px;border-radius:5px}
#aboutBox .x:hover{color:var(--fg);background:var(--line)}
#aboutContent{display:grid;gap:10px;justify-items:center;text-align:center}
.aboutLogo{display:grid;justify-items:center;gap:7px;margin-top:4px}
.aboutLogo svg{width:145px;height:126px;display:block}
.aboutLogo .wm{font-size:1.35em;font-weight:700;color:var(--acc);line-height:1}
#aboutBox .story{max-width:42ch;color:var(--item);font-size:.92em}
#aboutFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 14px;width:100%;margin:4px 0 0;text-align:left}
#aboutFacts>div{display:grid;gap:2px;min-width:0;border:1px solid var(--line);border-radius:6px;padding:6px 9px;background:var(--card)}
#aboutFacts dd{margin:0;color:var(--fg);font-size:.9em;font-weight:600;overflow-wrap:anywhere}
#aboutBox .built{max-width:42ch;color:var(--mut);font-size:.82em}
#aboutActions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;width:100%}
/* the dialog's controls follow the same grammar as the sidebar's, which is
   the concept row's — its close button matches the search box's clear
   button, the same control one layer down. */
#aboutActions button{background:transparent;border:1px solid transparent;border-radius:5px;color:var(--item);font-size:.95em}
#aboutActions button:hover{background:var(--line);color:var(--fg)}
</style></head><body>
<div id="side"><button id="aboutBtn" title="What this vault is, and the facts to quote when something looks wrong">__LOGO__<span class="tx"><span class="eyebrow">About</span><span class="wm">00_Cerebrum</span></span></button><div class="stat"><b>00_Cerebrum</b> · __NC__ concepts · __CIT__ citations<br>generated __STAMP__ by _scripts/visualize.py</div>
<div id="views"><button id="bList" class="on">Concepts</button><button id="bGraph">Graph</button></div><div id="kbbar"></div><button id="ball" title="Fold or unfold every group in the list">Collapse all</button><div id="qwrap"><input id="q" placeholder="Search title, description, tags…"><button id="qx" type="button" title="Clear the search" aria-label="Clear the search">×</button></div><div id="tree"></div></div><div id="splitter" title="drag to resize"></div>
<div id="main"><div class="meta">Pick a concept, or search. Dashed links point at concepts not written yet — legitimate under OKF.</div></div><div id="gpane"><div id="legend"></div><button id="gfit" title="Frame the whole graph (or double-click the background)">Fit</button><canvas id="gc"></canvas><div id="gcard"></div></div>
<div id="aboutWrap"><div id="aboutBox">
<header><div><p class="eyebrow">About</p><h2>00_Cerebrum</h2></div><button class="x" id="aboutX" title="Close about">&#215;</button></header>
<div id="aboutContent">
<div class="aboutLogo">__LOGO__
<div class="wm">00_Cerebrum</div><div class="tl">Open Knowledge Format</div>
</div>
<p class="story">A knowledge base that reads its own sources and cites every claim back to the page it came from, and the machinery that keeps it honest. <i>Cerebrum</i> is the Latin for brain.</p>
<dl id="aboutFacts"></dl>
<p class="built">Markdown and YAML in an Obsidian vault, Open Knowledge Format v0.2 for the bundles, Python for the checks, GitHub for the code.</p>
<div id="aboutActions"><button id="aboutList">Concepts</button><button id="aboutGraph">Graph</button></div>
</div></div></div>
<script>const D=__DATA__;const GIT='__GIT__';const STAMP='__STAMP__';const BUILDNO='__BUILDNO__';const STARTED='__STARTED__';
/* One order for the whole viewer: the knowledge-base buttons and the
   sidebar groups read the same sequence, so the two can never disagree.
   `KB_BLOCKS` is the single source of it and is derived from the concepts
   actually present — one block per knowledge base, sorted by name, each
   with its own hue and legend row.

   Group several bundles into one block if your vault has a real grouping
   to state; `KB_ORDER` and the legend follow whatever the blocks say. */
const KB_HUES=['#e8a14a','#4fc3d0','#c76bd4','#7fbf6a','#e07b7b','#8e9ae0','#d9b34a','#6fb3a8'];
const KB_BLOCKS=[...new Set(Object.values(D).map(c=>c.kb))].sort()
  .map((k,i)=>({kbs:[k],hue:KB_HUES[i%KB_HUES.length],tag:k.replace(/_kb$/,'')}));
const HUE={};KB_BLOCKS.forEach(b=>b.kbs.forEach(k=>HUE[k]=b.hue));
const KB_ORDER=KB_BLOCKS.flatMap(b=>b.kbs);
const tree=document.getElementById('tree'),main=document.getElementById('main'),q=document.getElementById('q');
const KB_LABEL={};        /* display names where the folder name is not the one you want */
function kbOf(id){return id.split('/')[0]}
function kbName(k){return KB_LABEL[k]||k.replace('_kb','')}
function group(id){const p=id.split('/'),sub=p.slice(2,-1).join('/');
/* A concept at the bundle root — questions.md — has no subpath, and the
   old expression relied on ||, which never fired because the left side was
   already truthy. It rendered as 'Name / ' with a dangling separator. */
return sub?kbName(p[0])+' / '+sub:kbName(p[0])}
/* Order the sidebar by knowledge base first, using the same order as the
   buttons, then by group inside it. localeCompare on the group label is
   case-insensitive, so a lowercase folder name used to sort into the middle
   of the others — an ordering that meant nothing and read as an accident. */
function kbRank(id){const i=KB_ORDER.indexOf(kbOf(id));return i<0?KB_ORDER.length:i}
var offKB=new Set();
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
const ga=group(a),gb=group(b);return ga===gb?D[a].t.localeCompare(D[b].t):ga.localeCompare(gb)}).forEach(id=>{const c=D[id];if(offKB.has(c.kb))return;
if(filter){const hay=(c.t+' '+c.d+' '+c.tags.join(' ')+' '+id).toLowerCase();if(!hay.includes(filter))return}
const g=group(id);if(!gs.has(g))gs.set(g,[]);gs.get(g).push(id)});
curGroups=[...gs.keys()];
gs.forEach((ids,g)=>{const open=!!filter||!collapsed.has(g);
const h=document.createElement('div');h.className='grp'+(open?'':' shut')+(filter?' flat':'');
const cv=document.createElement('span');cv.className='cv';cv.textContent='\u25be';h.appendChild(cv);
const gn=document.createElement('span');gn.className='gn';gn.textContent=g;h.appendChild(gn);
const ct=document.createElement('small');ct.textContent=ids.length;h.appendChild(ct);
h.title=filter?'showing search results':(open?'click to fold this group':'click to unfold this group');
const box=document.createElement('div');box.className='gitems';if(!open)box.style.display='none';
ids.forEach(id=>{const c=D[id];const e=document.createElement('a');e.className='it';e.dataset.t=id;e.textContent=c.t;e.title=c.d;e.onclick=()=>show(id);box.appendChild(e)});
if(!filter)h.onclick=()=>{collapsed.has(g)?collapsed.delete(g):collapsed.add(g);saveFold();build(q.value.toLowerCase())};
tree.appendChild(h);tree.appendChild(box)});
const anyOpen=curGroups.some(g=>!collapsed.has(g));
ball.textContent=anyOpen?'Collapse all':'Expand all';ball.disabled=!!filter||!curGroups.length;
ball.title=filter?'the list is showing search results':'Fold or unfold every group in the list';
markSel()}
ball.onclick=()=>{const anyOpen=curGroups.some(g=>!collapsed.has(g));
curGroups.forEach(g=>anyOpen?collapsed.add(g):collapsed.delete(g));saveFold();build(q.value.toLowerCase())};
function E(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function chip(txt,cls){return '<span class="badge '+(cls||'')+'">'+E(txt)+'</span>'}
function show(id){const c=D[id];if(!c)return;cur=id;
/* A concept reached from a body link may sit in a folded group; leaving it
   folded loses the highlight and the reader's place in the tree. */
if(!q.value&&collapsed.has(group(id))){collapsed.delete(group(id));saveFold();build('')}
markSel();const selEl=tree.querySelector('.it.on');if(selEl&&selEl.scrollIntoView)selEl.scrollIntoView({block:'nearest'});
let h='<button class="gbtn" title="Select this concept in the graph">&#9883; Show in graph</button><h1>'+E(c.t)+'</h1><div class="meta">'+chip(c.ty)+chip(c.st,c.st==='draft'?'dr':'')+chip(c.tr,c.tr==='human-reviewed'?'hu':'')+chip(c.ns+' sources')+' '+c.tags.map(t=>'#'+E(t)).join(' ')+'<br>'+E(c.d)+'</div>';
if(c.inb.length)h+='<div class="links">← linked from: '+c.inb.map(x=>'<a class="nav" data-t="'+x+'">'+E(D[x].t)+'</a>').join(' · ')+'</div>';
h+=c.html;
if(c.srcs.length){h+='<h2>Sources</h2><table><tr><th>Source</th><th>last_modified</th></tr>'+c.srcs.map(s=>'<tr><td>'+E(s[0])+'</td><td>'+E(s[1])+'</td></tr>').join('')+'</table>'}
main.innerHTML=h;main.scrollTop=0;
main.querySelectorAll('a.nav').forEach(a=>a.onclick=()=>show(a.dataset.t))}
q.oninput=()=>build(q.value.toLowerCase());build('');
const qwrap=document.getElementById('qwrap'),qx=document.getElementById('qx');
q.addEventListener('input',()=>qwrap.classList.toggle('has',!!q.value));
qx.onclick=()=>{q.value='';q.dispatchEvent(new Event('input'));q.focus()};
/* ---- graph view, built on a precomputed layout: opens settled, identical
   every regeneration. Click selects and shows the concept card with its
   neighbourhood lit; Open (or double-click) goes to the full page. Colors
   are the validated palette; identity is never hue alone: shapes + legend +
   labels. ---- */
/* One palette across every bundle. CATS names the Wiki subdirectories the
   viewer knows how to shelve; a concept in a directory CATS does not name
   renders as "meta / references", which is right for questions.md and
   references/ and wrong for real content. So when a bundle's groups are
   not in this list, add them here rather than special-casing the bundle:
   a set of concepts rendering as meta is the symptom that they are
   missing. Keep SHAPES at least as long as CATS. */
const CATS=['people','systems','projects','decisions','meeting-series','organisation','timelines','services','procedures','policies','hardware','tools','references','meta'];
const SHAPES=['circle','square','triangle','diamond','pentagon','hexagon','star','cross','ring','invtriangle','bars','shield','chip','gear','card','stack'];
const LBL={'meeting-series':'meeting series','meta':'meta / references'};
/* A concept's category is its Wiki subdirectory when that is a name CATS knows,
   and 'meta' otherwise — so a group you have not named yet still renders. Add
   your own group names to CATS rather than special-casing a knowledge base. */
function cat(id){const p=id.split('/');const g=p.length>3?p[2]:'meta';
return CATS.includes(g)?g:'meta'}
const gpane=document.getElementById('gpane'),gc=document.getElementById('gc'),card=document.getElementById('gcard'),
bL=document.getElementById('bList'),bG=document.getElementById('bGraph'),legend=document.getElementById('legend');
const ids=Object.keys(D),idx={};ids.forEach((id,i)=>idx[id]=i);
const N=ids.map((id,i)=>({id,i,c:CATS.indexOf(cat(id)),kb:D[id].kb,x:D[id].x,y:D[id].y,r:5.5+2.3*Math.sqrt(D[id].inb.length)}));
const L=[];ids.forEach(id=>D[id].out.forEach(o=>{if(idx[o]!==undefined&&idx[o]!==idx[id])L.push([idx[id],idx[o]])}));
const NB=N.map(()=>new Set());L.forEach(([a,b])=>{NB[a].add(b);NB[b].add(a)});
let tx=0,ty=0,sc=1,hov=-1,sel=-1,drag=null,pan=null,qv='',dirty=true,dpr=devicePixelRatio||1;
/* one soft halo per knowledge base, in its block's hue, so the clusters in
   the graph visibly belong to the sidebar block and legend row that share the
   colour. Geometry is derived from the settled layout at load. */
const KBC={};N.forEach(n=>{const c=KBC[n.kb]=KBC[n.kb]||{sx:0,sy:0,k:0,d:[]};c.sx+=n.x;c.sy+=n.y;c.k++});
for(const kb in KBC){const c=KBC[kb];c.cx=c.sx/c.k;c.cy=c.sy/c.k}
N.forEach(n=>{KBC[n.kb].d.push(Math.hypot(n.x-KBC[n.kb].cx,n.y-KBC[n.kb].cy))});
/* the cluster edge is the 90th-percentile distance, not the farthest node.
   Max-dist made the glow inconsistent: Beta is dense right up to its rim, so
   its halo stopped at the outer nodes, while Alpha's sparse outliers inflated
   its radius and the glow reached far past the dense mass. One robust edge,
   one multiplier, and every halo reaches out by the same proportion. */
for(const kb in KBC){const c=KBC[kb];c.d.sort((a,b)=>a-b);
c.r=Math.max(60,c.d[Math.floor(.9*(c.d.length-1))]+30);delete c.d}
const off=new Set();
function hid(n){return off.has(n.c)||offKB.has(n.kb)}
function rEff(n){return Math.min(30,Math.max(7,n.r*Math.sqrt(sc)))/sc}
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim()}
let COL=[];function loadCols(){COL=CATS.map((c,i)=>css('--s'+(i+1)));dirty=true}
loadCols();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{loadCols();chips()});
function ghost(n){if(hid(n))return true;
if(qv){const d=D[n.id];if(!(d.t+' '+d.d+' '+d.tags.join(' ')).toLowerCase().includes(qv))return true}
if(sel>=0&&n.i!==sel&&!NB[sel].has(n.i))return true;return false}
function setView(v){gpane.style.display=v==='graph'?'flex':'none';main.style.display=v==='graph'?'none':'block';
bG.classList.toggle('on',v==='graph');bL.classList.toggle('on',v!=='graph');if(v==='graph'){resize();fit()}}
bL.onclick=()=>setView('list');bG.onclick=()=>setView('graph');
const oldShow=show;show=function(id){setView('list');oldShow(id);
const b=main.querySelector('.gbtn');if(b){if(idx[id]===undefined)b.style.display='none';
else b.onclick=()=>{setView('graph');select(idx[id]);centerOn(idx[id])}}};
document.querySelectorAll('.it').forEach(e=>e.onclick=()=>show(e.dataset.t));
const kbbarEl=document.getElementById('kbbar');
/* The selector mirrors the vault's real structure, one block per ontology:
   the three employer archives, the two Alpha documentation bundles, the private
   base. 3 / 2 / 1 across full width, so each block is symmetric on its own
   line and the grouping needs no label. A knowledge base this list does not
   know lands in a fourth row rather than nowhere. */
function kbbar(){kbbarEl.innerHTML='';const seen=[...new Set(Object.values(D).map(c=>c.kb))];
const known=KB_BLOCKS.flatMap(b=>b.kbs);
const blocks=[...KB_BLOCKS.map(b=>({kbs:b.kbs.filter(k=>seen.includes(k)),hue:b.hue})),
 {kbs:seen.filter(k=>!known.includes(k)).sort(),hue:''}];
/* the buttons wear the block hue directly — filled when on, a tinted
   outline when off — so the row needs no accent bar. Owner's instruction
   of 01.09.2026, replacing the vertical line of the same morning. */
blocks.forEach(block=>{if(!block.kbs.length)return;
const row=document.createElement('div');row.className='krow';
block.kbs.forEach(kb=>{const s=document.createElement('button');s.className=offKB.has(kb)?'':'on';
if(block.hue){if(offKB.has(kb)){s.style.borderColor=block.hue+'66';s.style.color=block.hue}
else{s.style.background=block.hue;s.style.borderColor=block.hue;s.style.color='var(--bg)'}}
s.textContent=kbName(kb);
const sm=document.createElement('small');sm.textContent=Object.values(D).filter(c=>c.kb===kb).length;s.appendChild(sm);
s.title='show / hide this knowledge base — list and graph alike';
s.onclick=()=>{offKB.has(kb)?offKB.delete(kb):offKB.add(kb);kbbar();build(q.value.toLowerCase());if(sel>=0&&hid(N[sel]))clearSel();dirty=true};
row.appendChild(s)});
kbbarEl.appendChild(row)})}
/* One row per KB_BLOCKS entry, carrying the categories that block's own
   concepts actually use. Per block rather than global, so the legend rows and
   the sidebar's knowledge-base buttons stay one-to-one — viewer-check asserts
   that their accents match, and a global row count breaks it the moment a
   second knowledge base exists. */
function chips(){legend.innerHTML='';
KB_BLOCKS.forEach((blk,bi)=>{
const inBlk=new Set(blk.kbs);
const cnt=CATS.map(()=>0);N.forEach(n=>{if(inBlk.has(n.kb))cnt[n.c]++});
const row=document.createElement('div');row.className='lrow';
/* the accent bar alone names the block — a text tag repeated the sidebar
   and pushed each row's chips right by a different width, so the category
   columns never aligned. */
row.style.borderLeft='3px solid '+blk.hue;row.style.paddingLeft='8px';
let any=false;
for(let i=0;i<CATS.length;i++){const c=CATS[i];if(!cnt[i])continue;any=true;
const s=document.createElement('span');s.className='chip'+(off.has(i)?' off':'');
const cv=document.createElement('canvas');cv.width=cv.height=16;const x2=cv.getContext('2d');
x2.translate(8,8);x2.fillStyle=COL[i];shp(x2,5.5,i);x2.fill();
s.appendChild(cv);const bb=document.createElement('b');bb.textContent=LBL[c]||c;s.appendChild(bb);
const sm=document.createElement('small');sm.textContent=cnt[i];s.appendChild(sm);
s.title='click to hide / show this group';
s.onclick=()=>{off.has(i)?off.delete(i):off.add(i);if(sel>=0&&hid(N[sel]))clearSel();chips();dirty=true};
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
function fit(){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,any=false;
for(const n of N){if(hid(n))continue;any=true;x0=Math.min(x0,n.x);y0=Math.min(y0,n.y);x1=Math.max(x1,n.x);y1=Math.max(y1,n.y)}
if(!any)return;const pad=70;
sc=Math.max(.08,Math.min(2.2,Math.min(gc.clientWidth/(x1-x0+2*pad),gc.clientHeight/(y1-y0+2*pad))));
tx=-(x0+x1)/2;ty=-(y0+y1)/2;dirty=true}
function centerOn(i){const n=N[i];sc=Math.max(sc,1.5);tx=-n.x;ty=-n.y;dirty=true}
function world(e){const b=gc.getBoundingClientRect();
return[((e.clientX-b.left)-gc.clientWidth/2)/sc-tx,((e.clientY-b.top)-gc.clientHeight/2)/sc-ty]}
function pick(wx,wy){let best=-1,bd=1e18;
for(const n of N){if(hid(n))continue;const rr=rEff(n)+5/sc;const d=(n.x-wx)**2+(n.y-wy)**2;
if(d<rr*rr&&d<bd){bd=d;best=n.i}}return best}
function select(i){sel=i;renderCard();dirty=true}
function clearSel(){sel=-1;card.style.display='none';dirty=true}
function renderCard(){if(sel<0){card.style.display='none';return}
const id=N[sel].id,c=D[id];let h='<span class="x" title="close (Esc)">✕</span><h3>'+E(c.t)+'</h3>';
h+='<div>'+'<span class="badge">'+E(c.ty)+'</span><span class="badge">'+E(LBL[cat(id)]||cat(id))+'</span><span class="badge">'+c.ns+' sources</span></div>';
if(c.d)h+='<div class="desc">'+E(c.d)+'</div>';
const nb=[...NB[sel]];
const inb=nb.filter(j=>D[N[j].id].out.includes(id)||c.inb.includes(N[j].id));
if(c.inb.length){h+='<div class="sec">Linked from ('+c.inb.length+')</div>';
c.inb.slice(0,9).forEach(x=>{h+='<span class="nb" data-i="'+idx[x]+'">'+E(D[x].t)+'</span>'});
if(c.inb.length>9)h+='<span class="nb" style="color:var(--mut);cursor:default">… '+(c.inb.length-9)+' more</span>'}
if(c.out.length){h+='<div class="sec">Links to ('+c.out.length+')</div>';
c.out.slice(0,9).forEach(x=>{h+='<span class="nb" data-i="'+idx[x]+'">'+E(D[x].t)+'</span>'});
if(c.out.length>9)h+='<span class="nb" style="color:var(--mut);cursor:default">… '+(c.out.length-9)+' more</span>'}
h+='<button class="open">Open concept →</button>';
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
addEventListener('mouseup',()=>{if(drag&&(drag._m||0)<6)select(drag.i);drag=null;pan=null});
gc.addEventListener('dblclick',e=>{const[wx,wy]=world(e);const h=pick(wx,wy);
if(h>=0)show(N[h].id);else fit()});
gc.addEventListener('wheel',e=>{e.preventDefault();const b=gc.getBoundingClientRect();const[wx,wy]=world(e);
const ns=Math.max(.08,Math.min(14,sc*Math.exp(-e.deltaY*.0015)));
tx=(e.clientX-b.left-gc.clientWidth/2)/ns-wx;ty=(e.clientY-b.top-gc.clientHeight/2)/ns-wy;sc=ns;dirty=true},{passive:false});
addEventListener('keydown',e=>{if(gpane.style.display==='none')return;
if(e.key==='Escape')clearSel();if(e.key==='f')fit()});
const _oldQ=q.oninput;q.oninput=()=>{const f=q.value.toLowerCase();build(f);qv=f;dirty=true};
document.getElementById('gfit').onclick=fit;
function sxy(n){return[(n.x+tx)*sc+gc.clientWidth/2,(n.y+ty)*sc+gc.clientHeight/2]}
function draw(){const x2=gc.getContext('2d');x2.setTransform(dpr,0,0,dpr,0,0);
x2.clearRect(0,0,gc.clientWidth,gc.clientHeight);
x2.save();x2.translate(gc.clientWidth/2,gc.clientHeight/2);x2.scale(sc,sc);x2.translate(tx,ty);
const anySel=sel>=0;
for(const kb in KBC){if(offKB.has(kb)||!HUE[kb])continue;const c=KBC[kb];
const g=x2.createRadialGradient(c.cx,c.cy,0,c.cx,c.cy,c.r*1.3);
g.addColorStop(0,HUE[kb]+'30');g.addColorStop(.7,HUE[kb]+'1c');g.addColorStop(1,HUE[kb]+'00');
x2.fillStyle=g;x2.beginPath();x2.arc(c.cx,c.cy,c.r*1.3,0,7);x2.fill();
}
x2.lineWidth=1/sc;
for(const[a,b]of L){const na=N[a],nb2=N[b];if(hid(na)||hid(nb2))continue;
const strong=anySel&&(a===sel||b===sel);
x2.strokeStyle=css('--mut');x2.globalAlpha=strong?.85:anySel?.05:qv?.08:.28;x2.lineWidth=(strong?1.6:1)/sc;
x2.beginPath();x2.moveTo(na.x,na.y);x2.lineTo(nb2.x,nb2.y);x2.stroke()}
x2.globalAlpha=1;
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
   only the sparsest bundle let its through). */
for(const kb in KBC){if(offKB.has(kb)||!HUE[kb])continue;const c=KBC[kb];
/* one size for every name — scaling by radius made the big bundle shout and
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
(function loop(){if(gpane.style.display!=='none'&&(dirty||drag)){dirty=false;draw()}requestAnimationFrame(loop)})();
const side=document.getElementById('side'),split=document.getElementById('splitter');
let sdrag=false;
split.addEventListener('mousedown',e=>{sdrag=true;split.classList.add('on');document.body.style.userSelect='none';e.preventDefault()});
addEventListener('mousemove',e=>{if(!sdrag)return;const w=Math.max(220,Math.min(innerWidth*.6,e.clientX));side.style.width=w+'px';resize()});
addEventListener('mouseup',()=>{if(sdrag){sdrag=false;split.classList.remove('on');document.body.style.userSelect='';resize()}});
// About: every number is derived from D at open time, so the panel cannot
// drift from the page it describes the way a baked-in count would. The
// knowledge-base breakdown is deliberately absent — the selectors above the
// list already carry a count each, and a second copy is this vault's oldest
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
 fact(f,'Build code',GIT,'The commit this page was generated from. \u2019uncommitted\u2019 means the vault held edits that were in no commit when it ran, so the page matches no commit exactly and there is nothing to link to. Set REPO above to link the hash to your own repository.',
  REPO&&/^[0-9a-f]{7,40}$/.test(GIT)?REPO+'/commit/'+GIT:null);
 fact(f,'Build number',BUILDNO,'Commits on main when this page was generated');
 fact(f,'Build date',STAMP,'When _scripts/visualize.py last ran, in this machine\u2019s timezone');
 fact(f,'Started',STARTED,'The vault\u2019s first commit, and which day of building this is');
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
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&aboutWrap.classList.contains('on'))aboutClose()});
kbbar();chips();resize();
</script></body></html>"""
page = (page.replace('__LOGO__', logo_svg).replace('__GIT__', git_id)
        .replace('__BUILDNO__', build_no).replace('__STARTED__', started)).replace('__NC__', str(len(concepts))).replace('__CIT__', "%d" % ncit).replace('__STAMP__', stamp).replace('__DATA__', json.dumps(data, ensure_ascii=False))
out = os.path.join(VAULT, 'okf-viewer.html')
open(out, 'w', encoding='utf-8').write(page)
print('wrote %s  (%d concepts, %.1f MB)' % (out, len(concepts), os.path.getsize(out) / 1e6))
