#!/usr/bin/env python3
"""Canonical mechanical audit for the 00_Cerebrum vault.

This file is the executable memory of every mechanical defect class found so
far. The operating rule, from 00_Cerebrum/CLAUDE.md: a defect class is not
fixed until this script catches its recurrence. Prose in the skill explains
why a check exists; this script is the check.

Read-only over the corpus: it reports, the librarian repairs. The one
thing it writes is its own memory, _scripts/verify-state.json, which records
how many distinct run-days each finding has stood.

Usage:  python3 _scripts/verify.py [KnowledgeBase ...]   (default: all)
Exit code 1 if any DEFECT. FINDINGS do not fail the run on sight: dead links
and orphans are legitimate under OKF and deserve eyes, not alarms. But a
finding is a question, and questions do not get to stand unanswered: one
seen on three distinct run-days escalates to a DEFECT unless assertions.yaml
carries a finding_waivers entry saying why it may stand. Standing noise
trains the reader to skip the findings block, which is how a real one dies.
Bundle-level gauges (the contradiction-candidate count) never escalate; they
are backlog meters, drained by the health check's sweep cursor.
"""
import collections
import datetime
import importlib.util as _ilu
import fnmatch
import glob
import itertools
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    sys.exit('verify.py needs PyYAML, which this Python does not have.\n'
             'Install it with:\n'
             '    python3 -m pip install --user pyyaml\n'
             'If pip refuses with "externally-managed-environment", add\n'
             '--break-system-packages. Do not reach for that flag first: it is\n'
             'pip 23.0+, and the macOS Command Line Tools pip predates\n'
             'it and fails with "no such option". Learned 15.08.2026.')

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# A link whose path names a sibling knowledge base. Used to separate a
# broken cross-bundle path (a defect) from an unwritten in-bundle concept
# (a legitimate OKF placeholder). Added 15.08.2026.
CROSS_KB = re.compile(r'(?:^|/)[A-Za-z0-9_]+_kb/')
FM = re.compile(r'^---\n(.*?)\n---\n', re.S)
FENCE = re.compile(r'```.*?```', re.S)
INLINE_CODE = re.compile(r'`[^`\n]+`')
FOOTNOTE = re.compile(r'\[\^([^\]]+)\]')
FIRST_PERSON = re.compile(
    # The look-behind excluded letters only, so `S4I record` — the S4I
    # organisational record — read as a librarian saying "I record"
    # and failed a clean concept (Alpha_kb, 22.08.2026). Digits belong in
    # the class: an acronym ending in a digit then I is not a pronoun.
    #
    # This enumerated twelve fixed phrases until 22.08.2026, ten of them the
    # pronoun with a *present-tense* verb — use, carry, read, treat, have,
    # take, keep, record, found, chose. The past tense of those same verbs
    # walked straight through, and fifteen instances in twelve Gamma
    # concepts survived the sweep that rewrote ninety-six. A list of phrases
    # catches the phrases somebody thought of; the shape to match is the
    # pronoun with a word after it, whatever the word.
    #
    # So the shape is `I` plus a lowercase word. That alone over-matches, and
    # it over-matches on one thing: roman numerals. This corpus is full of
    # EP I, Phase I, Part I, Workshop I, and `Part I was reissued in French`
    # is not a librarian speaking. `clause_open` below is the other half of
    # the test, and a verb list could never have made that distinction —
    # `Phase I consolidated several packages` has a perfectly good verb in it.
    r'(?<![A-Za-z0-9])(I [a-z]{2,}|my reading|my own reading|in my view|'
    r'to my (knowledge|mind))(?![A-Za-z])')

# Words a pronoun can sit behind. A roman numeral sits behind the noun it
# numbers — Phase, Part, Workshop, EP, project — and no noun is in this set.
FP_CONNECTORS = {
    'and', 'but', 'so', 'or', 'nor', 'yet', 'that', 'which', 'what', 'where',
    'when', 'while', 'whether', 'because', 'since', 'though', 'although',
    'if', 'as', 'then', 'why', 'how', 'before', 'after', 'until', 'unless',
}
FP_TAIL_WORD = re.compile(r'([A-Za-z]+)$')
# A bare capital letter used as a label, in a list with other bare capital
# letters: the ToT rounds lettered C, L and I, and the spreadsheet columns
# G, I and K. Same class as the roman numerals — a letter naming something
# rather than a pronoun — but it opens a clause after `and` or a comma, so
# `clause_open` passes it. Both live instances were found on 22.08.2026.
FP_LETTER_LIST = re.compile(r'(?<![A-Za-z0-9])[A-HJ-Z](?![A-Za-z0-9])')


def letter_list(body, start, end):
    """True when this `I` sits among other bare capital letters."""
    ls = body.rfind('\n', 0, start) + 1
    le = body.find('\n', end)
    le = len(body) if le == -1 else le
    window = body[max(ls, start - 40):min(le, end + 40)]
    return bool(FP_LETTER_LIST.search(window))


def clause_open(body, start):
    """True when the `I` at *start* opens a clause, and so is a pronoun."""
    ls = body.rfind('\n', 0, start) + 1
    before = body[ls:start].rstrip()
    if not before:
        return True
    if before[-1] in '.,;:!?\u2014\u2013("*|>[':
        return True
    w = FP_TAIL_WORD.search(before)
    return bool(w) and w.group(1).lower() in FP_CONNECTORS
# A footnote definition contains the same [^label] shape as a reference, so a
# single regex counts `[^x]: source` as a use of x. That made the "source ids
# never cited" finding unable to fire whenever the dropped claim had left its
# definition line behind, which is the usual way it happens: 19 such ids stood
# across three knowledge bases while the check reported none (found
# 15.08.2026, Gamma_kb). References are counted separately from definitions.
FOOTREF = re.compile(r'\[\^([^\]]+)\](?!:)')
MDLINK = re.compile(r'\]\(([^)#\s]+\.md)\)')
PRESENT = re.compile(
    r'\b(currently|at present|as of today|still in use|remains in place)\b', re.I)
# A concept saying that somebody "has no concept yet" is a claim about the
# bundle, and the bundle changes underneath it. Nine people concepts were
# written on 09.08.2026 and five sentences elsewhere went on saying those
# people had no page (found 15.08.2026, Beta_kb). The claim is mechanically
# decidable, so it is checked rather than trusted.
NOCONCEPT = re.compile(r'[^.\n]*?\bno\s+concepts?\b[^.\n]*', re.I)
NAME2 = re.compile(r'\b([A-Z\u00c4\u00d6\u00dc][a-z\u00e4\u00f6\u00fc]+)'
                   r'\s+([A-Z\u00c4\u00d6\u00dc][a-z\u00e4\u00f6\u00fc]+)\b')


def translit(s):
    for a, b in (('\u00e4', 'ae'), ('\u00f6', 'oe'), ('\u00fc', 'ue'),
                 ('\u00df', 'ss'), ('\u00c4', 'Ae'), ('\u00d6', 'Oe'),
                 ('\u00dc', 'Ue'), ('\u00e9', 'e'), ('\u00e8', 'e'),
                 ('\u00e0', 'a')):
        s = s.replace(a, b)
    return s.lower()


