#!/bin/bash
# Puts the vault's mark on the Finder icon of `Open 00_Cerebrum.command`.
#
#     sh _scripts/set-icon.sh
#
# **Run it again after a fresh clone.** A custom Finder icon lives in the file's
# resource fork, and git tracks a file's bytes and not its forks, so the icon
# does not survive a clone or a copy through anything that drops extended
# attributes. The picture it draws from does survive: `_assets/cerebrum-icon.png`
# is the viewer's own mark, rendered at 1024px on the page's ground in the
# rounded square macOS expects, and it is tracked.
#
# Owner's instruction of 16.09.2026. Uses only what macOS and the Xcode command
# line tools already provide: `sips`, `iconutil`, `Rez` and `SetFile`.
set -eu
cd "$(dirname "$0")/.."

SRC=_scripts/_assets/cerebrum-icon.png
TARGET="Open 00_Cerebrum.command"
[ -f "$SRC" ] || { echo "!! $SRC is missing"; exit 1; }
[ -f "$TARGET" ] || { echo "!! $TARGET is missing"; exit 1; }
for t in sips iconutil Rez SetFile; do
  command -v "$t" >/dev/null 2>&1 || {
    echo "!! $t is not on PATH. The Xcode command line tools provide Rez and"
    echo "   SetFile: xcode-select --install"
    exit 1; }
done

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
SET="$WORK/icon.iconset"
mkdir -p "$SET"

# The sizes macOS asks for. Each is resampled from the 1024 original rather than
# from the previous step, so a small icon is not a blur of a blur.
for s in 16 32 128 256 512; do
  sips -z $s $s        "$SRC" --out "$SET/icon_${s}x${s}.png"     >/dev/null
  sips -z $((s*2)) $((s*2)) "$SRC" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
done

iconutil -c icns "$SET" -o "$WORK/icon.icns"

# The icon goes into the file's resource fork. `sips -i` first writes the icon
# into a carrier file, `DeRez` reads it back as a resource, and `Rez` appends it
# to the target; `SetFile -a C` is the flag that tells Finder to use it.
cp "$WORK/icon.icns" "$WORK/carrier.icns"
sips -i "$WORK/carrier.icns" >/dev/null
DeRez -only icns "$WORK/carrier.icns" > "$WORK/icon.rsrc"
Rez -append "$WORK/icon.rsrc" -o "$TARGET"
SetFile -a C "$TARGET"

echo "icon set on $TARGET"
echo "Finder sometimes keeps the old one cached; a relaunch of Finder shows it."
