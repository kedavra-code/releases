#!/bin/sh
# Commit everything in the vault and push it. RUN THIS ON THE MAC.
#
#   cd /path/to/00_Cerebrum
#   sh _scripts/sync.sh                    # generated message
#   sh _scripts/sync.sh "why this changed" # your own subject line
#   sh _scripts/sync.sh "subject" "body"  # and its opening paragraph
#
# Never from a Claude session VM. The VM cannot delete files, so git cannot
# remove its own lock files, and the repository wedges after one commit
# (proven 09.08.2026, and again 15.08.2026 via a bare `git status`).
#
# Why this exists: the commit step was a block of shell pasted into Terminal,
# and on 22.08.2026 a 48-line commit message pasted cleanly, reached
# COMMIT_EDITMSG, and then produced no commit — with no error anyone kept.
# A script fails loudly, in one place, and prints what went wrong. A pasted
# heredoc fails silently and leaves you comparing hashes.
set -e

cd "$(dirname "$0")/.."

if [ -n "$(find . -maxdepth 2 -name '*.lock' -path '*.git*' 2>/dev/null)" ]; then
  echo "A git lock file is present. If no git is running, remove it:"
  find . -maxdepth 2 -name '*.lock' -path '*.git*'
  exit 1
fi

# Same audit the pre-commit hook runs, but here the output is visible and the
# failure is legible before anything is staged.
python3 _scripts/verify.py || { echo; echo "verify.py found DEFECTs. Fix them; do not commit around them."; exit 1; }

# The vault is edited from Obsidian, from sessions and by the scheduled task,
# so local may be behind whatever else pushed. Rebase before adding.
git pull --rebase --autostash

if [ -z "$(git status --porcelain)" ]; then
  echo "Nothing to commit. Working tree is clean."
  exit 0
fi

git add -A

N_NEW=$(git diff --cached --name-status | grep -c '^A' || true)
N_DEL=$(git diff --cached --name-status | grep -c '^D' || true)
N_MOD=$(git diff --cached --name-status | grep -c '^M' || true)

SUBJECT="$1"
[ -n "$SUBJECT" ] || SUBJECT="Vault sync $(date +%Y-%m-%d): $N_NEW added, $N_MOD modified, $N_DEL deleted"

# --no-verify is deliberately absent: the hook is the point.
# -m twice gives a subject and a body without a heredoc to mis-paste.
# A body if one was given, else the diffstat and the audit result. The rule in
# CLAUDE.md is that the body carries the entry's opening paragraph, so `git log`
# reads without opening the CHANGELOG.
BODY="$2"
[ -n "$BODY" ] || BODY="$(git diff --cached --stat | tail -1)

Committed by _scripts/sync.sh. verify.py green: 0 defects across the vault."

git commit -m "$SUBJECT" -m "$BODY"

echo
git log --oneline -1
git push origin main
echo
echo "Pushed. GitHub now matches:"
git status -sb | head -1