def discover():
    return sorted(d for d in os.listdir(VAULT)
                  if os.path.isdir(os.path.join(VAULT, d, 'Wiki'))
                  and os.path.exists(os.path.join(VAULT, d, 'CLAUDE.md')))


def _load_coverage():
    """`coverage.py` as a module, so `archive_layer` has one definition.

    Copying the key's default would give this vault two places that decide
    where a bundle's archive lives, and the next edit would land in one of
    them. That is the failure this import exists to make impossible.
    """
    spec = _ilu.spec_from_file_location(
        'cerebrum_coverage', os.path.join(VAULT, '_scripts', 'coverage.py'))
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_coverage = _load_coverage()


def assertions(kb):
    p = os.path.join(VAULT, kb, 'assertions.yaml')
    if not os.path.exists(p):
        return {}
    return yaml.safe_load(open(p, encoding='utf-8')) or {}


_CHANGELOG_CACHE = {}


def changelog(kb):
    if kb not in _CHANGELOG_CACHE:
        f = os.path.join(VAULT, kb, 'CHANGELOG.md')
        _CHANGELOG_CACHE[kb] = (open(f, encoding='utf-8').read()
                                if os.path.exists(f) else '')
    return _CHANGELOG_CACHE[kb]


def source_real_date(concept_dir, src):
    """The cited page's own timestamp, or None when it cannot be read.

    A citation's `last_modified` is a **semantic** date: the house rule dates
    an archive page from its bare YYYYMMDD title, which for a scheduled meeting
    is the meeting date and can fall later than the day the page was written.
    The page's own exporter frontmatter carries a real one. Comparing
    generated.at against the semantic date reports a concept as stale when all
    that happened is the calendar moving past a meeting it cited.

    Added 28.08.2026. The freshness check already knew about this case and
    guarded it by ignoring sources dated after **today** — which is correct on
    the day a concept is written and decays from then on. Eight Alpha concepts
    citing the LK meeting of 25.08.2026 passed on 22. and 23.08.2026 and failed
    on the 28th, having not changed. The guard is now anchored to a real
    timestamp instead of to the run date.
    """
    tgt = os.path.normpath(os.path.join(concept_dir, str(src.get('resource', ''))))
    if not os.path.isfile(tgt):
        return None
    try:
        with open(tgt, encoding='utf-8', errors='replace') as fh:
            head = fh.read(2048)          # frontmatter only; these run 2-4 KB
    except OSError:
        return None
    for key in ('modified', 'created'):
        m = re.search(r'(?m)^%s:\s*["\']?(\d{4}-\d{2}-\d{2})' % key, head)
        if m:
            return m.group(1)
    return None


