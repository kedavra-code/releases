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
# Template builds up to 31 also held a commit that changed the one-file viewer
# to viewer-check.js here. The viewer is specula now, an app with checks of its
# own, so the hook runs the audit alone.
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/sh
# Installed by _scripts/gitsetup.sh. Blocks the commit on any DEFECT.
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 _scripts/verify.py || exit 1
exit 0
HOOK
chmod +x .git/hooks/pre-commit

# From 16.09.2026 to 24.10.2026 a post-commit hook rebuilt the old viewer, so
# its build code named the commit just made. specula reads the vault where it
# is and needs no rebuild, so a re-run removes that hook.
rm -f .git/hooks/post-commit

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
