#!/usr/bin/env python3
"""Apply the append-requests a compile batch hands back.

Compile agents run concurrently, so they may not edit an existing concept:
two agents in one file is a lost write. They emit APPEND blocks instead and
this script applies them serially. Without it the merge is manual, and at
roughly one request per three pages a full-archive compile would generate
thousands.

Frontmatter is edited textually, never re-serialised through YAML: a round
trip would reformat every concept in the bundle and bury the real change in
noise.

Block format, as written into <KB>/_extractions/<batch>.md:

    ### APPEND Wiki/people/marco-gehrig.md
    #### SOURCES
    - id: kt-2017-03-14
      resource: ../../OneNote/...
      title: ...
      author: human:owner
      last_modified: 2017-03-14
    #### SECTION Ownership
    | claim | [^kt-2017-03-14] |
    #### FOOTNOTES
    [^kt-2017-03-14]: 20170314 Kernteammeeting, image freeze

Usage:  python3 _scripts/merge-appends.py <KB> [batch-file ...]   (default: all)
        python3 _scripts/merge-appends.py <KB> --dry-run
"""
import collections
import datetime
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK = re.compile(r'^### APPEND (\S+)\s*$', re.M)
# [ \t]* not \s*: \s* matches the newline, so the first line of every
# block was captured as the heading's argument and silently dropped.
# That cost one source entry per append-request on 15.08.2026, each one
# leaving a dangling footnote that verify.py then caught.
SUB = re.compile(r'^#### (SOURCES|SECTION|FOOTNOTES)[ \t]*(.*)$', re.M)


def parse(path):
    text = open(path, encoding='utf-8').read()
    out, marks = [], list(BLOCK.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end]
        req = {'target': m.group(1), 'sources': '', 'sections': [], 'footnotes': ''}
        subs = list(SUB.finditer(body))
        for j, s in enumerate(subs):
            e = subs[j + 1].start() if j + 1 < len(subs) else len(body)
            chunk = body[s.end():e].strip('\n')
            if s.group(1) == 'SOURCES':
                req['sources'] = chunk
            elif s.group(1) == 'SECTION':
                req['sections'].append((s.group(2).strip(), chunk))
            else:
                req['footnotes'] = chunk
        out.append(req)
    return out


def resolve_resource(kb_root, concept_path, val):
    """Rewrite a resource path to the true relative depth.

    An agent writes `../../OneNote/...` because that is right for
    `Wiki/<group>/x.md`, and wrong for `Wiki/systems/vendors/x.md` which sits
    one level deeper. Fifteen citations landed unresolvable that way on
    15.08.2026.

    Fix the depth, not the name. The first version of this searched the
    archive for the basename and gave up unless there was exactly one hit,
    which held for Gamma and collapsed on Beta: eight `Bila XXX` folders carry
    the same date-stamped filenames, so every ambiguous name fell through
    unchanged and nineteen citations landed broken anyway. The part of the
    path the agent gets right is everything from `OneNote/` onward; only the
    number of `../` steps is wrong. So re-anchor on that and try each depth.
    Basename search stays as a last resort for a genuinely odd path.
    """
    d = os.path.dirname(concept_path)
    if os.path.isfile(os.path.normpath(os.path.join(d, val))):
        return val
    tail = re.sub(r'^(?:\.\./)+', '', val)
    for up in range(0, 8):
        cand = os.path.join(*(['..'] * up + [tail])) if up else tail
        if os.path.isfile(os.path.normpath(os.path.join(d, cand))):
            return cand
    base = os.path.basename(val)
    hits = []
    for dp, dn, fn in os.walk(os.path.join(kb_root, 'OneNote')):
        if base in fn:
            hits.append(os.path.join(dp, base))
    return os.path.relpath(hits[0], d) if len(hits) == 1 else val


