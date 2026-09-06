#!/usr/bin/env bash
# Snapshot one OneNote notebook so a later compile pass can be a diff.
# Usage: archive-snapshot.sh "<notebook dir>" "<out prefix>"
# Writes <prefix>.inventory.tsv  (path, md5, bytes)
#        <prefix>.missing-images.tsv (path, line, image filename)
set -euo pipefail
DIR="$1"; OUT="$(realpath -m "$2")"
cd "$DIR"
{ printf 'path\tmd5\tbytes\n'
  find . -name '*.md' -print0 | sort -z | while IFS= read -r -d '' f; do
    printf '%s\t%s\t%s\n' "${f#./}" "$(md5sum "$f" | cut -d' ' -f1)" "$(stat -c%s "$f")"
  done
} > "$OUT.inventory.tsv"
{ printf 'path\tline\timage\n'
  grep -rno '🖼 image: `[^`]*`' . 2>/dev/null \
    | sed 's/🖼 image: //' | tr -d '`' \
    | awk -F: '{p=$1; sub(/^\.\//,"",p); print p"\t"$2"\t"substr($0, index($0,$3))}' \
    | sort
} > "$OUT.missing-images.tsv"
wc -l "$OUT.inventory.tsv" "$OUT.missing-images.tsv"
