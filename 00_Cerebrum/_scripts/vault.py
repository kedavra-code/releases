#!/usr/bin/env python3
"""The vault, read-only, for any app or Claude session on this Mac.

One service that answers from the concepts with their sources and trust
signals, as a command line and as an MCP server over standard input and output.

    python3 _scripts/vault.py search "gadget system"
    python3 _scripts/vault.py concept Demo_kb/Wiki/people/jane-example.md
    python3 _scripts/vault.py person Jane
    python3 _scripts/vault.py project "Widget project"
    python3 _scripts/vault.py changed 2026-11-01
    python3 _scripts/vault.py questions gadget
    python3 _scripts/vault.py --kb Demo_kb,Second_kb search widget
    python3 _scripts/vault.py --check        # the settled questions in CHECK
    python3 _scripts/vault.py --mcp          # the MCP server

**It reads concepts only**: the `Wiki/` files of each knowledge base. It never
opens `Raw/`, `OneNote/`, `folia/`, `scripta/` or `_testimony/`, so a page
text reaches a caller only as far as a concept quotes it. It writes nothing
and opens no network port. A path that leaves the bundles is refused.
"""
import bisect
import collections
import datetime
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actionitems
import bundle

VAULT = bundle.VAULT
LINK = re.compile(r'\]\(([^)#\s]+\.md)(?:#[^)]*)?\)')
WORD = re.compile(r'[a-z0-9]+')
# A word the query's last word only starts counts this much of a whole word,
# so an exact word still ranks first.
PREFIX = 0.6
EXPAND = 300
FOOTDEF = re.compile(r'^\[\^[^\]]+\]:.*$', re.M)


def fold(s):
    """Lower case, umlauts written out, accents dropped: "Zürich" is "zuerich"."""
    s = str(s).lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def words(s):
    return WORD.findall(fold(s))


def today():
    return datetime.date.today().isoformat()