def apply(kb_root, req, dry):
    p = os.path.join(kb_root, req['target'])
    if not os.path.isfile(p):
        return 'MISSING  ' + req['target']
    text = open(p, encoding='utf-8').read()
    m = re.match(r'^(---\n)(.*?)(\n---\n)', text, re.S)
    if not m:
        return 'NO-FRONTMATTER  ' + req['target']
    fm, body = m.group(2), text[m.end():]
    added_src = added_sec = 0

    # A page already cited under another id must not gain a second entry.
    # Instead the appended footnotes are pointed at the id already in the
    # file. Sixteen labels dangled this way on 15.08.2026, because the
    # dedupe was right and the footnote was not remapped to match it.
    existing_by_res = {}
    for em in re.finditer(r'^\s*- id:\s*(\S+)\s*\n\s*resource:\s*\'?([^\'\n]+)\'?',
                          fm, re.M):
        existing_by_res[em.group(2).strip()] = em.group(1)

    # Sources are appended to the end of the sources: block, re-indented to
    # match the file. Two bugs on 15.08.2026, both fixed here: entries were
    # written at column 0 where these files indent by two, which broke the
    # YAML in 17 concepts; and the duplicate filter matched 'id: x' as a
    # substring, so 'id: kt-2017-01-23' was judged already present because
    # 'id: kt-2017-01-23b' existed, silently dropping the entry and leaving
    # its footnote dangling.
    if req['sources']:
        new_entries = [b for b in re.split(r'\n(?=\s*- id:)', req['sources'])
                       if b.strip()]
        have = set(re.findall(r'^\s*- id:\s*(\S+)\s*$', fm, re.M))
        keep = []
        for b in new_entries:
            idm = re.search(r'^\s*- id:\s*(\S+)\s*$', b, re.M)
            if idm and idm.group(1) in have:
                continue
            lines = []
            for ln in b.rstrip('\n').split('\n'):
                ls = ln.strip()
                if not ls:
                    continue
                # resolve_resource() was written on 15.08.2026 to fix exactly
                # this and then never called: nine citations landed
                # unresolvable in vendors/ and references/digests/ on the very
                # next wave, and verify.py caught them as defects while the
                # function that existed to prevent them sat unreferenced.
                # A fix that is not wired up is a comment.
                rm = re.match(r'^(resource:\s*)(.+)$', ls)
                if rm:
                    ls = rm.group(1) + resolve_resource(
                        kb_root, p, rm.group(2).strip().strip("'"))
                # A page title containing ": " is a YAML mapping value where
                # a scalar was meant, and it breaks the frontmatter of the
                # whole concept — one agent wrote `title: 20200713
                # Jira-Accounts: Team Meeting` on 15.08.2026 and
                # verify.py could not parse the file at all. The archive is
                # full of such titles, so quote on the way in rather than
                # asking every agent to remember.
                km = re.match(r'^(title|resource):\s*(.+)$', ls)
                if km and not km.group(2).startswith(("'", '"')):
                    v = km.group(2).strip()
                    # A bare YYYY-MM-DD title parses as a date object,
                    # which json.dumps in visualize.py cannot serialise —
                    # the viewer build died on four of them on 15.08.2026.
                    if (': ' in v or v.endswith(':')
                            or v[:1] in '[{&*!|>%@`#'
                            or re.fullmatch(r'\d{4}-\d\d-\d\d', v)):
                        ls = "%s: '%s'" % (km.group(1), v.replace("'", "''"))
                lines.append(('  ' + ls) if ls.startswith('- ')
                             else ('    ' + ls))
            keep.append('\n'.join(lines))
        if keep:
            if not re.search(r'^sources:\s*$', fm, re.M):
                fm = fm.rstrip('\n') + '\nsources:'
            fm = fm.rstrip('\n') + '\n' + '\n'.join(keep)
            added_src = len(keep)

    # sections: append at the end of the named heading's content
    for name, chunk in req['sections']:
        if not chunk.strip():
            continue
        h = re.search(r'^(#{1,3})\s+%s\s*$' % re.escape(name), body, re.M)
        if not h:
            body = body.rstrip('\n') + '\n\n# %s\n\n%s\n' % (name, chunk)
            added_sec += 1
            continue
        nxt = re.search(r'^#{1,3}\s+\S', body[h.end():], re.M)
        cut = h.end() + (nxt.start() if nxt else len(body) - h.end())
        head = body[:cut].rstrip('\n')
        # One newline glues the chunk onto whatever was there. That is right
        # when a chunk of table rows continues the table above it — the usual
        # case, and why this was written with a single '\n'. It is wrong for
        # every other shape: a paragraph appended under a paragraph became one
        # run-on paragraph, and 147 of them stood across Alpha_kb before anyone
        # looked (22.08.2026). Continue a table or a list; otherwise separate.
        prev = head.rsplit('\n', 1)[-1].lstrip()
        first = chunk.lstrip('\n').split('\n', 1)[0].lstrip()
        same_block = (prev[:1] == '|' and first[:1] == '|') or (
            prev[:2] in ('- ', '* ') and first[:2] in ('- ', '* '))
        body = (head + ('\n' if same_block else '\n\n') + chunk
                + '\n\n' + body[cut:].lstrip('\n'))
        added_sec += 1

    if req['footnotes']:
        for line in req['footnotes'].split('\n'):
            lm = re.match(r'\[\^([^\]]+)\]:', line.strip())
            if lm and ('[^%s]:' % lm.group(1)) not in body:
                body = body.rstrip('\n') + '\n' + line.strip() + '\n'

    fm = re.sub(r'(generated:\s*\{[^}]*at:\s*)[0-9T:\-Z]+',
                r'\g<1>' + datetime.datetime.now(
                    datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), fm)
    if not dry:
        open(p, 'w', encoding='utf-8').write('---\n' + fm + '\n---\n' + body)
    return 'ok  %-52s +%d sources, +%d sections' % (
        req['target'], added_src, added_sec)


