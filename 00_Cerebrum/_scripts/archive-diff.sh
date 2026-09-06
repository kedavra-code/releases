#!/usr/bin/env bash
# Compare a notebook against an earlier snapshot. Prints the pages a later
# compile pass has to re-read, and nothing else.
# Usage: archive-diff.sh "<notebook dir>" "<old prefix>" "<new prefix>"
set -euo pipefail
DIR="$1"; OLD="$(realpath -m "$2")"; NEW="$(realpath -m "$3")"
bash "$(dirname "$0")/archive-snapshot.sh" "$DIR" "$NEW" >/dev/null
join -t$'\t' -j1 -a1 -a2 -o 0,1.2,2.2 -e MISSING \
  <(tail -n +2 "$OLD.inventory.tsv" | cut -f1,2 | sort) \
  <(tail -n +2 "$NEW.inventory.tsv" | cut -f1,2 | sort) \
  | awk -F'\t' '$2!=$3 {
      if ($2=="MISSING") print "ADDED\t"$1;
      else if ($3=="MISSING") print "REMOVED\t"$1;
      else print "CHANGED\t"$1 }'
echo "--- image markers still unresolved ---"
tail -n +2 "$NEW.missing-images.tsv" | wc -l
echo "--- assets now present ---"
find "$DIR" -path '*_assets*' -type f | wc -l
