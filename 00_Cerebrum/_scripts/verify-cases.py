#!/usr/bin/env python3
"""A failing case for each check `verify.py` makes of a knowledge base.

The rule is "prove the new check fails without its fix". The proof was made
once by hand and thrown away, so nothing said when a check stopped firing:
the corpus is clean, and a clean corpus looks the same to a check that works
and to one that does not. On 05.10.2026 all six bases counted 0 blank-line
faults while a review of the rule found seven things wrong with it.

So the proof is kept. `fixture()` writes a small made-up knowledge base that
the audit passes with nothing to say. Each case changes it in one way and
names words the audit must then say and did not say before. `verify.py` runs
the cases in its vault pass, so a check that stops firing fails the commit.
A case may name words the audit must not say as well, where the fault is one
thing reported twice.

**A check with no case fails the commit too.** `sites()` reads `verify.py` and
lists every place where `audit()` or `export_contract()` reports something,
by the fixed words of its message. Each must be made to fire by some case, or
stand in `OWED`, which holds the few no case here can be counted for and says
why. A new check is not in `OWED`, so it needs its case in the commit that
adds it. A line of `OWED` whose check has a case, or is gone, fails as well:
the list only gets shorter.

The fixture is built in a temporary folder that stands in for the vault:
`bundle.VAULT` points at it while a fresh copy of `verify.py` is loaded and
run, and is put back after. Nothing of the real vault is read or written.

Usage:  python3 _scripts/verify-cases.py            every case, and what is owed
        python3 _scripts/verify-cases.py --sites    each reporting site and its case
"""
import ast
import contextlib
import datetime
import io
import os
import re
import shutil
import sys
import tempfile

import bundle

KB = 'Fixture_kb'
REAL = bundle.VAULT

CONCEPT = """---
type: System
title: {title}
description: {title} is a made-up system of the fixture.
tags: [fixture]
status: stable
generated: {{ by: librarian/claude-opus-5-5, at: 2026-01-10T10:00:00Z }}
sources:
  - id: {sid}
    resource: ../../Raw/{page}
    title: {ptitle}
    author: unknown
    last_modified: 2026-01-05
---

# {title}

{title} runs in the cellar and is switched off at night.[^{sid}] The page calls it "a small and quiet machine for the cellar".[^{sid}] It is described next to [{other}]({other_file}).

[^{sid}]: {ptitle}, 05.01.2026
"""

RAW = """---
title: {ptitle}
author: unknown
source_url: unknown
date_added: 2026-01-05
date_published: 2026-01-05
type: Article
---

# {ptitle}

It is a small and quiet machine for the cellar. It is switched off at night.
"""

FILES = {
    'CLAUDE.md': '# Fixture_kb\n\nA made-up knowledge base for `verify-cases.py`.\n',
    'memory.md': '# memory — Fixture_kb\n\n| What | State |\n|---|---|\n'
                 '| Concepts | 3 |\n| Citations | 2 |\n',
    'assertions.yaml': 'archive_layer: Raw\nquotes_in_page: true\n',
    'CHANGELOG.md': '# CHANGELOG — Fixture_kb\n\n## 2026-01-10 — Made\n\nMade.\n',
    'Raw/_INGESTED.md': '# Ingested\n\n| File | Title |\n|---|---|\n'
                        '| alpha-page.md | Alpha page |\n| beta-page.md | Beta page |\n',
    'Raw/alpha-page.md': RAW.format(ptitle='Alpha page'),
    'Raw/beta-page.md': RAW.format(ptitle='Beta page'),
    'Wiki/log.md': '# Bundle change log\n\n## 2026-01-10\n\n- **Created**: three concepts.\n',
    'Wiki/questions.md': '---\ntype: Open Questions\ntitle: Open questions\n'
                         'description: Open threads of the fixture.\nstatus: stable\n'
                         'generated: { by: librarian/claude-opus-5-5, at: 2026-01-10T10:00:00Z }\n'
                         '---\n\n# Action items\n\n| Id | Raised | Item | State | Resolution |\n'
                         '|---|---|---|---|---|\n\nSee [Alpha](systems/alpha.md) and '
                         '[Beta](systems/beta.md).\n',
    'Wiki/systems/alpha.md': CONCEPT.format(title='Alpha', sid='alpha-page', page='alpha-page.md',
                                            ptitle='Alpha page', other='Beta', other_file='beta.md'),
    'Wiki/systems/beta.md': CONCEPT.format(title='Beta', sid='beta-page', page='beta-page.md',
                                           ptitle='Beta page', other='Alpha', other_file='alpha.md'),
}

A, B = 'Wiki/systems/alpha.md', 'Wiki/systems/beta.md'
Q, RULES = 'Wiki/questions.md', 'assertions.yaml'

# What some cases add to the fixture: a page of a OneNote archive, dated by
# its title, a person, an action item, and an export's list of changed pages.
NOTE = 'OneNote/20260105-kickoff.md'
NOTE_PAGE = '---\ntitle: 20260105 Kickoff\n---\n\nThe kickoff was held in the cellar.\n'
KICKOFF = '../../' + NOTE
ADA = 'Wiki/people/ada-lovelace.md'
PERSON = CONCEPT.format(title='Ada Lovelace', sid='beta-page', page='beta-page.md',
                        ptitle='Beta page', other='Alpha', other_file='../systems/alpha.md')