class Vault:
    """Every concept of the chosen bases, parsed once, rebuilt when a file
    changes. A long-lived MCP server checks the files' times on each call;
    that is a stat per concept, well under a second for the whole vault."""

    def __init__(self, kbs=None):
        self.kbs = [k for k in bundle.discover() if not kbs or k in kbs]
        self.stamp = None
        self.refresh()

    def files(self):
        return [f for kb in self.kbs for f in bundle.concept_files(kb)]

    def refresh(self):
        fs = self.files()
        # The nicknames live in each base's assertions.yaml, so a change there
        # rebuilds the index too, not only a changed concept.
        ys = [os.path.join(VAULT, kb, 'assertions.yaml') for kb in self.kbs]
        stamp = (len(fs), max((os.path.getmtime(f) for f in fs + [y for y in ys if os.path.exists(y)]), default=0))
        if stamp == self.stamp:
            return
        self.stamp, self.c, self.alias = stamp, {}, {}
        for f in fs:
            rel = os.path.relpath(f, VAULT)
            text = open(f, encoding='utf-8').read()
            m = bundle.FM.match(text)
            try:
                fm = bundle.mapping(m.group(1)) if m else {}
            except Exception:
                fm = {}
            body = text[m.end():] if m else text
            d = os.path.dirname(f)
            links = {os.path.relpath(os.path.normpath(os.path.join(d, l)), VAULT)
                     for l in LINK.findall(body) if not l.startswith('http')}
            self.c[rel] = {
                'kb': rel.split('/')[0], 'path': rel, 'fm': fm, 'body': body,
                'title': str(fm.get('title') or os.path.basename(f)[:-3]),
                'description': str(fm.get('description') or ''),
                'tags': [str(t) for t in fm.get('tags') or []] if isinstance(fm.get('tags'), list) else [],
                'links': links,
                'w_title': set(words(fm.get('title') or os.path.basename(f)[:-3])),
                'w_desc': set(words(fm.get('description') or '')),
                'w_tags': set(w for t in (fm.get('tags') or []) if isinstance(fm.get('tags'), list) for w in words(t)),
                'c_body': collections.Counter(words(FOOTDEF.sub('', body))),
            }
        # Which concepts hold each word, and every word in order, so the last
        # word of a query can be read as the start of a word: the lookup panel
        # asks on every letter, and "kerb" has to find Kerberos (owner,
        # 05.11.2026).
        self.post = collections.defaultdict(set)
        for p, c in self.c.items():
            for w in c['w_title'] | c['w_desc'] | c['w_tags'] | set(c['c_body']):
                self.post[w].add(p)
        self.vocab = sorted(self.post)
        for kb in self.kbs:
            for a in bundle.assertions(kb).get('aliases') or []:
                if isinstance(a, dict) and a.get('alias') and a.get('person'):
                    p = '%s/Wiki/people/%s.md' % (kb, a['person'])
                    if p in self.c:
                        self.alias.setdefault(fold(a['alias']), set()).add(p)

    # -- what every answer carries ------------------------------------------

    def trust(self, c):
        fm = c['fm']
        v = fm.get('verified')
        by = str(v.get('by')) if isinstance(v, dict) else ''
        gen = fm.get('generated') if isinstance(fm.get('generated'), dict) else {}
        stale = str(fm.get('stale_after') or '')
        return {
            'status': str(fm.get('status') or 'stable'),
            'verified': 'human-reviewed' if by.startswith('human:') else
                        'machine-confirmed' if by else 'unverified',
            'written': str(gen.get('at') or '')[:10],
            'stale': bool(stale) and stale[:10] < today(),
            'stale_after': stale[:10] or None,
            'sources': len(fm.get('sources') or []) if isinstance(fm.get('sources'), list) else 0,
        }

    def card(self, p, score=None):
        c = self.c[p]
        out = {'path': p, 'kb': c['kb'], 'type': str(c['fm'].get('type') or ''),
               'title': c['title'], 'description': c['description'],
               'trust': self.trust(c)}
        if score is not None:
            out['score'] = round(score, 1)
        return out

    # -- the tools ------------------------------------------------------------

    def search(self, query, limit=10, group=None):
        self.refresh()
        q = words(query)
        if not q:
            return []
        hits = self.alias_hits(q)
        per = []
        for i, w in enumerate(q):
            d = {p: self.term(self.c[p], w) for p in self.post.get(w, ())}
            if i == len(q) - 1 and len(w) >= 2:
                for x in self.expand(w):
                    for p in self.post[x]:
                        s = PREFIX * self.term(self.c[p], x)
                        if s > d.get(p, 0):
                            d[p] = s
            per.append(d)
        scores = {}
        for p in set().union(*per):
            if group and f'/Wiki/{group}/' not in p:
                continue
            found = sum(p in d for d in per)
            s = sum(d.get(p, 0) for d in per) * (found / len(q)) ** 2
            if p.endswith('/questions.md'):
                s *= 0.3
            if p in hits:
                s += 100
            scores[p] = s
        for p in hits:
            scores.setdefault(p, 100)
        best = sorted(scores, key=lambda p: -scores[p])[:limit]
        return [self.card(p, scores[p]) for p in best]

    def term(self, c, w):
        """One word's weight in one concept: the title counts most, then the
        tags, the description, and the body, whose count is capped."""
        t = 10 * (w in c['w_title']) + 5 * (w in c['w_tags']) + 3 * (w in c['w_desc'])
        b = min(c['c_body'].get(w, 0), 20) if w not in c['w_title'] else 0
        return t + b ** 0.5

    def expand(self, w):
        """The words that start with `w`, longer than it, the most common
        first and at most EXPAND of them."""
        i = bisect.bisect_right(self.vocab, w)
        j = bisect.bisect_left(self.vocab, w + '{')
        out = self.vocab[i:j]
        if len(out) > EXPAND:
            out = sorted(out, key=lambda x: -len(self.post[x]))[:EXPAND]
        return out

    def alias_hits(self, q):
        """The people whose mapped nickname stands in the words `q`, in order,
        alone or inside a longer question."""
        out = set()
        for a, people in self.alias.items():
            aw = words(a)
            if aw and any(q[i:i + len(aw)] == aw for i in range(len(q) - len(aw) + 1)):
                out |= people
        return out

    def path(self, p):
        """A concept path, checked: it must be a concept of a chosen base."""
        p = os.path.normpath(str(p).strip().lstrip('/'))
        if p.startswith('..') or os.path.isabs(p) or p not in self.c:
            raise ValueError('not a concept of the vault: %s' % p)
        return p

    def concept(self, path):
        self.refresh()
        p = self.path(path)
        c = self.c[p]
        srcs = []
        for s in c['fm'].get('sources') or []:
            if isinstance(s, dict):
                srcs.append({k: str(s[k]) if not isinstance(s[k], list) else s[k]
                             for k in ('id', 'resource', 'title', 'author', 'last_modified') if k in s})
        out = self.card(p)
        out.update({'tags': c['tags'], 'sources': srcs, 'body': c['body'].strip(),
                    'linked_from': self.backlinks(p)})
        return out

    def backlinks(self, p):
        return sorted(q for q, c in self.c.items() if p in c['links'] and q != p)

    def who(self, name, group):
        self.refresh()
        hits = sorted(self.alias_hits(words(name)))
        if not hits:
            hits = [h['path'] for h in self.search(name, 3, group)]
        if not hits:
            return {'found': False, 'query': name}
        out = self.concept(hits[0])
        out['others'] = [self.card(h) for h in hits[1:]]
        return out

    def changed(self, since, limit=50):
        self.refresh()
        since = str(since)[:10]
        rows = [(self.trust(c)['written'], p) for p, c in self.c.items()
                if self.trust(c)['written'] >= since]
        return [dict(self.card(p), written=w) for w, p in sorted(rows, reverse=True)[:limit]]

    def questions(self, topic=None):
        """Open and deferred action items, and held contradiction rows, of
        each base, from its `questions.md`: the only place their state lives."""
        self.refresh()
        out = []
        tw = set(words(topic or ''))
        # The rows are read by `actionitems.py`, the roll-up's reader, which
        # takes a decorated state such as `**open**`. A reader of its own
        # here missed the one open item there was (05.11.2026).
        for kb in self.kbs:
            p = '%s/Wiki/questions.md' % kb
            for i in actionitems.items(kb):
                if i['state'] not in ('open', 'deferred'):
                    continue
                if tw and not tw <= set(words(' '.join((i['id'], i['item'], i['res'])))):
                    continue
                out.append({'kb': kb, 'id': i['id'], 'state': i['state'], 'raised': i['raised'],
                            'item': i['item'][:600], 'source': p})
        return out