def audit(kb):
    A = assertions(kb)
    root = os.path.join(VAULT, kb)
    defects, findings = [], []
    concepts, resources = {}, {}
    citations = 0
    # An archive layer whose folder exists but holds no pages means "deleted,
    # awaiting replacement" rather than "this knowledge base never had one".
    # See the note at the citation check below for why that distinction earns
    # its keep.
    _arch = os.path.join(root, 'OneNote')
    archive_absent = os.path.isdir(_arch) and not any(
        fn.endswith('.md') for _, _, fns in os.walk(_arch) for fn in fns)
    absent_cites = 0
    person_pages = {os.path.basename(p)[:-3] for p in
                    glob.glob(os.path.join(root, 'Wiki', '**', 'people',
                                           '*.md'), recursive=True)
                    + glob.glob(os.path.join(root, 'Wiki', 'people', '*.md'))
                    if os.path.basename(p) != 'index.md'}

    for f in sorted(glob.glob(os.path.join(root, 'Wiki', '**', '*.md'),
                              recursive=True)):
        if '_to_delete' in f or os.path.basename(f) in ('index.md', 'log.md'):
            continue
        rel = os.path.relpath(f, root)
        raw = open(f, encoding='utf-8').read()
        text = FENCE.sub('', raw)
        m = FM.match(text)
        if not m:
            defects.append((rel, 'frontmatter missing'))
            continue
        try:
            fm = yaml.safe_load(m.group(1))
        except Exception as e:
            defects.append((rel, 'frontmatter unparseable: '
                            + str(e).split('\n')[0]))
            continue
        body = text[m.end():]
        concepts[f] = (fm, body)

        if not fm.get('type'):
            defects.append((rel, 'type missing'))
        srcs = fm.get('sources') or []
        if not srcs and not rel.endswith(os.path.join('Wiki', 'questions.md')):
            defects.append((rel, 'sources missing'))
        # A verified key is legitimate, and only when the CHANGELOG records
        # the confirmation that produced it. Until 15.08.2026 this forbade the
        # key outright, which was the right guard while nothing was verified
        # and the wrong one the moment a verification sitting happened: it
        # would have failed the audit for doing exactly what the skill asks.
        # The rule it now encodes is the skill's own — no verified key unless
        # a prior CHANGELOG entry records the human confirmation behind it.
        v = fm.get('verified')
        if v:
            by = str((v or {}).get('by', ''))
            if not by.startswith('human:'):
                defects.append((rel, 'verified.by is not a human actor: ' + by))
            elif os.path.basename(rel) not in changelog(kb):
                defects.append((rel, 'verified key present but no CHANGELOG '
                                     'entry records the confirmation'))

        ids, res = set(), set()
        d = os.path.dirname(f)
        for s in srcs:
            if not isinstance(s, dict):
                defects.append((rel, 'malformed sources entry'))
                continue
            if s.get('id'):
                ids.add(s['id'])
            r = s.get('resource')
            if r:
                citations += 1
                tgt = os.path.normpath(os.path.join(d, r))
                res.add(tgt)
                if not os.path.exists(tgt):
                    # An archive that is not on disk is a different thing
                    # from a wrong path, and conflating them is how a
                    # deliberate replacement becomes a wall of defects that
                    # wedges the pre-commit hook. Alpha's export was deleted on
                    # 16.08.2026 pending a complete one, and its eight
                    # surviving concepts cite it 123 times; every one of
                    # those paths may be perfectly correct. Count them once,
                    # as a gauge, and say so. Nothing is waived — the moment
                    # the archive is back they are checked normally again.
                    if archive_absent and os.path.abspath(tgt).startswith(
                            os.path.abspath(_arch)):
                        absent_cites += 1
                    else:
                        defects.append((rel,
                                        'citation does not resolve: ' + r))
            # An archive scope the owner has barred. Not a gap, not a
            # queue: an instruction. Zeta_kb's private archive was
            # offered for compiling three times across 09.08, 15.08 and
            # 22.08.2026, twice after being told not to, because the state
            # files recorded it as "not without asking" and a 0.0% coverage
            # row reads as a gap to anything that measures. A standing
            # instruction that lives only in prose gets re-litigated by the
            # next run; this one fails the audit instead.
            for rule in A.get('barred_scopes') or []:
                if r and re.search(rule['pattern'], r):
                    defects.append((rel, 'cites a barred archive scope: %s (%s)'
                                    % (r, ' '.join(
                                        (rule.get('reason') or '').split()))))
            for rule in A.get('source_rules') or []:
                if r and re.search(rule['resource_pattern'], r):
                    want = str(rule.get('require_last_modified'))
                    if str(s.get('last_modified')) != want:
                        defects.append((rel, 'source %s: last_modified must be '
                                        '%s (%s)' % (r, want,
                                                     rule.get('reason', ''))))
        resources[f] = res

        used = set(FOOTNOTE.findall(body))
        refs = set(FOOTREF.findall(body))
        for lab in sorted(used - ids):
            defects.append((rel, 'footnote label has no sources id: ' + lab))
        unused = ids - refs
        if unused:
            findings.append((rel, 'source ids never cited: '
                             + ', '.join(sorted(unused))))

        # A source id naming a year the document it points at does not carry.
        # Swept on 15.08.2026 under AI-2026-08-15-4, after `revision-2019` in
        # organisation/cam-board.md was found bound to a Kernteam page of
        # January 2017 while naming the February 2019 audit correctly in four
        # other concepts. The sweep found six more of the same shape, and the
        # fault is worse than a misleading name: in every case the concept
        # carried claims from two documents under one footnote label, so the
        # claims belonging to the other one resolved to a page that does not
        # state them.
        #
        # OneNote export filenames carry the export date first and the content
        # date in two-digit form — 2018-08-28-20-12-17-damien-corti.md is the
        # interview of 20.12.2017 — so a two-digit match counts. Without that
        # allowance the check reports six false positives and gets ignored.
        for s2 in srcs:
            if not isinstance(s2, dict):
                continue
            sid = str(s2.get('id', ''))
            ym = re.search(r'(?:^|[-_])(20[0-2]\d)(?:[-_]|$)', sid)
            if not ym:
                continue
            yr = ym.group(1)
            # Compare against the resource path **and the document's own
            # title line**, never against the concept's `title` or
            # `last_modified` — those are written by whatever wrote the
            # resource, so they corroborate nothing, and on 15.08.2026 a test
            # that left them correct while pointing the resource elsewhere
            # passed a check that should have failed.
            #
            # The document's own title is what the archive hazard note calls
            # authoritative: OneNote export filenames carry the export date,
            # so `2018-09-03-tot-3.md` is titled "2020 10 20 - ToT" and is the
            # ToT of 20.10.2020. Reading the title clears about fifty findings
            # that are the hazard rather than a fault — and a findings block
            # that is mostly noise is one the reader learns to skip.
            hay = str(s2.get('resource', ''))
            tgt = os.path.normpath(os.path.join(d, hay))
            if os.path.exists(tgt):
                try:
                    with open(tgt, encoding='utf-8', errors='replace') as fh:
                        # The whole page, not a window. 400 characters
                        # stopped short of the pasted mail header where the
                        # real date lives; 1'200 then stopped short of the
                        # rolling boards. `Tips & Ticks` was created on
                        # 03.06.2019 and is still written into in 2026,
                        # carrying 2020, 2022, 2024 and 2026 figures far
                        # down the page, so five correct ids were reported
                        # as wrong and escalated to defects on 18.08.2026.
                        # These pages run 2-4 KB; reading all of one costs
                        # nothing and removes the whole class of window bug.
                        hay += ' ' + fh.read()
                except OSError:
                    pass
            if yr in hay or ('-' + yr[2:] + '-') in hay:
                continue
            findings.append((rel, 'source id %r names %s and its document '
                                  'carries no such date: %s'
                             % (sid, yr, os.path.basename(str(
                                 s2.get('resource', ''))))))

        g = str((fm.get('generated') or {}).get('at', ''))[:10]
        lms = [str(s.get('last_modified'))[:10] for s in srcs
               if isinstance(s, dict) and s.get('last_modified')
               and str(s.get('last_modified')) != 'unknown']
        # Only sources that already exist can date a concept. A live notebook
        # holds scheduled future meetings — the Alpha export of 21.08.2026 has
        # pages dated 25.08.2026 — and comparing generated.at against one of
        # those says the concept is stale when it is not. Four concepts failed
        # that way on the Alpha rebuild. Future-dated sources are reported
        # separately instead, because a date after the run is either a
        # scheduled meeting or a typo and both are worth seeing.
        _today = datetime.date.today().isoformat()
        past = [x for x in lms if x <= _today]
        ahead = [x for x in lms if x > _today]
        if g and past and max(past) > g:
            # The cheap comparison fired. Before calling it a defect, check
            # each implicated source against its own page timestamp, which is
            # real where the citation's date is semantic. A page that cannot
            # be read keeps the old behaviour and is still reported.
            stale = []
            for s3 in srcs:
                if not isinstance(s3, dict):
                    continue
                lm3 = str(s3.get('last_modified', ''))[:10]
                if not lm3 or lm3 == 'unknown' or lm3 <= g or lm3 > _today:
                    continue
                real = source_real_date(d, s3)
                if real is None or real > g:
                    stale.append(real or lm3)
            if stale:
                defects.append((rel, 'generated.at %s older than newest cited '
                                     'source %s' % (g, max(stale))))
        if ahead:
            findings.append((rel, '%d cited source(s) dated after today, '
                                  'newest %s: a scheduled future page, or a '
                                  'wrong date' % (len(ahead), max(ahead))))

        # A date in the future. Found 15.08.2026: a health-check sub-agent
        # working near midnight stamped its whole run a day ahead — CHANGELOG
        # heading, report filename, two drafted concepts and two action item
        # ids. Nothing was missing and every path resolved, so no check saw
        # it, and the vault's own arithmetic runs on run-days. A stamp that
        # has not happened yet is never right, so this is a defect rather
        # than a finding.
        if g and g > datetime.date.today().isoformat():
            defects.append((rel, 'generated.at %s is in the future' % g))

        # A concept speaking in the first person. Settled 15.08.2026, after
        # the owner read "I use this table to place people in streams" and
        # asked whether the "I" was his. It was the librarian's. In a corpus
        # built from one person's own notes that ambiguity is not stylistic:
        # a reader cannot tell whether "I use Meyer" records the owner's
        # naming preference or a compile agent's tie-break. 96 instances were
        # rewritten into the concept's own voice that day. Quotes and the
        # bracketed glosses that translate them are exempt, because there the
        # "I" belongs to the person quoted and must stay verbatim.
        for m in FIRST_PERSON.finditer(body):
            if m.group(0)[0] == 'I' and (
                    not clause_open(body, m.start())
                    or letter_list(body, m.start(), m.end())):
                continue
            lb = body.rfind('[', 0, m.start())
            rb = body.find(']', m.end())
            if lb != -1 and rb != -1 and '\n' not in body[lb:rb] \
                    and '](' not in body[lb:rb]:
                continue
            ls = body.rfind('\n', 0, m.start()) + 1
            if body[ls:m.start()].count('"') % 2 == 1:
                continue
            defects.append((rel, 'concept speaks in the first person; the '
                                 'voice is the librarian\'s and reads as the '
                                 'owner\'s: %r' % m.group(0)))
            break

        # The promotion rule, settled 15.08.2026 as AI-2026-08-15-4. `status`
        # is lifecycle, not trust — trust is derived from `verified` and is a
        # separate question. So a concept is `draft` only while it names
        # something unsettled that would change what it says, and `stable`
        # once it does not. That is not a new invention: it is what
        # Zeta_kb was already doing, where three concepts distilling a
        # closed published document sit at stable and the fourth sits at
        # draft under a heading saying which two of its claims are unverified.
        # The defect the item found was nine concepts at draft with no reason
        # given, which makes the field decorative.
        #
        # Opt-in per knowledge base via assertions.yaml `draft_needs_reason`,
        # because the three employer bundles hold 589 drafts that predate the
        # rule and flipping them is the owner's call, not the audit's.
        if A.get('draft_needs_reason') and fm.get('status') == 'draft' \
                and '`status: draft`' not in body:
            findings.append((rel, 'status is draft and the concept does not '
                                  'say why; a draft with no stated reason is '
                                  'a field nobody can act on'))

        sa = fm.get('stale_after')
        if sa and str(sa)[:10] < datetime.date.today().isoformat():
            findings.append((rel, 'past stale_after ' + str(sa)[:10]))
        # Quoted spans and bracketed glosses are verbatim or near-verbatim
        # source material, exempt from the tense rule by policy. Both false
        # positives of 10.08.2026 were this: "currently" inside an English
        # gloss of a German mail, and inside an action item quoting the word.
        own_prose = re.sub(r'"[^"\n]*"|\[[^\]\n]*\]', ' ', body)
        if not sa and PRESENT.search(own_prose):
            findings.append((rel, 'present-tense claim with no stale_after: '
                                  '"%s"' % PRESENT.search(own_prose).group(0)))

        # A paragraph glued to the one above it. The compile merge writes a
        # concept paragraph per line, so a line that ends in a footnote
        # reference and is followed immediately by a new sentence, with no
        # blank line between, renders as one run-on paragraph in Obsidian and
        # in the viewer. Found 16.08.2026 by counting em dashes per paragraph:
        # a paragraph with four of them turned out to be two paragraphs stuck
        # together. 222 occurrences across 98 concepts in Beta_kb that day, all
        # invisible to every check the audit had, because nothing was missing
        # and nothing failed to resolve.
        blines = body.split('\n')
        glued = 0
        infence = False
        for i in range(len(blines) - 1):
            a, b = blines[i], blines[i + 1]
            if a.strip().startswith('```'):
                infence = not infence
                continue
            if infence or not re.search(r'\[\^[^\]\s]+\]\s*$', a):
                continue
            if a.lstrip() != a or a.lstrip().startswith(('|', '*', '-', '#',
                                                         '>', '[^')):
                continue
            if not b.strip() or b.lstrip() != b:
                continue
            if b.startswith(('|', '*', '-', '#', '>', '[^', '```')):
                continue
            if b[:1].isupper() or b[:1] == '"' or re.match(r'\[[^\^\]]+\]\(',
                                                          b):
                glued += 1
        if glued:
            findings.append((rel, '%d paragraph(s) run on: a line ending in a '
                                  'footnote reference is followed by a new '
                                  'sentence with no blank line between'
                             % glued))

        # The rest of the merge-artefact family, added 22.08.2026 after the
        # four health checks of that day found the same untested cause in
        # three knowledge bases at once: merge-appends.py joining an appended
        # chunk to what precedes it with a single newline. The run-on check
        # above sees one symptom of it, the one where prose met prose. These
        # are the others, and between them they accounted for 598 repairs
        # that verify.py was green on both before and after — a rendering
        # fault is invisible to a checker that only asks whether things
        # resolve. Repairs live in _scripts/fix-tablebreaks.py and
        # _scripts/fix-glosses.py; this is what stops the class returning.
        lines = body.split('\n')
        pipes = headerless = 0
        infence = False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith('```'):
                infence = not infence
                continue
            if infence:
                continue
            row = ln.lstrip().startswith('|') and ln.rstrip().endswith('|')
            if not row:
                continue
            prev = lines[i - 1] if i else ''
            # A table row directly under prose: GFM swallows it into the
            # paragraph and the reader sees literal pipe characters.
            if prev.strip() and not prev.lstrip().startswith(('|', '#', '>')):
                pipes += 1
            # A table whose first row is data rather than a header, because
            # the header stayed behind with the table it was split from. The
            # separator row is what distinguishes the two.
            elif not prev.strip() and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt.startswith('|') and not re.match(r'^\|[\s:|-]+\|$', nxt):
                    headerless += 1
        if pipes:
            findings.append((rel, '%d table row(s) sit directly under prose '
                                  'and render as literal pipes; run python3 '
                                  '_scripts/fix-tablebreaks.py' % pipes))
        if headerless:
            findings.append((rel, '%d table(s) start on a data row, so the '
                                  'first row is lost to header styling; run '
                                  'python3 _scripts/fix-tablebreaks.py'
                             % headerless))

        # A run of rows whose width differs from the table it sits in. This
        # is the shape the other two checks cannot see, because both sides
        # are well-formed tables: `optimierung-druckerlandschaft.md` carried
        # four `Date | Event` rows appended under a `Story line | Argument`
        # table, and they matched that table's width exactly. Nothing looked
        # wrong to a parser, and a reader saw 2023-08-30 presented as a story
        # line. Found 22.08.2026, after fix-tablebreaks.py refused to move
        # them and was right to: by column count they belonged where they lay.
        #
        # Escaped pipes are neutralised first. `IK-Session 02\|23` is one
        # cell containing a pipe, not two cells, and counting it as two makes
        # every table holding an escaped pipe look broken.
        widths = 0
        run_w = None
        for ln in FENCE.sub('', body).split('\n'):
            if not ln.lstrip().startswith('|'):
                run_w = None
                continue
            bare = ln.replace('\\|', '')
            if re.match(r'^\s*\|[\s:|-]+\|\s*$', bare):
                continue
            n = bare.count('|')
            if run_w is None:
                run_w = n
            elif n != run_w:
                widths += 1
                run_w = n
        if widths:
            findings.append((rel, '%d row run(s) differ in column count from '
                                  'the table they sit in; run python3 '
                                  '_scripts/fix-tablebreaks.py --widths'
                             % widths))

        # A link description cut mid-word. The orphan sweep of 15.08.2026
        # glossed each bullet from the target concept's own `description` and
        # truncated at 110 characters on a character boundary, so 44 of them
        # ended inside a word: "copying home-driv", "non-customis". The full
        # text was on disk the whole time, which is what makes this a
        # restoration rather than a rewrite.
        cut = 0
        for m in re.finditer(r'^\s*[*-] \[[^\]]+\]\((?!http)([^)\n]+\.md)\)'
                             r' — (.+)$', body, re.M):
            g = m.group(2).rstrip()
            if not (100 <= len(g) <= 115) or g.endswith(('.', '!', '?')):
                continue
            tgt = os.path.normpath(os.path.join(d, m.group(1)))
            if not os.path.exists(tgt):
                continue
            t2 = FENCE.sub('', open(tgt, encoding='utf-8',
                                    errors='replace').read())
            m2 = FM.match(t2)
            if not m2:
                continue
            try:
                desc = ' '.join(str((yaml.safe_load(m2.group(1)) or {})
                                    .get('description') or '').split())
            except Exception:
                continue
            if desc and desc != g and desc.startswith(g):
                cut += 1
        if cut:
            findings.append((rel, '%d link description(s) truncated mid-word; '
                                  'run python3 _scripts/fix-glosses.py' % cut))

        # Stale "has no concept" claims. Exempt questions.md: its action
        # items table quotes the raising text of closed items verbatim, and
        # that quotation is history rather than a live claim.
        if not rel.endswith('questions.md'):
            for sent in NOCONCEPT.findall(body):
                for first, last in NAME2.findall(sent):
                    slug = translit(first + '-' + last)
                    if slug in person_pages:
                        findings.append(
                            (rel, 'says %s has no concept, but Wiki/people/'
                                  '%s.md exists' % (first + ' ' + last, slug)))

        # Forbidden strings are about prose, not about quoted code. The
        # wikilink guard fired on `[[ ]]` inside backticks — Bash test syntax
        # quoted verbatim from an interview exercise, which is exactly the
        # kind of source material a concept is supposed to carry (Alpha_kb,
        # 22.08.2026). Fenced blocks were already stripped from `text`;
        # inline code spans were not.
        prose = INLINE_CODE.sub(' ', text)
        for rule in A.get('forbid') or []:
            if any(fnmatch.fnmatch(rel, pat)
                   for pat in rule.get('exempt') or []):
                continue
            # 'only' scopes a rule to named concepts. Added 15.08.2026: a
            # settled fact about one person cannot be expressed as a rule over
            # the whole bundle, because the forbidden string is correct
            # everywhere else. Without it the Noor Tekin pronoun defect had
            # no executable guard at all.
            only = rule.get('only')
            if only and not any(fnmatch.fnmatch(rel, pat) for pat in only):
                continue
            if re.search(rule['pattern'], prose):
                defects.append((rel, 'forbidden pattern %r: %s'
                                % (rule['pattern'], rule.get('reason', ''))))

        # A settled correction restated without its correction. When a claim
        # is superseded but still legitimately narratable as the plan that was
        # abandoned, forbidding the string is wrong and saying nothing lets the
        # old reading spread to every coupled concept. Found 09.08.2026: the
        # FastTrack correction of that morning had reached the decision
        # concept and none of the three concepts sharing its sources.
        for rule in A.get('require_together') or []:
            if any(fnmatch.fnmatch(rel, pat)
                   for pat in rule.get('exempt') or []):
                continue
            if (re.search(rule['if_pattern'], text)
                    and not re.search(rule['then_pattern'], text)):
                defects.append((rel, 'states %r without %r: %s'
                                % (rule['if_pattern'], rule['then_pattern'],
                                   rule.get('reason', ''))))

        # Index accuracy is checked once per directory, below, against
        # reindex.py rather than by looking for the filename. The filename
        # test was all this did until 15.08.2026, and it is far weaker than it
        # reads: it passes an index whose description is a truncated version
        # of the concept's own, and it passes an index still listing a concept
        # that no longer exists. Seven truncated entries were sitting in
        # Beta_kb/Wiki/people/index.md while this check reported the bundle
        # clean. The vault manual has always required an index to quote the
        # current `description`; nothing was enforcing it.

    # The same future-stamp class, one level up: an action item id and a
    # CHANGELOG heading both carry the run's date, and both were wrong in the
    # same incident. Ids are never reused, so a future-dated one is a
    # correction that gets more expensive the longer it stands.
    _today = datetime.date.today().isoformat()
    _q = os.path.join(root, 'Wiki', 'questions.md')
    if os.path.exists(_q):
        for _id in sorted(set(re.findall(r'AI-(\d{4}-\d{2}-\d{2})-\d+',
                                         open(_q, encoding='utf-8').read()))):
            if _id > _today:
                defects.append(('Wiki/questions.md', 'action item id dated in '
                                'the future: AI-%s-n' % _id))
    _cl = os.path.join(root, 'CHANGELOG.md')
    if os.path.exists(_cl):
        for _h in sorted(set(re.findall(r'^## (\d{4}-\d{2}-\d{2})',
                                        open(_cl, encoding='utf-8').read(),
                                        re.M))):
            if _h > _today:
                defects.append(('CHANGELOG.md', 'entry dated in the future: '
                                + _h))

    # Index accuracy, against the generator. reindex.py is the definition of
    # a correct index, so the check is simply whether it would change one.
    # A finding rather than a defect: an index is derived and the repair is
    # one command, `python3 _scripts/reindex.py`.
    try:
        import reindex
        for idx in sorted(glob.glob(os.path.join(root, 'Wiki', '**',
                                                 'index.md'), recursive=True)):
            if os.path.dirname(idx) == os.path.join(root, 'Wiki') \
                    or '_to_delete' in idx:
                continue
            want = reindex.rebuild(idx)
            if want is not None and want != open(idx, encoding='utf-8').read():
                findings.append((os.path.relpath(idx, root),
                                 'index does not match its directory; run '
                                 'python3 _scripts/reindex.py'))
    except ImportError:
        pass

    # Archive coverage, measured rather than asserted. Until 15.08.2026
    # coverage answered "does a concept exist for this scope", which is a
    # question about the bundle: Alpha read as fully compiled while 10'122 of
    # 10'561 pages had never been cited. COVERAGE.md carries the measurement
    # and .coverage-state.json the bundle state it was taken from, so a
    # bundle that has moved on since the last measurement fails here rather
    # than quietly publishing a stale percentage.
    # The layer is `OneNote` for the bundles whose corpus came from OneNote and
    # whatever `assertions.yaml` declares for the ones whose did not. Read it
    # from coverage.py rather than restating it: this check tested a literal
    # `OneNote/` until 31.08.2026, so `Epsilon_kb` — which declares `Raw` and had
    # been measured at 100 per cent that morning — carried a COVERAGE.md and a
    # .coverage-state.json that nothing compared, from the hour they were
    # written. The state file's whole job is to fail a bundle that has moved on
    # since its last measurement, and it was doing that job unwatched. The key
    # was taught to coverage.py and not to the second script reading the same
    # fact, which is this vault's duplication-plus-edit hazard one layer below
    # where it has been caught before.
    cov = os.path.join(root, 'COVERAGE.md')
    cst = os.path.join(root, '.coverage-state.json')
    if os.path.isdir(os.path.join(root, _coverage.archive_layer(kb))):
        if not os.path.exists(cov):
            defects.append(('COVERAGE.md', 'archive coverage never measured; '
                            'run python3 _scripts/coverage.py'))
        else:
            import json as _json
            want = {'concepts': 0, 'citations': 0}
            for f2, (fm2, body2) in concepts.items():
                want['concepts'] += 1
                want['citations'] += len([1 for s2 in (fm2.get('sources') or [])
                                          if isinstance(s2, dict)
                                          and s2.get('resource')])
            try:
                got = _json.load(open(cst, encoding='utf-8'))
            except Exception:
                got = None
            if got != want:
                defects.append(('COVERAGE.md', 'coverage table stale: measured '
                                'at %s, bundle now %s. Regenerate with '
                                'python3 _scripts/coverage.py'
                                % (got, want)))

    for r in A.get('require_file') or []:
        if not os.path.exists(os.path.join(root, r)):
            defects.append((r, 'required file missing (settled fact)'))

    inbound = collections.defaultdict(set)
    for f, (fm, body) in concepts.items():
        d = os.path.dirname(f)
        for tgt in MDLINK.findall(body):
            if tgt.startswith('http'):
                continue
            n = os.path.normpath(os.path.join(d, tgt))
            if n in concepts:
                inbound[n].add(f)
            elif not os.path.exists(n):
                # A dead link inside the bundle is legitimate under OKF: it
                # is how knowledge not yet written gets recorded. A link that
                # crosses into a sibling knowledge base and resolves nowhere
                # is not that. It is a wrong path, and the fault is almost
                # always depth: an agent writes ../../OtherKb/ because that
                # is right from Wiki/<group>/x.md and wrong from anywhere
                # else. merge-appends.py already re-resolves this for
                # resource: paths; nothing guarded it in body links, so one
                # sat in projects/rsi-r50-rollout.md on 15.08.2026 wearing
                # the "legitimate under OKF" label while nine siblings in the
                # same directory used the correct ../../../. Splitting the
                # check on that distinction is the whole point: a placeholder
                # and a typo must not print the same line.
                if CROSS_KB.search(tgt):
                    # A knowledge base that has been deliberately cleared
                    # pending a new archive will have inbound links pointing
                    # at concepts that are coming back. That is not a wrong
                    # path — it was right yesterday and will be right again —
                    # and the tell is that the target's own archive layer is
                    # empty. Alpha was cleared on 21.08.2026 and one Beta link
                    # into it broke; treating that as a defect would have
                    # blocked commits on the two finished bundles for as long
                    # as Alpha waited. Deferred, not waived: the moment Alpha has
                    # an archive again this is a defect like any other.
                    _m = CROSS_KB.search(tgt)
                    _kbroot = os.path.join(
                        VAULT, tgt[_m.start():].lstrip('/').split('/')[0])
                    _oth = os.path.join(_kbroot, 'OneNote')
                    if os.path.isdir(_oth) and not any(
                            fn.endswith('.md')
                            for _, _, fns in os.walk(_oth) for fn in fns):
                        findings.append((
                            os.path.relpath(f, root),
                            'link into a knowledge base that is cleared and '
                            'awaiting a new archive; unverifiable until it is '
                            'rebuilt, not waived: ' + tgt))
                        continue
                    hint = ''
                    m_kb = CROSS_KB.search(tgt)
                    # lstrip: the pattern captures the separator before
                    # the _kb segment, and a leading / makes join()
                    # discard VAULT and return an absolute path.
                    cand = os.path.join(VAULT, tgt[m_kb.start():].lstrip('/'))
                    if os.path.exists(cand):
                        hint = ('; resolves as %s'
                                % os.path.relpath(cand, d).replace(os.sep, '/'))
                    defects.append((os.path.relpath(f, root),
                                    'cross-KB link resolves nowhere: %s%s'
                                    % (tgt, hint)))
                else:
                    findings.append((os.path.relpath(f, root),
                                     'dead link (legitimate under OKF): ' + tgt))
    ok = set(A.get('orphan_ok') or [])
    for f in concepts:
        rel = os.path.relpath(f, root).replace(os.sep, '/')
        if (not inbound[f] and rel not in ok
                and not rel.endswith('questions.md')):
            findings.append((rel, 'no inbound link from any concept'))

    pairs = [(len(resources[a] & resources[b]), a, b)
             for a, b in itertools.combinations(sorted(resources), 2)
             if len(resources[a] & resources[b]) >= 3]
    if pairs:
        n, a, b = max(pairs)
        findings.append(('(bundle)',
                         '%d contradiction-candidate pairs share 3+ sources; '
                         'largest overlap %d: %s <-> %s'
                         % (len(pairs), n, os.path.relpath(a, root),
                            os.path.relpath(b, root))))

    if absent_cites:
        findings.append(('(bundle)',
                         'archive layer absent: %d citations into OneNote/ '
                         'could not be checked because the export has been '
                         'deleted pending replacement. They are not waived; '
                         'they are unverifiable until it is back'
                         % absent_cites))
    return len(concepts), citations, defects, findings


