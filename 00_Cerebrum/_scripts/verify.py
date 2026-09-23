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
             'pip 23.0+, and the Command Line Tools pip on the owner Mac predates\n'
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
    #
    # The possessive had four fixed phrases until 15.09.2026 (my reading, my
    # own reading, in my view, to my knowledge), the enumeration the pronoun
    # arm had already been rescued from: 21 instances of "my scope" and 4 of
    # "my batch" walked through every run in Beta_kb (AI-2026-08-31-1, arm a).
    # Same shape as the pronoun, lowercase `my` and a lowercase word, so the
    # product names My Content, My Site and My Documents stay out.
    #
    # And until the second sitting of 15.09.2026 no other pronoun was tested,
    # so "the tally is mine" and an unquoted "we communicate more" were found
    # only by reading (Gamma_kb AI-2026-09-08-7). The plural and object forms
    # are matched whole and lower-case; "US" and "Our" in a product name are
    # not. Quotes and bracketed glosses stay exempt below.
    r'(?<![A-Za-z0-9])(I [a-z]{2,}|[Mm]y [a-z]{2,}|in my view|'
    r'to my (knowledge|mind)|(?<![/-])(?:[Ww]e|[Oo]ur|ours|us|me|mine))(?![A-Za-z0-9\'-])')

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
#
# It matched any bare capital letter within forty characters until 15.09.2026,
# and "bare" was tested against ASCII only, so the K of "Kürzel" counted: "the
# Kürzel map I work from" was suppressed as a letter list (Beta_kb
# AI-2026-08-31-1, arm b). A letter now has to be a Unicode word boundary on
# both sides and sit in an enumeration: before a comma, "and", "or", a slash
# or "for", or after a comma, "and" or "or".
FP_LETTER_LIST = re.compile(
    r'(?<!\w)[A-HJ-Z](?!\w)(?=\s*(?:,|/|\band\b|\bor\b|\bfor\b))'
    r'|(?:,|\band|\bor)\s+[A-HJ-Z](?!\w)')


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
    if not w:
        return False
    word = w.group(1)
    # A roman numeral follows the thing it numbers: Phase I, EP I, workshop I.
    # Until 15.09.2026 anything that was not a connector counted as that, so
    # "is not something I can confirm" was suppressed on the noun "something"
    # (Beta_kb AI-2026-08-31-1, arm e). A capitalised word is still read as a
    # name being numbered; a lowercase one only when it is a numbering noun.
    return (word.lower() in FP_CONNECTORS
            or (word[0].islower() and word.lower() not in FP_NUMBERED))


FP_NUMBERED = {
    'phase', 'phases', 'part', 'parts', 'stage', 'stages', 'workshop',
    'workshops', 'training', 'trainings', 'project', 'projects', 'level',
    'levels', 'grade', 'tier', 'round', 'rounds', 'type', 'class', 'section',
    'chapter', 'volume', 'wave', 'waves', 'step', 'steps', 'tranche', 'lot',
    'module', 'release', 'version', 'package', 'block', 'series', 'scenario',
    'option', 'alternative', 'track', 'war', 'session', 'sessions', 'band',
    'course', 'courses', 'lecture', 'unit', 'zone', 'category', 'pillar',
    'milestone', 'cohort', 'batch', 'act', 'annex', 'appendix', 'article',
}
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


def _load_script(name, filename):
    spec = _ilu.spec_from_file_location(
        name, os.path.join(VAULT, '_scripts', filename))
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# One definition each, shared with the scripts that repair what they find.
_tableorder = _load_script('cerebrum_tableorder', 'tableorder.py')
_staleclaims = _load_script('cerebrum_staleclaims', 'stale-claims.py')
_packer = _load_script('cerebrum_preparebatch', 'prepare-batch.py')

# Compile vocabulary in a concept. "Batch" is the pack of pages one compile
# agent was given: a unit that does not exist in the bundle, that no reader can
# resolve, and that silently narrows every scope claim built on it ("nothing in
# this batch records it"). 111 instances across 80 Beta concepts were rewritten
# by hand on 31.08.2026 and 44 more stood in Gamma_kb on 15.09.2026 with
# nothing to catch them (Beta_kb AI-2026-08-31-1, arm c). The technical sense —
# a batch job, a batch interface — is exempt by what follows the word, and
# the determiners are the five the item measured: "each batch" also names a
# migration wave in Gamma_kb/Wiki/systems/onedrive-for-business.md.
BATCH_WORD = re.compile(
    r'\b(?:this|these|the|one|my)\s+'
    r'batch(?:es)?\b(?!\s+(?:jobs?|files?|interfaces?|size|mode|process'
    r'|processing|scripts?|runs?|imports?|exports?|updates?|operations?'
    r'|windows?|systems?)\b)', re.I)
NUMWORDS = {w: i for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve '
    'thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty '
    'twenty-one twenty-two twenty-three twenty-four twenty-five twenty-six '
    'twenty-seven twenty-eight twenty-nine thirty'.split())}
NUM = r'(\d+|' + '|'.join(sorted(NUMWORDS, key=len, reverse=True)) + r')'


# The wall-clock minute this run started, in UTC. Held in a constant so
# every concept in one audit is judged against the same instant: a run that
# takes twenty minutes must not fail a concept for a stamp written while it
# was reading.
RUN_MINUTES_UTC = (datetime.datetime.utcnow().hour * 60
                   + datetime.datetime.utcnow().minute)

# A claim that the export lost something, matched by SHAPE rather than by a
# list of phrasings. The list is what this was until 20.09.2026: eight exact
# phrases, and `systems/ethis.md` slipped past all eight by writing "the link
# text is all that survives the export" — which was false, the URL being in
# the page twice. The row that created the check had itself proposed "link
# marker" as a phrase, and that was never added either. An enumeration only
# ever catches the wording in front of whoever wrote it; a shape catches the
# claim. Two shapes here: "export" near a word of loss, in either order.
# Calibrated 20.09.2026 over all six bundles — 22 hits before, 82 after, and
# the sample read was a genuine export-loss claim in every added case.
# (`Epsilon_kb` AI-2026-09-20-2.)
EXPORT_LOSS = re.compile(
    r'(?i)(?:'
    r'\bexport\b[^.\n]{0,80}?\b(?:did ?n[o\']t|does ?n[o\']t|never|failed to|'
    r'cannot|can ?n[o\']t|could ?n[o\']t|without|lacks?|omit(?:s|ted)?|'
    r'drop(?:s|ped)?|strip(?:s|ped)?|lost|missing)'
    r'|\b(?:did not survive|does not survive|survives?|survived|lost|missing|'
    r'stripped|dropped|omitted|absent|unavailable|not (?:in|part of|carried|'
    r'captured|present|included|kept)|cannot be (?:read|seen|checked|'
    r'recovered)|link marker)\b[^.\n]{0,80}?\bexport\b'
    r'|unavailable from this corpus'
    r')')
# `team:<id>` added 23.09.2026. SPEC.md gives it for a source written by a
# group rather than a person (its own examples cite `team:ga4-docs`), and the
# first version of this pattern left it out, so an EBU page correctly written
# as `team:ebu` failed the audit for following the format.
AUTHOR_FORM = re.compile(r'^(?:human:[a-z0-9\-]+|team:[a-z0-9\-]+|process:[\w\-/\.]+|unknown)$')
NO_CONCEPT = re.compile(
    r'([A-Z\u00c4\u00d6\u00dc][\w\u00e4\u00f6\u00fc\u00e9\u00e8\u00e0]+'
    r'(?: [A-Z\u00c4\u00d6\u00dc][\w\u00e4\u00f6\u00fc\u00e9\u00e8\u00e0]+){1,2})'
    r'[^.\n]{0,60}?\b(?:has no concept|no concept (?:exists|of (?:his|her|their)'
    r' own)|has no page of (?:his|her|their) own|is not identified|'
    r'not identified)\b')
