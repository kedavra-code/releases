#!/bin/bash
# Opens the vault's viewer, the app specula, after checking the login.
#
# Double-click this in Finder. The viewer is specula, an app of its own: install
# it from the releases page named in README.md, and choose this folder in its
# Settings › Armarium › Vault folder. The app starts its own server, so this starts nothing
# but the app. Template builds up to 31 started a one-file viewer here instead.

set -u
cd "$(dirname "$0")" || exit 1

echo "00_Cerebrum — $(pwd)"

# The command line signs in separately from the desktop app and its login dies
# after about a month, with nothing to say so: on 16.09.2026 the first sign was
# a job failing three weeks after the token had expired. macOS notifications do
# not reach this Mac, so the reminder is here, where you look every time you
# open the vault.
#
# **And it offers to fix it, rather than printing a command to copy.** The owner
# had to open a second Terminal and run `claude auth login` by hand, which is a
# reminder doing half a job. It is not run unconditionally: the login is
# interactive, it opens a browser and waits, so running it on every double-click
# would block the vault behind a sign-in that was not needed. It runs when the
# login is dead (exit 2), was never made (exit 3) or has seven days or fewer
# left (exit 1), and it asks first.
#
# The close expiry was added on 05.10.2026. Until then it printed and did not
# interrupt, so the viewer's Ask button carried the warning for a week and the
# owner still had to open a Terminal and type the command. The login lasts 28
# days and no setting lengthens it. He was offered a one-year token for
# scripts, `claude setup-token`, and chose this: one Return here and one click
# in the browser, once a month, and no token to keep.
python3 _scripts/check-login.py || LOGIN=$?
LOGIN=${LOGIN:-0}

if [ "$LOGIN" = 1 ]; then
  ASK='   Sign in again now, for another month? [Y/n] '
  SKIPPED='   skipped — this asks again at the next start'
else
  ASK='   Sign in now? [Y/n] '
  SKIPPED='   skipped — Ask Claude will not work until you run: claude auth login'
fi

if [ "$LOGIN" = 1 ] || [ "$LOGIN" = 2 ] || [ "$LOGIN" = 3 ]; then
  # Finder runs a .command through its shebang, so no shell profile is read and
  # `claude` is usually not on PATH: it lives in ~/.local/bin, which only an
  # interactive shell puts there. Look for it rather than assuming it.
  CLAUDE=$(command -v claude 2>/dev/null || true)
  if [ -z "$CLAUDE" ] && [ -x "$HOME/.local/bin/claude" ]; then
    CLAUDE="$HOME/.local/bin/claude"
  fi
  if [ -z "$CLAUDE" ]; then
    echo "   claude is not on PATH here. Sign in from a Terminal:  claude auth login"
  elif [ ! -t 0 ]; then
    # No keyboard attached — this was not a double-click. Never prompt into a
    # pipe: the read would return at once and look like an answer.
    echo "   Sign in with:  claude auth login"
  else
    printf '%s' "$ASK"
    read -r ANSWER || ANSWER=n
    case "$ANSWER" in
      [Nn]*) echo "$SKIPPED" ;;
      *) "$CLAUDE" auth login || echo "!! the sign-in did not finish"
         # Say what the login looks like now, so the answer is on screen rather
         # than assumed.
         python3 _scripts/check-login.py || true ;;
    esac
  fi
fi

echo "· opening specula"
open -a specula || echo "!! specula did not open. Install it into /Applications from the releases page named in README.md."