ROWS = '|---|---|---|---|---|\n'
ITEM = '| AI-2026-01-10-1 | 10.01.2026 | Read the Alpha page again | open | |\n'
CHANGES = 'Raw/_CHANGES-2026-02-01.json'
GLOSS = ('Beta is a made-up system of the fixture, kept in the cellar beside the lamp and the '
         'green door and switched off by hand each night.')
TWICE = 'The cellar door is painted green and the key hangs on a nail beside the lamp.'
LIST = '- System\n- Alpha\n'
CHANGED = ('{"generated": "2026-02-01T08:00:00", "complete": true, "changes": [{"path": '
           '"alpha-page.md", "status": "changed", "contentChanged": true}]}')


def sub(old, new):
    """A change to one file: `old` once, replaced by `new`."""
    def change(text):
        assert text.count(old) == 1, 'the fixture holds %r %d times' % (old, text.count(old))
        return text.replace(old, new)
    return change


def add(more):
    return lambda text: text + more


def chain(*changes):
    """Several changes to one file, one after the other."""
    def change(text):
        for c in changes:
            text = c(text)
        return text
    return change


def para(block):
    """A change to a concept: one more block, above its footnotes."""
    return sub('\n\n[^', '\n\n' + block + '\n\n[^')


def cite(sid, resource, **more):
    """A change to a concept: one more source, which its body does not cite."""
    return sub('sources:\n', 'sources:\n  - id: %s\n    resource: %s\n' % (sid, resource)
               + ''.join('    %s: %s\n' % kv for kv in more.items()))


def block(new):
    """A change to a concept: its frontmatter block replaced by `new`."""
    return lambda text: '---\n' + new + '---\n' + text.split('---\n', 2)[2]


def unlisted(value):
    """A change to a concept: `value` where its list of sources stood."""
    return lambda text: re.sub(r'sources:\n(  .*\n)+', 'sources: %s\n' % value, text)