TOOLS = [
    ('search', 'Search the vault\'s concepts. Returns the best matches with their path, title, description and trust signals (status, verified, written, stale).',
     {'query': ('string', 'Words to look for; a nickname such as "Jane" finds its person'),
      'limit': ('integer', 'How many results, default 10')}, ['query']),
    ('concept', 'One concept in full: its body, its sources with dates and authors, its trust signals, and the concepts that link to it.',
     {'path': ('string', 'The concept path as search returns it, e.g. Demo_kb/Wiki/people/jane-example.md')}, ['path']),
    ('person', 'The concept of a person, by name or nickname, with what links to it.',
     {'name': ('string', 'A name, surname or nickname')}, ['name']),
    ('project', 'The concept of a project, by name, with what links to it.',
     {'name': ('string', 'A project name')}, ['name']),
    ('changed_since', 'Concepts written or rewritten on or after a date, newest first.',
     {'date': ('string', 'YYYY-MM-DD')}, ['date']),
    ('open_questions', 'Open and deferred action items of the knowledge bases, optionally only those naming a topic.',
     {'topic': ('string', 'Words the item must contain; empty for all')}, []),
]


def call(v, name, a):
    if name == 'search':
        return v.search(a['query'], int(a.get('limit') or 10))
    if name == 'concept':
        return v.concept(a['path'])
    if name == 'person':
        return v.who(a['name'], 'people')
    if name == 'project':
        return v.who(a['name'], 'projects')
    if name == 'changed_since':
        return v.changed(a['date'])
    if name == 'open_questions':
        return v.questions(a.get('topic'))
    raise ValueError('no such tool: %s' % name)


