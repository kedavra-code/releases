#!/usr/bin/env python3
"""The meeting notes scripta writes into `Meetings/`, read the way a compile may read them.

scripta, the owner's transcription program, writes one note per meeting into
`Meetings/<year>/YYYYMMDD_HHMM.md` at the vault root. A note carries a Summary,
Decisions, Tasks and Open points, then the full Transcript and an "As heard"
block of unedited speech recognition. **Only the first four are compiled**,
owner's instruction of 26.09.2026. The transcript is the machine's hearing of
named colleagues, and a concept written from it would cite words nobody wrote.

So a compile never opens a note directly. It reads it through `--read`, which
prints the four sections and nothing after them, and the transcript never
reaches the context that writes the concept.

    python3 _scripts/meetings.py Alpha_kb            # notes no concept cites yet
    python3 _scripts/meetings.py --read <note>...  # the four sections of each

The queue is every note minus the notes some concept in the knowledge base
cites, minus the notes its `_COMPILE-LEDGER.md` records as carrying nothing
citable — the rule `plan-batches.py` applies to an archive layer. Meetings
belong to `Alpha_kb` by default, so that is the base to ask about.
"""
import os
import re
import sys

from bundle import VAULT

MEETINGS = os.path.join(VAULT, 'Meetings')
KEEP = ('Summary', 'Decisions', 'Tasks', 'Open points')
ANCHOR = re.compile(r'\[\[#\^p\d+\|([^\]]+)\]\]')     # [[#^p37|40:38]] -> 40:38


def notes():
    out = []
    for root, dirs, files in os.walk(MEETINGS):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        out += [os.path.relpath(os.path.join(root, f), VAULT)
                for f in sorted(files) if f.endswith('.md')]
    return out


def front(text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m:
        return {}, text
    meta, key = {}, None
    for line in m.group(1).splitlines():
        if line.startswith('  - ') and key:
            meta.setdefault(key, []).append(line[4:].strip().strip('"'))
        elif ':' in line and not line.startswith(' '):
            key, val = line.split(':', 1)
            val = val.strip().strip('"')
            meta[key] = val if val else []
    return meta, text[m.end():]


def sections(body):
    """The four kept sections, in order, each cut at the next `## ` heading.

    The first heading of a name wins, so a transcript line that happens to
    read `## Summary` cannot stand in for the real one above it."""
    parts = re.split(r'^## (.+)$', body, flags=re.M)
    got = {}
    for i in range(1, len(parts) - 1, 2):
        got.setdefault(parts[i].strip(), parts[i + 1].strip())
    return [(name, got.get(name)) for name in KEEP]


def read(rel):
    text = open(os.path.join(VAULT, rel), encoding='utf-8').read()
    meta, body = front(text)
    speakers = list(dict.fromkeys(meta.get('speakers') or []))
    print(f'=== {rel}')
    print(f"title: {meta.get('title', 'unknown')}")
    print(f"date: {meta.get('date', 'unknown')}  time: {meta.get('time', '?')}  "
          f"duration: {meta.get('duration', '?')}")
    print(f"speakers (speech recognition, may be wrong): {', '.join(speakers) or 'none'}")
    print(f"transcribed-by: {meta.get('transcribed-by', 'unknown')}")
    for name, content in sections(body):
        print(f'\n## {name}\n')
        print(ANCHOR.sub(r'\1', content) if content is not None
              else '*This note has no such section.*')
    print()


def queue(kb):
    wiki = os.path.join(VAULT, kb, 'Wiki')
    if not os.path.isdir(wiki):
        sys.exit(f'no such knowledge base: {kb}')
    seen = ''
    for root, _, files in os.walk(wiki):
        for f in files:
            if f.endswith('.md'):
                seen += open(os.path.join(root, f), encoding='utf-8', errors='replace').read()
    ledger = os.path.join(VAULT, kb, '_COMPILE-LEDGER.md')
    if os.path.exists(ledger):
        seen += open(ledger, encoding='utf-8').read()
    todo = [n for n in notes() if n not in seen]
    print(f'{kb}: {len(todo)} of {len(notes())} meeting notes not yet compiled')
    for n in todo:
        meta, _ = front(open(os.path.join(VAULT, n), encoding='utf-8').read())
        print(f"  {n}  {meta.get('date', '?')}  {meta.get('title', '')}")


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__.strip())
    elif args[0] == '--read':
        for rel in args[1:]:
            read(os.path.relpath(os.path.abspath(rel), VAULT))
    else:
        queue(args[0])
