#!/usr/bin/env python3
"""Run the command that re-measures each open action item, before a sitting.

B3 of `Outputs/2026-11-05_cerebrum-for-the-other-apps.md`. Items go stale in
both directions: another run fixes one and its row still says `open`. An item
a script can measure ends its Item cell with one fixed form, written by the
health check that raised it:

    Re-measure: `python3 _scripts/verify.py Alpha_kb` counting `past stale_after` = 3

The number after `=` is what was counted when the item was raised: the lines
of the command's output that hold the text after `counting`, or, without it,
its lines that are not blank. The form has no `|`, because a pipe would split
the table cell it stands in.
This script runs the command again and sorts every `open` and `deferred` item:

    still holds   the same number
    fixed?        0 now: confirm closing it with the owner, in one question
    changed       another number: read it again before asking
    no command    an item no script can measure; the evidence decides

It runs only `python3 _scripts/<name>.py` with its arguments, split by
`shlex` and never handed to a shell. Anything else is refused and reported.
It changes nothing in the tables; a command writes only what its script
writes, so a re-measure is best a script that only reads.

    python3 _scripts/remeasure.py                  # every live base
    python3 _scripts/remeasure.py Alpha_kb           # one or more bases
    python3 _scripts/remeasure.py --file <questions.md>   # any table, for the checks
"""
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bundle
import actionitems

VAULT = bundle.VAULT
FORM = re.compile(r'Re-measure:\s*`([^`]+)`(?:\s+counting\s+`([^`]+)`)?\s*=\s*(\d+)')
SCRIPT = re.compile(r'^_scripts/[A-Za-z0-9_-]+\.py$')


def parse(command):
    """The argv of a command in the allowed form, or a reason it is not."""
    if any(c in command for c in ';&|$<>\n'):
        return None, 'shell characters are not run'
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return None, 'cannot be split: %s' % e
    if len(argv) < 2 or argv[0] != 'python3' or not SCRIPT.match(argv[1]):
        return None, 'only `python3 _scripts/<name>.py …` is run'
    return argv, None


def measure(argv, needle):
    r = subprocess.run(argv, cwd=VAULT, capture_output=True, text=True, timeout=600)
    lines = r.stdout.splitlines()
    if needle is None:
        return len([l for l in lines if l.strip()])
    return sum(1 for l in lines if needle in l)


def table_rows(path):
    t = open(path, encoding='utf-8').read()
    m = re.search(r'^# Action items(.*?)^# ', t, re.S | re.M)
    for r in actionitems.ROW.findall(m.group(1) if m else ''):
        yield r[0].strip(), r[2], actionitems.state_of(r[3])


def sort(path, label):
    out = []
    for iid, item, state in table_rows(path):
        if state not in ('open', 'deferred'):
            continue
        f = FORM.search(item)
        if not f:
            out.append(('no command', label, iid, state, ''))
            continue
        argv, why = parse(f.group(1))
        if not argv:
            out.append(('refused', label, iid, state, why))
            continue
        then, now = int(f.group(3)), measure(argv, f.group(2))
        verdict = ('still holds' if now == then else
                   'fixed?' if now == 0 else 'changed')
        out.append((verdict, label, iid, state, '%d when raised, %d now' % (then, now)))
    return out


def main(argv):
    if argv[:1] == ['--file']:
        targets = [(p, p) for p in argv[1:]]
    else:
        kbs = [a for a in argv if not a.startswith('--')] or bundle.live()
        targets = [(os.path.join(VAULT, kb, 'Wiki', 'questions.md'), kb) for kb in kbs]
    rows = []
    for path, label in targets:
        if not os.path.exists(path):
            print('no table: %s' % path)
            return 2
        rows += sort(path, label)
    order = ['fixed?', 'changed', 'still holds', 'refused', 'no command']
    for v in order:
        for r in rows:
            if r[0] == v:
                print('%-12s %-10s %-18s %-9s %s' % r)
    if not rows:
        print('No open or deferred item.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