def main():
    kb = sys.argv[1]
    kb_root = os.path.join(VAULT, kb)
    dry = '--dry-run' in sys.argv
    files = [a for a in sys.argv[2:] if not a.startswith('--')] or sorted(
        f for f in glob.glob(os.path.join(kb_root, '_extractions', '*.md'))
        if not os.path.basename(f).startswith('_'))
    # Preflight: two batches that both created the same concept mean one
    # `cat >` destroyed the other, silently and before this script ran.
    # Six person concepts went that way in the wave of 15.08.2026 and only
    # the agents that noticed refiled their material; the rest was gone.
    # The merge cannot repair it, but it must not be the step that hides it.
    claimed = collections.defaultdict(list)
    for f in files:
        text = open(f, encoding='utf-8').read()
        m = re.search(r'^## Concepts created\n(.*?)(?=\n## |\Z)',
                      text, re.S | re.M)
        if not m:
            continue
        # An agent that hit the no-clobber guard and refiled as an append
        # often still lists the concept under Concepts created, annotated.
        # That is a guard working, not a lost write, and reporting it as one
        # is how a check earns being ignored — this vault's own rule about
        # standing noise. Anything the agent also declared a collision is
        # not a claim.
        cm = re.search(r'^## Collisions\n(.*?)(?=\n## |\Z)', text,
                       re.S | re.M)
        collided = set(re.findall(r'`([^`]*Wiki/[^`]+\.md)`',
                                  cm.group(1)) if cm else [])
        collided = {'Wiki/' + c.split('Wiki/')[1] for c in collided}
        for c in sorted(set(re.findall(r'`([^`]*Wiki/[^`]+\.md)`', m.group(1)))):
            # set(): a handback that names the same concept twice under
            # Concepts created is one agent being verbose, not two agents
            # colliding. NEMK-01 did exactly that on 21.08.2026 and the
            # preflight reported it as claimed by "NEMK-01 and NEMK-01".
            cid = 'Wiki/' + c.split('Wiki/')[1]
            if cid in collided:
                continue
            claimed[cid].append(os.path.basename(f)[:-3])
    for c, bs in sorted(claimed.items()):
        if len(bs) > 1:
            print('LOST WRITE  %s claimed by %s — one overwrote the other; '
                  'recover the loser before trusting this merge'
                  % (c, ' and '.join(bs)))

    n = 0
    for f in files:
        reqs = parse(f)
        if not reqs:
            continue
        print('== %s: %d append-requests' % (os.path.basename(f), len(reqs)))
        for r in reqs:
            print('   ' + apply(kb_root, r, dry))
            n += 1
    print('%s%d requests' % ('DRY RUN, would apply ' if dry else 'applied ', n))

    # Archive what was merged, in the same breath as merging it. Leaving a
    # merged batch where this script globs means the next run applies its
    # SECTION blocks a second time — sources dedupe, prose does not. It was
    # written down as a manual step on 15.08.2026 and skipped that same
    # afternoon by the person who wrote it down, which is the argument for
    # doing it here instead of documenting it again.
    if not dry and files:
        arch = os.path.join(kb_root, '_extractions', '_merged')
        os.makedirs(arch, exist_ok=True)
        for f in files:
            # Batch ids repeat across waves: the planner renumbers from what
            # is still unread, so a second wave over the same scope produces
            # NBeta-01 again. os.rename would overwrite the first wave's
            # handback and lose the only record of what that batch found.
            dest = os.path.join(arch, os.path.basename(f))
            n = 1
            while os.path.exists(dest):
                n += 1
                dest = os.path.join(arch, '%s-w%d.md'
                                    % (os.path.basename(f)[:-3], n))
            os.rename(f, dest)
        print('archived %d batch file(s) to _extractions/_merged/' % len(files))


if __name__ == '__main__':
    main()
