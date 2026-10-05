#!/usr/bin/env python3
"""Lists the concepts written before a page they cite was rewritten.

`plan-batches.py` derives what is unread from the disk, so a new page is
found with no bookkeeping. A page some concept already cites counts as
covered whatever it now says: rewrite it in OneNote and the planner stays
silent. Only the exporter knows, and it says so in the change list it writes
into the archive on every run, `_CHANGES-YYYY-MM-DD.json`, where
`contentChanged` hashes the prose alone. Until 05.10.2026 nothing joined that
list to the concepts, so the compile's short loop read the lists by eye.

A concept is listed when it cites a page whose content changed in an export
that ran after the concept's `generated.at`. Restamping is what clears it,
and the vault's rule for a restamp is that the page was read again first.

Every list in the archive is read, not the newest alone: a second run on one
day overwrites that day's list, and a list a second Mac wrote stands beside
it as a copy. The newest change of a page is the one that counts.

This is a reading list. Whether the new text extends the concept or
contradicts it is a judgement, and a contradiction goes to the owner: the
pipeline appends and cannot revise a sentence the change made wrong.

Usage:  python3 _scripts/changed-pages.py [KB ...] [--tsv]
"""
import glob
import json
import os
import sys

import bundle
from bundle import VAULT, FM, FENCE, concept_files, discover

_coverage = bundle.script('coverage.py')


def changes(kb):
    """{page: when} for every archive page whose content an export reported
    as changed, `when` being the newest such export's own stamp."""
    out = {}
    for root in _coverage.archive_roots(kb):
        for f in glob.glob(os.path.join(root, '_CHANGES-*.json')):
            try:
                doc = json.load(open(f, encoding='utf-8'))
            except (OSError, ValueError):
                continue
            when = str(doc.get('generated') or '')[:19]
            for c in doc.get('changes') or []:
                if (isinstance(c, dict) and c.get('contentChanged')
                        and c.get('path') and when):
                    page = bundle.canon(os.path.join(root, c['path']))
                    out[page] = max(when, out.get(page, ''))
    return out


def written(concept):
    """A concept's `generated.at`, as far as the second, or ''."""
    m = FM.match(FENCE.sub('', open(concept, encoding='utf-8').read()))
    try:
        fm = bundle.mapping(m.group(1)) if m else {}
    except Exception:
        return ''
    gen = (fm or {}).get('generated')
    at = gen.get('at') if isinstance(gen, dict) else ''
    # PyYAML hands a timestamp back as a datetime, a quoted one as a string.
    return at.isoformat()[:19] if hasattr(at, 'isoformat') else str(at or '')[:19]


def behind(changed, cites):
    """(page, when, concept, written) for each concept written before the
    newest change of a page it cites. `cites` is {concept: (written, pages)}."""
    return sorted((page, changed[page], concept, at)
                  for concept, (at, pages) in cites.items()
                  for page in pages
                  if page in changed and at and at < changed[page])


def scan(kb):
    changed = changes(kb)
    if not changed:
        return []
    return behind(changed, {f: (written(f), {p for _, p in bundle.sources(f) if p})
                            for f in concept_files(kb)})


def main():
    tsv = '--tsv' in sys.argv
    if tsv:
        print('kb\tpage\tchanged\tconcept\twritten')
    for kb in [a for a in sys.argv[1:] if not a.startswith('--')] or discover():
        rows, root = scan(kb), os.path.join(VAULT, kb)
        for page, when, concept, at in rows:
            row = (kb, os.path.relpath(page, root), when,
                   os.path.relpath(concept, root), at)
            print(('%s\t%s\t%s\t%s\t%s' if tsv else
                   '%s  %s  changed %s  <-  %s  written %s') % row)
        if not tsv:
            print('%s: %d concept(s) written before a page they cite changed'
                  % (kb, len(rows)))


if __name__ == '__main__':
    main()