def vault_assertions():
    p = os.path.join(VAULT, 'assertions.yaml')
    if not os.path.exists(p):
        return {}
    return yaml.safe_load(open(p, encoding='utf-8')) or {}


def section_of(text, heading):
    """The body under `heading`, up to the next heading of the same level."""
    if not heading:
        return text
    lines = text.split('\n')
    level = len(heading) - len(heading.lstrip('#'))
    out, inside = [], False
    for ln in lines:
        if ln.strip() == heading.strip():
            inside = True
            continue
        if inside and ln.startswith('#'):
            if len(ln) - len(ln.lstrip('#')) <= level:
                break
        if inside:
            out.append(ln)
    return '\n'.join(out)


def tracked_files():
    """Files git tracks. Read-only: --no-optional-locks takes no index lock,
    which a device-bridge session must not leave behind."""
    try:
        out = subprocess.run(['git', '--no-optional-locks', 'ls-files', '-z'],
                             cwd=VAULT, capture_output=True, text=True,
                             timeout=60)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return [x for x in out.stdout.split('\0') if x]


# A token with no vowels-and-spaces shape to it, long enough and mixed enough
# to be a secret rather than a word. Deliberately not a list of the strings
# already found: the obvious guard, "assert this passphrase never appears",
# would put the passphrase into assertions.yaml, which is tracked. A guard
# against a leak must not itself be the leak, so this matches on shape.
SECRET_SHAPE = re.compile(r'(?<![A-Za-z0-9/+=_-])'
                          r'(?=[A-Za-z0-9]{16,40}(?![A-Za-z0-9]))'
                          r'(?=[^\s]*[a-z])(?=[^\s]*[A-Z])(?=[^\s]*\d)'
                          r'[A-Za-z0-9]{16,40}')
