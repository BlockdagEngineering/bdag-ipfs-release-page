#!/usr/bin/env bash
# Bounded native lifecycle harness.  It is intentionally sequential: the
# published nodeworker health port is host-local and role targets never share
# a running service or data directory.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 SOFTWARE_RECORD_ROOT TEST_OUTPUT_ROOT COMPANION_DIR" >&2
  exit 2
fi

record_root=$(realpath -e "$1")
output_root=$(realpath -m "$2")
companion_dir=$(realpath -e "$3")
release_record=${BDAG_RC2_RELEASE_RECORD:-"$companion_dir/../records/release.json"}
arch=${BDAG_RC2_PLATFORM:-}
if [[ -z "$arch" ]]; then
  case "$(uname -m)" in
    x86_64|amd64) arch=linux-amd64 ;;
    aarch64|arm64) arch=linux-arm64 ;;
    *) echo "unsupported native architecture" >&2; exit 2 ;;
  esac
fi
case "$arch" in
  linux-amd64) expected_image_arch=linux/amd64; native_machine_re='^(x86_64|amd64)$' ;;
  linux-arm64) expected_image_arch=linux/arm64; native_machine_re='^(aarch64|arm64)$' ;;
  *) echo "unsupported native platform label" >&2; exit 2 ;;
esac
native_machine=$(uname -m)
if [[ ! "$native_machine" =~ $native_machine_re ]]; then
  echo "native uname architecture does not match selected platform" >&2
  exit 2
fi

[[ -d "$record_root" && -f "$release_record" && -d "$companion_dir" ]] || {
  echo "record root, release record, and companion directory are required" >&2
  exit 2
}
mkdir -p "$output_root/receipts" "$output_root/targets" "$output_root/private-owner-env"
chmod 700 "$output_root" "$output_root/receipts" "$output_root/targets"
chmod 700 "$output_root/private-owner-env"
installer="$companion_dir/bdag-install.py"
[[ -f "$installer" ]] || { echo "installer is missing" >&2; exit 2; }

if [[ -n "${BDAG_RC2_POOL_CORE_ENDPOINT:-}${BDAG_RC2_OBSERVER_NODE_URL:-}" ]]; then
  echo "Native qualification uses only its owned real Core fixture, never an external service" >&2
  exit 2
