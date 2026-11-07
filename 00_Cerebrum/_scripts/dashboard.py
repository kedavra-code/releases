#!/usr/bin/env python3
"""How the vault stands and what waits for the owner, as one JSON object.

A3 of `Outputs/2026-11-05_cerebrum-for-the-other-apps.md`: the figures for a
dashboard, which specula draws. No model, nothing new measured: every figure is
the one an existing script gives, called here rather than copied.

    python3 _scripts/dashboard.py --json     # the object, and nothing else
    python3 _scripts/dashboard.py --check    # each figure against its own script

Per base, each marked `live` or frozen (owner, 05.11.2026: "put all
knowledge bases in the dashboard"): concepts and drafts; concepts past their `stale_after` and those
reaching it in the next 30 days; open and deferred action items
(`actionitems.py`); the date of the last health check (`readset.py`); what
`verify.py` reports, run with `--no-clock`, so a look at the dashboard is not
counted as a run; the unread contradiction pairs (`pairs.py`); the `Raw/` files
no concept cites. For the vault: the `scripta/` notes no concept of `MEETINGS_KB` cites
(`meetings.py`), the reports at `pending review` in `Outputs/_REPORTS.md`, the
concepts written since yesterday, and every open item, which is what needs the
owner. And `owner_questions`, the open questions only the owner can answer,
from `owner-questions.json` (specula's request of 07.11.2026), with
`owner_questions_unsorted`, per base, the bullets and held rows no sort has
read yet.

It writes nothing and opens no port. It reads concepts' frontmatter, the item
tables and the register; it prints counts, titles, paths and item texts.
`verify.py` takes about half a minute, so a caller refreshes in the background.
"""
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bundle
import actionitems
import meetings
import pairs
import queues
import readset
import vault

VAULT = bundle.VAULT
# The knowledge base the meeting notes in scripta/ belong to; empty where a
# vault keeps none, and the count is then 0.
MEETINGS_KB = ''
SKIP = {'_INGESTED.md', '.DS_Store'}
LINE = re.compile(r'^== (\w+)(?: \(vault\))?: (?:(\d+) concepts, (\d+) citations, )?(\d+) defects(?:, (\d+) findings)?', re.M)


def today():
    return datetime.date.today()


def concepts(kb):
    """Each concept's path, title, status and stale_after, from its frontmatter."""
    out = []
    for f in bundle.concept_files(kb):
        m = bundle.FM.match(open(f, encoding='utf-8').read())
        try:
            fm = bundle.mapping(m.group(1)) if m else {}
        except Exception:
            fm = {}
        out.append({'path': os.path.relpath(f, VAULT),
                    'title': str(fm.get('title') or os.path.basename(f)[:-3]),
                    'status': str(fm.get('status') or 'stable'),
                    'stale_after': str(fm.get('stale_after') or '')[:10] or None})
    return out


def stale(cs, day, ahead=30):
    """(past, soon): concepts past their date, and those reaching it within
    `ahead` days. A date of today is past, as `vault.py` and `verify.py` read it."""
    end = (day + datetime.timedelta(days=ahead)).isoformat()
    d = day.isoformat()
    past = [c for c in cs if c['stale_after'] and c['stale_after'] < d]
    soon = [c for c in cs if c['stale_after'] and d <= c['stale_after'] <= end]
    return (sorted(past, key=lambda c: c['stale_after']),
            sorted(soon, key=lambda c: c['stale_after']))


def raw_uncited(kb):
    """The `Raw/` files no concept cites and no record gives a fate:
    `bundle.raw_without_fate()`, counted."""
    return len(bundle.raw_without_fate(kb))


def unread_pairs(kb):
    return len(pairs.unread(kb, pairs.candidates(pairs.cited(kb), pairs.threshold(kb))))