# Hex is what this vault is actually full of: md5 sums in every snapshot and
# fingerprint. A hex run carries no upper-and-lower-and-digit mix, so the
# look-aheads above already exclude it; this is here for the mixed-case ids
# that legitimately look like secrets.
#
# The other two rejections were measured rather than guessed. On the first run
# the scan raised 33 hits across two fingerprints and exactly one was a
# secret. The rest were German OneNote page titles in CamelCase —
# `2022MSGleitzeitFerienDAG`, `2023MSArbeitsverteilung` — and base64 fragments
# of Outlook item ids. A check that reports 32 false positives to find one
# real hit teaches the reader to skip it, which is the failure this vault
# already named about standing findings.
#
#   * a run of six or more consecutive lowercase letters is a word. Generated
#     secrets have them rarely; German compounds have them always.
#   * a leading four-digit year is a date prefix, not entropy.
SECRET_SKIP = re.compile(r'^(?:[0-9a-f]{32}|[0-9a-f]{40})$')
SECRET_WORDY = re.compile(r'[a-z]{6,}')
SECRET_YEAR = re.compile(r'^(?:19|20)\d{2}')


def export_contract(kb):
    """The ingest protocol reads fields the exporter promises. Check they exist.

    `onenote-export` writes `_CHANGES-YYYY-MM-DD.json` into the archive and the
    per-KB CLAUDE.md keys its ingest off three of its fields: `status` and
    `contentChanged` decide whether a page is rebuilt, and `complete` decides
    whether an absence may be read as a deletion. Those live in a different
    repository on a different release cadence, and the contract between them was
    written down twice and kept in step by hand until 29.08.2026.

    So this asserts the newest report still carries what the protocol reads. It
    is deliberately not a schema check: extra fields are fine and expected — the
    exporter added `runs` on 29.08.2026 — and a missing one is what breaks an
    ingest silently, by making every page look unchanged.

    Skipped where there is no export: the frozen bundles have no exporter, and a
    knowledge base whose archive has not been synced yet has nothing to check.
    """
    import json as _json
    defects = []
    roots = glob.glob(os.path.join(VAULT, kb, 'OneNote', '*'))
    reports = sorted(f for r in roots
                     for f in glob.glob(os.path.join(r, '_CHANGES-*.json')))
    if not reports:
        return defects
    newest = reports[-1]
    rel = os.path.relpath(newest, os.path.join(VAULT, kb))
    try:
        doc = _json.load(open(newest, encoding='utf-8'))
    except Exception as e:
        defects.append((rel, 'the newest change report does not parse: %s' % e))
        return defects
    if 'complete' not in doc:
        defects.append((rel, "no `complete` field; the ingest protocol reads it to "
                             'decide whether an absence may be read as a deletion'))
    changes = doc.get('changes')
    if not isinstance(changes, list):
        defects.append((rel, '`changes` is not a list; the ingest protocol iterates it'))
        return defects
    for want in ('status', 'contentChanged', 'path'):
        if changes and not any(want in c for c in changes if isinstance(c, dict)):
            defects.append((rel, 'no change record carries `%s`; the ingest protocol '
                                 'keys off it and would rebuild nothing' % want))
    return defects


