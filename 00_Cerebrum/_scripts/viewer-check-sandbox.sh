#!/usr/bin/env bash
# viewer-check-sandbox.sh — run viewer-check.js inside a Cowork sandbox that
# has no Chromium system libraries and no root.
#
# Lesson of 14.08.2026: on that day's image the only missing dependency was
# libXdamage.so.1, a pure X11 client library that headless Chromium links but
# never calls. A four-symbol stub satisfies the loader. npm and the playwright
# CDN are reachable from the sandbox even where apt downloads are blocked.
# If a future image reports a different library missing, find it with
#   ldd <headless_shell> | grep "not found"
# and extend the stub the same way — but only for pure X11 libraries; anything
# Chromium actually uses headless must be real.
set -euo pipefail
VAULT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/viewer-check-sandbox"
mkdir -p "$WORK"
cd "$WORK"
[ -d node_modules/playwright ] || npm install playwright --no-fund --no-audit
npx playwright install chromium >/dev/null 2>&1 || true

# macOS needs none of the stub below: Chromium ships its own frameworks and
# there is no X11 in the picture. Worse, the gcc line is Linux-only — Apple's
# linker has no -soname, it has -install_name — so running this script on the
# owner's Mac died at the compile with "ld: unknown options: -soname" rather
# than at anything to do with the viewer. Added 15.08.2026 after exactly that.
if [ "$(uname -s)" = "Darwin" ]; then
  NODE_PATH="$WORK/node_modules" exec node "$VAULT/_scripts/viewer-check.js" "$@"
fi

cat > xdamage_stub.c << 'CEOF'
int XDamageQueryExtension(void *dpy, int *e, int *r) { return 0; }
unsigned long XDamageCreate(void *dpy, unsigned long d, int l) { return 0; }
void XDamageDestroy(void *dpy, unsigned long d) {}
void XDamageSubtract(void *dpy, unsigned long d, unsigned long rp, unsigned long p) {}
CEOF
gcc -shared -fPIC -Wl,-soname,libXdamage.so.1 -o libXdamage.so.1 xdamage_stub.c
LD_LIBRARY_PATH="$WORK" PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 \
NODE_PATH="$WORK/node_modules" exec node "$VAULT/_scripts/viewer-check.js" "$@"