def day(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()


def dated(old, new, days):
    """`sub`, the `%s` of `new` being the date `days` from the day the case
    runs: a check that reads the clock is held to the clock."""
    return lambda text: sub(old, new % day(days))(text)


def clocked(old, new, hours):
    """`sub`, the `%s` of `new` being the UTC minute `hours` from the moment
    the case runs, as a `generated.at` is written."""
    return lambda text: sub(old, new % (
        datetime.datetime.utcnow() + datetime.timedelta(hours=hours)
    ).strftime('%Y-%m-%dT%H:%M:00Z'))(text)


# (what the case is, {file: change}, words the audit must then say), and
# after those, where it has any, words the audit must not say.
# A change is a function of the file's text, a string that replaces it, or
# None, which removes the file. A file the fixture does not hold is made.
CASES = [
    ('a concept with no frontmatter', {A: lambda t: t.split('---\n', 2)[2]},
     'frontmatter missing'),
    ('a concept with no type', {A: sub('type: System\n', '')}, 'type missing'),
    ('a concept with no sources',
     {A: lambda t: re.sub(r'sources:\n(  .*\n)+', '', t).replace('[^alpha-page]', '')},
     'sources missing'),
    ('a citation whose file is not there', {A: sub('../../Raw/alpha-page.md', '../../Raw/gone.md')},
     'gone.md'),
    ('a quotation with a word cut from its middle',
     {A: sub('a small and quiet machine', 'a small machine')},
     'quotes words that are in no page its footnotes cite'),
    ('the count in memory.md behind the bundle', {'memory.md': sub('| Concepts | 3 |', '| Concepts | 2 |')},
     'memory.md gives 2 concepts and the bundle holds 3'),
    ('memory.md grown past its rule', {'memory.md': add('\n'.join(['line'] * 80) + '\n')},
     'lines long; the rule is roughly 60'),
    ('a concept nothing links to',
     {'Wiki/systems/gamma.md': CONCEPT.format(title='Gamma', sid='alpha-page', page='alpha-page.md',
                                              ptitle='Alpha page', other='Beta', other_file='beta.md'),
      'memory.md': sub('| Concepts | 3 |', '| Concepts | 4 |')},
     'no inbound link from any concept'),
    ('frontmatter that is no YAML', {A: sub('title: Alpha\n', 'title: Alpha: the first\n')},
     'frontmatter unparseable'),
    ('a frontmatter block with nothing in it', {A: block('\n')},
     'frontmatter is not keys and values: it is empty'),
    # Four scripts the audit calls read the block too, and each stopped on a
    # list: `coverage.py` and `stale-claims.py` on every run, `reindex.py`
    # where the folder has an index, `changed-pages.py` where an export
    # changed a page. So did the audit's own `description_of()`, where a
    # bullet of another concept glosses the one with the list. One case for
    # each way in.
    ('a frontmatter block that is a list', {A: block(LIST)},
     'frontmatter is not keys and values: it is a list'),
    ('the same list, in a folder that has an index',
     {A: block(LIST), 'Wiki/systems/index.md': '# Systems\n'},
     'frontmatter is not keys and values: it is a list'),
    ('the same list, after an export changed a page', {A: block(LIST), CHANGES: CHANGED},
     'frontmatter is not keys and values: it is a list'),
    ('the same list, glossed in a bullet of another concept',
     {B: block(LIST), A: para('- [Beta](beta.md) — ' + GLOSS[:104])},
     'frontmatter is not keys and values: it is a list'),
    ('one page cited under two ids',
     {A: cite('alpha-again', '../../Raw/alpha-page.md', last_modified='2026-01-05')},
     'one page cited under 2 ids (alpha-again, alpha-page)'),
    ('an archive author written as a display name',
     {NOTE: NOTE_PAGE, A: cite('kickoff', KICKOFF, author='Ada Lovelace')},
     "source author 'Ada Lovelace' is not human:<slug>"),
    ('a concept verified by a script',
     {A: sub('status: stable\n', 'status: stable\nverified: { by: process:verify, '
                                 'at: 2026-01-11T08:00:00Z }\n')},
     'verified.by is not a human actor: process:verify'),
    ('a verified key the CHANGELOG knows nothing of',
     {A: sub('status: stable\n', 'status: stable\nverified: { by: human:owner, '
                                 'at: 2026-01-11T08:00:00Z }\n')},
     'verified key present but no CHANGELOG entry records the confirmation'),
    ('a verified key that is a bare actor',
     {A: sub('status: stable\n', 'status: stable\nverified: human:owner\n')},
     "verified is 'human:owner', not a mapping of by and at"),
    ('a generated key that is a bare actor',
     {A: sub('generated: { by: librarian/claude-opus-5-5, at: 2026-01-10T10:00:00Z }',
             'generated: librarian/claude-opus-5-5')},
     "generated is 'librarian/claude-opus-5-5', not a mapping of by and at"),
    ('a key written twice in one source',
     {A: sub('    author: unknown\n', '    author: unknown\n    author: human:owner\n')},
     "duplicate key 'author' inside one sources entry"),
    ('a source that is a bare path',
     {A: sub('sources:\n', 'sources:\n  - ../../Raw/beta-page.md\n')},
     'malformed sources entry'),
    # `sources` that is no list, and an `id` or a `resource` that is no text:
    # a number in any of the three stopped the whole audit, and so did an
    # `id` that is a list. A sentence went on, reported once for each letter.
    ('sources written as a number', {A: unlisted('5')},
     'sources is 5, not a list of entries'),
    ('sources written as a sentence, reported once', {A: unlisted('the alpha page')},
     "sources is 'the alpha page', not a list of entries", 'malformed sources entry'),
    ('a source id that is a list', {A: sub('- id: alpha-page', '- id: [alpha-page, beta]')},
     "source id is ['alpha-page', 'beta'], not text"),
    ('a source id that is a number', {A: sub('- id: alpha-page', '- id: 5')},
     'source id is 5, not text'),
    ('a source whose resource is a number',
     {A: sub('resource: ../../Raw/alpha-page.md', 'resource: 5')},
     'source resource is 5, not a path'),
    ('a citation into a scope the owner has barred',
     {RULES: add("barred_scopes:\n  - pattern: 'Raw/alpha'\n    reason: kept out\n")},
     'cites a barred archive scope: ../../Raw/alpha-page.md (kept out)'),
    ('a source dated against its rule',
     {RULES: add("source_rules:\n  - resource_pattern: 'Raw/alpha'\n"
                 "    require_last_modified: unknown\n    reason: the stamp is the export's\n")},
     'last_modified must be unknown'),
    ('a vault file dated other than its name',
     {'../_testimony/2026-01-05_testimony-cellar.md': 'The cellar is dry.\n',
      A: cite('cellar', '../../../_testimony/2026-01-05_testimony-cellar.md',
              last_modified='2026-01-06')},
     "last_modified 2026-01-06, but the file's own name gives 2026-01-05"),
    ('an archive page dated other than its title',
     {NOTE: NOTE_PAGE, A: cite('kickoff', KICKOFF, last_modified='2026-01-06')},
     "last_modified 2026-01-06, but the page's own title gives 2026-01-05"),
    ('the owner as author of a page older than his start',
     {RULES: add('owner_author_not_before:\n  date: 2026-02-01\n'), NOTE: NOTE_PAGE,
      A: cite('kickoff', KICKOFF, author='human:owner', last_modified='2026-01-05')},
     'author is human:owner, but the page is dated 2026-01-05, before 2026-02-01'),
    ('a footnote to a source the concept does not list',
     {A: sub('at night.[^alpha-page]', 'at night.[^alpha]')},
     'footnote label has no sources id: alpha'),
    ('a source no footnote cites',
     {A: cite('spare', '../../Raw/beta-page.md', last_modified='2026-01-05')},
     'source ids never cited: spare'),
    ('a source id naming a year its page does not carry',
     {A: cite('beta-2019', '../../Raw/beta-page.md', last_modified='2026-01-05')},
     "source id 'beta-2019' names 2019 and its document carries no such date"),
    ('a concept older than a page it cites',
     {A: sub('last_modified: 2026-01-05', 'last_modified: 2026-02-01')},
     'generated.at 2026-01-10 older than newest cited source 2026-02-01'),
    ('a source dated after today',
     {A: dated('last_modified: 2026-01-05', 'last_modified: %s', 30)},
     '1 cited source(s) dated after today'),
    ('a concept dated two days from now, with no time of day',
     {A: dated('at: 2026-01-10T10:00:00Z', 'at: %s', 2)}, 'is in the future'),
    ('a concept stamped three hours ahead of the clock',
     {A: clocked('at: 2026-01-10T10:00:00Z', 'at: %s', 3)}, 'minutes ahead of the clock'),
    ('a concept stamped two days ahead of the clock, reported once',
     {A: clocked('at: 2026-01-10T10:00:00Z', 'at: %s', 48)}, 'minutes ahead of the clock',
     'is in the future'),
    ('a concept saying I', {A: para('I read the page twice.')},
     "concept speaks in the first person; the voice is the librarian's"),
    ('a concept saying I straight after a footnote marker',
     {A: para('The lamp is new.[^alpha-page] I read the page twice.')},
     "concept speaks in the first person; the voice is the librarian's"),
    ('a concept naming the batch it was compiled from',
     {A: para('Nothing in this batch names the owner.')},
     "compile vocabulary in a concept: 'this batch'"),
    ('a footnote reference with no definition',
     {A: sub('[^alpha-page]: Alpha page, 05.01.2026\n', '')},
     'footnote reference(s) with no definition line, rendered as bracket text: alpha-page'),
    ('a heading inside a heading', {A: para('# ## The cellar')},
     "heading carries a second heading marker: '# ## The cellar'"),
    ('a fence that never closes', {A: para('```')}, 'a fenced block never closes'),
    ('a paragraph glued under a list item', {A: para('- one switch\nThe switch is grey.')},
     '1 paragraph(s) glued under a list item'),
    ('a paragraph glued under a footnote definition', {A: add('It hums.\n')},
     '1 paragraph(s) glued under a footnote definition'),
    ('a claim that the export lost a picture',
     {RULES: add('export_loss_claims: true\n'),
      A: para('The picture did not survive the export.')},
     "claims the export lost something: 'did not survive the export'"),
    ('a person said to be unidentified, who has a concept',
     {ADA: PERSON, A: para('Ada Lovelace is not identified in the page.')},
     "says 'Ada Lovelace' has no concept, but ada-lovelace.md exists now"),
    ('a paragraph written twice', {A: para(TWICE + '\n\n' + TWICE)},
     'a paragraph stands twice'),
    ('a source id naming a day its title and file name do not',
     {NOTE: NOTE_PAGE, A: cite('kickoff-20260107', KICKOFF, title='20260105 Kickoff',
                               last_modified='2026-01-05')},
     "source id 'kickoff-20260107' names 20260107; its title and file name both give 20260105"),
    ('three em dashes in one paragraph',
     {A: para('The cellar — cold — holds the machine — and little else.')},
     '1 paragraph(s) carry three em dashes or more'),
    ('a price with a comma', {A: para('The machine cost CHF 4,500.')},
     "currency written with a comma separator: 'CHF 4,500'"),
    ('a category said to hold more pages than Raw does',
     {RULES: add('category_page_counts: true\n'),
      'Raw/cellar__lamp.md': RAW.format(ptitle='The lamp'),
      A: chain(cite('lamp', '../../Raw/cellar__lamp.md', last_modified='2026-01-05'),
               para('Three pages carry an article.'))},
     'says the cellar category has Three pages; Raw/ holds 1'),
    ('a Date table with a row out of order',
     {A: para('| Date | Event |\n|---|---|\n| 2026-01-05 | The lamp was hung |\n'
              '| 2025-12-01 | The door was painted |')},
     '1 Date table(s) out of date order'),
    ('a count of open items the table does not hold',
     {Q: sub(ROWS, ROWS + ITEM + '\nTwo action items are open.\n\n# Open threads\n')},
     "prose says 'Two action items are open'; the Action items table holds 1 open"),
    ('a count of contradictions the table does not hold',
     {Q: add('\n# Contradictions\n\nTwo contradictions are held.\n\n| Pair | What |\n|---|---|\n'
             '| Alpha, Beta | two cellars |\n')},
     "prose says 'Two contradictions are held'; the Contradictions table holds 1 rows"),
    ('a draft that does not say why',
     {RULES: add('draft_needs_reason: true\n'), A: sub('status: stable', 'status: draft')},
     'status is draft and the concept does not say why'),
    ('a concept past its stale_after',
     {A: sub('status: stable\n', 'status: stable\nstale_after: 2026-02-01\n')},
     'past stale_after 2026-02-01'),
    ('a stale_after that is no date',
     {A: sub('status: stable\n', 'status: stable\nstale_after: soon\n')},
     "stale_after is not a YYYY-MM-DD date: 'soon'"),
    ('a stale_after that is no date, over a present-tense claim',
     {A: chain(sub('status: stable\n', 'status: stable\nstale_after: "2026-2-1"\n'),
               para('The machine is currently switched off.'))},
     "stale_after is not a YYYY-MM-DD date: '2026-2-1'"),
    ('a present-tense claim with no stale_after',
     {A: para('The machine is currently switched off.')},
     'present-tense claim with no stale_after: "currently"'),
    ('a paragraph run on under a footnote reference',
     {A: para('The lamp is new.[^alpha-page]\nThe key is old.')}, '1 paragraph(s) run on'),
    ('a table glued under a paragraph',
     {A: para('The parts are these.\n| Part | Colour |\n|---|---|\n| Lamp | green |')},
     '1 table row(s) sit directly under prose and render as literal pipes; run python3'),
    ('a row glued under a paragraph, below the table it continues',
     {A: para('| Part | Colour |\n|---|---|\n| Lamp | green |\n\nThe key came later.\n'
              '| Key | old |')},
     '1 table row(s) sit directly under prose and render as literal pipes; run python3'),
    ('a row glued under a paragraph, with no table to go to',
     {A: para('The parts are these.\n| Lamp | green |')},
     '1 table row(s) sit directly under prose and render as literal pipes; a reader must'),
    ('a table with no header row', {A: para('| Lamp | green |\n| Key | old |')},
     '1 table(s) start on a data row'),
    ('a row with its footnote in a cell too many',
     {A: para('| Part | Colour |\n|---|---|\n| Lamp | green | [^alpha-page] |')},
     '1 row run(s) differ in column count from the table they sit in; run python3'),
    ('a row a cell wider than its table',
     {A: para('| Part | Colour |\n|---|---|\n| Lamp | green | new |')},
     '1 row run(s) differ in column count from the table they sit in; a reader must'),
    ('a link description cut mid-word',
     {B: sub('description: Beta is a made-up system of the fixture.', 'description: ' + GLOSS),
      A: para('- [Beta](beta.md) — ' + GLOSS[:104])},
     '1 link description(s) truncated mid-word'),
    ('a person said to have no concept, who has one',
     {ADA: PERSON, A: para('There is no concept for Ada Lovelace.')},
     'says Ada Lovelace has no concept, but Wiki/people/ada-lovelace.md exists'),
    ('a person said to have no concept, in words two checks match: reported once',
     {ADA: PERSON, A: para('Ada Lovelace has no concept.')},
     "says 'Ada Lovelace' has no concept, but ada-lovelace.md exists now",
     'says Ada Lovelace has no concept, but Wiki/people/ada-lovelace.md exists'),
    ('a forbidden phrase',
     {RULES: add("forbid:\n  - pattern: 'switched off at night'\n    reason: it runs all night\n")},
     "forbidden pattern 'switched off at night': it runs all night"),
    ('a superseded claim without its correction',
     {RULES: add("require_together:\n  - if_pattern: 'runs in the cellar'\n"
                 "    then_pattern: 'until the move'\n    reason: it moved to the attic\n")},
     "states 'runs in the cellar' without 'until the move': it moved to the attic"),
    ('an action item id dated a month from now',
     {Q: dated('See [Alpha]', 'The lamp is AI-%s-1. See [Alpha]', 30)},
     'action item id dated in the future: AI-'),
    ('a CHANGELOG entry dated a month from now',
     {'CHANGELOG.md': dated('## 2026-01-10 — Made', '## %s — Later\n\nLater.\n\n'
                            '## 2026-01-10 — Made', 30)},
     'entry dated in the future: '),
    ('an index that lists one concept of two',
     {'Wiki/systems/index.md': '# Systems\n\n* [Alpha](alpha.md) - Alpha is a made-up system '
                               'of the fixture.\n'},
     'index does not match the concepts it lists'),
    ('a hand-written root index that links one concept of two',
     {RULES: add('root_index_complete: true\n'),
      'Wiki/index.md': '---\nokf_version: "0.2"\n---\n\n# Fixture\n\n'
                       '* [Alpha](systems/alpha.md) — the first system\n'},
     'the root index links concepts of systems/ and not beta.md'),
    ('an Action items table with no heading after it', {Q: sub(ROWS, ROWS + ITEM)},
     'carries AI- ids but no row was parsed'),
    ('an action item in a state nobody defined',
     {Q: sub(ROWS, ROWS + ITEM.replace('open', 'pending') + '\n# Open threads\n')},
     "unrecognised action item state 'pending'"),
    ('an archive whose coverage was never measured', {'COVERAGE.md': None},
     'archive coverage never measured'),
    ('a page added to the archive after its coverage was measured',
     {'Raw/gamma-page.md': RAW.format(ptitle='Gamma page')}, 'coverage table stale'),
    ('a required file that is gone', {RULES: add('require_file:\n  - Wiki/systems/gamma.md\n')},
     'required file missing (settled fact)'),
    ('a link into a knowledge base whose archive is cleared',
     {'../Cleared_kb/OneNote/_index.md': '# Index\n',
      A: para('It came from [Delta](../../../Cleared_kb/Wiki/systems/delta.md).')},
     'link into a knowledge base that is cleared and awaiting a new archive'),
    ('a link across knowledge bases at the wrong depth',
     {A: para('It is also [Beta](../../Fixture_kb/Wiki/systems/beta.md).')},
     'cross-KB link resolves nowhere: ../../Fixture_kb/Wiki/systems/beta.md; resolves as beta.md'),
    ('a link to a concept not yet written', {A: para('It is older than [Delta](delta.md).')},
     'dead link (legitimate under OKF): delta.md'),
    ('one archive page given two authors',
     {NOTE: NOTE_PAGE, A: cite('kickoff', KICKOFF, author='human:ada'),
      B: cite('kickoff', KICKOFF, author='human:bob')},
     '1 archive page(s) cited with two or more different authors'),
    ('two concepts that share a page and were never read together',
     {RULES: add('contradiction_threshold: 1\n'),
      B: cite('alpha-page', '../../Raw/alpha-page.md', last_modified='2026-01-05')},
     '1 of 1 contradiction-candidate pairs (1+ shared sources) are unread'),
    ('a footnote definition glued under a paragraph',
     {A: sub('.\n\n[^alpha-page]:', '.\n[^alpha-page]:')},
     '1 footnote definition(s) in 1 concept(s) sit on the line under a paragraph'),
    ('one page given two dates by two concepts',
     {B: cite('alpha-page', '../../Raw/alpha-page.md', last_modified='2026-01-06')},
     '1 archive page(s) are cited with more than one last_modified'),
    ('a backticked path to a concept that is not there',
     {A: para('It replaced `../systems/delta.md`.')},
     '1 backticked bundle path(s) resolve to nothing'),
    ('a date bound a newer source has passed', {A: para('The machine ran to at least 2025.')},
     '1 sentence(s) that later content may have disproved'),
    ('a claim that something is written nowhere',
     {A: para('Its colour is not recorded anywhere.')},
     '1 sentence(s) that later content may have disproved'),
    ('a page an export changed after its concept was written',
     {CHANGES: CHANGED},
     '1 concept(s) were written before a page they cite changed in an export'),
    ('a section written below the footnotes', {A: add('\n# Later\n\nThe lamp was changed.\n')},
     '1 concept(s) carry body content after their footnote definitions'),
    ('a section filed under Related',
     {A: para('# Related\n\nSee the lamp.\n\n# History\n\nThe lamp was changed.')},
     '1 concept(s) carry body content after their footnote definitions'),
    ('a description three years behind its newest source',
     {A: sub('fixture.\ntags', 'fixture, set up in 2023.\ntags')},
     '1 description(s) name a newest year two or more behind the newest source'),
    ('an undated image whose name carries its day',
     {'Raw/image2026-1-5_10-00-00.png': 'a picture',
      A: cite('shot', '../../Raw/image2026-1-5_10-00-00.png', last_modified='unknown')},
     '1 image source(s) stand at last_modified: unknown'),
    ('an undated image whose page names it by its day',
     {'Raw/79234575.png': 'a picture',
      'Raw/alpha-page.md': add('\n- [image2026-1-5_10-00-00.png](79234575.png)\n'),
      A: cite('shot', '../../Raw/79234575.png', last_modified='unknown')},
     'first: Wiki/systems/alpha.md -> image2026-1-5_10-00-00.png'),
    ('an archive deleted under its citations',
     {'Raw/alpha-page.md': None, 'Raw/beta-page.md': None},
     'archive layer absent: 2 citations into Raw/ could not be checked'),
    ('a change report that is no JSON', {CHANGES: '{'},
     'the newest change report does not parse'),
    ('a change report that does not say whether it is complete',
     {CHANGES: '{"generated": "2026-02-01T08:00:00", "changes": []}'}, 'no `complete` field'),
    ('a change report whose changes are no list', {CHANGES: '{"complete": true, "changes": {}}'},
     '`changes` is not a list'),
    ('a change report that does not say what changed',
     {CHANGES: '{"complete": true, "changes": [{"path": "alpha-page.md", "status": "changed"}]}'},
     'no change record carries `contentChanged`'),
]

# Reporting sites with no case the run can count: the fixed words each
# message opens with. The list only gets shorter. What is left, and why:
#
#   ''      The unreadable Action items table is reported in the words of
#           `actionitems.py`, so its message has no fixed words for a case to
#           be matched by. Two cases above make it fire, by those words.
#   stamp   A source stamp older than its file's last commit: the audit asks
#           git for the commit, and the fixture's folder is no repository.
OWED = {
    '',
    '%d source stamp(s) name a date older than the last commit of',
}


# Rules that are no reporting site of the audit: what a quotation is, when a
# pair counts as read, when a concept is behind a page. Each is (what, what
# the rule gives, what it must give).
PAGE = ('Er sagte: „Wir beginnen mit der ISG“ und ging. It is **not** a cloud '
        'product (see [the rules](x.html) ).')
QUOTED = [   # (what, a body, the quotations that must be reported)
    ('a quotation as the page has it', 'He said "Wir beginnen mit der ISG".[^p]', []),
    ('the first letter fitted to the sentence', 'He said "wir beginnen mit der ISG".[^p]', []),
    ('a full stop inside the closing mark', 'He said "Wir beginnen mit der ISG."[^p]', []),
    ('a word cut from the middle', 'He said "Wir beginnen der ISG".[^p]',
     ['Wir beginnen der ISG']),
    ('the same cut, with its ellipsis', 'He said "Wir beginnen ... der ISG".[^p]', []),
    ('a capital changed inside', 'He said "Wir beginnen mit der Isg".[^p]',
     ['Wir beginnen mit der Isg']),
    ('bold inside the page', 'It says "It is not a cloud product".[^p]', []),
    ('a nested quotation', 'It says "It is "not" a cloud product".[^p]', []),
    ('the space a link leaves before a bracket', 'It says "(see the rules)".[^p]', []),
    ('an English gloss after a quotation',
     'He said "Wir beginnen mit der ISG" ("we start with the ISG").[^p]', []),
    ('a label of two words', 'The button "der Keller" is grey.[^p]', []),
    ('a block with no footnote', 'He said "these words are in no page".', []),
    ('a mark inside inline code', 'Type `echo "x` and "Wir beginnen mit der ISG".[^p]', []),
    ('words no page holds', 'He said "these words are in no page".[^p]',
     ['these words are in no page']),
]

# The clock check at fixed instants, so the hour the cases run at decides
# nothing: (what, a `generated.at`, the UTC clock, the minutes it is ahead).
# Until 05.10.2026 the audit held a stamp's date to the local day and its
# minutes to the UTC clock, and the second line passed at 00:30 in Zurich.
_AT = datetime.datetime
AHEAD = [
    ('three hours ahead inside one UTC day', '2026-10-05T13:00:00Z', _AT(2026, 10, 5, 10, 0), 180),
    ('across UTC midnight', '2026-10-06T03:00:00Z', _AT(2026, 10, 5, 22, 30), 270),
    ('in the last hour of the UTC day', '2026-10-06T01:15:00Z', _AT(2026, 10, 5, 23, 30), 105),
    ('as PyYAML hands a stamp back', '2026-10-06 03:00:00+00:00', _AT(2026, 10, 5, 22, 30), 270),
    ('with an offset of its own', '2026-10-06T01:00:00+02:00', _AT(2026, 10, 5, 22, 30), 30),
    ('behind the clock', '2026-10-05T10:00:00Z', _AT(2026, 10, 5, 22, 30), -750),
    ('two days ahead', '2026-10-07T22:30:00Z', _AT(2026, 10, 5, 22, 30), 2880),
    ('a bare date', '2026-10-07', _AT(2026, 10, 5, 22, 30), None),
]


def rule_failures():
    out = []
    V = bundle.script('verify.py')
    for what, at, now, want in AHEAD:
        got = V.minutes_ahead(at, now)
        if got != want:
            out.append('verify.py, a stamp %s: %s at %s is %r minutes ahead, must be %r'
                       % (what, at, now, got, want))
    Q = bundle.script('quotes.py')
    for what, body, want in QUOTED:
        got = [q for _, q, _ in Q.missing(body.split('\n'), {'p': Q.normal(PAGE)})[0]]
        if got != want:
            out.append('quotes.py, %s: reports %r, must report %r' % (what, got, want))
    if Q.missing(['He said "these words are in no page".[^p]'], {'p': None})[0]:
        out.append('quotes.py reports a quotation whose page is no text')

    P = bundle.script('pairs.py')
    bodies = {'a.md': 'one', 'b.md': 'two', 'c.md': 'three'}
    P._body, P.name = (lambda f: bodies[f]), (lambda kb, f: f)
    pairs = P.candidates({'a.md': {1, 2, 3}, 'b.md': {1, 2, 3, 4}, 'c.md': {1}}, 3)
    done = {}
    steps = [('one candidate pair at three shared pages', pairs, [(3, 'a.md', 'b.md')]),
             ('a mistyped path is recorded as nothing',
              (P.mark(KB, [('a.md', 'x.md')], pairs, done), dict(done)), ([('a.md', 'x.md')], {})),
             ('a pair marked in either order is read',
              (P.mark(KB, [('b.md', 'a.md')], pairs, done), P.unread(KB, pairs, done)), ([], []))]
    bodies['a.md'] = 'one, changed'
    steps.append(('a changed side puts the pair back', P.unread(KB, pairs, done), pairs))
    out += ['pairs.py, %s: gives %r, must give %r' % s for s in steps if s[1] != s[2]]

    C = bundle.script('changed-pages.py')
    got = C.behind({'pg': '2026-09-13T17:31:20'},
                   {'old.md': ('2026-09-01T00:00:00', {'pg'}),
                    'new.md': ('2026-09-20T00:00:00', {'pg'}),
                    'else.md': ('2026-09-01T00:00:00', {'other'})})
    if [r[2] for r in got] != ['old.md']:
        out.append('changed-pages.py: a concept written before its page changed is %r, '
                   'must be old.md alone' % [r[2] for r in got])
    return out


def fixture(root):
    """Write the made-up vault under `root`, which `bundle.VAULT` already
    names, and return its knowledge base. The coverage table is written by
    `coverage.py` itself, as in a real base."""
    os.symlink(os.path.join(REAL, '_scripts'), os.path.join(root, '_scripts'))
    for rel, text in FILES.items():
        p = os.path.join(root, KB, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8').write(text)
    argv, sys.argv = sys.argv, ['coverage.py', KB]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            bundle.script('coverage.py').main()
    finally:
        sys.argv = argv
    return os.path.join(root, KB)


def messages(V):
    n, c, defects, findings = V.audit(KB)
    return ([('DEFECT', m) for _, m in defects + V.export_contract(KB)]
            + [('finding', m) for _, m in findings])


def _own():
    """The vault's own scripts that are imported by name, `bundle` left out."""
    here = os.path.join(REAL, '_scripts') + os.sep
    return [n for n, m in sys.modules.items()
            if n != 'bundle' and (getattr(m, '__file__', None) or '').startswith(here)]


def run(cases=None):
    """(clean, results): what the audit says of the untouched fixture, and for
    each case the messages it added and the words it must not say.

    A script imported by name keeps the vault it was imported under. The
    audit imports `actionitems` and `reindex` that way and late, so the first
    version of this run left them bound to the made-up vault, and the real
    audit that followed read no action item and no index of any base: found
    on 05.10.2026, the day it was written. Such scripts are set aside for the
    run and put back after, and what the run imported is dropped."""
    root = tempfile.mkdtemp(prefix='verify-cases-')
    held = {n: sys.modules.pop(n) for n in _own()}
    try:
        bundle.VAULT = root
        base = fixture(root)
        clean = messages(bundle.script('verify.py'))
        results = []
        for what, changes, expect, *never in (CASES if cases is None else cases):
            kept = {}
            for rel, change in changes.items():
                p = os.path.join(base, rel)
                kept[p] = open(p, encoding='utf-8').read() if os.path.exists(p) else None
                new = change(kept[p] or '') if callable(change) else change
                if new is None:
                    os.remove(p)
                else:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, 'w', encoding='utf-8').write(new)
            bundle._parsed.clear()
            try:
                said = [m for m in messages(bundle.script('verify.py')) if m not in clean]
            finally:
                for p, old in kept.items():
                    if old is None:
                        os.remove(p)
                    else:
                        open(p, 'w', encoding='utf-8').write(old)
            results.append((what, expect, said, never))
        return clean, results
    finally:
        bundle.VAULT = REAL
        bundle._parsed.clear()
        for n in _own():
            del sys.modules[n]
        sys.modules.update(held)
        shutil.rmtree(root, ignore_errors=True)


def sites():
    """(line, the fixed opening words of the message) for each place where
    `audit()` or `export_contract()` reports. A message built from no fixed
    words is given as ''."""
    src = open(os.path.join(REAL, '_scripts', 'verify.py'), encoding='utf-8').read()
    out = []
    for fn in ast.parse(src).body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name in ('audit', 'export_contract')):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'append'
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ('defects', 'findings')
                    and node.args and isinstance(node.args[0], ast.Tuple)
                    and len(node.args[0].elts) == 2):
                words = next((n.value for n in ast.walk(node.args[0].elts[1])
                              if isinstance(n, ast.Constant) and isinstance(n.value, str)
                              and len(n.value.strip()) > 3), '')
                out.append((node.lineno, words))
    return sorted(out)


