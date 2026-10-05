#!/bin/sh
# One-time git setup for the 00_Cerebrum vault. RUN THIS ON THE MAC, in
# Terminal, from the vault folder — never from a Claude session VM: the VM
# cannot delete files, git cannot remove its own lock files there, and every
# repository it touches wedges after one commit (proven 09.08.2026).
#
#   cd /path/to/00_Cerebrum
#   sh _scripts/gitsetup.sh
#
# Safe to re-run after a failure: every step tolerates having already happened.
set -e

# verify.py needs PyYAML; macOS system Python ships without it (found the hard
# way, 09.08.2026, first run on the owner's machine).
python3 -c "import yaml" 2>/dev/null \
  || python3 -m pip install --user pyyaml 2>/dev/null \
  || python3 -m pip install --user --break-system-packages pyyaml \
  || { echo "Could not install PyYAML. Run: python3 -m pip install --user pyyaml"; exit 1; }

python3 _scripts/verify.py                 # green before the first commit, like every commit

git init -b main
# SSH, not HTTPS: HTTPS prompts for a username and token, SSH uses the key
# that already pushes j4k from this machine (learned 09.08.2026, first push).
REMOTE="${CEREBRUM_REMOTE:-}"
if [ -z "$REMOTE" ]; then
  echo "Set CEREBRUM_REMOTE to your repository first, for example:"
  echo "  CEREBRUM_REMOTE=git@github.com:you/your-vault.git sh _scripts/gitsetup.sh"
  exit 1
fi
git remote add origin "$REMOTE" 2>/dev/null || git remote set-url origin "$REMOTE"

# The audit runs before every commit, structurally. "verify.py green before
# every commit" held only when the commit command happened to chain it; a
# hook holds even for a hand-typed commit at midnight. Installed on every
# run of this script, so re-running repairs a deleted hook.
mkdir -p .git/hooks
#
# Since 05.10.2026 a commit that changes the viewer, its helper or their check
# is held to the rendered page as well. "No viewer delivery without
# viewer-check.js green" was a sentence in CLAUDE.md and nothing ran it: that
# day a change to `viewer-server.py` went in with the check not run, and the
# check stood broken at 133 of 171 until the next commit. The page is built
# from the tree being committed and checked before the commit is made. Where
# node or playwright is missing the hook says so and lets the commit through,
# so a Mac without them can still commit; the line it prints is the record
# that the viewer went in unchecked.
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/sh
# Installed by _scripts/gitsetup.sh. Blocks the commit on any DEFECT, and a
# commit that changes the viewer on a red viewer-check.js.
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 _scripts/verify.py || exit 1
if git diff --cached --name-only | grep -q -E '^_scripts/(visualize\.py|viewer-server\.py|viewer-check\.js)$'; then
  if command -v node >/dev/null 2>&1 && node -e "require('playwright')" >/dev/null 2>&1; then
    python3 _scripts/visualize.py >/dev/null 2>&1 \
      || { echo "!! visualize.py failed, so the viewer was not built. The commit is refused."; exit 1; }
    OUT="${TMPDIR:-/tmp}/viewer-check.$$.out"
    if node _scripts/viewer-check.js > "$OUT" 2>&1; then
      echo "· viewer-check.js green, $(grep -c '^ok' "$OUT") checks"
      rm -f "$OUT"
    else
      grep -E '^FAIL' "$OUT" | head -20
      tail -3 "$OUT"
      echo "!! viewer-check.js is red and this commit changes the viewer or its helper. The commit is refused."
      echo "   The whole output is in $OUT"
      exit 1
    fi
  else
    echo "!! This commit changes the viewer or its helper, and node or playwright is missing here: viewer-check.js did NOT run."
  fi
fi
exit 0
HOOK
chmod +x .git/hooks/pre-commit

# The viewer is built before a commit, because `viewer-check.js` has to be green
# before the work goes in — so at build time the tree still holds the edits, and
# the page stamps itself with the previous commit and the word `uncommitted`.
# Nothing rebuilt it afterwards, so the word never went away and the build code
# named the wrong commit for the life of the page. The owner asked why on
# 16.09.2026. The stamp was never wrong; the order was. Rebuilding after the
# commit costs eight seconds and makes the page match the commit exactly.
#
# It must never fail a commit that has already been made, so every failure is
# reported and swallowed.
cat > .git/hooks/post-commit <<'HOOK'
#!/bin/sh
# Installed by _scripts/gitsetup.sh. Rebuilds the viewer so its build code
# names the commit just made, rather than the one before it plus `uncommitted`.
cd "$(git rev-parse --show-toplevel)" || exit 0
if python3 _scripts/visualize.py >/dev/null 2>&1; then
  echo "· viewer rebuilt for $(git --no-optional-locks rev-parse --short HEAD)"
else
  echo "!! the viewer was not rebuilt. Run: python3 _scripts/visualize.py"
fi
exit 0
HOOK
chmod +x .git/hooks/post-commit

git add -A
if git diff --cached --quiet && git rev-parse -q --verify HEAD >/dev/null; then
  echo "Nothing new to commit."
else
  git commit -m "Initial commit: the vault, archives excluded

The vault skeleton: the operating docs, the OKF spec and knowledge-base
template, the three skills and the _scripts executable checks. Archive
layers, Raw/, _testimony/ and _to_delete/ bins are ignored by design."
fi
git push -u origin main
echo "Done. If your corpus carries anything you would not publish, check on github.com that the repository is PRIVATE."
