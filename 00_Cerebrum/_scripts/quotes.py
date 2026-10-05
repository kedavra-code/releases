#!/usr/bin/env python3
"""Lists quotations that are not in the page they cite.

`verify.py` resolves every citation to a file and never compares the sentence
with the page. A model was tried for that comparison on 23.09.2026 and failed
its bench. What a script can compare exactly is a direct quotation: the words
between quotation marks either stand in the cited page or they do not. On
04.10.2026 readers corrected sixteen quotations in eleven `Delta_kb` concepts,
words cut from the middle of a sentence with no ellipsis, a capital changed, a
sentence footnoted to the page in the other language, and no check had seen
one (`Delta_kb` AI-2026-10-04-5).

How a quotation is read:

  - A span between two straight double quotation marks, in one paragraph,
    table row or list item, with three words or more. Shorter spans are
    labels and menu names far more often than quotations.
  - It is looked for in the pages of every footnote of its block. One page
    holding it is enough: a sentence may quote one page to say that another
    dropped the words.
  - Both sides are compared with quotation marks, emphasis marks and line
    breaks taken out, and no space before a closing mark of punctuation, so a
    nested quotation, bold inside a quotation, a page's own `„…“` and the
    space a link leaves before a bracket do not part them. Every letter
    counts. Two things are the writer's to fit a quotation into a sentence:
    the case of its first letter, and punctuation at its two ends.
  - An ellipsis or a bracketed insertion cuts a span into parts, and each
    part of two words or more must be in the page.
  - A span in round or square brackets straight after another quotation is
    its English gloss, a translation, and is left alone.

What it cannot see it does not report: a page that is a picture or an office
document with no extracted text, a web address, a block with no footnote, a
block whose quotation marks do not pair.

Calibrated on `Delta_kb` on 05.10.2026, whose pages are public: 514 quotations
compared and 5 flagged, each read against its pages. None was a misquotation.
One was the concept quoting its own earlier wording, two a label that other
pages carry, two the concept's own name for a notice. `verify.py` raises a
finding for each in a base that sets `quotes_in_page: true`, and those five
are waived there by reason. The other bases were counted that day and not
read: 186 of 3'411 in `Alpha_kb`, 82 of 1'185 in `Beta_kb`, 89 of 1'224 in
`Gamma_kb`, 28 of 280 in `Epsilon_kb`, 2 of 33 in `Zeta_kb`. `Alpha_kb` takes
14 seconds, which a base that opts in pays on every audit.

Figures and dates were tried the same day by the same method, each number of
three digits or more and each date looked for in the pages of its block, and
are not built. 289 of 844 were flagged in `Delta_kb` and 1'252 of 13'858 in
`Alpha_kb`. Twelve drawn from the `Delta_kb` flags were all the concept's own
measurements: the day a search ran, a count of pages or characters, a status
code. A concept states what it counted, and no page holds that.

Usage:  python3 _scripts/quotes.py [KB ...] [--tsv] [--stats]
"""
import functools
import os
import re
import sys
import unicodedata

import bundle
from bundle import VAULT, FM, concept_files, discover

_blanklines = bundle.script('blanklines.py')

WORDS = 3                       # a span shorter than this is a label
PART = 2                        # words a part of a cut span needs
QUOTE_CHARS = '"„“”«»‚‘’‹›\''
DASHES = '‐‑‒–—−'
REF = re.compile(r'\[\^([^\]\s]+)\]')
CUT = re.compile(r'\[[^\]]*\]|\((?:\.\.\.|…)\)|\.\.\.|…')
TEXT_FILE = re.compile(r'\.(?:md|txt|py|js|sh|yaml|yml|json|mjs|html?|csv)$', re.I)


def normal(s):
    """A text as the comparison reads it."""
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', s)              # an image
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)           # a link's text
    s = REF.sub('', s)
    s = re.sub(r'<[^>\n]{0,80}>', ' ', s)                    # <br>, <span ...>
    s = s.replace('\\|', '|')
    for gone in (0xad, 0x200b, 0xfffc):     # soft hyphen, zero width, object mark
        s = s.replace(chr(gone), '')
    s = s.translate({ord(c): None for c in QUOTE_CHARS + '*`\\'})
    s = s.translate({ord(c): '-' for c in DASHES})
    s = re.sub(r'\s+([)\].,;:!?])', r'\1', re.sub(r'([(\[])\s+', r'\1', s))
    return ' '.join(s.split())