def repo_hygiene():
    """Two guards on the boundary between the archive and the repository.

    `OneNote/` is gitignored because the archive is sensitive. On 22.08.2026 a
    certificate passphrase was found in the repository anyway, and on GitHub:
    `archive-fingerprint.py` wrote the first 120 characters of every archive
    page into `_snapshots/*.fingerprint.tsv` as a convenience, and those files
    were tracked. 2'592 rows of raw page text per snapshot went in with it.
    The token is what got noticed, not what was there.

    So the first guard is the exact recurrence — nothing under a `_snapshots/`
    directory may be tracked — and the second is the class: a tracked file
    outside the concept bundles carrying something shaped like a credential.
    A check that only knew about `_snapshots/` would miss the next script that
    writes archive text somewhere else, which is precisely how this one
    escaped notice.
    """
    defects = []
    tracked = tracked_files()
    if tracked is None:
        return defects                      # no git here; nothing to assert
    for rel in tracked:
        if '/_snapshots/' in rel or rel.startswith('_snapshots/'):
            defects.append((rel, 'a snapshot file is git-tracked; snapshots '
                                 'are derived from the gitignored archive '
                                 'layers and must not enter the repository'))
    waived = set((vault_assertions().get('secret_waivers') or []))
    for rel in tracked:
        if rel.endswith(('.md', '.py', '.sh', '.js', '.yaml', '.yml')):
            continue                        # prose and code, not data dumps
        if rel in waived:
            continue
        if '/_snapshots/' in rel or rel.startswith('_snapshots/'):
            continue                        # already condemned above
        f = os.path.join(VAULT, rel)
        try:
            raw = open(f, 'rb').read()
        except OSError:
            continue
        # Binary files are excluded, not scanned. A PDF's compressed streams
        # produce mixed-case alphanumeric runs by the hundred and every one of
        # them matches the shape; the owner's own CV raised a defect on the
        # first run. A secret typed into a binary is not the leak this guards.
        if b'\0' in raw[:8192]:
            continue
        body = raw.decode('utf-8', errors='replace')
        for m in SECRET_SHAPE.finditer(body):
            g = m.group(0)
            if (SECRET_SKIP.match(g) or SECRET_WORDY.search(g)
                    or SECRET_YEAR.match(g)):
                continue
            defects.append((rel, 'a tracked data file carries a token shaped '
                                 'like a credential; archive-derived files '
                                 'belong outside the repository'))
            break
    return defects


