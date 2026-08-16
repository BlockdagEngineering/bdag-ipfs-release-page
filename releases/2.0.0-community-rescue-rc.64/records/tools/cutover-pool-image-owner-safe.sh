#!/usr/bin/env bash
# Replace only the existing Stratum pool image. The ASIC endpoint, configured
# worker, payout address, node backend, and Postgres accounting stay unchanged.
set -Eeuo pipefail
umask 077
export LANG=C LC_ALL=C

[[ $# -eq 10 ]] || {
  echo "usage: $0 DOCKER_ARCHIVE ARCHIVE_SHA256 IMAGE_REF IMAGE_ID STACK_SHA POOL_SHA EXPECTED_MINERS EXPECTED_PAYOUT EVIDENCE_DIR DEADLINE_SECONDS" >&2
  exit 64
}

archive=$1
archive_sha=$2
image_ref=$3
expected_image_id=$4
stack_sha=$5
pool_sha=$6
expected_miners=$7
expected_payout=$8
evidence=$9
deadline_seconds=${10}

[[ $archive == /* && -f $archive && ! -L $archive ]]
[[ $archive_sha =~ ^[0-9a-f]{64}$ ]]
[[ $image_ref =~ ^[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+$ ]]
[[ $expected_image_id =~ ^sha256:[0-9a-f]{64}$ ]]
[[ $stack_sha =~ ^[0-9a-f]{40}$ && $pool_sha =~ ^[0-9a-f]{40}$ ]]
[[ $expected_miners =~ ^[0-9]+$ ]]
[[ $expected_payout =~ ^0x[0-9A-Fa-f]{40}$ ]]
[[ ${expected_payout,,} != 0x0000000000000000000000000000000000000000 ]]
[[ $evidence =~ ^/var/lib/blockdag-successor-rollouts/[A-Za-z0-9._-]+$ ]]
[[ ! -e $evidence && ! -L $evidence ]]
[[ $deadline_seconds =~ ^[1-9][0-9]*$ ]]
((deadline_seconds >= 60 && deadline_seconds <= 900))

[[ $(sha256sum "$archive" | awk '{print $1}') == "$archive_sha" ]]
archive_config_path=$(tar -xOf "$archive" manifest.json | jq -er --arg ref "$image_ref" '
  select(length==1 and .[0].RepoTags==[$ref]) |
  .[0].Config | select(test("^blobs/sha256/[0-9a-f]{64}$"))
')
archive_config_digest=${archive_config_path##*/}
archive_config_id=sha256:$archive_config_digest
[[ $(tar -xOf "$archive" "$archive_config_path" | sha256sum | awk '{print $1}') == "$archive_config_digest" ]]
archive_manifest_id=$(tar -xOf "$archive" index.json | jq -er '
  select((.manifests|length)==1) | .manifests[0].digest |
  select(test("^sha256:[0-9a-f]{64}$"))
')
[[ $archive_manifest_id == "$expected_image_id" ]]
docker load --input "$archive" >/dev/null
runtime_image_id=$(docker image inspect -f '{{.Id}}' "$image_ref")
[[ $runtime_image_id == "$archive_manifest_id" || $runtime_image_id == "$archive_config_id" ]]
[[ $(docker image inspect -f '{{.Architecture}}' "$image_ref") == amd64 ]]
[[ $(docker image inspect -f '{{index .Config.Labels "org.blockdag.recovery.stack-sha"}}' "$image_ref") == "$stack_sha" ]]
[[ $(docker image inspect -f '{{index .Config.Labels "org.blockdag.recovery.pool-sha"}}' "$image_ref") == "$pool_sha" ]]

for container in node pool postgres; do
  [[ $(docker inspect -f '{{.State.Running}} {{.State.OOMKilled}}' "$container") == 'true false' ]]
done
node_id=$(docker inspect -f '{{.Id}}' node)
postgres_id=$(docker inspect -f '{{.Id}}' postgres)
old_pool_image_id=$(docker inspect -f '{{.Image}}' pool)
old_pool_image_ref=$(docker inspect -f '{{.Config.Image}}' pool)
[[ $old_pool_image_id =~ ^sha256:[0-9a-f]{64}$ && $old_pool_image_id != "$runtime_image_id" ]]
[[ $old_pool_image_ref =~ ^[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+$ ]]
[[ $(docker image inspect -f '{{.Id}}' "$old_pool_image_ref") == "$old_pool_image_id" ]]

pool_inspect=$(docker inspect pool)
project=$(jq -er '.[0].Config.Labels["com.docker.compose.project"]' <<<"$pool_inspect")
workdir=$(jq -er '.[0].Config.Labels["com.docker.compose.project.working_dir"]' <<<"$pool_inspect")
envfile=$(jq -er '.[0].Config.Labels["com.docker.compose.project.environment_file"]' <<<"$pool_inspect")
compose_csv=$(jq -er '.[0].Config.Labels["com.docker.compose.project.config_files"]' <<<"$pool_inspect")
[[ $project =~ ^[A-Za-z0-9_.-]+$ && $workdir == /* && -d $workdir && ! -L $workdir ]]
[[ $envfile == /* && -f $envfile && ! -L $envfile ]]
IFS=, read -r -a compose_files <<<"$compose_csv"
((${#compose_files[@]} >= 1))
compose=(docker compose --project-directory "$workdir" --project-name "$project" --env-file "$envfile")
for file in "${compose_files[@]}"; do
  [[ $file == /* && -f $file && ! -L $file ]]
  compose+=( -f "$file" )
done

configured_payout=$(jq -er '
  [.[0].Config.Env[] |
    select(test("^(POOL_COINBASE_ADDRESS|MINING_POOL_ADDRESS|MINING_ADDRESS)=")) |
    sub("^[^=]+=";"") | select(test("^0x[0-9A-Fa-f]{40}$"))] |
  unique | select(length==1) | .[0]
' <<<"$pool_inspect")
[[ ${configured_payout,,} == "${expected_payout,,}" ]]

pool_metrics() {
  curl -fsS --max-time 10 http://127.0.0.1:9090/metrics | awk '
    $1=="pool_active_connections{pool_id=\"0\"}" {active=$2; a=1}
    $1=="pool_job_health_authorized_miners{pool_id=\"0\"}" {authorized=$2; b=1}
    $1=="pool_job_health_physical_miners{pool_id=\"0\"}" {physical=$2; c=1}
    $1=="pool_job_health_ready_physical_miners{pool_id=\"0\"}" {ready=$2; d=1}
    $1=="pool_shares_accepted_total{pool_id=\"0\"}" {shares=$2; e=1}
    $1=="pool_block_submit_outcomes_total{outcome=\"accepted\",pool_id=\"0\",reason=\"ok\"}" {submissions=$2}
    END {
      if (!(a&&b&&c&&d&&e)) exit 1
      printf "{\"active\":%d,\"authorized\":%d,\"physical\":%d,\"ready\":%d,\"shares\":%d,\"submissions\":%d}\n", active,authorized,physical,ready,shares,submissions
    }'
}

pool_jobs() {
  curl -fsS --max-time 10 http://127.0.0.1:9090/health/job-state
}

active_macs() {
  jq -c '[.clients[]? |
    select(.authorized==true and (.asic_mac|strings|length)>0) |
    (.asic_mac|ascii_downcase)] | unique | sort' <<<"$1"
}

validate_predecessor_owner() {
  local jobs=$1 metrics=$2 registry=$3 macs
  if ((expected_miners == 0)); then
    jq -e '.active==0 and .authorized==0 and .physical==0 and (.shares|numbers)' <<<"$metrics" >/dev/null
    [[ $(active_macs "$jobs") == '[]' ]]
    return
  fi
  jq -e --argjson miners "$expected_miners" '
    .active >= $miners and .authorized >= $miners and .physical >= $miners and
    (.shares|numbers)
  ' <<<"$metrics" >/dev/null
  macs=$(active_macs "$jobs")
  jq -e --argjson miners "$expected_miners" 'length >= $miners' <<<"$macs" >/dev/null
  jq -e --arg payout "${expected_payout,,}" --argjson macs "$macs" '
    . as $registry |
    all($macs[]; . as $mac |
      any($registry.miners[]?;
        ((.mac // "" | ascii_downcase) == $mac) and
        ((.expected_worker_user // "" | ascii_downcase) == $payout) and
        ([.last_workers[]? | ascii_downcase] | unique) == [$payout]))
  ' "$registry" >/dev/null
}

validate_successor_owner() {
  local jobs=$1 metrics=$2 before_macs=$3
  if ((expected_miners == 0)); then
    jq -e '
      (.status=="ok" or .status=="idle" or .status=="degraded") and
      .reason_code=="no_active_miners" and
      .active_connections==0 and .authorized_connections==0 and
      .physical_miners==0 and .ready_physical_miners==0 and
      ([.clients[]?|select(.authorized==true)]|length)==0
    ' <<<"$jobs" >/dev/null
    jq -e '.active==0 and .authorized==0 and .physical==0 and .ready==0 and (.shares|numbers)' <<<"$metrics" >/dev/null
    [[ $before_macs == '[]' && $(active_macs "$jobs") == '[]' ]]
    return
  fi
  jq -e --arg payout "${expected_payout,,}" --argjson miners "$expected_miners" '
    .status=="ok" and .reason_code=="ok" and
    (.current_template_seq|numbers)>0 and (.current_parent|strings|length)>0 and
    .active_connections >= $miners and .authorized_connections >= $miners and
    .physical_miners >= $miners and .ready_physical_miners >= $miners and
    ([.clients[]? |
      select(.authorized==true and .ready==true and (.current_job_id|strings|length)>0) |
      (.asic_mac|ascii_downcase)] | unique | length) >= $miners and
    all(.clients[]? |
      select(.authorized==true and .ready==true and (.current_job_id|strings|length)>0);
      ((.authorized_worker // "" | ascii_downcase) == $payout))
  ' <<<"$jobs" >/dev/null
  jq -e --argjson miners "$expected_miners" '
    .active >= $miners and .authorized >= $miners and .physical >= $miners and
    .ready >= $miners and (.shares|numbers)
  ' <<<"$metrics" >/dev/null
  [[ $(active_macs "$jobs") == "$before_macs" ]]
}

pool_runtime_spec() {
  docker inspect pool | jq -ce '.[0] | {
    env:([.Config.Env[]?] | sort), cmd:.Config.Cmd,
    user:.Config.User, workingDir:.Config.WorkingDir, healthcheck:.Config.Healthcheck,
    exposedPorts:((.Config.ExposedPorts // {})|keys|sort),
    hostConfig:{networkMode:.HostConfig.NetworkMode,portBindings:.HostConfig.PortBindings,
      restartPolicy:.HostConfig.RestartPolicy,readonlyRootfs:.HostConfig.ReadonlyRootfs,
      privileged:.HostConfig.Privileged,capAdd:.HostConfig.CapAdd,capDrop:.HostConfig.CapDrop,
      securityOpt:.HostConfig.SecurityOpt,usernsMode:.HostConfig.UsernsMode,
      ipcMode:.HostConfig.IpcMode,pidMode:.HostConfig.PidMode,extraHosts:.HostConfig.ExtraHosts,
      devices:.HostConfig.Devices,deviceRequests:.HostConfig.DeviceRequests},
    mounts:([.Mounts[]? | {type:.Type,source:.Source,destination:.Destination,rw:.RW,
      propagation:.Propagation,name:(.Name//""),driver:(.Driver//"")}] | sort_by(.destination,.source)),
    networks:((.NetworkSettings.Networks//{})|to_entries|
      map({name:.key,aliases:((.value.Aliases//[])|sort)})|sort_by(.name))
  }'
}

successor_entrypoint_is_expected() {
  [[ $(docker inspect -f '{{json .Config.Entrypoint}}' pool 2>/dev/null) == \
    '["/usr/local/bin/docker-entrypoint-pool.sh","/usr/local/bin/mining-pool"]' ]]
}

container_env_value() {
  local key=$1
  jq -er --arg prefix "$key=" '
    [.[0].Config.Env[]? | select(startswith($prefix)) | ltrimstr($prefix)] |
    unique | select(length==1) | .[0]
  ' <<<"$pool_inspect"
}

bind_host_path() {
  local container_path=$1
  jq -er --arg path "$container_path" '
    [.[0].Mounts[]? |
      select(.Type=="bind") |
      . as $mount |
      select($path == $mount.Destination or ($path | startswith($mount.Destination + "/"))) |
      {source:.Source,destination:.Destination,rw:.RW}] |
    sort_by(.destination | length) | last |
    select(.rw==false) | . as $mount |
    $mount.source + ($path | ltrimstr($mount.destination))
  ' <<<"$pool_inspect"
}

issue_release_cutover_lease() {
  local mode=${1:-initial} now expires temporary lease_uid lease_gid lease_dir reason
  [[ $mode == initial || $mode == refresh ]]
  [[ $lease_host_path == /* && -f $lease_host_path && ! -L $lease_host_path ]]
  [[ $control_host_path == /* && -f $control_host_path && ! -L $control_host_path ]]
  [[ $(realpath -e -- "$lease_host_path") == "$lease_host_path" ]]
  [[ $(realpath -e -- "$control_host_path") == "$control_host_path" ]]
  lease_dir=$(dirname "$lease_host_path")
  [[ $lease_dir == "$(dirname "$control_host_path")" ]]
  [[ -d $lease_dir && ! -L $lease_dir ]]
  [[ $(realpath -e -- "$lease_dir") == "$lease_dir" ]]
  [[ $(jq -er '.state' "$control_host_path") == normal ]]
  [[ $(jq -er '.high_risk_controller' "$control_host_path") == watchdog ]]
  lease_uid=$(stat -c %u "$lease_host_path")
  lease_gid=$(stat -c %g "$lease_host_path")
  [[ $lease_uid =~ ^[0-9]+$ && $lease_gid =~ ^[0-9]+$ ]]
  now=$(date +%s)
  expires=$((now+lease_ttl_seconds))
  if [[ $mode == initial ]]; then
    install -m 0600 "$lease_host_path" "$evidence/pool-start-lease.before"
    reason=rc64-owner-safe-cutover
  else
    reason=rc64-owner-safe-cutover-active-refresh
  fi
  temporary=$lease_dir/.pool-start-lease.${BASHPID}.tmp
  [[ ! -e $temporary && ! -L $temporary ]]
  trap 'rm -f -- "$temporary"' RETURN
  printf 'BDAG_POOL_START_LEASE_EPOCH=%s\nBDAG_POOL_START_LEASE_EXPIRES=%s\nBDAG_POOL_START_LEASE_ACTOR=release-controller\nBDAG_POOL_START_LEASE_REASON=%s\n' \
    "$now" "$expires" "$reason" >"$temporary"
  chown "$lease_uid:$lease_gid" "$temporary"
  chmod 0644 "$temporary"
  sync -d "$temporary"
  mv -T -- "$temporary" "$lease_host_path"
  sync -d "$lease_host_path" "$lease_dir"
  trap - RETURN
  if [[ $mode == initial ]]; then
    printf 'actor=release-controller\nepoch=%s\nexpires=%s\nttlSeconds=%s\ncontrolState=normal\nhighRiskController=watchdog\n' \
      "$now" "$expires" "$lease_ttl_seconds" >"$evidence/pool-start-lease.receipt"
  else
    printf 'actor=release-controller epoch=%s expires=%s reason=active-exact-cutover-refresh\n' \
      "$now" "$expires" >>"$evidence/pool-start-lease-refresh.log"
    chmod 0600 "$evidence/pool-start-lease-refresh.log"
  fi
}

lease_refresh_pid=
start_release_cutover_lease_refresher() {
  local interval=$((lease_ttl_seconds/3)) cutover_pid=$BASHPID
  ((interval < 20)) && interval=20
  (
    while sleep "$interval"; do
      kill -0 "$cutover_pid" 2>/dev/null || exit 0
      issue_release_cutover_lease refresh
    done
  ) &
  lease_refresh_pid=$!
}

stop_release_cutover_lease_refresher() {
  [[ -n ${lease_refresh_pid:-} ]] || return 0
  if kill -0 "$lease_refresh_pid" 2>/dev/null; then
    kill "$lease_refresh_pid" 2>/dev/null || true
    wait "$lease_refresh_pid" 2>/dev/null || true
  fi
  lease_refresh_pid=
}

before_jobs=$(pool_jobs)
before_metrics=$(pool_metrics)
miner_registry=$workdir/ops/runtime/miners.json
[[ -f $miner_registry && ! -L $miner_registry ]]
validate_predecessor_owner "$before_jobs" "$before_metrics" "$miner_registry"
before_macs=$(active_macs "$before_jobs")
before_spec=$(pool_runtime_spec)
before_shares=$(jq -er '.shares' <<<"$before_metrics")
before_ready=$(jq -er '.ready' <<<"$before_metrics")
lease_container_path=$(container_env_value BDAG_POOL_START_LEASE_FILE)
control_container_path=$(container_env_value BDAG_AUTOMATION_CONTROL_FILE)
lease_max_age=$(container_env_value BDAG_POOL_START_LEASE_MAX_AGE_SECONDS)
[[ $lease_container_path == /var/lib/bdagStack/runtime/pool-start-lease.env ]]
[[ $control_container_path == /var/lib/bdagStack/runtime/automation-control.json ]]
[[ $lease_max_age =~ ^[1-9][0-9]*$ ]]
((lease_max_age >= 30 && lease_max_age <= 900))
lease_ttl_seconds=$lease_max_age
((lease_ttl_seconds > 120)) && lease_ttl_seconds=120
lease_host_path=$(bind_host_path "$lease_container_path")
control_host_path=$(bind_host_path "$control_container_path")

install -d -m 0700 "$evidence"
override=$evidence/pool-image.override.yml
printf 'services:\n  pool:\n    image: "%s"\n' "$image_ref" >"$override"
chmod 0600 "$override"
printf '%s\n' "$before_jobs" >"$evidence/pool-job-state-before.json"
printf '%s\n' "$before_metrics" >"$evidence/pool-metrics-before.json"
printf '%s\n' "$before_spec" >"$evidence/pool-runtime-spec-before.json"
docker inspect -f '{{json .Config.Entrypoint}}' pool >"$evidence/pool-entrypoint-before.json"
docker inspect node pool postgres >"$evidence/containers-before.json"
printf 'status=running\nstartedAt=%s\noldPoolImage=%s\nnewPoolImage=%s\narchiveManifestImage=%s\narchiveConfigImage=%s\npayoutAddress=%s\npayoutIdentityProof=mac-keyed-registry-before-and-live-authorized-worker-after\npayoutConfigProof=running-pool-container-env\nasicConfigurationChanged=false\nstratumEndpointChanged=false\nnodeBackendChanged=false\npostgresRetained=true\nexpectedMiners=%s\n' \
  "$(date -u +%FT%TZ)" "$old_pool_image_id" "$runtime_image_id" "$archive_manifest_id" "$archive_config_id" \
  "$configured_payout" "$expected_miners" >"$evidence/intent.receipt"
issue_release_cutover_lease

write_sums() {
  : >"$evidence/SHA256SUMS"
  local file
  for file in "$evidence"/*; do
    [[ -f $file && $file != "$evidence/SHA256SUMS" ]] || continue
    sha256sum "$file" >>"$evidence/SHA256SUMS"
  done
  sha256sum -c "$evidence/SHA256SUMS" >/dev/null
}

cutover_started=$(date -u +%s)
rollback() {
  local rc=${1:-$?}
  trap - ERR HUP INT TERM
  set +e
  stop_release_cutover_lease_refresher
  local status=rollback-failed first=-1 last=-1 restored_samples=0 deadline jobs metrics current_macs
  "${compose[@]}" up -d --no-deps --force-recreate --no-build --pull never pool
  deadline=$((SECONDS+deadline_seconds))
  while ((SECONDS < deadline)); do
    jobs=$(pool_jobs 2>/dev/null)
    metrics=$(pool_metrics 2>/dev/null)
    current_macs=$(active_macs "$jobs" 2>/dev/null)
    if [[ $(docker inspect -f '{{.Image}} {{.State.Running}} {{.State.OOMKilled}}' pool 2>/dev/null) == "$old_pool_image_id true false" ]] \
      && [[ $(docker inspect -f '{{.Id}}' node 2>/dev/null) == "$node_id" ]] \
      && [[ $(docker inspect -f '{{.Id}}' postgres 2>/dev/null) == "$postgres_id" ]] \
      && [[ $current_macs == "$before_macs" ]] \
      && validate_predecessor_owner "$jobs" "$metrics" "$miner_registry"; then
      last=$(jq -er '.shares' <<<"$metrics")
      ((first<0)) && first=$last
      ((restored_samples+=1))
      if ((expected_miners==0 || last>first)); then
        status=rolled-back
        break
      fi
      if ((restored_samples>=2 && before_ready<expected_miners)); then
        status=rolled-back-to-predecessor-state
        break
      fi
    fi
    sleep 5
  done
  printf 'status=%s\nfinishedAt=%s\nexitStatus=%s\noldPoolImage=%s\nnewPoolImage=%s\narchiveManifestImage=%s\narchiveConfigImage=%s\npayoutAddress=%s\nasicConfigurationChanged=false\nstratumEndpointChanged=false\npreCutoverReady=%s\nrollbackReady=%s\nrollbackShareDelta=%s\n' \
    "$status" "$(date -u +%FT%TZ)" "$rc" "$old_pool_image_id" "$runtime_image_id" \
    "$archive_manifest_id" "$archive_config_id" "$configured_payout" "$before_ready" \
    "$(jq -r '.ready // -1' <<<"$metrics" 2>/dev/null)" "$((last-first))" >"$evidence/result.receipt"
  write_sums || status=rollback-failed
  [[ $status == rolled-back || $status == rolled-back-to-predecessor-state ]] || rc=79
  exit "$rc"
}
phase=pre-cutover
failure_context() {
  local rc=$1 line=$2 command=$3
  trap - ERR
  command=${command//$'\n'/ }
  command=${command:0:500}
  printf 'phase=%s\nline=%s\nexitStatus=%s\ncommand=%s\n' \
    "$phase" "$line" "$rc" "$command" >"$evidence/failure-context.receipt"
  rollback "$rc"
}
trap 'failure_context "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap 'rollback 129' HUP
trap 'rollback 130' INT
trap 'rollback 143' TERM

successor_compose=("${compose[@]}" -f "$override")
phase=pool-recreate
start_release_cutover_lease_refresher
"${successor_compose[@]}" up -d --no-deps --force-recreate --no-build --pull never pool
stop_release_cutover_lease_refresher

phase=post-restart-acceptance
deadline=$((SECONDS+deadline_seconds))
valid=0
first_after=-1
last_after=-1
after_jobs=
after_metrics=
while ((SECONDS < deadline)); do
  jobs=$(pool_jobs 2>/dev/null || true)
  metrics=$(pool_metrics 2>/dev/null || true)
  current_pool_state=$(docker inspect -f '{{.Image}} {{.State.Running}} {{.State.OOMKilled}} {{.RestartCount}}' pool 2>/dev/null || true)
  current_node_id=$(docker inspect -f '{{.Id}}' node 2>/dev/null || true)
  current_postgres_id=$(docker inspect -f '{{.Id}}' postgres 2>/dev/null || true)
  current_spec=$(pool_runtime_spec 2>/dev/null || true)
  if [[ $current_pool_state == "$runtime_image_id true false 0" ]] \
    && [[ $current_node_id == "$node_id" ]] \
    && [[ $current_postgres_id == "$postgres_id" ]] \
    && [[ $current_spec == "$before_spec" ]] \
    && successor_entrypoint_is_expected \
    && validate_successor_owner "$jobs" "$metrics" "$before_macs"; then
    shares=$(jq -er '.shares' <<<"$metrics")
    ((first_after<0)) && first_after=$shares
    last_after=$shares
    after_jobs=$jobs
    after_metrics=$metrics
    ((valid+=1))
    ((valid>=2 && (expected_miners==0 || last_after>first_after))) && break
  fi
  sleep 5
done

((valid>=2 && (expected_miners==0 || last_after>first_after)))
[[ $(docker inspect -f '{{.Id}}' node) == "$node_id" ]]
[[ $(docker inspect -f '{{.Id}}' postgres) == "$postgres_id" ]]
[[ $(docker inspect -f '{{.Image}}' pool) == "$runtime_image_id" ]]
[[ $(pool_runtime_spec) == "$before_spec" ]]
successor_entrypoint_is_expected
validate_successor_owner "$after_jobs" "$after_metrics" "$before_macs"

printf '%s\n' "$after_jobs" >"$evidence/pool-job-state-after.json"
printf '%s\n' "$after_metrics" >"$evidence/pool-metrics-after.json"
pool_runtime_spec >"$evidence/pool-runtime-spec-after.json"
docker inspect -f '{{json .Config.Entrypoint}}' pool >"$evidence/pool-entrypoint-after.json"
docker inspect node pool postgres >"$evidence/containers-after.json"
printf 'status=passed\nfinishedAt=%s\noldPoolImage=%s\nnewPoolImage=%s\narchiveManifestImage=%s\narchiveConfigImage=%s\nstackSha=%s\npoolSha=%s\npayoutAddress=%s\npayoutIdentityProof=mac-keyed-current-authorized-stratum-worker\npayoutConfigProof=running-pool-container-env\nasicConfigurationChanged=false\nstratumEndpointChanged=false\nnodeBackendChanged=false\nexpectedMiners=%s\npreCutoverShareCounter=%s\npostRestartShareDelta=%s\ncutoverSeconds=%s\npredecessorImageRetained=true\npostgresRetained=true\n' \
  "$(date -u +%FT%TZ)" "$old_pool_image_id" "$runtime_image_id" "$archive_manifest_id" "$archive_config_id" "$stack_sha" "$pool_sha" \
  "$configured_payout" "$expected_miners" "$before_shares" "$((last_after-first_after))" \
  "$(($(date -u +%s)-cutover_started))" >"$evidence/result.receipt"
write_sums
trap - ERR HUP INT TERM
cat "$evidence/result.receipt"