CURRENCY_COMMA = re.compile(r'\b(?:CHF|EUR|USD|GBP|kCHF|kEUR)\s?\d{1,3}(?:,\d{3})+'
                            r'(?!,?\d)')
TITLE_DATE = re.compile(r'(20\d\d)[-\s]?(\d\d)[-\s]?(\d\d)')
ID_DATE = re.compile(r'(?<!\d)(20[0-3]\d)-?(0[1-9]|1[0-2])-?(0[1-9]|[12]\d|3[01])'
                     r'(?!\d)')
ID_DMY = re.compile(r'(?<!\d)(\d\d)\.(\d\d)\.(20\d\d)(?!\d)')


def _dates_in(txt):
    """Every valid calendar date in a string, as YYYYMMDD."""
    out = set()
    for m in ID_DATE.finditer(txt):
        try:
            datetime.date(*map(int, m.groups()))
            out.add(''.join(m.groups()))
        except ValueError:
            pass
    for m in ID_DMY.finditer(txt):
        try:
            datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            out.add(m.group(3) + m.group(2) + m.group(1))
        except ValueError:
            pass
    return out


def _prose_paragraphs(body):
    """Prose paragraphs: no table, list, heading, quote, footnote or fence."""
    for p in re.split(r'\n\s*\n', FENCE.sub('', body)):
        s = p.strip()
        if s and not s.startswith(('|', '#', '>', '[^', '- ', '* ', '+ ')) \
                and not re.match(r'\d+\. ', s):
            yield s


_UNITS = ('zero one two three four five six seven eight nine ten eleven '
          'twelve thirteen fourteen fifteen sixteen seventeen eighteen '
          'nineteen').split()
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60,
         'seventy': 70, 'eighty': 80, 'ninety': 90}
PAGENUM = (r'\d+|(?:%s)(?:-(?:%s))?|%s'
           % ('|'.join(_TENS), '|'.join(_UNITS[1:10]), '|'.join(_UNITS)))


def _pagenum(s):
    s = s.lower()
    if s.isdigit():
        return int(s)
    if '-' in s:
        a, b = s.split('-')
        return _TENS[a] + _UNITS.index(b)
    return _TENS.get(s, _UNITS.index(s) if s in _UNITS else -1)


def _num(s):
    s = s.lower()
    return int(s) if s.isdigit() else NUMWORDS[s]


def _section(text, heading):
    m = re.search(r'^%s\s*$(.*?)(?=^# |\Z)' % re.escape(heading), text,
                  re.S | re.M)
    return m.group(1) if m else None