def mcp(v):
    """MCP over standard input and output: JSON-RPC, one message a line."""
    def send(msg):
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
        sys.stdout.flush()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        mid, meth = m.get('id'), m.get('method')
        if mid is None:
            continue                                   # a notification
        if meth == 'initialize':
            res = {'protocolVersion': (m.get('params') or {}).get('protocolVersion', '2024-11-05'),
                   'capabilities': {'tools': {}},
                   'serverInfo': {'name': 'cerebrum', 'version': '1'},
                   'instructions': 'Read-only access to the 00_Cerebrum knowledge bases. '
                                   'Answers carry trust signals: say when a concept is unverified, '
                                   'a draft, or stale, and cite the concept path.'}
        elif meth == 'ping':
            res = {}
        elif meth == 'tools/list':
            res = {'tools': [{'name': n, 'description': d,
                              'inputSchema': {'type': 'object',
                                              'properties': {k: {'type': t, 'description': x}
                                                             for k, (t, x) in props.items()},
                                              'required': req},
                              'annotations': {'readOnlyHint': True}}
                             for n, d, props, req in TOOLS]}
        elif meth == 'tools/call':
            p = m.get('params') or {}
            try:
                out = call(v, p.get('name'), p.get('arguments') or {})
                res = {'content': [{'type': 'text', 'text': json.dumps(out, ensure_ascii=False, indent=1)}]}
            except Exception as e:
                res = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
        else:
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': 'no such method'}})
            continue
        send({'jsonrpc': '2.0', 'id': mid, 'result': res})


# The check: questions whose answers stand in a `memory.md` as settled facts,
# each with the concept that must come back in the first three. Empty in the
# template: fill it with your own vault's known answers, as
#     ('the question', '<Topic>_kb/Wiki/<group>/<concept>.md'),
CHECK = []

# A nickname the assertions map, and the person it must rank first, alone or
# inside a longer question. Empty in the template, filled the same way.
ALIAS_FIRST = []

def check(v):
    bad = 0
    for q, want in CHECK:
        got = [h['path'] for h in v.search(q, 3)]
        ok = want in got
        bad += not ok
        print('%s  %-32s %s' % ('ok  ' if ok else 'MISS', q, want if ok else 'got %s' % got))
    # The guards: nothing outside the concepts, and no path out of the bundles.
    for p in ('../CLAUDE.md', '/etc/passwd', 'Alpha_kb/OneNote/x.md', 'Alpha_kb/folia/x.md'):
        try:
            v.concept(p)
            print('FAIL  %s was served' % p)
            bad += 1
        except ValueError:
            print('ok    refused %s' % p)
    if any('/OneNote/' in p or '/folia/' in p or '/Raw/' in p for p in v.c):
        print('FAIL  an archive file is in the index')
        bad += 1
    # A nickname the assertions map ranks its person first, alone or inside a
    # longer question (kit found "who is ..." missing it, 05.11.2026).
    for q, want in ALIAS_FIRST:
        got = [h['path'] for h in v.search(q, 1)]
        ok = got == [want]
        bad += not ok
        print('%s  %-32s %s' % ('ok  ' if ok else 'MISS', q, want if ok else 'first is %s' % got))
    # Every open and deferred item, as the roll-up reads the tables, with
    # the day it was raised (folia found the date missing, 05.11.2026).
    want = sorted((kb, i['id']) for kb in v.kbs for i in actionitems.items(kb)
                  if i['state'] in ('open', 'deferred'))
    got = v.questions()
    ok = sorted((q['kb'], q['id']) for q in got) == want and all(
        re.fullmatch(r'\d{4}-\d{2}-\d{2}', q.get('raised') or '') for q in got)
    bad += not ok
    print('%s  questions: %d open or deferred items with their date%s' % (
        'ok  ' if ok else 'MISS', len(want), '' if ok else ', got %s' % [(q['id'], q.get('raised')) for q in got]))
    print('%d of %d failed' % (bad, len(CHECK) + 6 + len(ALIAS_FIRST)))
    return bad


def main(argv):
    kbs = None
    if argv[:1] == ['--kb']:
        kbs, argv = set(argv[1].split(',')), argv[2:]
    v = Vault(kbs)
    if argv[:1] == ['--mcp']:
        return mcp(v)
    if argv[:1] == ['--check']:
        return 1 if check(v) else 0
    if len(argv) < 1:
        print(__doc__)
        return 2
    cmd, rest = argv[0], ' '.join(argv[1:])
    name = {'changed': 'changed_since', 'questions': 'open_questions'}.get(cmd, cmd)
    key = {'search': 'query', 'concept': 'path', 'person': 'name', 'project': 'name',
           'changed_since': 'date', 'open_questions': 'topic'}.get(name)
    if not key:
        print(__doc__)
        return 2
    print(json.dumps(call(v, name, {key: rest}), ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