def vault_audit():
    """Audits the files above the knowledge bases. Nothing checked these until
    15.08.2026, which is how a stale concept count sat in CLAUDE.md through two
    runs. The per-KB assertions guard concepts; these guard the map."""
    A = vault_assertions()
    defects = []
    for rule in A.get('forbid_in') or []:
        rel = rule.get('path', '')
        f = os.path.join(VAULT, rel)
        if not os.path.exists(f):
            defects.append((rel, 'assertion names a file that does not exist'))
            continue
        body = section_of(open(f, encoding='utf-8').read(),
                          rule.get('section'))
        if rule.get('lines') == 'table':
            body = '\n'.join(ln for ln in body.split('\n')
                              if ln.lstrip().startswith('|'))
        m = re.search(rule.get('pattern', r'(?!x)x'), body)
        if m:
            where = rule.get('section') or 'file'
            defects.append((rel, 'forbidden in %s: %r matched %r: %s'
                            % (where, rule['pattern'], m.group(0),
                               ' '.join((rule.get('reason') or '').split()))))
    defects.extend(dead_kb_paths())
    defects.extend(skill_packages())
    return defects


def skill_packages():
    """A .skill package must match its source under _skills/.

    A skill has two representations: the source that is edited and diffed,
    and the package the app installs. They drift silently, because the
    package is a binary blob whose git diff shows only that its size
    changed. The health-check skill had no tracked source at all for its
    first week, edited inside an ephemeral session container with only the
    zip written back; the installed copy, the vault package and the build
    source were three copies with no readable original. This check makes
    the drift fail the audit instead of waiting to be noticed.
    """
    import zipfile
    out = []
    src = os.path.join(VAULT, '_skills')
    if not os.path.isdir(src):
        return out
    for name in sorted(os.listdir(src)):
        d = os.path.join(src, name)
        if not os.path.isdir(d):
            continue
        want = {}
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if not x.startswith('.')]
            for f in fn:
                if f.startswith('.'):
                    continue
                full = os.path.join(dp, f)
                want[os.path.relpath(full, src).replace(os.sep, '/')] = \
                    open(full, 'rb').read()
        pkg = os.path.join(VAULT, name + '.skill')
        if not os.path.exists(pkg):
            out.append((name + '.skill', 'source exists under _skills/ but no '
                        'package was built; run _scripts/build-skill.py'))
            continue
        try:
            with zipfile.ZipFile(pkg) as z:
                have = {i.filename: z.read(i) for i in z.infolist()
                        if not i.filename.endswith('/')}
        except Exception as e:
            out.append((name + '.skill', 'unreadable package: %s' % e))
            continue
        diff = sorted(set(have) ^ set(want)) + sorted(
            k for k in set(have) & set(want) if have[k] != want[k])
        if diff:
            out.append((name + '.skill', 'package differs from its _skills/ '
                        'source (%s); rebuild with _scripts/build-skill.py'
                        % ', '.join(diff[:3])))
    return out