def _first_table_rows(sec):
    rows, started = [], False
    for ln in sec.split('\n'):
        if ln.lstrip().startswith('|'):
            started = True
            rows.append(ln)
        elif started:
            break
    return [r for r in rows[2:] if not re.match(r'^\s*\|[\s:|-]+\|\s*$', r)]


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

        # One page cited twice under two ids, so it reads as two independent
        # sources. Found on 20.09.2026 in three bundles at once — two Alpha
        # concepts, six pairs in `Delta_kb`, four concepts in `Epsilon_kb` — and
        # nothing saw any of them, because every id was distinct, every path
        # resolved and every footnote bound. It is the sharp form of the
        # hazard the manuals already name: do not cite two copies as two
        # independent sources. Here it is one file rather than two copies, so
        # a claim footnoted to both ids looks corroborated by a second page
        # that does not exist. Concurrent compile agents produce it: each
        # invents its own id for the page it is reading.
        #
        # Paths are compared after `normpath`, because the same page reached
        # from two directory depths is written with a different number of
        # `../` steps and is still one page. A finding, not a defect: merging
        # two ids means choosing which survives and repointing its footnotes,
        # which is a content decision and not something a hook should block a
        # commit on. (`Alpha_kb` AI-2026-09-20-12, `Delta_kb` AI-2026-09-20-5,
        # `Epsilon_kb` AI-2026-09-20-1.)
        seen_res = {}
        for s in srcs:
            if not isinstance(s, dict):
                continue
            res = str(s.get('resource') or '')
            if not res:
                continue
            key = os.path.normpath(res)
            seen_res.setdefault(key, []).append(str(s.get('id') or '(no id)'))
        for key, ids in seen_res.items():
            if len(ids) > 1:
                findings.append((rel, 'one page cited under %d ids (%s): %s'
                                      % (len(ids), ', '.join(ids), key)))

        # An `author` on an archive citation that is not one of the three
        # forms the format allows. `SPEC.md` and every manual give
        # `human:<slug>`, `team:<id>`, `process:<id>` or `unknown`; 140 archive citations
        # write a bare display name instead — `Yusuf Demirel`, `Tobias
        # Bärtschi`, and in one concept `librarian/claude-opus-5`, which is the
        # `generated.by` form in the wrong field. It matters beyond tidiness:
        # nine pages carry both `human:rafael-baertschi` and `Rafael Bärtschi`,
        # so the same person reads as two authors and the split-author gauge
        # below cannot see through it. Found 20.09.2026 by a reader draining
        # the Gamma contradiction queue.
        #
        # Scoped to the archive layers on purpose. A mirrored help-centre
        # page is authored by an organisation — `Alpha Central IT` on 823
        # `Delta_kb` citations — and there is no slug for an institution. The
        # unscoped check fires 3'356 times and is wrong in almost all of them.
        for s in srcs:
            if not isinstance(s, dict) or 'author' not in s:
                continue
            if '/OneNote/' not in str(s.get('resource') or ''):
                continue
            a = str(s.get('author'))
            if not AUTHOR_FORM.match(a):
                findings.append((rel, 'source author %r is not human:<slug>, '
                                      'team:<id>, process:<id> or unknown' % a))
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

        # A key written twice inside one sources entry. yaml.safe_load keeps
        # the last and drops the first without a word, so the entry ends up
        # attributed to whatever the stray pair said and the entry above it
        # loses the fields that stray pair belonged to. Invisible to a reader
        # scanning line by line and invisible to every other check here,
        # because by the time anything looks at the parsed object the losing
        # value is gone. Found 20.09.2026 in Gamma_kb organisation/cam-board.md,
        # where blogs-register had taken blog-software-mgmt's author and stamp.
        # A DEFECT: there is no case where writing a key twice is meant.
        _entry = None
        for _l in m.group(1).split('\n'):
            if re.match(r'^\s*-\s+\w+:', _l):
                _entry = set()
            elif _entry is not None:
                _k = re.match(r'^\s{4,}([A-Za-z_]+):', _l)
                if _k:
                    if _k.group(1) in _entry:
                        defects.append((rel, "duplicate key '%s' inside one "
                                        'sources entry; the parser keeps the '
                                        'last and drops the first silently'
                                        % _k.group(1)))
                    _entry.add(_k.group(1))
                elif re.match(r'^\S', _l):
                    _entry = None

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

            # `last_modified` is the source page's own `modified` stamp, and
            # `author` may not name a person who was not there. Both are opt-in
            # per knowledge base, because only a bundle whose archive carries
            # frontmatter stamps can be measured this way.
            #
            # The date rule was settled by the owner on 16.09.2026 (Beta_kb
            # AI-2026-09-14-4): 989 of 4'055 citations gave the date in the
            # page title instead, and the convention had never been written
            # down, so both readings looked right. A value of `unknown` is
            # always allowed: the News Posts under a contradicted export stamp
            # take it, enforced by `source_rules` above.
            #
            # The author rule was settled the same day (Beta_kb AI-2026-09-14-1):
            # 147 citations of minutes written before the owner reached that
            # employer named him as their author, which that bundle's CLAUDE.md
            # makes the credibility signal of the whole archive. Only the date
            # arm is scripted; an author wrong for any other reason needs a
            # reading, which is why this fires on the one case a pattern sees.
            if r and os.path.isfile(tgt):
                head = open(tgt, encoding='utf-8',
                            errors='replace').read(3000)
                # `last_modified` is the date in the archive page's own
                # title, and its `modified` stamp only where the title carries
                # no date. Owner's ruling of 20.09.2026, section 2 of
                # `_testimony/2026-09-20_testimony-health-check-sweep.md`.
                #
                # It replaces `last_modified_is_page_stamp`, which enforced the
                # opposite and was `Beta_kb`'s alone. That rule was settled
                # 16.09.2026 on the reading that the field means when the
                # source file last changed; the owner superseded it four days
                # later in favour of one rule for the vault, because an export
                # stamp records when the exporter ran. On 48 Bila pages it is
                # the series start, years from the sitting, and the librarian
                # had been reading the title all along: 3'144 of the 3'356
                # citations the ruling moved already carried a source id naming
                # the title date.
                #
                # 4'735 citations were re-dated that day across three bundles
                # and nothing checked the rule that replaced the old one, which
                # is the gap this closes: a pass that fixes the instances and
                # leaves the class unguarded is not a fix (`Beta_kb`
                # AI-2026-09-20-10). A finding rather than a defect, so it
                # carries the three-run-day clock like any other and a
                # legitimate exception is waived with its reason rather than
                # wedging the pre-commit hook.
                #
                # Scoped to the OneNote archive layer, which is what the ruling
                # was applied to. A help-centre page mirrored into `Raw/` has
                # no date in its title, so it would never fire there anyway.
                if '/OneNote/' not in r and '/Raw/' not in r:
                    _fn = os.path.basename(os.path.normpath(
                        os.path.join(d, r)))
                    _fd = re.match(r'(\d{4})-(\d{2})-(\d{2})', _fn)
                    _lm = str(s.get('last_modified'))[:10]
                    if _fd and _lm not in ('unknown', 'None', ''):
                        _want = '-'.join(_fd.groups())
                        if _lm != _want:
                            findings.append(
                                (rel, 'source %s: last_modified %s, but the '
                                      'file\'s own name gives %s'
                                      % (r, _lm, _want)))
                if '/OneNote/' in r:
                    _td_t = re.search(r'^title:\s*(.+)$', head, re.M)
                    td = None
                    if _td_t:
                        # The forms the archive actually uses, leading token
                        # first: `20240304 ID AL-Sitzung`, `2024-03-04 …`,
                        # `08.11.2022 …`. A page title carrying two dates is
                        # read by its first, which is the OneNote convention.
                        # Named `_td_*` and not `d` or `m`: the enclosing
                        # loop holds the concept's own directory in `d`, and
                        # shadowing it here made every later citation resolve
                        # against a regex match object. The audit crashed, and
                        # a `grep -c` on the new message counted zero and read
                        # as a clean bundle. Caught 20.09.2026 by reintroducing
                        # the defect the check is for, which is the only reason
                        # it was caught at all.
                        _td_m = re.search(r'(\d{4})-?(\d{2})-?(\d{2})',
                                          _td_t.group(1))
                        if _td_m:
                            td = '%s-%s-%s' % _td_m.groups()
                        else:
                            _td_m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})',
                                              _td_t.group(1))
                            if _td_m:
                                td = '%s-%s-%s' % (_td_m.group(3),
                                                   _td_m.group(2),
                                                   _td_m.group(1))
                    lm = str(s.get('last_modified'))
                    if td and lm not in ('unknown', 'None') and lm != td:
                        try:
                            datetime.date(*[int(x) for x in td.split('-')])
                        except ValueError:
                            td = None          # not a date; say nothing
                        if td:
                            findings.append(
                                (rel, 'source %s: last_modified %s, but the '
                                      'page\'s own title gives %s'
                                      % (r, lm, td)))
                # The rule's second arm — "the page's `modified` stamp where
                # the title carries none" — is NOT checked here, and the
                # measurement is recorded so the next run does not try again
                # without one. Written and run on 20.09.2026: it fires 511
                # times across the vault, and the sample read was false in
                # every case. Where an archive title carries no date the
                # librarian reads the sitting's date out of the page body, and
                # the exporter's `modified` stamp is usually the day the export
                # ran. No script can read a date out of prose, so the arm is
                # unwritable as stated rather than merely unwritten. A check
                # with that false-positive rate teaches the reader to skip the
                # findings block, which is the cost the three-run-day clock
                # exists to avoid. (`Beta_kb` AI-2026-09-20-10.)
                #
                # What IS checkable is below: a cited file whose own NAME
                # begins with a date. That is exact — no prose is involved —
                # and it covers testimony and vault files, which is where the
                # class was found (`Zeta_kb` AI-2026-09-20-1, ten stamps in
                # one concept naming a date older than the file). The archive
                # layers are excluded on purpose: their filename prefix is the
                # exporter's stamp, which the ruling of 20.09.2026 says is
                # never the page's date.
                oa = A.get('owner_author_not_before') or {}
                owner_start = oa.get('date')
                # Scoped to the archive scopes whose page dates are reliable.
                # Unscoped, the rule fired on the owner's own Gamma-era pages in
                # a sibling bundle and on his personal notebook, where
                # `human:owner` is right, and on one page whose title year is
                # a typing slip. A check that is wrong four ways is not a
                # check; the scope is the item's own method.
                if owner_start and str(s.get('author')) == 'human:owner' \
                        and re.search(oa.get('resource_pattern', '.'), r):
                    tm = re.search(r'^title:\s*[\'"]?(.*)$', head, re.M)
                    dm = TITLE_DATE.search(tm.group(1)) if tm else None
                    if not dm:
                        cm = re.search(r'^created:\s*[\'"]?'
                                       r'(\d{4})-(\d{2})-(\d{2})', head, re.M)
                        dm = cm
                    if dm and '-'.join(dm.groups()) < str(owner_start):
                        defects.append(
                            (rel, 'source %s: author is human:owner, but the '
                                  'page is dated %s, before %s'
                             % (r, '-'.join(dm.groups()), owner_start)))
        resources[f] = res

        # Inline code is blanked first, same length, so a concept or a
        # questions.md that writes `[^label]` while describing the footnote
        # rules is not read as citing a source called "label". Fenced blocks
        # were already excluded; inline code was not, and the action sitting
        # of 16.09.2026 tripped over it within minutes of writing the rule
        # down. Same treatment as the first-person and prose checks below.
        foot_body = INLINE_CODE.sub(lambda x: ' ' * len(x.group(0)), body)
        used = set(FOOTNOTE.findall(foot_body))
        refs = set(FOOTREF.findall(foot_body))
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
        # date in two-digit form — 2018-08-28-20-12-17-damien-cortez.md is the
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
            # A Word file, a deck, a workbook, a PDF or an image cannot be
            # searched this way: its words sit compressed inside the file, so
            # reading it as text finds no year, and every id dated from the
            # document's own title page was reported. 259 findings on
            # 13.09.2026, the first compile of the documents the owner filed
            # into Alpha_kb/Raw/, every one of them against a .docx, .pptx,
            # .xlsx, .pdf or .png. The path still corroborates when it carries
            # the year. When it does not, the check holds no evidence either
            # way and says nothing, rather than reporting what it cannot see.
            binary = os.path.splitext(tgt)[1].lower() not in (
                '', '.md', '.txt', '.html', '.htm', '.csv', '.json', '.xml')
            if os.path.exists(tgt) and not binary:
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
            if yr in hay or ('-' + yr[2:] + '-') in hay or binary:
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

        # The same defect inside one day, which the date-only compare above
        # cannot see. The Alpha delta compile of 20.09.2026 stamped fifteen
        # concepts `2026-09-20T21:40:00Z`, about four hours after it ran and
        # three ahead of the clock, and every check passed: the date was
        # today's. A compile that writes fifteen such stamps at once is not a
        # clock skew, it is an agent inventing a timestamp, and the whole
        # freshness layer is arithmetic on these values. Compared against the
        # moment this run starts rather than against `now`, so a long audit
        # cannot fail a concept a sibling agent legitimately stamped while it
        # was reading. One hour of slack absorbs a timezone-naive writer.
        # (`Alpha_kb` AI-2026-09-20-10.)
        gat = str((fm.get('generated') or {}).get('at', ''))
        if gat and gat[:10] == datetime.date.today().isoformat():
            gm = re.match(r'^\d{4}-\d{2}-\d{2}[T ](\d{2}):(\d{2})', gat)
            if gm:
                mins = int(gm.group(1)) * 60 + int(gm.group(2))
                if mins > RUN_MINUTES_UTC + 60:
                    defects.append((rel, 'generated.at %s is %d minutes ahead '
                                         'of the clock' % (gat,
                                                           mins - RUN_MINUTES_UTC)))

        # A concept speaking in the first person. Settled 15.08.2026, after
        # the owner read "I use this table to place people in streams" and
        # asked whether the "I" was his. It was the librarian's. In a corpus
        # built from one person's own notes that ambiguity is not stylistic:
        # a reader cannot tell whether "I use Meyer" records the owner's
        # naming preference or a compile agent's tie-break. 96 instances were
        # rewritten into the concept's own voice that day. Quotes and the
        # bracketed glosses that translate them are exempt, because there the
        # "I" belongs to the person quoted and must stay verbatim.
        # Inline code is blanked first, same length, so a path such as
        # `About me/writing-rules.md` or a locale `en-us` is not a pronoun.
        fp_body = INLINE_CODE.sub(lambda x: ' ' * len(x.group(0)), body)
        for m in FIRST_PERSON.finditer(fp_body):
            if m.group(0)[0] == 'I' and (
                    not clause_open(fp_body, m.start())
                    or letter_list(fp_body, m.start(), m.end())):
                continue
            # A bracketed gloss is exempt only when the match sits inside one
            # pair of brackets. Until 15.09.2026 the nearest `[` before and `]`
            # after were enough, so a sentence between two footnote markers,
            # `[^a] Here we see it.[^b]`, read as a gloss and passed.
            lb = fp_body.rfind('[', 0, m.start())
            rb = fp_body.find(']', m.end())
            if lb != -1 and rb != -1 and '\n' not in fp_body[lb:rb] \
                    and '](' not in fp_body[lb:rb] \
                    and fp_body[lb + 1:lb + 2] != '^' \
                    and fp_body.rfind(']', 0, m.start()) < lb \
                    and fp_body.find('[', m.end(), rb) == -1:
                continue
            ls = fp_body.rfind('\n', 0, m.start()) + 1
            if fp_body[ls:m.start()].count('"') % 2 == 1:
                continue
            # A footnote definition carries a page title, and titles speak
            # in the first person: "M365 - Where is my data".
            if fp_body[ls:ls + 2] == '[^':
                continue
            # A block quote is the source speaking, like a quoted span.
            if fp_body[ls:m.start()].lstrip().startswith('>'):
                continue
            defects.append((rel, 'concept speaks in the first person; the '
                                 'voice is the librarian\'s and reads as the '
                                 'owner\'s: %r' % m.group(0)))
            break

        # The checks below were added together on 15.09.2026, on the owner's
        # decision to write every check Beta_kb AI-2026-08-31-1 and Epsilon_kb
        # AI-2026-08-31-4 had asked for. Each class had been repaired by hand
        # and come back; the item had waited three weeks because a sweep's
        # concurrent audits may not change this file.
        prose_c = INLINE_CODE.sub(' ', body)
        if not any(fnmatch.fnmatch(rel, pat)
                   for pat in A.get('compile_vocabulary_ok') or []) \
                and not rel.endswith('questions.md'):
            bm = BATCH_WORD.search(prose_c)
            if bm:
                defects.append((rel, 'compile vocabulary in a concept: %r. '
                                     'Name what was read, as "the pages cited '
                                     'here", never the compile\'s unit'
                                % bm.group(0)))

        # A footnote reference with no definition line renders as literal
        # bracket text while every label still matches a source id, so the
        # checks above pass it. michael-heiniger.md in Beta_kb cited one
        # source ten times with no definition (fixed 13.09.2026), and six
        # stood in Gamma_kb on 15.09.2026 (arm g).
        defined = set(re.findall(r'^\[\^([^\]]+)\]:', prose_c, re.M))
        undefined = sorted(set(FOOTREF.findall(prose_c)) - defined)
        if undefined and not rel.endswith('questions.md'):
            defects.append((rel, 'footnote reference(s) with no definition '
                                 'line, rendered as bracket text: '
                            + ', '.join(undefined)))

        # A heading that is two headings. merge-appends.py matched a SECTION
        # name only at levels one to three and without stripping the name's
        # own hashes, so an agent's `#### SECTION ## The CIS rule table` came
        # out as `# ## The CIS rule table`, below the footnotes: eleven in
        # four Epsilon concepts on 31.08.2026 (Epsilon_kb AI-2026-08-31-4). The
        # script is fixed; this catches the shape from any writer.
        hh = re.search(r'^#+[ \t]+#', body, re.M)
        if hh:
            defects.append((rel, 'heading carries a second heading marker: %r'
                            % body[hh.start():body.find('\n', hh.start())]))

        # A paragraph glued under a list item. CommonMark reads an unindented
        # line after a list item as a lazy continuation, so the paragraph
        # renders inside the bullet. The run-on check above exempts a list
        # item on the left, so this shape was invisible: two in Beta_kb on
        # 31.08.2026 (arm d), five across the vault on 15.09.2026.
        lz = 0
        infence = False
        bl = body.split('\n')
        for i in range(len(bl) - 1):
            a, b = bl[i], bl[i + 1]
            if a.lstrip().startswith('```'):
                infence = not infence
            if infence:
                continue
            if (re.match(r'^\s*(?:[-*+]|\d+\.)\s+\S', a) and b.strip()
                    and b == b.lstrip()
                    and not re.match(r'^(?:[-*+]|\d+\.)\s', b)
                    and not b.startswith(('|', '#', '>', '[^', '```'))
                    and (b[:1].isupper() or b[:2] == '**' or b[:1] == '"')):
                lz += 1
        if lz:
            findings.append((rel, '%d paragraph(s) glued under a list item '
                                  'render inside the bullet; add a blank '
                                  'line' % lz))

        # A paragraph glued under a footnote definition, which is the same
        # shape one line further down: CommonMark reads it as a lazy
        # continuation of the footnote, so the paragraph renders inside the
        # note. 43 of them stood in 31 Gamma_kb concepts on 14.09.2026 and
        # were repaired by hand; the check is what the item asked for
        # (Gamma_kb AI-2026-09-14-10). A list marker closes a footnote, and
        # renderers disagree about a prose line directly above a definition,
        # so neither of those neighbouring shapes is flagged.
        fz = 0
        infence = False
        for i in range(len(bl) - 1):
            a2, b2 = bl[i], bl[i + 1]
            if a2.lstrip().startswith('```'):
                infence = not infence
            if infence:
                continue
            if (a2.startswith('[^') and ']:' in a2 and b2.strip()
                    and b2 == b2.lstrip()
                    and not re.match(r'^(?:[-*+]|\d+\.)\s', b2)
                    and not b2.startswith(('|', '#', '>', '[^', '```'))):
                fz += 1
        if fz:
            findings.append((rel, '%d paragraph(s) glued under a footnote '
                                  'definition render inside the note; add a '
                                  'blank line' % fz))

        # A claim that the export lost something. A compile agent reads a
        # packed batch, where images are invisible and every URL is replaced
        # by a marker, and writes that the export lost what its batch could
        # not show it. Sixteen such claims stood in Epsilon_kb until
        # 14.09.2026, three of them corrected on 31.08.2026 and back again,
        # because nothing caught the class (Epsilon_kb AI-2026-09-14-2). The
        # finding puts every one in front of the next audit; a claim checked
        # and found true takes a `finding_waivers` entry naming what really
        # is missing. Opt in with `export_loss_claims`.
        if A.get('export_loss_claims') and not rel.endswith('questions.md'):
            em2 = EXPORT_LOSS.search(prose_c)
            if em2:
                findings.append((rel, 'claims the export lost something: %r. '
                                      'Check the attachment folder before '
                                      'believing it' % em2.group(0)))

        # A sentence saying a named person has no concept, where that concept
        # now exists. The sentence is true the day it is written and false the
        # day someone writes the page, and nothing revisits it: four stood in
        # `Beta_kb` on 20.09.2026, one of them four weeks old. It is the cheap
        # half of the staleness problem — a claim about the bundle itself,
        # which the bundle can check, unlike a claim about the world.
        #
        # Matched by shape: a capitalised name of two or three words, then
        # within sixty characters a phrase saying no page covers them. The
        # name is slugged by the same transliteration the filenames use, so
        # "Dorian Mölk" finds `dorian-moelk.md`. Calibrated 20.09.2026
        # over all six bundles: seven sentences of the shape, one of them
        # stale, no false positives. (`Beta_kb` AI-2026-09-20-8.)
        # Not in `questions.md`. The item table's whole job is to record faults,
        # so a row describing this very class quotes the sentence that caused
        # it — and the check then fires on the record of its own fix. It did,
        # on 22.09.2026, against the row that had closed it two days earlier.
        # A guard that cannot tell a defect from the note saying the defect was
        # repaired is a guard that punishes writing things down.
        for pm in ([] if rel.endswith('questions.md')
                   else NO_CONCEPT.finditer(prose_c)):
            cand = re.sub(r'[^a-z0-9]+', '-', translit(pm.group(1))).strip('-')
            if cand in person_pages:
                findings.append((rel, 'says %r has no concept, but %s.md '
                                      'exists now' % (pm.group(1), cand)))

        # The checks below were added in the second sitting of 15.09.2026.
        #
        # A paragraph written twice. The compile's linking pass appended a
        # linked copy of a sentence instead of editing it, so five Epsilon_kb
        # concepts carried the same sentence plain and linked, and the fifth
        # survived a first scan because one copy was a prefix of the other
        # (AI-2026-08-31-5). Compared with links and footnote markers stripped;
        # a prefix counts from 80 characters. None stood on 15.09.2026.
        seen_p = []
        dup = None
        for s in _prose_paragraphs(body):
            n = re.sub(r'\[\^[^\]]+\]', '', s)
            n = ' '.join(re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', n).split())
            if len(n) < 60:
                continue
            for o in seen_p:
                if n == o or (min(len(n), len(o)) >= 80
                              and (n.startswith(o) or o.startswith(n))):
                    dup = n[:70]
                    break
            if dup:
                break
            seen_p.append(n)
        if dup:
            findings.append((rel, 'a paragraph stands twice, or once as the '
                                  'start of another: %r' % dup))

        # A source id naming a date its page does not carry, where the page's
        # title and file name agree with each other. The year check above
        # reads the whole page and so passed `stea-20170809` bound to a
        # Kernteam page of 10.10.2016 that mentions 2017 three times (Gamma_kb
        # AI-2026-08-31-6). Measured 15.09.2026: 29 hits, each read; an id that
        # deliberately names a date inside its page is waived with the reason.
        for s4 in srcs:
            if not isinstance(s4, dict):
                continue
            idd = _dates_in(str(s4.get('id', '')))
            if len(idd) != 1:
                continue
            td = _dates_in(str(s4.get('title', '')))
            rd = _dates_in(os.path.basename(str(s4.get('resource', ''))))
            if td & rd and not idd & (td | rd):
                findings.append((rel, 'source id %r names %s; its title and file '
                                      'name both give %s'
                                 % (s4.get('id'), next(iter(idd)),
                                    ', '.join(sorted(td & rd)))))

        # Three em dashes or more in one prose paragraph. The house rule since
        # the owner's ruling of 15.09.2026 is one aside per paragraph, written
        # with one dash or a pair; a third dash is a second aside
        # (Gamma_kb AI-2026-09-08-9, Beta_kb AI-2026-09-08-1).
        dashy = sum(1 for s in _prose_paragraphs(body)
                    if re.sub(r'"[^"\n]*"', '', s).count('\u2014') >= 3)
        if dashy:
            findings.append((rel, '%d paragraph(s) carry three em dashes or '
                                  'more; one aside per paragraph' % dashy))

        # Currency with a comma separator. The owner ruled on 15.09.2026 that
        # the house form is `CHF 4'500` (Beta_kb AI-2026-09-08-1); 157 comma
        # figures stood, 133 of them in Beta_kb, some beside the apostrophe
        # form of the same price. Quoted source text is exempt.
        cm2 = CURRENCY_COMMA.search(re.sub(r'"[^"\n]*"', ' ', prose_c))
        if cm2:
            findings.append((rel, 'currency written with a comma separator: %r; '
                                  "the house form is CHF 4'500" % cm2.group(0)))

        # A category's page total stated against the Raw count, where a
        # knowledge base opts in with `category_page_counts`. Delta_kb wrote
        # six figures from an anonymous crawl as site-wide after the signed-in
        # enumeration replaced them (AI-2026-09-08-1). Only the total-shaped
        # sentences are checked, "N pages carry an article" and "`/en/help/x`
        # is N pages": every other "N pages" in that bundle is a subset, and
        # the general form gave dozens of false hits on 15.09.2026.
        if A.get('category_page_counts') and not rel.endswith('questions.md'):
            cats = collections.Counter(
                os.path.basename(x).split('__')[0]
                for x in re.findall(r'resource:\s*[\'"]?\.\./\.\./Raw/([^\'"\n]+)',
                                    raw)
                if '__' in x and not os.path.basename(x).startswith('de__'))
            if cats:
                cat = cats.most_common(1)[0][0]
                real = len(glob.glob(os.path.join(root, 'Raw', cat + '__*.md')))
                for pm in re.finditer(
                        r'(?i)(?:`/en/help/[a-z0-9-]+` is |\bat )?\b(%s) pages'
                        r'(?= carry an article|,| and|\b)' % PAGENUM, body):
                    ctx = body[max(0, pm.start() - 40):pm.end() + 20]
                    if not re.search(r'carry an article|/en/help/', ctx):
                        continue
                    if _pagenum(pm.group(1)) != real:
                        findings.append((rel, 'says the %s category has %s '
                                              'pages; Raw/ holds %d'
                                         % (cat, pm.group(1), real)))

        # A Date table out of date order. See _scripts/tableorder.py for the
        # definition, which this check, the sort and merge-appends.py share.
        oo = _tableorder.out_of_order(body)
        if oo:
            findings.append((rel, '%d Date table(s) out of date order; run '
                                  'python3 _scripts/tableorder.py %s'
                             % (oo, kb)))

        # A count in questions.md prose against the table it counts. Three
        # times the opening paragraph of Beta_kb's questions.md said a number
        # its table did not carry, and once the run that corrected one count
        # left the next clause wrong (arm f). A DEFECT, because the repair is
        # arithmetic.
        if rel.endswith(os.path.join('Wiki', 'questions.md')):
            flat = '\n'.join(ln for ln in body.split('\n')
                              if not ln.lstrip().startswith('|'))
            ai = _section(body, '# Action items')
            if ai is not None:
                n_open = 0
                for r in re.findall(r'^\|\s*AI-[^|\n]+\|[^|\n]*\|[^|\n]*\|'
                                    r'([^|\n]*)\|', ai, re.M):
                    w = re.sub(r'[*~]', '', r).strip().split()
                    if w and w[0].strip(' ,.;:()[]').lower() == 'open':
                        n_open += 1
                for cm in re.finditer(r'(?i)\b%s (?:action )?items? (?:are|is)'
                                      r' open\b' % NUM, flat):
                    if _num(cm.group(1)) != n_open:
                        defects.append((rel, 'prose says %r; the Action items '
                                             'table holds %d open'
                                        % (cm.group(0), n_open)))
            co = _section(body, '# Contradictions')
            if co is not None:
                n_held = len(_first_table_rows(co))
                claims = list(re.finditer(r'(?i)\b%s contradictions? (?:are|is)'
                                          r' held\b' % NUM, flat))
                lead = re.match(r'\W*%s (?:are|is) held\b' % NUM,
                                co.lstrip('\n'), re.I)
                if lead:
                    claims.append(lead)
                for cm in claims:
                    if _num(cm.group(1)) != n_held:
                        defects.append((rel, 'prose says %r; the Contradictions '
                                             'table holds %d rows'
                                        % (cm.group(0), n_held)))

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
            # everywhere else. Without it the Neda Kaplan pronoun defect had
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
    # one command, `python3 _scripts/reindex.py`. The bundle-root index was
    # skipped here until 14.09.2026, while two root indexes quoted six stale
    # descriptions and one lacked 36 concepts (Zeta_kb AI-2026-09-13-1).
    try:
        import reindex
        for idx in sorted(glob.glob(os.path.join(root, 'Wiki', '**',
                                                 'index.md'), recursive=True)):
            if '_to_delete' in idx:
                continue
            if reindex.expected(idx) != open(idx, encoding='utf-8').read():
                findings.append((os.path.relpath(idx, root),
                                 'index does not match the concepts it lists; '
                                 'run python3 _scripts/reindex.py'))
    except ImportError:
        pass

    # The Action items table must be readable by the generator of the vault
    # roll-up. `actionitems.py` raises when a questions.md carries AI- ids and
    # parses to no rows, and this turns that into a DEFECT so the pre-commit
    # hook blocks on it. Epsilon_kb's table sat in a shape the parser could not
    # read from 31.08. to 14.09.2026, and the roll-up reported 0 open items
    # for it while eight stood. Nothing said anything: an unreadable table and
    # an empty one look identical downstream (Epsilon_kb AI-2026-09-14-3).
    try:
        import actionitems
        actionitems.items(kb)
    except ImportError:
        pass
    except ValueError as e:
        defects.append(('Wiki/questions.md', str(e)))

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
            want = _coverage.state_key(kb)
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

    # The threshold is per knowledge base since 15.09.2026. Beta_kb read five
    # pairs a run from a set that grew from 94 to 366 at three shared sources,
    # and every contradiction it ever found came from a pair sharing seven or
    # more, so the owner set seven there (Beta_kb AI-2026-08-31-3). The others
    # keep three until their own runs measure where findings come from.
    thr = int(A.get('contradiction_threshold') or 3)
    pairs = [(len(resources[a] & resources[b]), a, b)
             for a, b in itertools.combinations(sorted(resources), 2)
             if len(resources[a] & resources[b]) >= thr]
    # Archive pages cited with two or more different `author` values. The
    # exact mirror of the `last_modified` split this vault already gauges —
    # a page has one author as it has one date, so two concepts giving two
    # means at least one is wrong. Measured 20.09.2026 while draining the Gamma
    # SSR contradiction queue: 95 pages split in `Gamma_kb`, 52 in `Beta_kb`,
    # 45 in `Alpha_kb`, against **2** for `last_modified`, which is checked. The
    # defect was some forty times more common than its twin purely because
    # nobody had pointed a script at it, and eight of one reader's sixteen
    # findings were instances of it.
    #
    # A gauge rather than a per-concept finding: the split is a property of
    # the page, not of either concept, and the fix is a reading. Gauges never
    # escalate to a DEFECT.
    auth = collections.defaultdict(set)
    for f in concepts:
        for s in (concepts[f][0] or {}).get('sources') or []:
            if not isinstance(s, dict) or 'author' not in s:
                continue
            r = str(s.get('resource') or '')
            if '/OneNote/' in r:
                auth[r.split('OneNote/')[-1]].add(str(s.get('author')))
    nsplit = sum(1 for v in auth.values() if len(v) > 1)
    if nsplit:
        worst = max(auth.items(), key=lambda kv: len(kv[1]))
        findings.append(('(bundle)',
                         '%d archive page(s) cited with two or more different '
                         'authors; worst %s: %s'
                         % (nsplit, os.path.basename(worst[0]),
                            ', '.join(sorted(worst[1])))))

    if pairs:
        n, a, b = max(pairs)
        findings.append(('(bundle)',
                         '%d contradiction-candidate pairs share %d+ sources; '
                         'largest overlap %d: %s <-> %s'
                         % (len(pairs), thr, n, os.path.relpath(a, root),
                            os.path.relpath(b, root))))

    # A footnote definition written on the line directly under a paragraph,
    # with no blank line between. This is the mirror of the check built for
    # Gamma_kb AI-2026-09-14-10, which catches a paragraph starting under a
    # definition; this catches a definition starting under a paragraph. Under
    # lazy continuation the definition is swallowed as more prose, so the
    # footnote never defines and its marker renders as bracket text. Found in
    # quantity on 20.09.2026 by eight readers working the whole Gamma_kb
    # bundle. A gauge rather than a DEFECT: the two bundles carrying it hold
    # over a hundred cases between them, and wedging the pre-commit hook on
    # a rendering fault nobody has been given a chance to repair would stop
    # unrelated work. `_scripts/fix-footnote-gaps.py` repairs them.
    _glued = []
    for _f, (_fm, _body) in concepts.items():
        _lines = _body.split('\n')
        _fence = False
        for _i, _l in enumerate(_lines):
            if _l.lstrip().startswith('```'):
                _fence = not _fence
                continue
            if _fence or _i == 0:
                continue
            if re.match(r'^\[\^[^\]]+\]:', _l):
                _p = _lines[_i - 1]
                if _p.strip() and not re.match(r'^\[\^[^\]]+\]:', _p):
                    _glued.append(os.path.relpath(_f, root))
    if _glued:
        findings.append(('(bundle)',
                         '%d footnote definition(s) in %d concept(s) sit on '
                         'the line under a paragraph and are swallowed by it; '
                         'repair with python3 _scripts/fix-footnote-gaps.py %s'
                         % (len(_glued), len(set(_glued)), kb)))

    # One archive page given two different `last_modified` values by two
    # concepts. `last_modified` is a semantic date, not the exporter's stamp
    # — see source_real_date above — but a page has one semantic date, so two
    # concepts disagreeing about it means at least one of them is wrong, and
    # nothing outside a reading could tell before this. Found 20.09.2026 by
    # two readers who happened to hold the same pages: `app-v.md` and
    # `programme-app-stream.md` disagreed on two, `gustav-lindqvist.md` and
    # `rafael-ekdahl.md` on five, one of them the page whose year a concept
    # had left open. A gauge, because which side is right needs the page
    # opened, and because the house rule genuinely allows a date the
    # exporter's stamp does not carry.
    _lm = {}
    for _f, (_fm, _body) in concepts.items():
        for _s in (_fm.get('sources') or []):
            if not isinstance(_s, dict) or not _s.get('resource'):
                continue
            _t = os.path.normpath(os.path.join(os.path.dirname(_f),
                                               str(_s['resource'])))
            _lm.setdefault(_t, {}).setdefault(
                str(_s.get('last_modified', 'unknown')), []).append(
                    os.path.relpath(_f, root))
    _split = {t: v for t, v in _lm.items() if len(v) > 1}
    if _split:
        _t, _v = sorted(_split.items())[0]
        findings.append(('(bundle)',
                         '%d archive page(s) are cited with more than one '
                         'last_modified; a page has one semantic date, so at '
                         'least one concept is wrong on each. First: %s, given '
                         '%s' % (len(_split), os.path.basename(_t),
                                 ' and '.join('%s by %s' % (d, c[0])
                                              for d, c in sorted(_v.items())))))

    # A bundle path written inside backticks rather than as a markdown link.
    # The link graph never sees it, so a restructure that moves the target
    # leaves it pointing nowhere and every existing guard passes. The one in
    # Gamma_kb, `../../meeting-series/gamma/programme-streammeeting.md`, survived
    # the three-way split of 15.08.2026 and its "0 broken afterwards" check
    # for that reason, and was found by a reader on 20.09.2026. A gauge,
    # because a backticked path is sometimes quoting history on purpose —
    # log.md and questions.md do it deliberately — and only a reading tells.
    # Only a path that names a concept group, so an archive page quoted by
    # its notebook path and a glob standing for a page set are both left
    # alone. Both are legitimate and neither is a link.
    _groups = {os.path.basename(p) for p in
               glob.glob(os.path.join(root, 'Wiki', '*')) if os.path.isdir(p)}
    _dead = []
    for _f, (_fm, _body) in concepts.items():
        if os.path.basename(_f) == 'questions.md':
            continue
        for _m in re.finditer(r'`([^`\n*]*\.md)`', _body):
            _t = _m.group(1)
            if not any(('/%s/' % g) in _t or _t.startswith('%s/' % g)
                       for g in _groups):
                continue
            _abs = os.path.normpath(os.path.join(os.path.dirname(_f), _t))
            if not os.path.exists(_abs):
                _dead.append((os.path.relpath(_f, root), _t))
    if _dead:
        findings.append(('(bundle)',
                         '%d backticked bundle path(s) resolve to nothing and '
                         'no link check sees them: %s'
                         % (len(_dead), '; '.join('%s -> %s' % d
                                                  for d in _dead[:3]))))

    # Sentences a concept's own later content may have disproved: a date
    # bound a newer cited source passes, or a claim that something is written
    # nowhere. A gauge, never a DEFECT, because about half the date hits are
    # still true and only a reading can tell (Alpha_kb AI-2026-08-31-1).
    sc = len(_staleclaims.scan(kb))
    if sc:
        findings.append(('(bundle)',
                         '%d sentence(s) that later content may have '
                         'disproved; read them first: python3 '
                         '_scripts/stale-claims.py %s' % (sc, kb)))

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


# A meeting join code in a tracked file. The spaced Teams shapes were the
# first form found (Alpha_kb AI-2026-09-14-1, cleaned 15.09.2026); the third arm
# was keyed to the same spacing and so could not see `conference ID 334250`,
# a Skype for Business code standing in two confirmed Gamma_kb concepts and
# found by a reader on 16.09.2026 rather than by this check. The arm now takes
# any digit run of six or more after the words, however it is grouped.
#
# The separator class was ` ` and `:` only, so `conference identifier, 9999999`
# escaped it on a comma. That form stood in `Gamma_kb` in `people/joerg-lanker.md`
# and `meeting-series/cfo-board.md` until 20.09.2026 and was again found by a
# reader rather than by this check, one run after the arm was last widened.
# Comma, dash and equals join the class; a trailing `[withheld]` still passes.
TEAMS_CODE = re.compile(r'\b\d{3} \d{3} \d{3} \d{2,3}\b|\b\d{3} \d{3} \d{2,3}#'
                        r'|(?i:conference (?:ID|identifier|-?ID)\b[\s:,\-–—=]+)'
                        r'(?:\d[\d ]{4,}\d)\b')


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
    # Teams join codes. The concept guard of 14.09.2026 kept them out of the
    # bundles; six tracked compile handbacks still carried them until the
    # owner's ruling of 15.09.2026 (Alpha_kb AI-2026-09-14-1), because a concept
    # rule does not read `_extractions/`. The shape is checked in every tracked
    # text file outside the archive layers.
    for rel in tracked:
        if not rel.endswith(('.md', '.txt', '.tsv', '.json')):
            continue
        try:
            body = open(os.path.join(VAULT, rel), encoding='utf-8',
                        errors='replace').read()
        except OSError:
            continue
        if TEAMS_CODE.search(body):
            defects.append((rel, 'a tracked file carries a Teams join code '
                                 '(meeting or conference ID); record that it '
                                 'exists, never its value'))
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


def packer_dedup():
    """Two pages that differ only in a link are not duplicates.

    `prepare-batch.py` packs a page by swapping every URL for `<link>` and
    every GUID for `<id>`, which is the saving the script exists for. Until
    20.09.2026 it then hashed that packed body to find duplicates, so two
    pages whose only difference was a link hashed alike and one was dropped
    from the pack as `DUPLICATE-OF` the other. The agent was handed a marker
    where it had been told to read a page, and any claim it then made about
    that page was a claim about something nobody opened.

    Three of them were caught by hand in the Delta compile of 20.09.2026, by
    three agents independently, and in one case the page dropped was the one
    carrying a broken link. Telling the next wave to disbelieve the marker
    was a workaround; this is the check, so the class cannot return quietly.

    Run against the module rather than against a packed file, because the
    fault is in the comparison and a pack only shows it when the archive
    happens to hold such a pair.
    """
    rel = '_scripts/prepare-batch.py'
    one = '---\ntitle: A page\n---\n\nOrder it at https://example.org/one please.\n'
    two = '---\ntitle: A page\n---\n\nOrder it at https://example.org/two please.\n'
    try:
        _, _, id_one = _packer.clean_text(one)
        _, _, id_two = _packer.clean_text(two)
    except AttributeError:
        return [(rel, 'clean_text() is gone, so the duplicate check cannot be '
                      'tested: two pages differing only in a link may be '
                      'packed as DUPLICATE-OF each other again')]
    if id_one == id_two:
        return [(rel, 'two pages differing only in a link compare as identical,'
                      ' so one would be packed as DUPLICATE-OF the other and '
                      'never read. Compare the page before its links are '
                      'replaced, as clean_text() documents')]
    return []


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


# Audit reports — health checks and the action sittings on their findings —
# live in this folder under Outputs/. Owner's instruction of 16.09.2026.
AUDIT_DIR = 'HealthChecks'
# A report's German version, same file name one folder deeper.
DE_DIR = 'de'


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
    for sub in ('', AUDIT_DIR):
        dd = os.path.join(d, sub) if sub else d
        if not os.path.isdir(dd):
            continue
        for name in sorted(os.listdir(dd)):
            if not name.endswith('.md') or name.startswith('_'):
                continue
            if name not in text:
                out.append((os.path.join('Outputs', sub, name),
                            'report has no row in Outputs/_REPORTS.md'))

    # An audit report lives in Outputs/HealthChecks/ and a question report at
    # the root of Outputs/. Owner's instruction of 16.09.2026: the audits had
    # grown to 40 of the 50 reports on file and buried the ten that answer a
    # question, which is what the folder is for. The register is the authority
    # on which is which, because it already carries the distinction: an audit
    # report is never promoted, so its Promotion cell reads `audit`.
    #
    # The check reads the register rather than the file names. A name test
    # would pass `2026-08-09_contradiction-sweep.md`, which is an audit and
    # says nothing about health checks, and would fail a question report that
    # happened to ask about one.
    for row in re.finditer(r'^\|\s*20\d\d-\d\d-\d\d\s*\|([^\n]*)$', text, re.M):
        cells = [c.strip() for c in row.group(1).split('|')]
        if len(cells) < 4:
            continue
        link = re.search(r'\]\(([^)]+\.md)\)', cells[2])
        if not link:
            continue
        is_audit = cells[1].lower().startswith('audit')
        in_dir = link.group(1).startswith(AUDIT_DIR + '/')
        if is_audit and not in_dir:
            out.append(('Outputs/_REPORTS.md',
                        'audit report %s belongs in Outputs/%s/'
                        % (link.group(1), AUDIT_DIR)))
        elif in_dir and not is_audit:
            out.append(('Outputs/_REPORTS.md',
                        '%s sits in Outputs/%s/ but its row is not an audit'
                        % (link.group(1), AUDIT_DIR)))

    # A German version is the same report in another language, so it takes no
    # row of its own. **Every question report has one.** Owner's instruction of
    # 16.09.2026, replacing the on-demand rule of the same morning: the
    # translation was written from a button on the report, and the owner wants
    # both languages without asking for the second. The viewer's helper now
    # writes the German version as the last step of answering a question, so
    # the only way one goes missing is a report filed by a session, which is
    # what this catches. Audit reports are English: they are process history
    # and the owner does not read them in German.
    #
    # It is a defect rather than a finding because the fix is one command and
    # the rule is absolute — `python3 _scripts/viewer-server.py` is not needed,
    # the session that filed the report writes the translation the same way it
    # wrote the report. A finding would sit for three run-days first, and by
    # then the report has been read in one language and nobody is looking.
    ddir = os.path.join(d, DE_DIR)
    if os.path.isdir(ddir):
        for name in sorted(os.listdir(ddir)):
            if not name.endswith('.md') or name.startswith('_'):
                continue
            if not os.path.isfile(os.path.join(d, name)):
                out.append((os.path.join('Outputs', DE_DIR, name),
                            'a translation whose English original is gone'))
    for name in sorted(os.listdir(d)):
        if not name.endswith('.md') or name.startswith('_'):
            continue
        if not os.path.isfile(os.path.join(ddir, name)):
            out.append((os.path.join('Outputs', name),
                        'no German version at Outputs/%s/%s' % (DE_DIR, name)))
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
        vd = (vault_audit() + repo_hygiene() + reports_register()
              + packer_dedup())
        print('== 00_Cerebrum (vault): %d defects' % len(vd))
        for rel, msg in vd:
            print('  DEFECT  %s: %s' % (rel, msg))
        total += len(vd)
    touched = list(sys.argv[1:] or discover())
    for kb in touched:
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
        # Findings print in two parts, and both halves were added 20.09.2026.
        #
        # A waived finding used to print character for character like an open
        # one. Nine were waived that day, each with a written reason in
        # `assertions.yaml`, and they went on reading as outstanding work at
        # every run — so the block trained its reader to skip it, which is the
        # exact cost the three-run-day clock exists to avoid. They are marked
        # `waived` now and sort last. (`Beta_kb` AI-2026-09-20-1.)
        #
        # The tail used to be one line: "... N more findings". That hid a
        # whole class. A guard written the same day fired correctly on its
        # proof case and printed nothing, because its finding sat at position
        # 30 of 48 — the check passed its own test and was invisible, which is
        # worse than having no check, since the run reads as clean. The tail is
        # now one line per distinct message shape with its count, so a class
        # can be silent only if it never fires at all.
        def _waived(rel, msg):
            return any(fnmatch.fnmatch(rel, w.get('path', '*'))
                       and w.get('contains', '') in msg
                       for w in waivers)

        open_f = [(r, m) for r, m in findings if not _waived(r, m)]
        waived_f = [(r, m) for r, m in findings if _waived(r, m)]
        for rel, msg in open_f[:20]:
            print('  finding %s: %s' % (rel, msg))
        if len(open_f) > 20:
            shapes = {}
            for rel, msg in open_f[20:]:
                # The shape is the message with its variable parts removed, so
                # 300 citations with 300 different dates collapse to one line.
                key = re.sub(r'\d+', 'N', msg)
                key = re.sub(r'`[^`]*`|\'[^\']*\'', 'X', key)[:90]
                shapes[key] = shapes.get(key, 0) + 1
            print('  ... %d more findings, by shape:' % len(open_f[20:]))
            for key, cnt in sorted(shapes.items(), key=lambda x: -x[1]):
                print('      %4d  %s' % (cnt, key))
        for rel, msg in waived_f:
            print('  waived  %s: %s' % (rel, msg))
        total += len(defects)
    # Re-read and merge rather than writing back what was read at start. A
    # health-check sweep runs one verify.py per knowledge base concurrently,
    # and whole-file read-modify-write made that a lost update: an agent
    # auditing a base with no clocked findings would write back the copy it
    # read, rolling another base's clock back by a run-day. That clock is the
    # thing that escalates a standing finding to a DEFECT, so losing a day
    # delays the escalation silently. Only the bases this run actually audited
    # are taken from memory; every other prefix comes from disk as it stands.
    on_disk = {}
    if os.path.exists(STATE):
        try:
            on_disk = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            on_disk = {}
    mine = tuple(kb + '|' for kb in touched)
    merged = {k: v for k, v in on_disk.items() if not k.startswith(mine)}
    merged.update({k: v for k, v in state.items() if k.startswith(mine)})
    json.dump(merged, open(STATE, 'w', encoding='utf-8'),
              indent=0, sort_keys=True)
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    main()
