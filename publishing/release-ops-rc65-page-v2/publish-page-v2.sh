#!/usr/bin/env bash
# Publish the exact qualified RC65 rich page, then advance Pages and both IPNS names.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C AWS_PAGER='' PYTHONDONTWRITEBYTECODE=1

[[ $# -eq 3 ]] || { echo "usage: $0 SUBJECT_JSON SUBJECT_SHA256 RESULT_JSON" >&2; exit 64; }
readonly subject_file=$1
readonly subject_sha=$2
readonly result=$3
readonly repo=/home/jeremy/worktrees/bdag-rc64-release-page
readonly release_root=$repo/releases/2.0.0-community-rescue-rc.65-page-v2
readonly branch=jeremy/release/2026-08-17-rc65-rich-ipfs-page-v2
readonly repository=BlockdagEngineering/bdag-ipfs-release-page
readonly page_cid=bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku
readonly records_cid=bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe
readonly admission_cid=bafkreie7lwh7jxxv4qsbz26kzaz4xul5e3lmilbawrwce5uigppd3jihq4
readonly provider_peer=12D3KooWD3c6UAMwSBjuPbYinx4mJMTsEBK1kNjW9s5TtZL8L6Gi
readonly local_ipns=k51qzi5uqu5dgijozv3dne65cp7iqv96tpsa8dflmwmqvdw9oxx4w3gsvt0ctl
readonly profile=257455992626
readonly region=eu-central-1
readonly instance=i-0003578e60e4abcb0
readonly local_port=15005
readonly ssm_cache=/home/jeremy/.cache/r65ssm-page-v2-publication

[[ $subject_sha =~ ^sha256:[0-9a-f]{64}$ ]]
[[ -f $subject_file && ! -L $subject_file && -d $release_root && ! -L $release_root ]]
[[ $result == /home/jeremy/live-ops-artifacts/rc65-page-v2-publication-20260817/evidence-v6/publication.json ]]
[[ ! -e $result && ! -L $result ]]
for command in aws curl df find gh git ipfs jq openssl sha256sum ssh ss stat; do command -v "$command" >/dev/null; done

actual_subject=sha256:$(sha256sum "$subject_file" | awk '{print $1}')
[[ $actual_subject == "$subject_sha" ]]
[[ $(jq -er '.page.cid' "$subject_file") == "$page_cid" ]]
[[ $(jq -er '.git.branch' "$subject_file") == "$branch" ]]
base_commit=$(jq -er '.git.baseCommit' "$subject_file")
expected_tree=$(jq -er '.git.stagedTree' "$subject_file")
readonly base_commit expected_tree
[[ $base_commit =~ ^[0-9a-f]{40}$ && $expected_tree =~ ^[0-9a-f]{40}$ ]]

cd "$repo"
[[ $(git branch --show-current) == "$branch" ]]
[[ -z $(git diff --name-only) ]]
[[ -z $(git ls-files --others --exclude-standard) ]]
[[ $(git write-tree) == "$expected_tree" ]]
[[ $(ipfs add -r --only-hash --hidden=true --empty-dirs=true --cid-version=1 --raw-leaves=true \
  --chunker=size-262144 --hash=sha2-256 --preserve-mode=false --preserve-mtime=false \
  -Q "$release_root") == "$page_cid" ]]
[[ $(ipfs add -r --only-hash --hidden=true --empty-dirs=true --cid-version=1 --raw-leaves=true \
  --chunker=size-262144 --hash=sha2-256 --preserve-mode=false --preserve-mtime=false \
  -Q "$release_root/records") == "$records_cid" ]]

read -r filesystem_bytes available_bytes < <(df -B1 --output=size,avail "$repo" | awk 'NR==2 {print $1, $2}')
reserve_bytes=$((filesystem_bytes * 15 / 100)); ((reserve_bytes >= 21474836480)) || reserve_bytes=21474836480
page_bytes=$(find "$release_root" -xdev -type f -printf '%s\n' | awk '{n+=$1} END{print n+0}')
((available_bytes >= reserve_bytes + page_bytes * 3 + 268435456))
[[ -z $(ss -H -lnt "sport = :$local_port") ]]
install -d -m 0700 "$ssm_cache" "$(dirname "$result")"
[[ ! -L $ssm_cache && ! -L $(dirname "$result") ]]

work=$(mktemp -d /home/jeremy/live-ops-artifacts/rc65-page-v2-publication-20260817/evidence-v6/.publish.XXXXXX)
readonly work
forward_pid=''
cleanup() {
  rc=$?
  trap - EXIT INT TERM HUP
  set +e
  [[ -z $forward_pid ]] || kill "$forward_pid" 2>/dev/null
  [[ -z $forward_pid ]] || wait "$forward_pid" 2>/dev/null
  if [[ -d $work && ! -L $work && $work == /home/jeremy/live-ops-artifacts/rc65-page-v2-publication-20260817/evidence-v6/.publish.* ]]; then
    find "$work" -xdev -type f -delete
    rmdir "$work"
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM HUP

production_before=$(curl -fsS --max-time 20 -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' \
  https://rpc.blockdag.engineering | jq -er '.result')
[[ $production_before =~ ^0x[0-9a-f]+$ ]]

# Add only the tiny page DAG locally. Existing payload roots remain on the public provider.
actual_page_cid=$(ipfs add -Qr --hidden=true --empty-dirs=true --cid-version=1 --raw-leaves=true \
  --chunker=size-262144 --hash=sha2-256 --preserve-mode=false --preserve-mtime=false "$release_root")
[[ $actual_page_cid == "$page_cid" ]]
ipfs pin ls --type=recursive "$page_cid" | awk -v cid="$page_cid" '$1==cid && $2=="recursive" {found=1} END{exit !found}'

TMPDIR="$ssm_cache" TMP="$ssm_cache" TEMP="$ssm_cache" \
  aws --profile "$profile" --region "$region" ssm start-session --target "$instance" \
  --document-name AWS-StartPortForwardingSession \
  --parameters "{\"portNumber\":[\"5001\"],\"localPortNumber\":[\"$local_port\"]}" \
  >"$work/port-forward.log" 2>&1 &
forward_pid=$!
deadline=$((SECONDS + 60)); remote_peer=
while ((SECONDS < deadline)); do
  remote_peer=$(curl -fsS --max-time 5 -X POST "http://127.0.0.1:$local_port/api/v0/id" 2>/dev/null | jq -er '.ID' 2>/dev/null || true)
  [[ $remote_peer == "$provider_peer" ]] && break
  kill -0 "$forward_pid" 2>/dev/null || break
  sleep 1
done
[[ $remote_peer == "$provider_peer" ]]

ipfs dag export "$page_cid" | curl --fail --silent --show-error --max-time 600 -X POST \
  -F 'file=@-;filename=chain1404-rc65-page-v2.car' \
  "http://127.0.0.1:$local_port/api/v0/dag/import?pin-roots=true" >"$work/import.ndjson"
for cid in "$page_cid" "$records_cid" "$admission_cid"; do
  curl -fsS --max-time 120 -X POST \
    "http://127.0.0.1:$local_port/api/v0/pin/add?arg=$cid&recursive=true&progress=false" \
    >"$work/pin-$cid.json"
  jq -e --arg cid "$cid" '.Pins | index($cid)' "$work/pin-$cid.json" >/dev/null
done
curl -fsS --max-time 180 -X POST \
  "http://127.0.0.1:$local_port/api/v0/pin/ls?type=recursive" >"$work/remote-pins.json"
jq -e --slurpfile remote "$work/remote-pins.json" \
  'all(.pins[] | select(.name | startswith("full-archive-part-") | not); ($remote[0].Keys[.cid].Type == "recursive"))' \
  publishing/free-pinning-cids.json >/dev/null

# The repository mutation is exact-tree and branch confined.
current_head=$(git rev-parse HEAD)
if [[ $current_head == "$base_commit" ]]; then
  git commit -m 'Publish rich RC65 IPFS release experience'
  publication_commit=$(git rev-parse HEAD)
elif [[ $(git rev-parse HEAD^ 2>/dev/null || true) == "$base_commit" && $(git rev-parse "HEAD^{tree}") == "$expected_tree" ]]; then
  publication_commit=$current_head
else
  echo 'repository head no longer matches the qualified publication transition' >&2
  exit 1
fi
[[ $(git rev-parse "$publication_commit^{tree}") == "$expected_tree" ]]
[[ -z $(git status --porcelain=v1) ]]

if ! gh api "repos/$repository/environments/github-pages/deployment-branch-policies" --paginate \
  --jq '.branch_policies[].name' | grep -Fqx "$branch"; then
  gh api --method POST "repos/$repository/environments/github-pages/deployment-branch-policies" \
    -f name="$branch" -f type=branch >"$work/branch-policy.json"
  [[ $(jq -er '.name' "$work/branch-policy.json") == "$branch" ]]
fi
git push origin "HEAD:refs/heads/$branch"
[[ $(git ls-remote origin "refs/heads/$branch" | awk '{print $1}') == "$publication_commit" ]]

run_id=; run_url=; deadline=$((SECONDS + 180))
while ((SECONDS < deadline)); do
  gh run list --repo "$repository" --workflow pages.yml --branch "$branch" --event push \
    --limit 20 --json databaseId,headSha,status,conclusion,url >"$work/runs.json"
  run_id=$(jq -er --arg sha "$publication_commit" '[.[] | select(.headSha==$sha)][0].databaseId // empty' "$work/runs.json" 2>/dev/null || true)
  run_url=$(jq -er --arg sha "$publication_commit" '[.[] | select(.headSha==$sha)][0].url // empty' "$work/runs.json" 2>/dev/null || true)
  [[ -n $run_id ]] && break
  sleep 3
done
[[ -n $run_id && -n $run_url ]]
gh run watch "$run_id" --repo "$repository" --exit-status --interval 5
[[ $(gh run view "$run_id" --repo "$repository" --json headSha,status,conclusion --jq '.headSha+":"+.status+":"+.conclusion') == "$publication_commit:completed:success" ]]

pages_base=$(gh api "repos/$repository/pages" --jq '.html_url')
[[ $pages_base == https://blockdagengineering.github.io/bdag-ipfs-release-page/ ]]
nonce=$(date +%s%N)
curl -fsSL --max-time 60 -H 'Cache-Control: no-cache' "${pages_base}index.html?nocache=$nonce" -o "$work/pages-root.html"
curl -fsSL --max-time 60 -H 'Cache-Control: no-cache' \
  "${pages_base}releases/2.0.0-community-rescue-rc.65-page-v2/index.html?nocache=$nonce" -o "$work/pages-release.html"
[[ $(sha256sum "$work/pages-root.html" | awk '{print $1}') == $(sha256sum index.html | awk '{print $1}') ]]
[[ $(sha256sum "$work/pages-release.html" | awk '{print $1}') == $(sha256sum "$release_root/index.html" | awk '{print $1}') ]]

# Require the user-facing dweb URL to answer, and an anonymous gateway to return exact bytes.
readonly dweb_url="https://dweb.link/ipfs/$page_cid/index.html"
curl -fsSL --max-time 90 -H 'Cache-Control: no-cache' "$dweb_url?nocache=$nonce" -o "$work/dweb.html"
grep -Fq 'Support the developers by supporting the community' "$work/dweb.html"
exact_gateway=
for candidate in \
  "https://$page_cid.ipfs.dweb.link/index.html" \
  "https://ipfs.io/ipfs/$page_cid/index.html" \
  "https://w3s.link/ipfs/$page_cid/index.html"; do
  if curl -fsSL --max-time 90 -H 'Cache-Control: no-cache' "$candidate?nocache=$nonce" -o "$work/gateway.html" && \
     [[ $(sha256sum "$work/gateway.html" | awk '{print $1}') == $(sha256sum "$release_root/index.html" | awk '{print $1}') ]]; then
    exact_gateway=$candidate
    break
  fi
done
[[ -n $exact_gateway ]]

off_lan_hash=$(ssh -o BatchMode=yes -o ConnectTimeout=15 francois-140-zt \
  "curl -fsSL --max-time 90 '$exact_gateway?offlan=$nonce' | sha256sum" | awk '{print $1}')
[[ $off_lan_hash == $(sha256sum "$release_root/index.html" | awk '{print $1}') ]]

# Move both convenience pointers only after immutable CID, Pages, and off-LAN proofs pass.
curl -fsS --max-time 120 -X POST \
  "http://127.0.0.1:$local_port/api/v0/name/publish?arg=%2Fipfs%2F$page_cid&key=self&allow-offline=true&lifetime=8760h&quieter=true" \
  >"$work/remote-ipns.json"
jq -e --arg value "/ipfs/$page_cid" --arg name "$provider_peer" '.Name==$name and .Value==$value' "$work/remote-ipns.json" >/dev/null
ipfs name publish --key=bdag-community-rescue-latest --allow-offline=true --lifetime=8760h "/ipfs/$page_cid" >"$work/local-ipns.txt"
[[ $(ipfs name resolve --nocache "/ipns/$local_ipns") == "/ipfs/$page_cid" ]]
curl -fsS --max-time 120 -X POST \
  "http://127.0.0.1:$local_port/api/v0/name/resolve?arg=%2Fipns%2F$provider_peer&nocache=true" \
  >"$work/remote-resolve.json"
jq -e --arg value "/ipfs/$page_cid" '.Path==$value' "$work/remote-resolve.json" >/dev/null

production_after=$(curl -fsS --max-time 20 -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":2,"method":"eth_blockNumber","params":[]}' \
  https://rpc.blockdag.engineering | jq -er '.result')
[[ $production_after =~ ^0x[0-9a-f]+$ ]]
before_dec=$((16#${production_before#0x})); after_dec=$((16#${production_after#0x})); ((after_dec >= before_dec))

jq -n -S \
  --arg subject "$subject_sha" --arg at "$(date -u +%FT%TZ)" --arg cid "$page_cid" \
  --arg commit "$publication_commit" --arg runUrl "$run_url" --arg pages "$pages_base" \
  --arg dweb "$dweb_url" --arg exactGateway "$exact_gateway" --arg offLanHash "$off_lan_hash" \
  --arg provider "$provider_peer" --arg localIpns "$local_ipns" \
  --arg before "$production_before" --arg after "$production_after" --argjson bytes "$page_bytes" \
  '{schema:"chain1404-rc65-page-v2-publication/v1",status:"passed",subject_sha256:$subject,
    finishedAt:$at,pageCid:$cid,pageBytes:$bytes,git:{commit:$commit,branch:"jeremy/release/2026-08-17-rc65-rich-ipfs-page-v2"},
    github:{workflow:$runUrl,pages:$pages},ipfs:{dweb:$dweb,exactGateway:$exactGateway,providerPeerId:$provider,
    remoteIpns:("/ipns/"+$provider),localIpns:("/ipns/"+$localIpns),awsCurrentRootsPinned:true,all47RootsPublic:true},
    offLan:{host:"Francois",sha256:$offLanHash},productionRpc:{before:$before,after:$after,touched:false}}' >"$result"
chmod 0600 "$result"

kill "$forward_pid" 2>/dev/null || true
wait "$forward_pid" 2>/dev/null || true
forward_pid=''
trap - EXIT INT TERM HUP
find "$work" -xdev -type f -delete
rmdir "$work"
jq -c . "$result"