def blocks(lines):
    """(first line number, text) for each paragraph, table row and list item
    of a body, fenced blocks blanked, headings, block quotes and footnote
    definitions left out. A quotation mark inside inline code is no mark: it
    is written curly here, which `normal()` takes out with the others."""
    out, cur = [], None
    for i, l in enumerate(_blanklines.unfenced(lines)):
        l = re.sub(r'`[^`\n]*`', lambda m: m.group(0).replace('"', '\u201d'), l)
        if (not l.strip() or l.startswith(('#', '>'))
                or _blanklines.DEFN.match(l)):
            cur = None
            continue
        if cur is None or l.startswith('|') or _blanklines.ITEM.match(l.lstrip()):
            cur = [i, l]
            out.append(cur)
        else:
            cur[1] += '\n' + l
    return [(i, t) for i, t in out]


def spans(text):
    """(quotation, footnote ids) for each quotation of one block, or None
    where its quotation marks do not pair."""
    marks = [m.start() for m in re.finditer('"', text)]
    if len(marks) % 2:
        return None
    every = REF.findall(text)
    out, before = [], ''
    for k in range(0, len(marks), 2):
        a, b = marks[k], marks[k + 1]
        lead = text[marks[k - 1] + 1:a] if k else text[:a]
        gloss = bool(out or before) and re.search(r'[(\[]\s*$', lead) \
            and re.match(r'^\W{0,3}[(\[]\s*$', lead)
        before = text[a + 1:b]
        if gloss:
            continue
        out.append((text[a + 1:b], every))
    return out


def parts(quotation):
    """The pieces of a quotation that must each be in the page."""
    whole = [normal(p).strip(' .,;:!?-') for p in CUT.split(quotation)]
    if len(whole) == 1:
        return whole if len(whole[0].split()) >= WORDS else []
    return [p for p in whole if len(p.split()) >= PART]


@functools.lru_cache(maxsize=None)
def page_text(path):
    """A cited page as the comparison reads it, or None where it is no text."""
    if not TEXT_FILE.search(path):
        base = os.path.join(VAULT, path.split(os.sep + 'Raw' + os.sep)[0])
        txt = os.path.join(base, '_extractions', 'raw-text',
                           path.split(os.sep + 'Raw' + os.sep)[-1] + '.txt')
        if os.sep + 'Raw' + os.sep not in path or not os.path.isfile(txt):
            return None
        path = txt
    try:
        return normal(open(path, encoding='utf-8', errors='replace').read())
    except OSError:
        return None


def missing(body_lines, pages):
    """(line, quotation, ids) for each quotation of a body that no page of
    its footnotes holds, and how many were compared. `pages` is {id: text},
    with None for a page that is no text."""
    out, seen = [], 0
    for line, text in blocks(body_lines):
        for quotation, ids in spans(text) or ():
            texts = [pages[i] for i in ids if pages.get(i) is not None]
            want = parts(quotation)
            if not want or not texts or len(texts) < len([i for i in ids if i in pages]):
                continue
            seen += 1
            if not any(all(p in t or p[:1].swapcase() + p[1:] in t
                           for p in want) for t in texts):
                out.append((line, ' '.join(quotation.split()), ids))
    return out, seen


def scan(kb):
    """Every quotation of a base that its cited page does not hold, as
    (concept, line, quotation, ids), and how many quotations were compared."""
    rows, seen = [], 0
    for f in concept_files(kb):
        if os.path.basename(f) == 'questions.md':
            continue
        raw = open(f, encoding='utf-8').read()
        m = FM.match(raw)
        if not m:
            continue
        pages = {str(s.get('id')): page_text(p) if p and os.path.isfile(p) else None
                 for s, p in bundle.sources(f) if s.get('id')}
        got, n = missing(raw[m.end():].split('\n'), pages)
        offset = raw[:m.end()].count('\n') + 1
        seen += n
        rows += [(f, offset + line, q, ids) for line, q, ids in got]
    return rows, seen


def main():
    tsv = '--tsv' in sys.argv
    if tsv:
        print('kb\tconcept\tline\tids\tquotation')
    for kb in [a for a in sys.argv[1:] if not a.startswith('--')] or discover():
        rows, seen = scan(kb)
        root = os.path.join(VAULT, kb)
        for f, line, q, ids in rows:
            row = (kb, os.path.relpath(f, root), line, ','.join(ids), q)
            print(('%s\t%s\t%d\t%s\t%s' if tsv else '%s/%s:%d  [%s]  "%s"') % row)
        if not tsv:
            print('%s: %d quotation(s) compared, %d not in the page cited'
                  % (kb, seen, len(rows)))


if __name__ == '__main__':
    main()
