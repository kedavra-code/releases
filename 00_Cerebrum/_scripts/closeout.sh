#!/bin/sh
# Close a compile, a health check or an action sitting in one command.
#
#   sh _scripts/closeout.sh             # every live knowledge base
#   sh _scripts/closeout.sh Alpha_kb      # one or more knowledge bases
#
# Runs the six scripts every run closes with, in the order the action skill
# gives them, and prints one line for each. `close-items.py` comes first
# (owner, 08.11.2026): it moves closed rows out of each questions.md, so the
# roll-up and the audit after it read them where they now live. It stops at the first step that
# fails, names it, and prints its DEFECT or error lines. B5 of
# `Outputs/2026-11-05_cerebrum-for-the-other-apps.md`.
#
# With no knowledge base named, `reindex.py`, `inventory.py` and `coverage.py`
# write the live bases only: nothing more is done in a frozen one (owner,
# 24.10.2026). `bundle.live()` reads which bases are frozen from the Current
# state table of CLAUDE.md. `actionitems.py` and `verify.py` always
# cover every base: the roll-up is one file, and the audit scans the frozen
# bases on every commit. The CHANGELOG and log.md entries, memory.md and the
# commit stay the run's own.

cd "$(dirname "$0")/.." || exit 1
out=$(mktemp "${TMPDIR:-/tmp}/closeout.XXXXXX") || exit 1
trap 'rm -f "$out"' EXIT

if [ $# -eq 0 ]; then
  set -- $(cd _scripts && python3 -c 'import bundle; print(" ".join(bundle.live()))')
  [ $# -gt 0 ] || { echo "FAILED  no live knowledge base found"; exit 1; }
fi
# The scripts take an unknown name without a word, which would close out
# nothing and still end green.
for kb in "$@"; do
  [ -d "$kb/Wiki" ] && [ -f "$kb/CLAUDE.md" ] || { echo "FAILED  $kb is not a knowledge base. Nothing ran."; exit 2; }
done
echo "Knowledge bases: $*"

for s in close-items.py actionitems.py reindex.py inventory.py coverage.py verify.py; do
  case $s in
    actionitems.py|verify.py) python3 "_scripts/$s" >"$out" 2>&1 ;;
    *) python3 "_scripts/$s" "$@" >"$out" 2>&1 ;;
  esac
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "FAILED  $s (exit $rc). Nothing after it ran."
    grep -E 'DEFECT|Error|Traceback' "$out" | head -n 20 || true
    grep -qE 'DEFECT|Error|Traceback' "$out" || tail -n 15 "$out"
    exit $rc
  fi
  echo "ok      $s"
done
echo "Close-out green."
