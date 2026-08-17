#!/usr/bin/env bash
# Verify the original RC65 release and the signed richer presentation revision.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

readonly release_root=${1:-$(cd "$(dirname "$0")" && pwd)}
[[ $release_root == /* && -d $release_root && ! -L $release_root ]]
for command in bash openssl python3 sha256sum stat; do
  command -v "$command" >/dev/null 2>&1 || { printf 'required command unavailable: %s\n' "$command" >&2; exit 1; }
done

"$release_root/verify-load.sh" "$release_root" >/dev/null
python3 "$release_root/revision/verify-compact-admission.py" "$release_root" --ipfs-cid-check