def audit():
    """What `verify.py --no-clock` reports, per base and for the vault."""
    r = subprocess.run([sys.executable, os.path.join(VAULT, '_scripts', 'verify.py'), '--no-clock'],
                       cwd=VAULT, capture_output=True, text=True)
    out = {}
    for m in LINE.finditer(r.stdout):
        out[m.group(1)] = {'defects': int(m.group(4)),
                           'findings': int(m.group(5)) if m.group(5) else None}
    return {'green': r.returncode == 0, 'bases': out,
            'defect_lines': [l.strip() for l in r.stdout.splitlines() if l.strip().startswith('DEFECT')][:20]}


def pending_reports():
    rows = []
    for line in open(os.path.join(VAULT, 'Outputs', '_REPORTS.md'), encoding='utf-8'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 6 and re.match(r'\d{4}-\d{2}-\d{2}$', cells[0]) \
                and cells[-1].lower().startswith('pending review'):
            link = re.search(r'\[([^\]]+)\]\(([^)]+)\)', cells[3])
            rows.append({'date': cells[0], 'scope': cells[1],
                         'title': link.group(1) if link else cells[3],
                         'path': 'Outputs/' + link.group(2) if link else None})
    return rows


def health_report(kb, day):
    """The report of a base's health check of `day`, or None. The files are
    named `<day>_health-check-<slug>.md`, the slug the base's name with or
    without `-kb` (`alpha`, `alpha-kb`), and a second report of the day ends in
    `-v2`; the latest of the day is taken."""
    if not day:
        return None
    d = os.path.join(VAULT, 'Outputs', 'HealthChecks')
    slug = kb[:-3].lower() if kb.endswith('_kb') else kb.lower()
    pat = re.compile(r'^%s_health-check-%s(?:-kb)?(?:-v(\d+))?\.md$' % (re.escape(day), re.escape(slug)))
    hits = [(int(m.group(1) or 1), f) for f in os.listdir(d) if (m := pat.match(f))] if os.path.isdir(d) else []
    return 'Outputs/HealthChecks/' + max(hits)[1] if hits else None


def owner_questions():
    """The questions only the owner can answer that still stand, from
    `owner-questions.json`: a bullet while it stands as written in its
    concept's `# Open questions`, a held row of questions.md while it is not
    marked settled. Also the count in each base that no sort has read yet:
    bullets and held rows that stand and are not on the list."""
    spec = json.load(open(os.path.join(VAULT, '_scripts', 'owner-questions.json'), encoding='utf-8'))
    out, cache = [], {}
    for b in spec['bullets']:
        f = os.path.join(VAULT, b['kb'], 'Wiki', b['concept'])
        if f not in cache:
            cache[f] = queues.bullets(f) if os.path.exists(f) else []
        if b['q'] in cache[f]:
            out.append({'kb': b['kb'], 'path': os.path.relpath(f, VAULT), 'title': title(f), 'question': b['q']})
    held = {}
    for h in spec['held']:
        q = os.path.join(VAULT, h['kb'], 'Wiki', 'questions.md')
        if q not in held:
            held[q] = queues.held_lines(open(q, encoding='utf-8').read())
        line = next((l for l in held[q] if l.startswith(h['row'])), None)
        if line:
            first = re.search(r'\]\(([^)]+)\)', h['row'])
            f = os.path.normpath(os.path.join(os.path.dirname(q), first.group(1))) if first else q
            out.append({'kb': h['kb'], 'path': os.path.relpath(f, VAULT), 'title': title(f),
                        'question': [c.strip() for c in line.split('|')][2]})
    listed = {(b['kb'], b['concept'], b['q']) for b in spec['bullets']}
    rows = {(h['kb'], h['row']) for h in spec['held']}
    unsorted = {}
    for kb in {b['kb'] for b in spec['bullets']} | {h['kb'] for h in spec['held']}:
        n = sum(1 for f in bundle.concept_files(kb) for q in queues.bullets(f)
                if (kb, os.path.relpath(f, os.path.join(VAULT, kb, 'Wiki')), q) not in listed)
        q = os.path.join(VAULT, kb, 'Wiki', 'questions.md')
        n += sum(1 for l in queues.held_lines(open(q, encoding='utf-8').read())
                 if not any(l.startswith(r) for k, r in rows if k == kb)) if os.path.exists(q) else 0
        unsorted[kb] = n
    return out, unsorted


def title(f):
    t = open(f, encoding='utf-8').read() if os.path.exists(f) else ''
    m = bundle.FM.match(t)
    return str((bundle.mapping(m.group(1)) if m else {}).get('title') or os.path.basename(f)[:-3])


def build(run_audit=True):
    day = today()
    yesterday = (day - datetime.timedelta(days=1)).isoformat()
    live = bundle.live()
    checked = audit() if run_audit else None
    bases, needs = [], []
    for kb in bundle.discover():
        cs = concepts(kb)
        past, soon = stale(cs, day)
        items = actionitems.items(kb)
        for it in items:
            if it['state'] == 'open':
                needs.append({'kb': kb, 'id': it['id'], 'item': it['item']})
        bases.append({
            'kb': kb,
            'live': kb in live,
            'concepts': len(cs),
            'drafts': sum(c['status'] == 'draft' for c in cs),
            'stale_past': len(past),
            'stale_soon': len(soon),
            'items_open': sum(i['state'] == 'open' for i in items),
            'items_deferred': sum(i['state'] == 'deferred' for i in items),
            'last_health_check': readset.previous_run(kb),
            'health_check_report': health_report(kb, readset.previous_run(kb)),
            'items': [{'id': i['id'], 'state': i['state'], 'raised': i['raised'], 'item': i['item']}
                      for i in items if i['state'] in ('open', 'deferred')],
            'verify': (checked or {}).get('bases', {}).get(kb),
            'pairs_unread': unread_pairs(kb),
            'raw_uncited': raw_uncited(kb),
            'stale': [dict(c, kb=kb) for c in past + soon],
        })
    v = vault.Vault(set(live))
    changed = [{'path': c['path'], 'kb': c['kb'], 'title': c['title'], 'written': c['written']}
               for c in v.changed(yesterday, limit=200)]
    hc = os.path.join(VAULT, 'Outputs', 'HealthChecks')
    sittings = sorted(f for f in os.listdir(hc) if f.endswith('_action-sitting.md')) if os.path.isdir(hc) else []
    oq, unsorted = owner_questions()
    return {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'live': live,
        'bases': bases,
        'verify': {'green': checked['green'], 'vault_defects': checked['bases'].get('00_Cerebrum', {}).get('defects'),
                   'defect_lines': checked['defect_lines']} if checked else None,
        'meetings_uncited': len(meetings.pending(MEETINGS_KB)) if MEETINGS_KB else 0,
        'reports_pending_review': pending_reports(),
        'changed_since_yesterday': changed,
        'stale_next_30_days': [s for b in bases for s in b['stale'] if s['stale_after'] >= day.isoformat()],
        'needs_owner': needs,
        'owner_questions': oq,
        'owner_questions_unsorted': unsorted,
        'last_decision_page': 'Outputs/HealthChecks/' + sittings[-1] if sittings else None,
    }


def check():
    """Each figure against what its own script prints, and the stale rule on made-up dates."""
    bad = 0

    def say(ok, what):
        nonlocal bad
        bad += not ok
        print('%s  %s' % ('ok  ' if ok else 'FAIL', what))

    d = build()
    run = lambda *a: subprocess.run([sys.executable] + [os.path.join(VAULT, '_scripts', a[0])] + list(a[1:]),
                                    cwd=VAULT, capture_output=True, text=True).stdout
    for b in d['bases']:
        kb = b['kb']
        line = re.search(r'^%s: \d+ candidate pair\(s\) at \d+\+ shared sources, (\d+) unread' % kb,
                         run('pairs.py', kb), re.M)
        say(line and int(line.group(1)) == b['pairs_unread'], '%s unread pairs %s = pairs.py' % (kb, b['pairs_unread']))
        v = re.search(r'^== %s: (\d+) concepts, \d+ citations, (\d+) defects' % kb, run('verify.py', '--no-clock', kb), re.M)
        say(v and int(v.group(1)) == b['concepts'] and int(v.group(2)) == b['verify']['defects'],
            '%s concepts %d and defects %s = verify.py' % (kb, b['concepts'], b['verify']['defects']))
        items = actionitems.items(kb)
        say(sum(i['state'] == 'open' for i in items) == b['items_open'], '%s open items %d = actionitems.py' % (kb, b['items_open']))
        say(sorted(i['id'] for i in b['items']) == sorted(i['id'] for i in items if i['state'] in ('open', 'deferred')),
            '%s items listed %d = actionitems.py' % (kb, len(b['items'])))
        r = b['health_check_report']
        say(r is None or (os.path.exists(os.path.join(VAULT, r)) and b['last_health_check'] in r
                          and r.split('/')[-1] in open(os.path.join(VAULT, 'Outputs', '_REPORTS.md'), encoding='utf-8').read()),
            '%s health check report %s exists, is of %s and has its register row' % (kb, r, b['last_health_check']))
    for kb, n in d['owner_questions_unsorted'].items():
        listed = sum(q['kb'] == kb for q in d['owner_questions'])
        qp = os.path.join(VAULT, kb, 'Wiki', 'questions.md')
        seen = sum(len(queues.bullets(f)) for f in bundle.concept_files(kb)) \
            + (queues.held_rows(open(qp, encoding='utf-8').read()) if os.path.exists(qp) else 0)
        say(listed + n == seen, '%s owner questions %d + %d not yet sorted = %d bullets and held rows queues.py sees'
            % (kb, listed, n, seen))
    first = d['owner_questions'][0] if d['owner_questions'] else None
    if first:
        keep = queues.bullets
        queues.bullets = lambda f: [] if os.path.relpath(f, VAULT) == first['path'] else keep(f)
        gone = all(q['path'] != first['path'] or q['question'] not in keep(os.path.join(VAULT, first['path']))
                   for q in owner_questions()[0])
        queues.bullets = keep
        say(gone, 'a bullet answered and removed drops out of owner_questions')
    if MEETINGS_KB:
        m = re.search(r'^%s: (\d+) of \d+ meeting notes' % MEETINGS_KB, run('meetings.py', MEETINGS_KB), re.M)
        say(m and int(m.group(1)) == d['meetings_uncited'], 'meeting notes %d = meetings.py' % d['meetings_uncited'])
    day = datetime.date(2026, 11, 5)
    fake = [{'path': 'a', 'title': 'tomorrow', 'status': 'stable', 'stale_after': '2026-11-06'},
            {'path': 'b', 'title': 'next year', 'status': 'stable', 'stale_after': '2027-11-06'},
            {'path': 'c', 'title': 'yesterday', 'status': 'stable', 'stale_after': '2026-11-04'},
            {'path': 'd', 'title': 'none', 'status': 'stable', 'stale_after': None}]
    past, soon = stale(fake, day)
    say([c['path'] for c in soon] == ['a'], 'stale_after tomorrow is listed as soon, next year is not')
    say([c['path'] for c in past] == ['c'], 'stale_after yesterday is listed as past')
    clock = os.path.join(VAULT, '_scripts', 'verify-state.json')
    before = os.path.getmtime(clock) if os.path.exists(clock) else None
    build()
    say((os.path.getmtime(clock) if os.path.exists(clock) else None) == before,
        'the audit clock is not written')
    print('%d failed' % bad)
    return bad


def main(argv):
    if argv[:1] == ['--json']:
        print(json.dumps(build(), ensure_ascii=False, indent=1))
        return 0
    if argv[:1] == ['--check']:
        return 1 if check() else 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
