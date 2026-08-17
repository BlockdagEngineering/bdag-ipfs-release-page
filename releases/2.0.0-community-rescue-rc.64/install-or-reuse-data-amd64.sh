#!/usr/bin/env bash
# Reuse existing data, or authenticate and stage the RC64 snapshot for an empty node.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

[[ $# -eq 2 ]] || {
  printf 'usage: %s VERIFIED_RC64_DIRECTORY DATA_DIRECTORY\n' "$0" >&2
  exit 64
}
readonly verified=$1
readonly target=$2
[[ $verified == /* && -d $verified && ! -L $verified ]]
[[ $target == /* && ! -L $target && $target != / ]]
for command in curl df getent jq openssl sha256sum stat tar; do
  command -v "$command" >/dev/null 2>&1 || {
    printf 'required command unavailable: %s\n' "$command" >&2
    exit 1
  }
done
while IFS=: read -r _ _ _ _ _ account_home _; do
  [[ -z $account_home || $target != "$account_home" && $target != "$account_home/" ]] || {
    printf '%s\n' 'the data directory must not be an account home directory' >&2
    exit 1
  }
done < <(getent passwd)
case $(uname -m) in x86_64|amd64) ;; *) printf '%s\n' 'RC64 data is qualified only on AMD64.' >&2; exit 1 ;; esac

for file in release-public.pem latest-data-manifest.json latest-data-manifest.json.sig; do
  [[ -f $verified/$file && ! -L $verified/$file ]]
done
openssl pkeyutl -verify -pubin -inkey "$verified/release-public.pem" -rawin \
  -in "$verified/latest-data-manifest.json" \
  -sigfile "$verified/latest-data-manifest.json.sig" >/dev/null
jq -e '.schema=="chain1404-latest-data-manifest/v1" and
  .network.chainId==1404 and .platform=="linux/amd64" and .cleanShutdown==true' \
  "$verified/latest-data-manifest.json" >/dev/null

if [[ -d $target ]] && find "$target" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  printf '%s\n' \
    'Existing non-empty data directory detected; RC64 will reuse it.' \
    'No snapshot request was made. Let canonical existing data continue or follow the backup-backed recovery guide if it is divergent, latched, corrupt, or stalled.'
  exit 0
fi
[[ ! -e $target || -d $target ]]
parent=$(dirname "$target")
readonly parent
install -d -m 0700 "$parent"

# The signed archive and extracted data coexist during authenticated staging.
# Keep a filesystem reserve as well, so a new install cannot consume the space
# needed by the operating system, Docker, logs, or a rollback lane. The
# sanitized RC64 snapshot is below this conservative 32 GiB extraction bound.
readonly expected_extract_bytes=34359738368
readonly staging_overhead_bytes=2147483648
read -r filesystem_bytes available_bytes < <(
  df -B1 --output=size,avail "$parent" | awk 'NR==2 {print $1, $2}'
)
[[ $filesystem_bytes =~ ^[0-9]+$ && $available_bytes =~ ^[0-9]+$ ]]
reserve_bytes=$((filesystem_bytes * 15 / 100))
readonly minimum_reserve_bytes=21474836480
if (( reserve_bytes < minimum_reserve_bytes )); then
  reserve_bytes=$minimum_reserve_bytes
fi
expected_bytes=$(jq -er '.snapshot.bytes' "$verified/latest-data-manifest.json")
[[ $expected_bytes =~ ^[0-9]+$ ]]
required_bytes=$((expected_bytes + expected_extract_bytes + staging_overhead_bytes + reserve_bytes))
if (( available_bytes < required_bytes )); then
  printf '%s\n' \
    'Insufficient capacity for an authenticated RC64 empty-data installation.' \
    "Available bytes: $available_bytes" \
    "Required bytes: $required_bytes (archive $expected_bytes + extraction allowance $expected_extract_bytes + staging margin $staging_overhead_bytes + retained reserve $reserve_bytes)." \
    'Keep the active data, current images, evidence, and one known-good rollback. Reclaim only exact, inactive, reproducible superseded archives, image tags, or abandoned staging directories after proving that no running service references them; then rerun this installer.' >&2
  exit 1
fi

stage=$(mktemp -d "$parent/.rc64-data-stage.XXXXXX")
archive=$stage/latest-data-linux-amd64.tar.zst
cleanup() {
  if [[ -n ${stage:-} && -d $stage && ! -L $stage && $stage == "$parent/.rc64-data-stage."* ]]; then
    find "$stage" -xdev -depth -delete 2>/dev/null || true
  fi
}
trap cleanup EXIT

cid=$(jq -er '.snapshot.cid' "$verified/latest-data-manifest.json")
expected_sha=$(jq -er '.snapshot.sha256' "$verified/latest-data-manifest.json")
url=${BDAG_RC64_SNAPSHOT_URL:-https://dweb.link/ipfs/$cid}
[[ $url == https://* ]]
curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 10 \
  --max-time 14400 --output "$archive" "$url"
[[ $(sha256sum "$archive" | awk '{print $1}') == "$expected_sha" ]]
[[ $(stat -c %s "$archive") == "$expected_bytes" ]]

tar --zstd -tf "$archive" >"$stage/archive-members.txt"
if grep -E '(^/|(^|/)[.][.](/|$)|(^|/)(network[.]key|nodekey|peerstore)(/|$)|(^|/)[.]git(/|$))' \
  "$stage/archive-members.txt" >/dev/null; then
  printf '%s\n' 'snapshot contains an unsafe or private path' >&2
  exit 1
fi
install -d -m 0700 "$stage/data"
tar --zstd --no-same-owner --no-same-permissions -xf "$archive" -C "$stage/data"
[[ -d $stage/data/mainnet ]]
if find "$stage/data" -xdev -type f \( -name network.key -o -name nodekey \) \
  -print -quit | grep -q .; then
  printf '%s\n' 'snapshot contains a node identity key' >&2
  exit 1
fi
if find "$stage/data" -xdev -type d -name peerstore -print -quit | grep -q .; then
  printf '%s\n' 'snapshot contains a peerstore' >&2
  exit 1
fi
[[ ! -e $target ]]
mv -T -- "$stage/data" "$target"
trap - EXIT
find "$stage" -xdev -depth -delete
printf 'Authenticated RC64 data installed at %s. Generate a fresh local node identity before starting.\n' "$target"