def pattern(words):
    """A message's fixed words as a pattern, its `%s` and `%d` open."""
    return re.compile('.*'.join(re.escape(p) for p in re.split(r'%[-#0 +]*\d*(?:\.\d+)?[sdrfi]', words)))


def opening(words):
    return ' '.join(words.split())[:60]


def failures():
    """What `verify.py` reports: a case that no longer fires, a reporting
    site with no case that is not owed, an owed line that is no longer owed."""
    clean, results = run()
    out = ['the untouched fixture is not clean: %s: %s' % m for m in clean]
    out += ['the run left `%s` bound to the made-up vault, so the audit that follows '
            'reads nothing through it' % n for n in _own()
            if getattr(sys.modules[n], 'VAULT', REAL) != REAL]
    fired = [m for _, _, said, _ in results for _, m in said]
    for what, expect, said, never in results:
        if not any(expect in m for _, m in said):
            out.append('case "%s" no longer makes the audit say: %s' % (what, expect))
        out += ['case "%s" makes the audit say what it must not: %s' % (what, m)
                for _, m in said if any(n in m for n in never)]
    found = set()
    for line, words in sites():
        key = opening(words)
        found.add(key)
        covered = bool(words) and any(pattern(words).search(m) for m in fired)
        if covered and key in OWED:
            out.append('"%s" has a case now; take it out of OWED' % key)
        if not covered and key not in OWED:
            out.append('the check at line %d has no kept case: "%s"' % (line, key))
    out += ['OWED names a check that is gone: "%s"' % k for k in sorted(OWED - found)]
    return out + rule_failures()


def main():
    if '--sites' in sys.argv:
        clean, results = run()
        fired = [(what, m) for what, _, said, _ in results for _, m in said]
        for line, words in sites():
            by = next((w for w, m in fired if words and pattern(words).search(m)), None)
            print('%5d  %-5s %s%s' % (line, 'case' if by else 'OWED' if opening(words) in OWED else 'NONE',
                                      opening(words), '   <- ' + by if by else ''))
        return
    bad = failures()
    for m in bad:
        print('FAIL  ' + m)
    print('%d case(s), %d reporting site(s), %d owed, %d failure(s)'
          % (len(CASES), len(sites()), len(OWED), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
