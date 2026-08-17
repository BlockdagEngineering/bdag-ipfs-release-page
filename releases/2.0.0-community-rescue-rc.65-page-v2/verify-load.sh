#!/usr/bin/env bash
# Authenticate the RC65 page records and select the exact local architecture.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

readonly release_root=${1:-$(cd "$(dirname "$0")" && pwd)}
readonly records=$release_root/records
readonly outer_key_sha=9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66
readonly software_key_sha=26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb
readonly dataset_key_sha=f9f2f7df88d43c8d51df8bdc2a369601ff0b4b9de224e8ab9b609b423b203d24
readonly software_tag=jeremy-community-rescue-rc.65.6

[[ $release_root == /* && -d $release_root && ! -L $release_root ]]
for command in jq openssl python3 sha256sum stat uname; do
  command -v "$command" >/dev/null 2>&1 || { printf 'required command unavailable: %s\n' "$command" >&2; exit 1; }
done
case $(uname -m) in
  x86_64|amd64) platform=linux-amd64 ;;
  aarch64|arm64) platform=linux-arm64 ;;
  *) printf '%s\n' 'unsupported architecture; RC65 supports Linux AMD64 and ARM64 only' >&2; exit 1 ;;
esac

required=(
  release.json release.json.sig release-public.pem SHA256SUMS
  bootstrap-peers.txt bootstrap-peers.txt.sig
  bootstrap-peers.manifest.json bootstrap-peers.manifest.json.sig
  dataset/compact-data-manifest.json dataset/compact-data-manifest.json.sig
  dataset/compact-release-public.pem dataset/full-archive-v28-canonical-manifest.json
  dataset/full-archive-v28-parts.json dataset/full-archive-v28-validation-spec.json
  dataset/qualification-v2-20260711.pem dataset/verify-canonical-manifest.py
  software/bootstrap.sh software/release-auth-manifest.json
  software/release-auth-manifest.json.sig software/release-key.pem
  software/publication-attestation.json software/publication-attestation.json.sig
)
for relative in "${required[@]}"; do
  [[ -f $records/$relative && ! -L $records/$relative ]] || {
    printf 'required signed record is missing or unsafe: %s\n' "$relative" >&2
    exit 1
  }
done
if grep -R -E 'PLACEHOLDER|publication-pending' "$records" >/dev/null 2>&1; then
  printf '%s\n' 'publication placeholders remain; refusing RC65 verification' >&2
  exit 1
fi

fingerprint() {
  openssl pkey -pubin -in "$1" -outform DER | sha256sum | awk '{print $1}'
}
[[ $(fingerprint "$records/release-public.pem") == "$outer_key_sha" ]]
[[ $(fingerprint "$records/software/release-key.pem") == "$software_key_sha" ]]
[[ $(fingerprint "$records/dataset/qualification-v2-20260711.pem") == "$dataset_key_sha" ]]
verify() {
  openssl pkeyutl -verify -pubin -inkey "$1" -rawin -in "$2" -sigfile "$3" >/dev/null
}
verify "$records/release-public.pem" "$records/release.json" "$records/release.json.sig"
verify "$records/release-public.pem" "$records/bootstrap-peers.txt" "$records/bootstrap-peers.txt.sig"
verify "$records/release-public.pem" "$records/bootstrap-peers.manifest.json" "$records/bootstrap-peers.manifest.json.sig"
verify "$records/dataset/compact-release-public.pem" "$records/dataset/compact-data-manifest.json" "$records/dataset/compact-data-manifest.json.sig"
verify "$records/software/release-key.pem" "$records/software/release-auth-manifest.json" "$records/software/release-auth-manifest.json.sig"
verify "$records/software/release-key.pem" "$records/software/publication-attestation.json" "$records/software/publication-attestation.json.sig"

(cd "$records" && sha256sum --check --strict SHA256SUMS >/dev/null)
bootstrap_sha=$(sha256sum "$records/bootstrap-peers.txt" | awk '{print $1}')
bootstrap_lines=$(wc -l <"$records/bootstrap-peers.txt")
jq -e --arg sha "$bootstrap_sha" --argjson lines "$bootstrap_lines" '
  .schema=="chain1404-bootstrap-peers-manifest/v1" and .status=="published" and
  .network.chainId==1404 and .file.name=="bootstrap-peers.txt" and
  .file.sha256==$sha and .file.lineCount==$lines and $lines>=3 and
  .trust.discoveryOnly==true and .trust.consensusAuthority==false and
  .trust.miningReadinessVoter==false
' "$records/bootstrap-peers.manifest.json" >/dev/null

jq -e --arg platform "$platform" --arg tag "$software_tag" '
  .schema=="bdag.community-release-index.v3" and .status=="published" and
  .version=="2.0.0-community-rescue-rc.65" and .sequence==65 and
  .network.chainId==1404 and .platforms==["linux/amd64","linux/arm64"] and
  .provenance.softwareTag==$tag and
  .existingDataUpgrade=={downloadsCompact:false,downloadsFullArchive:false,reusesQualifiedData:true} and
  (.software.targets[$platform].cid|type=="string" and startswith("b")) and
  (.software.targets[$platform].sha256|test("^[0-9a-f]{64}$")) and
  .software.targets[$platform].bytes>0 and
  .datasets.compactMiningNode.status=="published" and
  .datasets.fullArchive.status=="published" and
  .datasets.fullArchive.catchUpRequiredFromPublishedBoundary==true and
  (.datasets.fullArchive.delivery.parts|length)==40 and
  .runtimePolicy.legacyV45NoiseCannotBlockNativeSafeMining==true and
  .runtimePolicy.ownerPayoutIdentityPreserved==true
' "$records/release.json" >/dev/null
jq -e --arg tag "$software_tag" '
  .schema=="chain1404-compact-data-manifest/v2" and .release=="2.0.0-community-rescue-rc.65" and
  .softwareTag==$tag and .network.chainId==1404 and .cleanShutdown==true and
  .datasetClass=="normal-mining-node" and
  (.artifact.cid|type=="string" and startswith("b")) and
  (.artifact.sha256|test("^[0-9a-f]{64}$")) and .artifact.bytes>0 and
  .sanitization.nodeIdentityExcluded==true and .sanitization.peerstoreExcluded==true and
  .sanitization.credentialsExcluded==true and .sanitization.componentSourceExcluded==true
' "$records/dataset/compact-data-manifest.json" >/dev/null
jq -e --arg tag "$software_tag" --arg key "$software_key_sha" '
  .schema=="bdag.release-auth-manifest.v1" and .release.version==$tag and
  .release.sequence==65 and .release_key_sha256==$key and (.assets|length)==3
' "$records/software/release-auth-manifest.json" >/dev/null
python3 "$records/dataset/verify-canonical-manifest.py" verify \
  --envelope "$records/dataset/full-archive-v28-canonical-manifest.json" \
  --trusted-key-dir "$records/dataset" >/dev/null

jq -r --arg platform "$platform" '
  "RC65 records authenticated for " + $platform + ".\n" +
  "Software: " + .software.targets[$platform].name + "\n" +
  "Software CID: " + .software.targets[$platform].cid + "\n" +
  "Compact data CID: " + .datasets.compactMiningNode.artifact.cid + "\n" +
  "Existing qualified data is reused; no dataset download is required for an upgrade."
' "$records/release.json"
