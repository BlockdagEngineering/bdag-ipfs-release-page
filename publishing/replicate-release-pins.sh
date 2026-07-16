#!/usr/bin/env bash
set -Eeuo pipefail

manifest=${1:-}

if [[ -z "$manifest" || ! -f "$manifest" ]]; then
  echo "usage: $0 <free-pinning-cids.json>" >&2
  exit 2
fi

for command in ipfs jq; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required command not found: $command" >&2
    exit 1
  fi
done

if ! ipfs id >/dev/null; then
  echo "the local IPFS daemon is not available" >&2
  exit 1
fi

while IFS=$'\t' read -r name cid; do
  [[ -n "$name" && -n "$cid" ]] || continue
  echo "pinning $name ($cid)"
  ipfs pin add --progress=false "$cid"
  ipfs block stat "$cid" >/dev/null
  ipfs provide once --recursive "$cid"
  echo "ready $name ($cid)"
done < <(jq -er '.pins[] | [.name, .cid] | @tsv' "$manifest")

echo "all release roots are pinned and advertised"