# Files whose job is to describe a world that no longer exists. A CHANGELOG
# entry naming Combined_kb is correct; the folder was there when it was
# written. Exempting them is the difference between a check and a nuisance.
HISTORY = ('CHANGELOG.md',
           '_BUILD-BRIEF', 'Outputs/', '/_testimony/', '_COMPILE-LEDGER.md',
           '_COMPILE-RESUME.md', '/_skills/')
SKIP_DIRS = ('/OneNote/', '/_to_delete/', '/.git/', '/_extractions/',
             '/.obsidian/', '/_snapshots/', '/uploads/')
BACKTICK = re.compile(r'`([^`\n]+)`')
MDLINK = re.compile(r'\]\(([^)\n]+)\)')
KB_TOKEN = re.compile(r'(?:^|/)([A-Za-z0-9]+_kb)/')


def dead_kb_paths():
    """A path naming a knowledge base that does not exist.

    Raised as AI-2026-08-15-8 after the rename of 15.08.2026 swept 73
    Private references and left Combined_kb standing in six live places,
    through two health checks that both reported green. The per-KB forbid
    entry that first fixed it was the wrong shape twice over: it fired on the
    honest history in every CHANGELOG, and it could not see the real defect,
    which is a path that does not resolve rather than a name that offends.

    So the test is resolution, not spelling, and it is graded:

      the knowledge base directory itself is gone  -> DEFECT
      the base exists and the path does not        -> not raised here

    The second case is left alone on purpose. Under OKF a link to a concept
    that has not been written yet is legitimate and marks knowledge worth
    writing, and Audit 2 already resolves every sources[].resource. Only a
    dead *knowledge base* is unambiguously wrong: no concept will ever be
    written into a folder that does not exist.
    """
    out = []
    bases = {d for d in os.listdir(VAULT)
             if d.endswith('_kb') and os.path.isdir(os.path.join(VAULT, d))}
    for dirp, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        if any(x in (dirp + '/').replace(os.sep, '/') for x in SKIP_DIRS):
            continue
        for fn in files:
            if not fn.endswith('.md'):
                continue
            f = os.path.join(dirp, fn)
            rel = os.path.relpath(f, VAULT).replace(os.sep, '/')
            if any(h in '/' + rel for h in HISTORY):
                continue
            txt = FENCE.sub('', open(f, encoding='utf-8',
                                     errors='replace').read())
            seen = set()
            for rx in (BACKTICK, MDLINK):
                for m in rx.finditer(txt):
                    t = m.group(1).strip().rstrip('.,;:').split('#')[0]
                    # A trailing slash means a directory, and the only
                    # directory paths written here are illustrative: the
                    # cross-KB citation pattern in the vault manual uses
                    # '../../../OtherTopic_kb/OneNote/' as a stand-in for any
                    # sibling. A real citation names a file.
                    if (not t or t.startswith('http') or t.endswith('/')
                            or any(c in t for c in '*\u2026<>|')):
                        continue
                    km = KB_TOKEN.search(t)
                    if not km or km.group(1) in bases or t in seen:
                        continue
                    seen.add(t)
                    out.append((rel, 'names the knowledge base %s, which does '
                                'not exist: %s' % (km.group(1), t)))
    return out


def reports_register():
    """Every report in Outputs/ carries a row in the register.

    The rule is the vault's own — a report with no row is invisible to the
    next session, which defeats the point of filing it — and until 31.08.2026
    it lived only as prose in two skills, checked by whoever remembered. That
    is the shape of every defect class this script exists to catch: the rule
    was right and the instances were right, and nothing would have said so if
    one had gone missing. A sweep is where one goes missing first, because it
    files a report per knowledge base at once and the orchestrator appends the
    rows by hand after the last agent is in.

    A leading underscore marks a generated working file rather than a report:
    `_REPORTS.md` is the register itself and `_READING-BLOCKS.md` is written by
    `readblocks.py`. Neither is query history and neither takes a row, so
    honouring the convention is what keeps this a check rather than a nuisance.
    """
    out = []
    d = os.path.join(VAULT, 'Outputs')
    if not os.path.isdir(d):
        return out
    reg = os.path.join(d, '_REPORTS.md')
    if not os.path.exists(reg):
        return [('Outputs/_REPORTS.md', 'the register is missing')]
    text = open(reg, encoding='utf-8').read()
    for name in sorted(os.listdir(d)):
        if not name.endswith('.md') or name.startswith('_'):
            continue
        if name not in text:
            out.append(('Outputs/' + name,
                        'report has no row in Outputs/_REPORTS.md'))
    return out


STATE = os.path.join(VAULT, '_scripts', 'verify-state.json')


def main():
    import json
    total = 0
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            state = {}
    today = datetime.date.today().isoformat()
    if not sys.argv[1:]:
        vd = vault_audit() + repo_hygiene() + reports_register()
        print('== 00_Cerebrum (vault): %d defects' % len(vd))
        for rel, msg in vd:
            print('  DEFECT  %s: %s' % (rel, msg))
        total += len(vd)
    for kb in (sys.argv[1:] or discover()):
        n, c, defects, findings = audit(kb)
        defects = defects + export_contract(kb)
        waivers = assertions(kb).get('finding_waivers') or []
        fresh = {}
        for rel, msg in findings:
            if rel == '(bundle)':
                continue  # gauge, not a question; it never escalates
            fp = '%s|%s|%s' % (kb, rel, msg)
            dates = state.get(fp, [])
            if today not in dates:
                dates = (dates + [today])[-5:]
            fresh[fp] = dates
            if len(dates) >= 3:
                if any(fnmatch.fnmatch(rel, w.get('path', '*'))
                       and w.get('contains', '') in msg
                       for w in waivers):
                    continue
                defects.append((rel, 'standing finding, %d distinct run-days '
                                '(fix it, or waive it with a reason in '
                                'assertions.yaml finding_waivers): %s'
                                % (len(dates), msg)))
        for fp in [k for k in state if k.startswith(kb + '|')]:
            del state[fp]
        state.update(fresh)
        print('== %s: %d concepts, %d citations, %d defects, %d findings'
              % (kb, n, c, len(defects), len(findings)))
        for rel, msg in defects:
            print('  DEFECT  %s: %s' % (rel, msg))
        for rel, msg in findings[:20]:
            print('  finding %s: %s' % (rel, msg))
        if len(findings) > 20:
            print('  ... %d more findings' % (len(findings) - 20))
        total += len(defects)
    json.dump(state, open(STATE, 'w', encoding='utf-8'),
              indent=0, sort_keys=True)
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    main()
