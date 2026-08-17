#!/usr/bin/env bash
# Download, authenticate, and stage the exact RC64 AMD64 node and pool images.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

readonly tag=jeremy-community-rescue-rc.64-amd64
readonly base_url=${BDAG_RC64_BASE_URL:-https://github.com/BlockdagEngineering/stack/releases/download/$tag}
readonly destination=${1:-$PWD/blockdag-community-rescue-rc64-amd64}
readonly key_sha=9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66
readonly node_manifest=sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02
readonly pool_manifest=sha256:118bfca120162191449c6cca0e703815b365c2b0dbf4ad9732d69a3a151747ba
readonly node_binary_sha=3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19

for command in curl docker jq openssl sha256sum stat uname; do
  command -v "$command" >/dev/null 2>&1 || {
    printf 'required command unavailable: %s\n' "$command" >&2
    exit 1
  }
done
case $(uname -m) in
  x86_64|amd64) ;;
  *) printf '%s\n' 'RC64 is AMD64-only; ARM64 is explicitly deferred.' >&2; exit 1 ;;
esac
[[ $base_url == https://* && $destination == /* && ! -L $destination ]]
install -d -m 0700 "$destination"

readonly files=(
  release.json
  release.json.sig
  release-public.pem
  bootstrap-peers.txt
  bootstrap-peers.txt.sig
  bootstrap-peers.manifest.json
  bootstrap-peers.manifest.json.sig
  latest-data-manifest.json
  latest-data-manifest.json.sig
  recovery-image-linux-amd64.docker.tar
  pool-image-linux-amd64.docker.tar
)
for filename in "${files[@]}"; do
  target=$destination/$filename
  [[ ! -e $target && ! -L $target ]] || {
    printf 'refusing to overwrite: %s\n' "$target" >&2
    exit 1
  }
  curl --fail --location --proto '=https' --tlsv1.2 \
    --connect-timeout 10 --max-time 7200 --output "$target" "$base_url/$filename"
  chmod 0600 "$target"
done

actual_key_sha=$(openssl pkey -pubin -in "$destination/release-public.pem" \
  -outform DER | sha256sum | awk '{print $1}')
[[ $actual_key_sha == "$key_sha" ]] || {
  printf '%s\n' 'release public-key fingerprint mismatch' >&2
  exit 1
}
verify_signature() {
  local payload=$1 signature=$2
  openssl pkeyutl -verify -pubin -inkey "$destination/release-public.pem" \
    -rawin -in "$payload" -sigfile "$signature" >/dev/null
}
verify_signature "$destination/release.json" "$destination/release.json.sig"
verify_signature "$destination/bootstrap-peers.txt" "$destination/bootstrap-peers.txt.sig"
verify_signature "$destination/bootstrap-peers.manifest.json" \
  "$destination/bootstrap-peers.manifest.json.sig"
verify_signature "$destination/latest-data-manifest.json" \
  "$destination/latest-data-manifest.json.sig"

jq -e --arg node "$node_manifest" --arg pool "$pool_manifest" '
  .schema=="bdag.community-canonical-recovery-release.v4" and
  .version=="2.0.0-community-rescue-rc.64" and .sequence==64 and
  .status=="published" and .platforms==["linux/amd64"] and
  .deferredPlatforms==["linux/arm64"] and .network.chainId==1404 and
  .images.node.qualifiedRuntimeManifest==$node and
  .images.pool.qualifiedRuntimeManifest==$pool and
  .acceptance.minimumExactNodes>=3 and .acceptance.minimumExactMiningHosts>=3 and
  .acceptance.ownerPayoutIdentityPreserved==true and
  .acceptance.realDivergentAdoption==true and
  .acceptance.sustainedIndependentConvergence==true and
  .acceptance.publicRpcExactBlueGreen==true and
  .runtimePolicy.evmReferenceUrlsDefaultEmpty==true and
  .runtimePolicy.nativeSafeMiningIgnoresLegacyV45Noise==true and
  .runtimePolicy.evmAdvisoryWhenGuardDisabled==true
' "$destination/release.json" >/dev/null

bootstrap_sha=$(sha256sum "$destination/bootstrap-peers.txt" | awk '{print $1}')
bootstrap_lines=$(wc -l <"$destination/bootstrap-peers.txt")
jq -e --arg sha "$bootstrap_sha" --argjson lines "$bootstrap_lines" '
  .schema=="chain1404-bootstrap-peers-manifest/v1" and
  .network.chainId==1404 and .file.name=="bootstrap-peers.txt" and
  .file.sha256==$sha and .file.lineCount==$lines and $lines>=3 and
  .trust.discoveryOnly==true and .trust.consensusAuthority==false and
  .trust.miningReadinessVoter==false
' "$destination/bootstrap-peers.manifest.json" >/dev/null
bootstrap_manifest_sha=$(sha256sum "$destination/bootstrap-peers.manifest.json" | awk '{print $1}')
data_manifest_sha=$(sha256sum "$destination/latest-data-manifest.json" | awk '{print $1}')
jq -e --arg bootstrap "$bootstrap_manifest_sha" --arg data "$data_manifest_sha" '
  .assets.bootstrapPeers.manifestSha256==$bootstrap and
  .assets.latestData.manifestSha256==$data
' "$destination/release.json" >/dev/null
jq -e '
  .schema=="chain1404-latest-data-manifest/v1" and .network.chainId==1404 and
  .platform=="linux/amd64" and .cleanShutdown==true and
  .sanitization.nodeIdentityExcluded==true and
  .sanitization.peerstoreExcluded==true and
  .sanitization.credentialsExcluded==true and
  (.snapshot.cid|type=="string" and startswith("b")) and
  (.snapshot.sha256|type=="string" and test("^[0-9a-f]{64}$")) and
  (.snapshot.bytes|type=="number" and .>0)
' "$destination/latest-data-manifest.json" >/dev/null

verify_artifact() {
  local role=$1 path=$2 expected_sha expected_bytes
  expected_sha=$(jq -er --arg role "$role" \
    '.images[$role].dockerArchive.sha256' "$destination/release.json")
  expected_bytes=$(jq -er --arg role "$role" \
    '.images[$role].dockerArchive.bytes' "$destination/release.json")
  [[ $(sha256sum "$path" | awk '{print $1}') == "$expected_sha" ]]
  [[ $(stat -c %s "$path") == "$expected_bytes" ]]
}
verify_artifact node "$destination/recovery-image-linux-amd64.docker.tar"
verify_artifact pool "$destination/pool-image-linux-amd64.docker.tar"

docker load --input "$destination/recovery-image-linux-amd64.docker.tar" >/dev/null
docker load --input "$destination/pool-image-linux-amd64.docker.tar" >/dev/null
[[ $(docker image inspect -f '{{.Architecture}} {{index .Config.Labels "org.blockdag.recovery.stack-sha"}} {{index .Config.Labels "org.blockdag.recovery.core-sha"}}' "$node_manifest") == \
  'amd64 ae1e8f1b4685d0e02888b127adbace5849c3a4f5 f07e084c06d758bc92377fc18cb5a0130fe6f89c' ]]
[[ $(docker image inspect -f '{{.Architecture}} {{index .Config.Labels "org.blockdag.recovery.stack-sha"}} {{index .Config.Labels "org.blockdag.recovery.pool-sha"}}' "$pool_manifest") == \
  'amd64 99579d1998a131ab7e7542ffda9608c058a1a43d 68d3f7471352cce2164cfab5550abafacf8dfae7' ]]
measured_binary=$(docker run --rm --network none --entrypoint sha256sum \
  "$node_manifest" /usr/local/bin/blockdag-node | awk '{print $1}')
[[ $measured_binary == "$node_binary_sha" ]]

printf '%s\n' \
  'RC64 authentication and image staging passed.' \
  "Node image: $node_manifest" \
  "Pool image: $pool_manifest" \
  'Signed bootstrap and latest-data manifests passed.' \
  'No running container, existing chain data, pool accounting, payout, or ASIC configuration was changed.'
