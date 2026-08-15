#!/usr/bin/env bash
# Download, authenticate, and stage the exact RC63 AMD64 node and pool images.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

tag=jeremy-community-rescue-rc.63-amd64
base_url=${BDAG_RC63_BASE_URL:-https://github.com/BlockdagEngineering/stack/releases/download/$tag}
destination=${1:-$PWD/blockdag-community-rescue-rc63-amd64}
key_sha=9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66
node_manifest=sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02
pool_manifest=sha256:db0b7376d39e44dfbf35ced780fc2349e95f9bb197bc4ac8628de02e2c17c62c
node_binary_sha=3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19

for command in curl docker jq openssl sha256sum stat uname; do
  command -v "$command" >/dev/null 2>&1 || { echo "required command unavailable: $command" >&2; exit 1; }
done
case $(uname -m) in x86_64|amd64) ;; *) echo 'RC63 is AMD64-only; ARM64 is deferred.' >&2; exit 1 ;; esac
[[ $base_url == https://* && $destination == /* ]]
[[ ! -L $destination ]]
install -d -m 0700 "$destination"

files=(
  release.json
  release.json.sig
  release-public.pem
  recovery-image-linux-amd64.docker.tar
  pool-image-linux-amd64.docker.tar
)
for filename in "${files[@]}"; do
  target=$destination/$filename
  [[ ! -e $target && ! -L $target ]] || { echo "refusing to overwrite: $target" >&2; exit 1; }
  curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 7200 \
    --output "$target" "$base_url/$filename"
  chmod 0600 "$target"
done

actual_key_sha=$(openssl pkey -pubin -in "$destination/release-public.pem" -outform DER | sha256sum | awk '{print $1}')
[[ $actual_key_sha == "$key_sha" ]] || { echo 'release public-key fingerprint mismatch' >&2; exit 1; }
openssl pkeyutl -verify -pubin -inkey "$destination/release-public.pem" -rawin \
  -in "$destination/release.json" -sigfile "$destination/release.json.sig" >/dev/null
jq -e --arg node "$node_manifest" --arg pool "$pool_manifest" '
  .schema=="bdag.community-canonical-recovery-release.v3" and
  .version=="2.0.0-community-rescue-rc.63" and .status=="published" and
  .platforms==["linux/amd64"] and .network.chainId==1404 and
  .images.node.qualifiedRuntimeManifest==$node and
  .images.pool.qualifiedRuntimeManifest==$pool and
  .acceptance.fleetComplete==true and
  .acceptance.ownerPayoutIdentityPreserved==true and
  .acceptance.publicRpcExactBlueGreen==true
' "$destination/release.json" >/dev/null

verify_artifact() {
  local role=$1 path=$2 expected_sha expected_bytes
  expected_sha=$(jq -er --arg role "$role" '.images[$role].dockerArchive.sha256' "$destination/release.json")
  expected_bytes=$(jq -er --arg role "$role" '.images[$role].dockerArchive.bytes' "$destination/release.json")
  [[ $(sha256sum "$path" | awk '{print $1}') == "$expected_sha" ]]
  [[ $(stat -c %s "$path") == "$expected_bytes" ]]
}
verify_artifact node "$destination/recovery-image-linux-amd64.docker.tar"
verify_artifact pool "$destination/pool-image-linux-amd64.docker.tar"

docker load --input "$destination/recovery-image-linux-amd64.docker.tar" >/dev/null
docker load --input "$destination/pool-image-linux-amd64.docker.tar" >/dev/null
[[ $(docker image inspect -f '{{.Architecture}} {{index .Config.Labels "org.blockdag.recovery.stack-sha"}} {{index .Config.Labels "org.blockdag.recovery.core-sha"}}' "$node_manifest") == 'amd64 ae1e8f1b4685d0e02888b127adbace5849c3a4f5 f07e084c06d758bc92377fc18cb5a0130fe6f89c' ]]
[[ $(docker image inspect -f '{{.Architecture}} {{index .Config.Labels "org.blockdag.recovery.pool-sha"}}' "$pool_manifest") == 'amd64 64c834a93bd7f5a2f91df7291c0328b39df12541' ]]
measured_binary=$(docker run --rm --network none --entrypoint sha256sum "$node_manifest" /usr/local/bin/blockdag-node | awk '{print $1}')
[[ $measured_binary == "$node_binary_sha" ]]

printf '%s\n' \
  'RC63 authentication and image staging passed.' \
  "Node image: $node_manifest" \
  "Pool image: $pool_manifest" \
  'No running container or ASIC configuration was changed.' \
  'Follow docs/recover-divergent-node.md for a backup-backed node successor.' \
  'For a pool upgrade, keep its existing Stratum endpoint and owner payout address; use the signed owner-safe cutover tool.'
