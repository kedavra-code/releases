#!/usr/bin/env python3
"""Find a concept that gives one person's mail or invitation to another.

The defect class this exists for was found on 20.09.2026, when eight readers
working the whole of `Gamma_kb` kept reporting the same shape from different
concepts. Seven cases were corrected that day:

    systems/stepone.md                   the vault owner set the brief   -> Hafner
    systems/email-signature-manager.md   the vault owner reopened it     -> Hafner
    projects/uam.md                      Hafner called it    -> Osterwald
    meeting-series/programme-auslegeordnung-windows-engineering.md  (twice)
    decisions/2018-06-easyvista-redirect-to-the-programme-app-store.md
    systems/active-directory.md          Ferraro answered  -> Nystrom

The cause is one line of the per-knowledge-base manual read the wrong way.
`author: human:owner` on a `sources` entry means the OneNote page is his —
his notebook, his minutes. It does not mean he wrote the mail pasted into it.
A compile agent reading the frontmatter rather than the page attributes every
act on the page to the page's owner, and in two of the seven the vault owner was not
even a participant.

**How it works.** For every sentence naming a person as the originator of
something — called, convened, briefed, announced, offered, wrote to — and
carrying a footnote, the footnote is resolved to its page and the page's own
`**Von:**` headers and `(Besprechungsorganisator)` markers are read. A hit is
a sentence whose named person appears in none of them.

**Three rules the first three drafts of this script got wrong, each costing a
false positive, and each worth keeping:**

1. **Read every `Von:` on the page, not the first.** A pasted mail chain runs
   newest first, so the top header is the last reply. `2016-08-23-lizenzen-
   sccm-scsm-sma.md` opens with Lorenz Hafner and carries two the vault owner
   messages below it; reading only the top called a correct sentence wrong.
2. **Normalise the apostrophe names.** `Almeida` and `D'Almeida` are the same
   man, and the page writes the second.
3. **It cannot see passive voice.** "Ettore Ravelli invited alongside the
   standing members" means he *was* invited. This is the one shape the scan
   reports and should not, and there is no cheap way to tell subject from
   object here, so it stays a reported hit for a reader to dismiss.

**It is a tool rather than a `verify.py` check**, on the same footing as
`namescan.py`: it measures and a person judges. Precision on `Gamma_kb` after
the three rules above is two hits, both of them shape 3. Whether it earns a
gauge in `verify.py` is an open action item, and the number to decide it on is
how many true positives it finds in a bundle nobody has swept — `Alpha_kb` is
the obvious test.

Usage:  python3 _scripts/attribution-scan.py <KB> [more KBs...]
"""
import os
import re
import sys

import yaml

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERBS = (r'(?:called|convened|organised|set the brief|briefed|announced'
         r'|offered|invited|wrote to|put the question|opened the|sent the)')

# Sentence and section words that start a clause and are not names.
STOP = {'She', 'He', 'They', 'It', 'Alternatives', 'Outcome', 'Situation',
        'Decision', 'Argument', 'Notes', 'Record', 'Purpose', 'Period',
        'Scope', 'Course', 'Mandate', 'Structure', 'Changes', 'Related',
        'Full', 'Mini', 'The', 'This', 'That', 'Both', 'Each', 'One', 'Two',
        'Three', 'Every', 'Another', 'Its', 'His', 'Her', 'Their'}

CLAIM = re.compile(r'(?<![\w`])([A-ZÄÖÜ][a-zäöü]+(?:\s+[A-ZÄÖÜ][a-zäöü]+)?)'
                   r'\s+' + VERBS + r'\b[^\n]{0,400}?\[\^([A-Za-z0-9_-]+)\]')
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)


def page_people(path):
    """Everyone the page presents as an author: every mail header, every
    meeting organiser. Rule 1 above is why this returns a list."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            t = fh.read(60000)
    except OSError:
        return None
    who = re.findall(r'(?m)^\*\*Von:\*\*\s*(.+)$', t)
    who += re.findall(r'\[([^\]]+)\]\([^)]*\)\s*\(Besprechungsorganisator\)', t)
    return who or None


def names(s):
    """The name words in a string, apostrophes folded away (rule 2)."""
    s = re.sub(r'<[^>]*>', '', s)
    s = re.sub(r'\(mailto:[^)]*\)', '', s)
    out = set()
    for w in re.findall(r"[A-ZÄÖÜ][\wäöüéèà'’-]{2,}", s):
        w = w.lower().strip(",;'’")
        out.add(w)
        if "'" in w or '’' in w:
            out.add(re.split(r"['’]", w)[-1])
    return out


def organisations(kbs):
    """Vendor and org-unit filenames. A company acts through a person, so
    "Ontrex offered ..." is not this defect."""
    out = set()
    for kb in kbs:
        for group in ('systems/vendors', 'organisation'):
            d = os.path.join(VAULT, kb, 'Wiki', group)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.endswith('.md') and f != 'index.md':
                    out.add(f[:-3].replace('-', ' '))
    return out


def scan(kbs):
    orgs = organisations(kbs)
    hits = []
    for kb in kbs:
        root = os.path.join(VAULT, kb, 'Wiki')
        for d, _, files in os.walk(root):
            if '_to_delete' in d:
                continue
            for f in sorted(files):
                if not f.endswith('.md') or f in ('index.md', 'log.md',
                                                  'questions.md'):
                    continue
                p = os.path.join(d, f)
                s = open(p, encoding='utf-8').read()
                m = FM.match(s)
                if not m:
                    continue
                try:
                    fm = yaml.safe_load(m.group(1)) or {}
                except Exception:
                    continue
                byid = {e['id']: e for e in (fm.get('sources') or [])
                        if isinstance(e, dict) and e.get('id')
                        and e.get('resource')}
                body = re.sub(r'```.*?```', '', s[m.end():], flags=re.S)
                for sm in CLAIM.finditer(body):
                    who, lab = sm.group(1), sm.group(2)
                    if who.split()[0] in STOP or who.lower() in orgs:
                        continue
                    e = byid.get(lab)
                    if not e:
                        continue
                    tgt = os.path.normpath(os.path.join(d, str(e['resource'])))
                    pp = page_people(tgt)
                    if not pp:
                        continue
                    if any(names(who) & names(x) for x in pp):
                        continue
                    hits.append((os.path.relpath(p, VAULT), who, lab,
                                 os.path.basename(tgt), pp))
    return hits


def main():
    kbs = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not kbs:
        print('usage: python3 _scripts/attribution-scan.py <KB> [more KBs...]')
        return 1
    hits = scan(kbs)
    for rel, who, lab, page, pp in hits:
        print(rel)
        print('    claim      %s ... [^%s]' % (who, lab))
        print('    page       %s' % page)
        print('    names      %s' % '; '.join(x.strip()[:48] for x in pp[:4]))
    print('%d sentence(s) attribute an act to someone the cited page does not '
          'present as its author. Read each: a passive construction reads the '
          'same to this scan and is not a defect.' % len(hits))
    return 0


if __name__ == '__main__':
    sys.exit(main())
