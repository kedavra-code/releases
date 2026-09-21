#!/usr/bin/env python3
"""Says how long the Claude Code command-line login has left.

    python3 _scripts/check-login.py            # print the state
    python3 _scripts/check-login.py --notify   # and try a macOS notification
                                               # when it is expired or close to it
    python3 _scripts/check-login.py --quiet    # print only when something is wrong

**The command line signs in separately from the desktop app, and nothing tells
you when that login dies.** The app keeps working on its own session, so the
first sign is a job failing with "OAuth session expired and could not be
refreshed" — which is what happened on 16.09.2026, three weeks after the token
had expired on 27.08.2026. Nothing in this vault caused it and nothing in this
vault could have seen it coming, because nobody was looking.

This looks. It reads the login's own expiry out of the login keychain, where
Claude Code keeps it, and says how many days are left. It never prints or
copies a token: it reads two numbers out of the JSON and nothing else.

**Do not rely on `--notify`.** Tested on the owner's Mac on 16.09.2026: the
notification never appeared, because the process posting it is not one macOS
has been granted notification rights for. The flag is kept because it costs
nothing and may work elsewhere, and because a reminder must never be the thing
that fails — it is best effort and its result is not checked. What the owner
reads instead is the launcher, which prints this on every start, and the viewer,
which shows it on the Ask button.

Exit codes, so a caller can act on it without parsing the words:
    0  fine
    1  expiring within the warning window (7 days by default)
    2  expired
    3  no credential found, or it could not be read
"""
import argparse
import datetime
import json
import subprocess
import sys

SERVICE = 'Claude Code-credentials'
WARN_DAYS = 7


def read_expiry():
    """(access-token expiry, refresh-token expiry), either possibly None.

    The refresh token is the one that matters: while it is alive the access
    token renews itself, and when it dies the whole login does.
    """
    try:
        raw = subprocess.run(
            ['security', 'find-generic-password', '-s', SERVICE, '-w'],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return None, None, 'could not run security: %s' % e
    if raw.returncode != 0 or not raw.stdout.strip():
        return None, None, 'no Claude Code credential in the login keychain'
    try:
        d = json.loads(raw.stdout)
    except ValueError as e:
        return None, None, 'the credential is not readable JSON: %s' % e
    o = d.get('claudeAiOauth') or {}

    def at(key):
        v = o.get(key)
        try:
            return datetime.datetime.fromtimestamp(int(v) / 1000)
        except (TypeError, ValueError):
            return None
    return at('expiresAt'), at('refreshTokenExpiresAt'), None


def notify(title, body):
    """A macOS notification. Best effort: a reminder must never be the thing
    that fails."""
    try:
        subprocess.run(['osascript', '-e',
                        'display notification %s with title %s'
                        % (json.dumps(body), json.dumps(title))],
                       capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--notify', action='store_true',
                    help='post a macOS notification when action is needed')
    ap.add_argument('--quiet', action='store_true',
                    help='print only when something is wrong')
    ap.add_argument('--days', type=int, default=WARN_DAYS,
                    help='warn this many days ahead (default %d)' % WARN_DAYS)
    a = ap.parse_args()

    _, refresh, err = read_expiry()
    if err or refresh is None:
        msg = err or 'the credential carries no refresh expiry'
        print('Claude Code login: unknown — %s' % msg)
        if a.notify:
            notify('Claude Code login', msg + '. Run: claude auth login')
        return 3

    left = refresh - datetime.datetime.now()
    days = left.days
    when = refresh.strftime('%d.%m.%Y')

    if days < 0:
        print('Claude Code login: EXPIRED on %s. Run:  claude auth login' % when)
        if a.notify:
            notify('Claude Code login expired',
                   'It expired on %s. Run: claude auth login' % when)
        return 2
    if days <= a.days:
        print('Claude Code login: expires in %d day(s), on %s. Run:  '
              'claude auth login' % (days, when))
        if a.notify:
            notify('Claude Code login expires soon',
                   'In %d day(s), on %s. Run: claude auth login' % (days, when))
        return 1
    if not a.quiet:
        print('Claude Code login: fine, %d day(s) left (until %s)'
              % (days, when))
    return 0


if __name__ == '__main__':
    sys.exit(main())