fi
secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(24), end="")'; }
current_target=""
fixture_target=""
cleanup() {
  if [[ -n "$current_target" && -f "$current_target/install-pin.json" ]]; then
    timeout --foreground 120 python3 "$installer" stop --target "$current_target" >/dev/null 2>&1 || true
  fi
  if [[ -n "$fixture_target" && "$fixture_target" != "$current_target" ]]; then
    timeout --foreground 120 python3 "$installer" stop --target "$fixture_target" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

write_receipt() {
  local mode=$1 status=$2 detail=$3
  MODE="$mode" STATUS="$status" DETAIL="$detail" ARCH="$arch" \
    POOL_GATE_TEMPLATE_PROBED="${POOL_GATE_TEMPLATE_PROBED:-false}" \
    POOL_GATE_TEMPLATE_READY="${POOL_GATE_TEMPLATE_READY:-false}" \
    POOL_GATE_MINEABLE="${POOL_GATE_MINEABLE:-false}" \
    POOL_GATE_LOG_SEEN="${POOL_GATE_LOG_SEEN:-false}" \
    NATIVE_MACHINE="$native_machine" \
    IMAGE_ARCHES_JSON="${IMAGE_ARCHES_JSON:-[]}" \
    ARCHITECTURE_MATCH="${ARCHITECTURE_MATCH:-false}" \
    OUT="$output_root/receipts/${mode}-${arch}.json" \
    python3 - <<'PY'
import json, os
from pathlib import Path
value = {"schema":"bdag.rc2.native-install-receipt.v1", "mode":os.environ["MODE"],
         "platform":os.environ["ARCH"], "status":os.environ["STATUS"],
         "detail":os.environ["DETAIL"],
         "pool_gate_template_probed":os.environ["POOL_GATE_TEMPLATE_PROBED"] == "true",
         "pool_gate_template_ready":os.environ["POOL_GATE_TEMPLATE_READY"] == "true",
         "pool_gate_mineable":os.environ["POOL_GATE_MINEABLE"] == "true",
         "pool_gate_log_seen":os.environ["POOL_GATE_LOG_SEEN"] == "true",
         "native_uname_machine":os.environ["NATIVE_MACHINE"],
         "running_image_architectures":json.loads(os.environ["IMAGE_ARCHES_JSON"]),
         "architecture_match":os.environ["ARCHITECTURE_MATCH"] == "true"}
Path(os.environ["OUT"]).write_text(json.dumps(value, sort_keys=True) + "\n")
PY
}

for mode in node pool redis-dash all-in-one; do
  POOL_GATE_TEMPLATE_PROBED=false
  POOL_GATE_TEMPLATE_READY=false
  POOL_GATE_MINEABLE=false
  POOL_GATE_LOG_SEEN=false
  if [[ "$mode" == all-in-one && -n "$fixture_target" ]]; then
    timeout --foreground 120 python3 "$installer" stop --target "$fixture_target" >/dev/null
    fixture_target=""
  fi
  owner_env="$output_root/private-owner-env/$mode.env"
  target="$output_root/targets/$mode"
  current_target="$target"
  node_user="rc2_node_$(printf '%s' "$arch-$mode" | sha256sum | cut -c1-10)"
  node_pass=$(secret)
  limit_user="rc2_observer_$(printf '%s' "$arch-$mode" | sha256sum | cut -c1-10)"
  limit_pass=$(secret)
  pool_core_user=${BDAG_RC2_POOL_CORE_USER:-$node_user}
  pool_core_pass=${BDAG_RC2_POOL_CORE_PASS:-$node_pass}
  observer_user=${BDAG_RC2_OBSERVER_USER:-$limit_user}
  observer_pass=${BDAG_RC2_OBSERVER_PASS:-$limit_pass}
  pg_pass=$(secret)
  case "$mode" in
    node) mode_index=0 ;;
    pool) mode_index=1 ;;
    redis-dash) mode_index=2 ;;
    all-in-one) mode_index=3 ;;
  esac
  dashboard_port=$(( ${BDAG_RC2_DASHBOARD_PORT_BASE:-18088} + mode_index ))
  {
    printf 'BDAG_ENABLE_NODE_MINING=0\nPOOL_BIND_ADDR=127.0.0.1:3334\nMETRICS_ADDR=127.0.0.1:9090\nPOOL_FEE_PERCENTAGE=0\n'
    if [[ "$mode" == pool ]]; then
      printf 'NODE_RPC_USER=%s\nNODE_RPC_PASS=%s\n' "$pool_core_user" "$pool_core_pass"
    else
      printf 'NODE_RPC_USER=%s\nNODE_RPC_PASS=%s\n' "$node_user" "$node_pass"
    fi
    if [[ "$mode" == redis-dash ]]; then
      printf 'NODE_RPC_LIMIT_USER=%s\nNODE_RPC_LIMIT_PASS=%s\n' "$observer_user" "$observer_pass"
    else
      printf 'NODE_RPC_LIMIT_USER=%s\nNODE_RPC_LIMIT_PASS=%s\n' "$limit_user" "$limit_pass"
    fi
    case "$mode" in
      pool)
        printf 'NODE_RPC_URL=%s\n' "$BDAG_RC2_POOL_CORE_ENDPOINT"
        printf 'POSTGRES_USER=rc2_pool\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=rc2pool\n' "$pg_pass"
        printf 'MINING_POOL_ADDRESS=0x1111111111111111111111111111111111111111\n'
        ;;
      all-in-one)
        printf 'POSTGRES_USER=rc2_pool\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=rc2pool\n' "$pg_pass"
        printf 'MINING_POOL_ADDRESS=0x1111111111111111111111111111111111111111\n'
        printf 'DASHBOARD_LISTEN=127.0.0.1:%s\n' "$dashboard_port"
        ;;
      redis-dash)
        printf 'BDAG_NODE_RPC_URL=%s\nDASHBOARD_LISTEN=127.0.0.1:%s\n' "$BDAG_RC2_OBSERVER_NODE_URL" "$dashboard_port"
        ;;
    esac
  } >"$owner_env"
  chmod 600 "$owner_env"
  prepare_out=""
  log="$output_root/receipts/${mode}-${arch}.log"
  if ! prepare_out=$(timeout --foreground "${BDAG_NATIVE_PREPARE_TIMEOUT_SECONDS:-900}" \
      python3 "$installer" prepare --record-root "$record_root" --release-record "$release_record" \
      --target "$target" --owner-env "$owner_env" --mode "$mode" --platform "$arch" 2>"$log"); then
    write_receipt "$mode" "PREPARE_FAILED" "installer prepare failed; private log retained at $log"
    exit 1
  fi
  printf '%s\n' "$prepare_out" >"$output_root/receipts/${mode}-${arch}.prepare.json"
  if ! timeout --foreground "${BDAG_NATIVE_START_TIMEOUT_SECONDS:-900}" \
      python3 "$installer" start --record-root "$record_root" --release-record "$release_record" --target "$target" >>"$log" 2>&1; then
    write_receipt "$mode" "START_FAILED" "installer start failed; private log retained at $log"
    exit 1
  fi
  status_json=""
  if ! status_json=$(timeout --foreground "${BDAG_NATIVE_STATUS_TIMEOUT_SECONDS:-120}" \
      python3 "$installer" status --target "$target" 2>>"$log"); then
    write_receipt "$mode" "STATUS_FAILED" "installer status failed; private log retained at $log"
    exit 1
  fi
  printf '%s\n' "$status_json" >"$output_root/receipts/${mode}-${arch}.status.json"
  project=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["project"])' "$target/runner-config.json")
  # Running services prove lifecycle execution only.  Health may legitimately
  # remain pending while a fresh Core catches up; retain that distinction.
  readiness=$(STATUS_JSON="$status_json" python3 - <<'PY'
import json, os
try:
    value=json.loads(os.environ["STATUS_JSON"])
    rows=value.get("services", [])
    if rows and all(row.get("State") == "running" for row in rows):
        print("RUNNING_READINESS_PENDING")
    else:
        print("NOT_RUNNING")
except Exception:
    print("STATUS_UNPARSEABLE")
PY
  )
  if [[ "$readiness" == NOT_RUNNING || "$readiness" == STATUS_UNPARSEABLE ]]; then
    write_receipt "$mode" "READINESS_FAILED" "selected services did not reach running state; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  # Read the actual image architecture from the running containers selected by
  # this unique Compose project.  Status labels alone do not prove that the
  # native image matches the host architecture.
  case "$mode" in
    node) compose_services=(node) ;;
    pool) compose_services=(pool pool-db) ;;
    redis-dash) compose_services=(dashboard) ;;
    all-in-one) compose_services=(node pool pool-db dashboard) ;;
  esac
  architecture_probe=$(mktemp "$output_root/receipts/.${mode}-${arch}.architecture.XXXXXX")
  if ! timeout --foreground 60 docker compose --project-directory "$target/compose-context" \
      --project-name "$project" --env-file "$target/.env" -f "$target/compose.json" \
      ps -q "${compose_services[@]}" >"$architecture_probe" 2>>"$log"; then
    rm -f "$architecture_probe"
    write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "running container architecture probe failed; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  mapfile -t container_ids <"$architecture_probe"
  rm -f "$architecture_probe"
  if (( ${#container_ids[@]} == 0 )); then
    write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "selected Compose project returned no running container IDs; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  for container_id in "${container_ids[@]}"; do
    if [[ ! "$container_id" =~ ^[0-9a-fA-F]{12,64}$ ]]; then
      write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "Compose returned an invalid container identifier; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
  done
  image_ids_file=$(mktemp "$output_root/receipts/.${mode}-${arch}.images.XXXXXX")
  if ! timeout --foreground 60 docker inspect --format '{{.Image}}' "${container_ids[@]}" >"$image_ids_file" 2>>"$log"; then
    rm -f "$image_ids_file"
    write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "container image readback failed; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  mapfile -t image_ids < <(sort -u "$image_ids_file")
  rm -f "$image_ids_file"
  if (( ${#image_ids[@]} == 0 )); then
    write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "running containers returned no image identifiers; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  for image_id in "${image_ids[@]}"; do
    if [[ ! "$image_id" =~ ^sha256:[0-9a-fA-F]{64}$ ]]; then
      write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "Docker returned an invalid image identifier; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
  done
  image_arches_file=$(mktemp "$output_root/receipts/.${mode}-${arch}.image-arches.XXXXXX")
  if ! timeout --foreground 60 docker image inspect --format '{{.Os}}/{{.Architecture}}' "${image_ids[@]}" >"$image_arches_file" 2>>"$log"; then
    rm -f "$image_arches_file"
    write_receipt "$mode" "ARCHITECTURE_PROBE_FAILED" "Docker image architecture readback failed; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  image_arches_json=$(python3 - "$image_arches_file" <<'PY'
import json, sys
values=sorted(set(line.strip() for line in open(sys.argv[1], encoding="utf-8") if line.strip()))
print(json.dumps(values, separators=(",", ":")))
PY
  )
  architecture_match=$(EXPECTED_IMAGE_ARCH="$expected_image_arch" ARCHES_FILE="$image_arches_file" python3 - <<'PY'
import os
values={line.strip() for line in open(os.environ["ARCHES_FILE"], encoding="utf-8") if line.strip()}
print("true" if values == {os.environ["EXPECTED_IMAGE_ARCH"]} else "false")
PY
  )
  rm -f "$image_arches_file"
  IMAGE_ARCHES_JSON="$image_arches_json" ARCHITECTURE_MATCH="$architecture_match"
  if [[ "$architecture_match" != true ]]; then
    write_receipt "$mode" "ARCHITECTURE_MISMATCH" "running image architecture did not match native host; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  # Typed Core identity probe: this is a read-only JSON-RPC request and does
  # not print the owner credentials or response body.
  core_url=""
  core_user="$node_user"
  core_pass="$node_pass"
  case "$mode" in
    pool) core_url="$BDAG_RC2_POOL_CORE_ENDPOINT"; core_user="$pool_core_user"; core_pass="$pool_core_pass" ;;
    redis-dash) core_url="$BDAG_RC2_OBSERVER_NODE_URL"; core_user="$observer_user"; core_pass="$observer_pass" ;;
    *) core_url="http://127.0.0.1:38131/" ;;
  esac
  if ! MODE="$mode" CORE_URL="$core_url" CORE_USER="$core_user" CORE_PASS="$core_pass" RELEASE_RECORD="$release_record" python3 - <<'PY' >>"$log" 2>&1
import base64, json, os, urllib.request
record=json.load(open(os.environ["RELEASE_RECORD"], encoding="utf-8"))
expected=record["dataset"]["chain_identity"]
method="getBlockCount" if os.environ["MODE"]=="redis-dash" else "getChainIdentity"
body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":[]}, separators=(",", ":")).encode()
request=urllib.request.Request(os.environ["CORE_URL"], data=body, headers={"Content-Type":"application/json"})
token=base64.b64encode((os.environ["CORE_USER"]+":"+os.environ["CORE_PASS"]).encode()).decode()
request.add_header("Authorization", "Basic "+token)
with urllib.request.urlopen(request, timeout=5) as response:
    value=json.loads(response.read(65536))
actual=value.get("result")
if method=="getBlockCount":
    if value.get("error") is not None or not isinstance(actual, int):
        raise SystemExit("limited observer read failed")
elif actual != expected:
    raise SystemExit("Core getChainIdentity mismatch")
print("LIMITED_OBSERVER_READ_PASS" if method=="getBlockCount" else "CORE_IDENTITY_PASS")
PY
  then
    write_receipt "$mode" "CORE_IDENTITY_FAILED" "typed Core identity probe failed; private log retained at $log"
    timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
    exit 1
  fi
  if [[ "$mode" == pool || "$mode" == all-in-one ]]; then
    # The fresh Core is expected to be syncing.  Probe the typed template
    # health result directly and require both readiness signals to be false;
    # a merely unreachable node would not prove the pool's closed start gate.
    template_probe="$output_root/receipts/.${mode}-${arch}.template-health"
    if ! MODE="$mode" CORE_URL="$core_url" CORE_USER="$core_user" CORE_PASS="$core_pass" \
        python3 - >"$template_probe" 2>>"$log" <<'PY'
import base64, json, os, urllib.request
body=json.dumps({"jsonrpc":"2.0","id":1,"method":"getTemplateHealth","params":[]}, separators=(",", ":")).encode()
request=urllib.request.Request(os.environ["CORE_URL"], data=body, headers={"Content-Type":"application/json"})
token=base64.b64encode((os.environ["CORE_USER"]+":"+os.environ["CORE_PASS"]).encode()).decode()
request.add_header("Authorization", "Basic "+token)
with urllib.request.urlopen(request, timeout=5) as response:
    value=json.loads(response.read(65536))
if value.get("error") is not None or not isinstance(value.get("result"), dict):
    raise SystemExit("typed getTemplateHealth result missing")
result=value["result"]
ready=result.get("get_block_template_ready")
mineable=result.get("mineable_now")
if not isinstance(ready, bool) or not isinstance(mineable, bool):
    raise SystemExit("typed getTemplateHealth booleans missing")
print(("true" if ready else "false")+" "+("true" if mineable else "false"))
PY
    then
      rm -f "$template_probe"
      write_receipt "$mode" "TEMPLATE_HEALTH_FAILED" "typed syncing Core template-health probe failed; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
    read -r gate_template_ready gate_mineable <"$template_probe" || true
    rm -f "$template_probe"
    gate_template_ready=${gate_template_ready:-invalid}
    gate_mineable=${gate_mineable:-invalid}
    POOL_GATE_TEMPLATE_PROBED=true
    POOL_GATE_TEMPLATE_READY="$gate_template_ready"
    POOL_GATE_MINEABLE="$gate_mineable"
    if [[ "$gate_template_ready" != false || "$gate_mineable" != false ]]; then
      write_receipt "$mode" "TEMPLATE_HEALTH_NOT_SYNCING" "fresh Core template-health was not the expected closed gate; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
    # Poll only the selected pool service, bounded by a finite deadline.  The
    # exact supervisor line proves it is waiting on a typed syncing response,
    # rather than simply failing because the node cannot be reached.
    gate_logs=$(mktemp "$output_root/receipts/.${mode}-${arch}.pool-gate.XXXXXX")
    gate_deadline=$((SECONDS + ${BDAG_NATIVE_POOL_GATE_TIMEOUT_SECONDS:-120}))
    gate_seen=false
    while (( SECONDS < gate_deadline )); do
      : >"$gate_logs"
      timeout --foreground 15 docker compose --project-directory "$target/compose-context" \
        --project-name "$project" --env-file "$target/.env" -f "$target/compose.json" \
        logs --no-color --tail 200 pool >"$gate_logs" 2>>"$log" || true
      if grep -Eq '\[poolworker\] start gate: waiting on node: template_ready=false mineable=false reason_code=[^[:space:]]+ reason=.+$' "$gate_logs"; then
        gate_seen=true
        break
      fi
      sleep 2
    done
    rm -f "$gate_logs"
    if [[ "$gate_seen" != true ]]; then
      write_receipt "$mode" "POOL_START_GATE_FAILED" "poolworker sync start-gate log was not observed before the bounded deadline; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
    POOL_GATE_LOG_SEEN=true
  fi
  if [[ "$mode" == pool || "$mode" == all-in-one ]]; then
    if ! timeout --foreground 60 docker compose --project-directory "$target/compose-context" --project-name "$project" --env-file "$target/.env" -f "$target/compose.json" exec -T pool-db pg_isready >>"$log" 2>&1; then
      write_receipt "$mode" "POSTGRES_READINESS_FAILED" "PostgreSQL readiness probe failed; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
  fi
  if [[ "$mode" == redis-dash || "$mode" == all-in-one ]]; then
    if ! timeout --foreground 60 curl --fail --silent --show-error --retry 20 --retry-connrefused --retry-delay 1 --max-time 5 "http://127.0.0.1:${dashboard_port}/" >>"$log" 2>&1; then
      write_receipt "$mode" "DASHBOARD_HTTP_FAILED" "dashboard HTTP probe failed; private log retained at $log"
      timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1 || true
      exit 1
    fi
  fi
  write_receipt "$mode" "LIFECYCLE_PASS_READINESS_PENDING" "$readiness"
  if [[ "$mode" == node ]]; then
    # This already tested real node is outside the pool/dashboard projects.
    # Keep its one writer alive, then stop it before all-in-one uses port 38131.
    fixture_target="$target"
    BDAG_RC2_POOL_CORE_ENDPOINT=http://127.0.0.1:38131/
    BDAG_RC2_OBSERVER_NODE_URL=http://127.0.0.1:38131/
    BDAG_RC2_POOL_CORE_USER="$node_user"
    BDAG_RC2_POOL_CORE_PASS="$node_pass"
    BDAG_RC2_OBSERVER_USER="$limit_user"
    BDAG_RC2_OBSERVER_PASS="$limit_pass"
    current_target=""
    continue
  fi
  if ! timeout --foreground 120 python3 "$installer" stop --target "$target" >>"$log" 2>&1; then
    write_receipt "$mode" "STOP_FAILED" "installer stop failed; private log retained at $log"
    exit 1
  fi
done

python3 - "$output_root/receipts" "$output_root/native-summary-${arch}.json" "$arch" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
arch=sys.argv[3]
receipts=[json.loads(p.read_text()) for p in sorted(root.glob(f"*-{arch}.json"))]
Path(sys.argv[2]).write_text(json.dumps({"schema":"bdag.rc2.native-install-summary.v1", "platform":arch, "receipts":receipts}, sort_keys=True) + "\n")
print(json.dumps({"status":"PASS", "platform":arch, "modes":len(receipts)}, sort_keys=True))
PY
