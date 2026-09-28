#!/bin/bash
# Opens the vault viewer with Ask Claude working.
#
# Double-click this in Finder. It starts `_scripts/viewer-server.py` if it is
# not already up, then opens `00_Cerebrum_viewer.html` in your browser.
#
# It exists because a page opened from disk cannot start anything: browsers
# forbid it, so the helper has to be running before the page asks. Opening the
# HTML directly still works — the page searches exactly the same — but the Ask
# Claude and Reports buttons are grey, because there is nothing for them to
# talk to. Owner's instruction of 16.09.2026.
#
# Nothing here is left running that was not already: the helper is started
# detached and keeps running after this window closes, so a second double-click
# finds it and starts nothing. Stop it with `pkill -f viewer-server.py`.

set -u
cd "$(dirname "$0")" || exit 1

PORT=8760
VIEWER=00_Cerebrum_viewer.html
LOG="${TMPDIR:-/tmp}/cerebrum-viewer-server.log"

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
# would block the vault behind a sign-in that was not needed. It runs only when
# the login is dead (exit 2) or was never made (exit 3), and it asks first.
# An expiry that is merely close (exit 1) prints and does not interrupt.
python3 _scripts/check-login.py || LOGIN=$?
LOGIN=${LOGIN:-0}

if [ "$LOGIN" = 2 ] || [ "$LOGIN" = 3 ]; then
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
    printf '   Sign in now? [Y/n] '
    read -r ANSWER || ANSWER=n
    case "$ANSWER" in
      [Nn]*) echo "   skipped — Ask Claude will not work until you run: claude auth login" ;;
      *) "$CLAUDE" auth login || echo "!! the sign-in did not finish"
         # Say what the login looks like now, so the answer is on screen rather
         # than assumed. The helper reads the keychain on every /health, so a
         # helper already running needs no restart.
         python3 _scripts/check-login.py || true ;;
    esac
  fi
fi

# The viewer is generated and gitignored, so a fresh clone has none. Build it
# rather than opening a browser at a file that is not there.
if [ ! -f "$VIEWER" ]; then
  echo "· no viewer yet, generating it (this takes a moment)"
  python3 _scripts/visualize.py || { echo "!! visualize.py failed"; exit 1; }
fi

# Is the helper already answering? Ask it rather than looking for a process:
# what matters is whether the port responds, not whether something is named
# like it.
if curl -fsS -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "· helper already running on 127.0.0.1:$PORT"
else
  echo "· starting the helper on 127.0.0.1:$PORT"
  nohup python3 _scripts/viewer-server.py --port "$PORT" >>"$LOG" 2>&1 &
  # Wait for it to answer rather than sleeping a guess: the page checks once on
  # load, and opening the browser first would grey the buttons for no reason.
  for _ in $(seq 1 40); do
    if curl -fsS -m 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
  if curl -fsS -m 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "· helper is up"
  else
    echo "!! the helper did not come up. Its log is $LOG"
    echo "   The viewer still opens and searches; Ask Claude will be grey."
  fi
fi

echo "· opening the viewer"
open "$VIEWER"

echo
echo "Ask Claude writes a question report into Outputs/ using Claude Opus 5.5."
echo "Stop the helper with:  pkill -f viewer-server.py"
