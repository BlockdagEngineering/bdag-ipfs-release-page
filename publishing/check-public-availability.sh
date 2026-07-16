#!/usr/bin/env bash
set -Eeuo pipefail

manifest=${1:-}
delegated_router=${BDAG_IPFS_DELEGATED_ROUTER:-https://delegated-ipfs.dev}
trustless_gateway=${BDAG_IPFS_TRUSTLESS_GATEWAY:-https://trustless-gateway.link}
minimum_providers=${BDAG_IPFS_MIN_PROVIDERS:-2}

if [[ -z "$manifest" || ! -f "$manifest" ]]; then
  echo "usage: $0 <free-pinning-cids.json>" >&2
  exit 2
fi

if [[ ! "$minimum_providers" =~ ^[1-9][0-9]*$ ]]; then
  echo "BDAG_IPFS_MIN_PROVIDERS must be a positive integer" >&2
  exit 2
fi

for command in curl jq; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required command not found: $command" >&2
    exit 1
  fi
done

nonce=$(date +%s%N)

while IFS=$'\t' read -r name cid; do
  [[ -n "$name" && -n "$cid" ]] || continue

  providers=$(
    curl -4 --http1.1 -fsS --max-time 30 \
      -H 'Accept: application/x-ndjson' \
      -H 'Cache-Control: no-cache' \
      "$delegated_router/routing/v1/providers/$cid?nocache=$nonce" |
      jq -s '[.[].ID] | unique | length'
  )

  if (( providers < minimum_providers )); then
    echo "insufficient providers for $name ($cid): $providers < $minimum_providers" >&2
    exit 1
  fi

  curl -4 --http1.1 -fsS --max-time 60 \
    -H 'Accept: application/vnd.ipld.raw' \
    -H 'Cache-Control: no-cache' \
    "$trustless_gateway/ipfs/$cid?format=raw&nocache=$nonce" \
    -o /dev/null

  echo "available $name ($cid), delegated providers: $providers"
done < <(jq -er '.pins[] | [.name, .cid] | @tsv' "$manifest")

page_cid=$(jq -er '.pins[] | select(.name == "release-page-root") | .cid' "$manifest")
curl -4 --http1.1 -fsS --max-time 60 \
  -H 'Accept: application/vnd.ipld.car; version=1; order=dfs; dups=n' \
  -H 'Cache-Control: no-cache' \
  "$trustless_gateway/ipfs/$page_cid/index.html?format=car&nocache=$nonce" \
  -o /dev/null

echo "available complete release page DAG ($page_cid)"
