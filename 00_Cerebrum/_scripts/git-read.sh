#!/bin/sh
# The only git a device-bridge session may run.
#
# "Bridge sessions may read history" was too loose. `git status` and `git
# diff` are not pure reads: they refresh the index and take .git/index.lock.
# The bridge VM cannot delete files, so the lock survives the session and the
# next real commit fails with "Unable to create index.lock". That happened on
# 15.08.2026 — a health-check sub-agent ran `git status --short` per the
# skill's own step 1, and the owner's commit failed 3.5 hours later.
#
# --no-optional-locks tells git to skip every optional lock, which makes
# status and diff genuinely read-only.
#
# Usage:  _scripts/git-read.sh status --short
#         _scripts/git-read.sh log --oneline -5
case "$1" in
  status|log|diff|show|ls-files|check-ignore|rev-parse|branch|remote|blame)
    exec git --no-optional-locks "$@" ;;
  *)
    echo "git-read.sh: '$1' is not a read command." >&2
    echo "A device-bridge session must not write git: the lock it leaves" >&2
    echo "behind cannot be removed from here and wedges the next commit." >&2
    exit 2 ;;
esac
