#!/usr/bin/env bash
# Reuse qualified data, or authenticate and install one RC65 new-node dataset.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

[[ $# -eq 2 ]] || { printf 'usage: %s VERIFIED_RC65_DIRECTORY DATA_DIRECTORY\n' "$0" >&2; exit 64; }
readonly verified=$1
readonly target=$2
readonly records=$verified/records
readonly manifest=$records/release.json
readonly gateway=${BDAG_RC65_IPFS_GATEWAY:-https://dweb.link/ipfs}
readonly choice=${BDAG_RC65_DATASET:-compactMiningNode}

[[ $verified == /* && -d $verified && ! -L $verified ]]
[[ $target == /* && ! -L $target && $target != / ]]
[[ $gateway == https://* ]]
case $choice in compactMiningNode|fullArchive) ;; *) printf '%s\n' 'BDAG_RC65_DATASET must be compactMiningNode or fullArchive' >&2; exit 64 ;; esac
for command in find getent; do
  command -v "$command" >/dev/null 2>&1 || { printf 'required command unavailable: %s\n' "$command" >&2; exit 1; }
done
"$verified/verify-load.sh" "$verified" >/dev/null

while IFS=: read -r _ _ _ _ _ account_home _; do
  [[ -z $account_home || $target != "$account_home" && $target != "$account_home/" ]] || {
    printf '%s\n' 'the data directory must not be an account home directory' >&2
    exit 1
  }
done < <(getent passwd)

target_was_empty=false
if [[ -d $target ]] && find "$target" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  printf '%s\n' \
    'Existing non-empty data directory detected; RC65 will reuse it.' \
    'No compact or full-archive download was requested. Keep canonical data online and use the backup-backed recovery guide only for divergent, latched, corrupt, or stalled data.'
  exit 0
fi
[[ ! -e $target || -d $target ]]
[[ ! -d $target ]] || target_was_empty=true
for command in curl dd df jq sha256sum stat tar truncate zstd; do
  command -v "$command" >/dev/null 2>&1 || { printf 'required empty-install command unavailable: %s\n' "$command" >&2; exit 1; }
done
readonly parent=$(dirname "$target")
install -d -m 0700 "$parent"

if [[ $choice == compactMiningNode ]]; then
  archive_name=$(jq -er '.datasets.compactMiningNode.artifact.name' "$manifest")
  archive_cid=$(jq -er '.datasets.compactMiningNode.artifact.cid' "$manifest")
  archive_sha=$(jq -er '.datasets.compactMiningNode.artifact.sha256' "$manifest")
  archive_bytes=$(jq -er '.datasets.compactMiningNode.artifact.bytes' "$manifest")
  unpacked_bytes=68719476736
  largest_part=0
else
  archive_name=$(jq -er '.datasets.fullArchive.filename' "$manifest")
  archive_cid=
  archive_sha=$(jq -er '.datasets.fullArchive.sha256' "$manifest")
  archive_bytes=$(jq -er '.datasets.fullArchive.size_bytes' "$manifest")
  unpacked_bytes=$(jq -er '.datasets.fullArchive.unpacked_size_bytes' "$manifest")
  largest_part=$(jq -er '[.datasets.fullArchive.delivery.parts[].size_bytes]|max' "$manifest")
  [[ $(jq -er '.datasets.fullArchive.delivery.parts|length' "$manifest") == 40 ]]
fi
[[ $archive_name =~ ^[A-Za-z0-9][A-Za-z0-9._+-]{0,255}$ ]]
[[ $archive_sha =~ ^[0-9a-f]{64}$ && $archive_bytes =~ ^[0-9]+$ && $archive_bytes -gt 0 ]]
[[ $unpacked_bytes =~ ^[0-9]+$ && $unpacked_bytes -gt 0 && $largest_part =~ ^[0-9]+$ ]]

read -r filesystem_bytes available_bytes < <(df -B1 --output=size,avail "$parent" | awk 'NR==2 {print $1, $2}')
[[ $filesystem_bytes =~ ^[0-9]+$ && $available_bytes =~ ^[0-9]+$ ]]
reserve_bytes=$((filesystem_bytes * 15 / 100))
((reserve_bytes >= 21474836480)) || reserve_bytes=21474836480
required_bytes=$((archive_bytes + unpacked_bytes + largest_part + 2147483648 + reserve_bytes))
if ((available_bytes < required_bytes)); then
  printf '%s\n' \
    'Insufficient space for authenticated RC65 data staging.' \
    "Available bytes: $available_bytes" \
    "Required bytes: $required_bytes (archive $archive_bytes + extraction $unpacked_bytes + largest part $largest_part + staging 2147483648 + retained reserve $reserve_bytes)." \
    'Preserve active data, current images, release evidence, and one known-good rollback. Reclaim only exact inactive reproducible artifacts, then rerun.' >&2
  exit 1
fi

stage=$(mktemp -d "$parent/.rc65-data-stage.XXXXXX")
readonly stage
readonly archive=$stage/$archive_name
cleanup() {
  if [[ -d $stage && ! -L $stage && $stage == "$parent/.rc65-data-stage."* ]]; then
    find "$stage" -xdev -depth -delete 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM HUP

download_cid() {
  local cid=$1 output=$2
  [[ $cid =~ ^b[a-z2-7]{20,}$ && $output == "$stage/"* && ! -e $output && ! -L $output ]]
  curl --fail --location --proto '=https' --tlsv1.2 --ipv4 --http1.1 \
    --connect-timeout 15 --max-time 21600 --retry 5 --retry-all-errors \
    --continue-at - --output "$output.part" "$gateway/$cid"
  mv -T -- "$output.part" "$output"
}

if [[ $choice == compactMiningNode ]]; then
  download_cid "$archive_cid" "$archive"
else
  truncate -s 0 "$archive"
  while IFS= read -r part; do
    part_name=$(jq -er '.filename' <<<"$part")
    part_cid=$(jq -er '.cid' <<<"$part")
    part_sha=$(jq -er '.sha256' <<<"$part")
    part_bytes=$(jq -er '.size_bytes' <<<"$part")
    [[ $part_name =~ ^[A-Za-z0-9][A-Za-z0-9._+-]{0,255}$ && $part_sha =~ ^[0-9a-f]{64}$ && $part_bytes =~ ^[0-9]+$ ]]
    part_path=$stage/$part_name
    download_cid "$part_cid" "$part_path"
    [[ $(sha256sum "$part_path" | awk '{print $1}') == "$part_sha" ]]
    [[ $(stat -c %s "$part_path") == "$part_bytes" ]]
    dd if="$part_path" of="$archive" oflag=append conv=notrunc status=none
    rm -- "$part_path"
  done < <(jq -c '.datasets.fullArchive.delivery.parts[]' "$manifest")
fi
[[ $(sha256sum "$archive" | awk '{print $1}') == "$archive_sha" ]]
[[ $(stat -c %s "$archive") == "$archive_bytes" ]]

tar --zstd -tf "$archive" >"$stage/archive-members.txt"
if grep -E '(^/|(^|/)[.][.](/|$)|(^|/)(network[.]key|nodekey|peerstore)(/|$)|(^|/)[.]git(/|$)|(^|/)recovery-required(-cleared)?[.]json$|(^|/)(go[.]mod|go[.]sum)$|[.]go$|[.]map$)' \
  "$stage/archive-members.txt" >/dev/null; then
  printf '%s\n' 'dataset contains an unsafe, private, recovery-latch, or component-source path' >&2
  exit 1
fi
install -d -m 0700 "$stage/data"
tar --zstd --no-same-owner --no-same-permissions -xf "$archive" -C "$stage/data"
[[ -d $stage/data/mainnet ]]
if find "$stage/data" -xdev \( -type f \( -name network.key -o -name nodekey \) -o -type d -name peerstore \) -print -quit | grep -q .; then
  printf '%s\n' 'dataset contains node identity or peerstore material' >&2
  exit 1
fi
if [[ $target_was_empty == true ]]; then
  [[ -d $target && ! -L $target && -z $(find "$target" -mindepth 1 -maxdepth 1 -print -quit) ]]
  rmdir -- "$target"
fi
[[ ! -e $target ]]
mv -T -- "$stage/data" "$target"
trap - EXIT INT TERM HUP
find "$stage" -xdev -depth -delete
printf 'Authenticated RC65 %s data installed at %s. Generate a fresh local node identity before starting.\n' "$choice" "$target"
