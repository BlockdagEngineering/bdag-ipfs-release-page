const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const CHAIN_HASH_PATTERN = /^0x[0-9a-f]{64}$/;
const CID_PATTERN = /^b[a-z2-7]{20,}$/;
const COMMIT_PATTERN = /^[0-9a-f]{40}$/;
const WALLET_PATTERN = /^0x[0-9a-fA-F]{40}$/;
const MAC_PATTERN = /^[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}$/;
const SAFE_FILENAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._+-]*$/;

export function isSha256(value) {
  return typeof value === "string" && SHA256_PATTERN.test(value);
}

export function isCid(value) {
  return typeof value === "string" && CID_PATTERN.test(value);
}

export function isPositiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

export function isSafeFilename(value) {
  return typeof value === "string" && SAFE_FILENAME_PATTERN.test(value);
}

export function isSafeRelativePath(value) {
  if (typeof value !== "string" || value.length === 0 || value.startsWith("/") || value.includes("\\")) {
    return false;
  }
  return value.split("/").every((part) => part !== "." && part !== ".." && SAFE_FILENAME_PATTERN.test(part));
}

export function isWallet(value) {
  return WALLET_PATTERN.test(value);
}

export function isMacList(value) {
  const entries = value.split(",").map((entry) => entry.trim()).filter(Boolean);
  return entries.length > 0 && entries.every((entry) => MAC_PATTERN.test(entry));
}

export function normalizeMacList(value) {
  return value.split(",").map((entry) => entry.trim().toLowerCase()).filter(Boolean).join(",");
}

export function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

export function formatBytes(value) {
  if (!isPositiveInteger(value)) {
    return "Pending";
  }
  const units = ["bytes", "KiB", "MiB", "GiB", "TiB"];
  let amount = value;
  let unitIndex = 0;
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024;
    unitIndex += 1;
  }
  const display = unitIndex === 0 ? amount.toLocaleString("en-US") : amount.toFixed(2);
  return `${display} ${units[unitIndex]} (${value.toLocaleString("en-US")} bytes)`;
}

export function shortValue(value) {
  if (typeof value !== "string" || value.length < 24) {
    return value || "Pending";
  }
  return `${value.slice(0, 12)}...${value.slice(-10)}`;
}

export function gatewayUrl(template, cid) {
  if (!isCid(cid) || typeof template !== "string" || !template.includes("{cid}")) {
    return null;
  }
  try {
    const candidate = new URL(template.replace("{cid}", cid));
    return candidate.protocol === "https:" ? candidate.href : null;
  } catch {
    return null;
  }
}

export function gatewayTemplatesReady(templates) {
  if (!Array.isArray(templates) || templates.length < 2) {
    return false;
  }
  return templates.every((template) => {
    if (
      typeof template !== "string" ||
      template.split("{cid}").length !== 2 ||
      /[\\`"$\r\n]/.test(template)
    ) {
      return false;
    }
    try {
      return new URL(template.replace("{cid}", "cid-placeholder")).protocol === "https:";
    } catch {
      return false;
    }
  });
}

export function isHttpsUrl(value) {
  if (typeof value !== "string") {
    return false;
  }
  try {
    const candidate = new URL(value);
    return candidate.protocol === "https:" && Boolean(candidate.hostname) && !candidate.username && !candidate.password;
  } catch {
    return false;
  }
}

export function boundaryReady(value, native = false) {
  if (!value || typeof value !== "object") {
    return false;
  }
  const numberKey = native ? "order" : "number";
  const keys = native ? [numberKey, "hash"] : [numberKey, "hash", "state_root"];
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key)) &&
    Number.isSafeInteger(value[numberKey]) &&
    value[numberKey] >= 0 &&
    CHAIN_HASH_PATTERN.test(value.hash) &&
    (native || CHAIN_HASH_PATTERN.test(value.state_root))
  );
}

export function artifactReady(artifact) {
  return Boolean(
    artifact &&
    artifact.status === "published" &&
    isSafeFilename(artifact.filename) &&
    isCid(artifact.cid) &&
    isSha256(artifact.sha256) &&
    isPositiveInteger(artifact.size_bytes)
  );
}

export function artifactIdentityReady(artifact) {
  return Boolean(
    artifact &&
    ["signed-pending-cid", "published"].includes(artifact.status) &&
    isSafeFilename(artifact.filename) &&
    isSha256(artifact.sha256) &&
    isPositiveInteger(artifact.size_bytes)
  );
}

export function partReady(part) {
  return Boolean(
    part &&
    isSafeFilename(part.filename) &&
    isCid(part.cid) &&
    isSha256(part.sha256) &&
    isPositiveInteger(part.size_bytes)
  );
}

export function deliveryReady(delivery) {
  if (!delivery || typeof delivery !== "object") {
    return false;
  }
  if (delivery.mode === "direct") {
    return isCid(delivery.cid) && (!Array.isArray(delivery.parts) || delivery.parts.length === 0);
  }
  if (delivery.mode === "multipart") {
    const validParts = (
      delivery.cid === null &&
      isSafeRelativePath(delivery.parts_manifest_path) &&
      Array.isArray(delivery.parts) &&
      delivery.parts.length > 1 &&
      delivery.parts.every(partReady)
    );
    if (!validParts) {
      return false;
    }
    return (
      new Set(delivery.parts.map((part) => part.filename)).size === delivery.parts.length &&
      new Set(delivery.parts.map((part) => part.cid)).size === delivery.parts.length
    );
  }
  return false;
}

export function datasetReady(dataset) {
  return Boolean(
    dataset &&
    dataset.status === "published" &&
    typeof dataset.archive_node_equivalent === "boolean" &&
    typeof dataset.version === "string" &&
    dataset.version.length > 0 &&
    isSafeFilename(dataset.filename) &&
    isSha256(dataset.sha256) &&
    isPositiveInteger(dataset.size_bytes) &&
    isPositiveInteger(dataset.unpacked_size_bytes) &&
    deliveryReady(dataset.delivery) &&
    isSafeRelativePath(dataset.canonical_manifest_path) &&
    isSha256(dataset.canonical_manifest_sha256) &&
    isSafeRelativePath(dataset.validation_spec_path) &&
    boundaryReady(dataset.native_boundary, true) &&
    boundaryReady(dataset.evm_boundary) &&
    boundaryReady(dataset.fixed_checkpoint) &&
    (dataset.delivery.mode !== "multipart" || dataset.delivery.parts.reduce((total, part) => total + part.size_bytes, 0) === dataset.size_bytes)
  );
}

export function datasetIdentityReady(dataset) {
  return Boolean(
    dataset &&
    ["qualified-pending-cid", "published"].includes(dataset.status) &&
    typeof dataset.archive_node_equivalent === "boolean" &&
    typeof dataset.version === "string" &&
    dataset.version.length > 0 &&
    isSafeFilename(dataset.filename) &&
    isSha256(dataset.sha256) &&
    isPositiveInteger(dataset.size_bytes) &&
    isPositiveInteger(dataset.unpacked_size_bytes) &&
    isSafeRelativePath(dataset.canonical_manifest_path) &&
    isSha256(dataset.canonical_manifest_sha256) &&
    isSafeRelativePath(dataset.validation_spec_path) &&
    boundaryReady(dataset.native_boundary, true) &&
    boundaryReady(dataset.evm_boundary) &&
    boundaryReady(dataset.fixed_checkpoint)
  );
}

export function datasetPending(dataset, archiveNodeEquivalent) {
  if (!dataset || dataset.status !== "pending" || dataset.archive_node_equivalent !== archiveNodeEquivalent) {
    return false;
  }
  const nullableFields = [
    "version",
    "filename",
    "sha256",
    "size_bytes",
    "unpacked_size_bytes",
    "canonical_manifest_path",
    "canonical_manifest_sha256",
    "validation_spec_path",
    "native_boundary",
    "evm_boundary",
    "fixed_checkpoint",
  ];
  return (
    nullableFields.every((key) => dataset[key] === null) &&
    (!archiveNodeEquivalent || dataset.archive_audit === null) &&
    dataset.delivery?.mode === null &&
    dataset.delivery?.cid === null &&
    dataset.delivery?.parts_manifest_path === null &&
    Array.isArray(dataset.delivery?.parts) &&
    dataset.delivery.parts.length === 0
  );
}

export function fullArchivePending(dataset) {
  return datasetPending(dataset, true);
}

export function publicationReady(manifest) {
  if (!manifest || manifest.release?.status !== "published" || manifest.qualification?.status !== "passed") {
    return false;
  }
  const software = manifest.software?.targets || {};
  const datasets = manifest.datasets || {};
  const source = manifest.source || {};
  const records = manifest.software?.records || {};
  const qualification = manifest.qualification || {};
  const portableAvailable = datasetReady(datasets.portable);
  const archiveAvailable = datasetReady(datasets.full_archive);
  const datasetTrustReady = portableAvailable || archiveAvailable
    ? (
        isSha256(manifest.trust?.dataset_key_sha256) &&
        isSafeRelativePath(manifest.trust?.dataset_key_path) &&
        isSafeFilename(manifest.trust?.dataset_key_id)
      )
    : (
        manifest.trust?.dataset_key_sha256 === null &&
        manifest.trust?.dataset_key_path === null &&
        manifest.trust?.dataset_key_id === null
      );
  return Boolean(
    isSafeFilename(manifest.release.version) &&
    isPositiveInteger(manifest.release.sequence) &&
    manifest.release.chain_id === 1404 &&
    manifest.runtime_change?.transient_startup_canonical_boundary_rpc === "bounded-retry" &&
    manifest.runtime_change?.transient_startup_peer_readiness === "bounded-retry" &&
    manifest.runtime_change?.canonical_mismatch === "fail-immediately" &&
    typeof manifest.release.published_at === "string" &&
    !Number.isNaN(Date.parse(manifest.release.published_at)) &&
    isHttpsUrl(source.release_url) &&
    source.tag === manifest.release.version &&
    [source.stack_commit, source.corechain_commit, source.pool_commit, source.dashboard_commit].every((value) => COMMIT_PATTERN.test(value)) &&
    isSha256(source.source_lock_sha256) &&
    manifest.software.independent_from_datasets === true &&
    datasets.independent_from_software === true &&
    artifactReady(manifest.installer) &&
    artifactReady(software["linux-amd64"]) &&
    artifactReady(software["linux-arm64"]) &&
    (datasetPending(datasets.portable, false) || (
      portableAvailable &&
      datasets.portable.archive_node_equivalent === false
    )) &&
    (fullArchivePending(datasets.full_archive) || (
      archiveAvailable &&
      datasets.full_archive.archive_node_equivalent === true &&
      datasets.full_archive.archive_audit?.status === "passed"
    )) &&
    gatewayTemplatesReady(manifest.download_policy?.ipfs_gateways) &&
    manifest.download_policy?.requires_ipv4 === true &&
    manifest.download_policy?.requires_http_version === "HTTP/1.1" &&
    manifest.download_policy?.software_http_fallback_base === null &&
    manifest.records_delivery?.mode === "ipfs-directory" &&
    isCid(manifest.records_delivery?.cid) &&
    manifest.records_delivery?.path_prefix === "records/" &&
    isSha256(manifest.trust?.release_key_sha256) &&
    isSafeRelativePath(manifest.trust?.release_key_path) &&
    isSafeRelativePath(manifest.trust?.dataset_verifier_path) &&
    datasetTrustReady &&
    [records.release_auth_manifest_path, records.release_auth_signature_path, records.release_notes_path].every(isSafeRelativePath) &&
    qualification.signed_package_integrity_verified === true &&
    qualification.portable_dataset_verified === portableAvailable &&
    qualification.full_archive_dataset_verified === archiveAvailable &&
    qualification.restore_path_verified === true &&
    qualification.runtime_path_verified === true
  );
}

function resolvedRecordUrl(path, pageUrl) {
  if (!isSafeRelativePath(path)) {
    return null;
  }
  try {
    const candidate = new URL(path, pageUrl);
    const octets = candidate.hostname.split(".").map((part) => Number.parseInt(part, 10));
    const ipv4Loopback = octets.length === 4 && octets.every(Number.isInteger) && octets[0] === 127;
    const loopbackHttp = (
      candidate.protocol === "http:" &&
      (candidate.hostname === "localhost" || candidate.hostname === "[::1]" || ipv4Loopback)
    );
    return candidate.protocol === "https:" || loopbackHttp ? candidate.href : null;
  } catch {
    return null;
  }
}

function basename(path) {
  return path.split("/").at(-1);
}

function downloadFunction(gatewayTemplates) {
  const urls = gatewayTemplates.map((template) => {
    const interpolated = template.replace("{cid}", "${_cid}");
    return `    "${interpolated}" \\`;
  });
  urls[urls.length - 1] = urls.at(-1).replace(/ \\$/, "");
  const pathUrls = gatewayTemplates.map((template) => {
    const interpolated = template.replace("{cid}", "${_cid}").replace(/\/+$/, "");
    return `    "${interpolated}/\${_path}" \\`;
  });
  pathUrls[pathUrls.length - 1] = pathUrls.at(-1).replace(/ \\$/, "");
  return [
    "download_ipfs() {",
    "  _cid=$1",
    "  _output=$2",
    "  for _url in \\",
    ...urls,
    "  do",
    "    if curl -4 --http1.1 --fail --location --show-error \\",
    "      --connect-timeout 20 --retry 12 --retry-delay 3 --retry-all-errors \\",
    "      --speed-limit 1024 --speed-time 90 -C - -o \"$_output\" \"$_url\"; then",
    "      return 0",
    "    fi",
    "  done",
    "  return 1",
    "}",
    "",
    "download_ipfs_path() {",
    "  _cid=$1",
    "  _path=$2",
    "  _output=$3",
    "  for _url in \\",
    ...pathUrls,
    "  do",
    "    if curl -4 --http1.1 --fail --location --show-error \\",
    "      --connect-timeout 20 --retry 12 --retry-delay 3 --retry-all-errors \\",
    "      --speed-limit 1024 --speed-time 90 -C - -o \"$_output\" \"$_url\"; then",
    "      return 0",
    "    fi",
    "  done",
    "  return 1",
    "}",
  ];
}

function directArtifactLines(artifact, variableName) {
  return [
    `${variableName}=${shellQuote(artifact.filename)}`,
    `download_ipfs ${shellQuote(artifact.cid)} \"$${variableName}.part\"`,
    `printf '%s  %s\\n' ${shellQuote(artifact.sha256)} \"$${variableName}.part\" | sha256sum -c -`,
    `mv \"$${variableName}.part\" \"$${variableName}\"`,
  ];
}

function softwareSelectionLines(manifest) {
  const amd64 = manifest.software.targets["linux-amd64"];
  const arm64 = manifest.software.targets["linux-arm64"];
  const unsupportedMessage = `Unsupported CPU architecture; ${manifest.release.version} supports AMD64 and ARM64 Linux.`;
  return [
    'case "$(uname -m)" in',
    "  x86_64|amd64)",
    "    PACKAGE=" + shellQuote(amd64.filename),
    "    PACKAGE_CID=" + shellQuote(amd64.cid),
    "    PACKAGE_SHA256=" + shellQuote(amd64.sha256),
    "    PACKAGE_SIZE=" + shellQuote(String(amd64.size_bytes)),
    "    ;;",
    "  arm64|aarch64)",
    "    PACKAGE=" + shellQuote(arm64.filename),
    "    PACKAGE_CID=" + shellQuote(arm64.cid),
    "    PACKAGE_SHA256=" + shellQuote(arm64.sha256),
    "    PACKAGE_SIZE=" + shellQuote(String(arm64.size_bytes)),
    "    ;;",
    `  *) echo ${shellQuote(unsupportedMessage)} >&2; exit 1 ;;`,
    "esac",
  ];
}

function softwareDownloadLines(manifest) {
  const records = manifest.software.records;
  return [
    "",
    ...recordDownloadLines(records.release_auth_manifest_path, "RELEASE_AUTH_MANIFEST", manifest),
    ...recordDownloadLines(records.release_auth_signature_path, "RELEASE_AUTH_SIGNATURE", manifest),
    ...recordDownloadLines(manifest.trust.release_key_path, "RELEASE_KEY", manifest),
    "",
    'download_ipfs "$PACKAGE_CID" "$PACKAGE.part"',
    'printf \'%s  %s\\n\' "$PACKAGE_SHA256" "$PACKAGE.part" | sha256sum -c -',
    'mv "$PACKAGE.part" "$PACKAGE"',
    "",
    'ACTUAL_RELEASE_KEY_SHA256=$(openssl pkey -pubin -in "$RELEASE_KEY" -pubout -outform DER | sha256sum | awk \'{print $1}\')',
    'if [ "$ACTUAL_RELEASE_KEY_SHA256" != ' + shellQuote(manifest.trust.release_key_sha256) + " ]; then",
    "  echo 'Release public-key fingerprint mismatch.' >&2",
    "  exit 1",
    "fi",
    'openssl pkeyutl -verify -rawin -pubin -inkey "$RELEASE_KEY" -in "$RELEASE_AUTH_MANIFEST" -sigfile "$RELEASE_AUTH_SIGNATURE"',
    'python3 - "$RELEASE_AUTH_MANIFEST" "$PACKAGE" "$PACKAGE_SHA256" "$PACKAGE_SIZE" ' +
      shellQuote(manifest.release.version) + " " +
      shellQuote(String(manifest.release.sequence)) + " " +
      shellQuote(manifest.trust.release_key_sha256) + " <<'PY'",
    "import json",
    "import os",
    "import sys",
    "",
    "manifest_path, package_path, expected_sha, expected_size, version, sequence, key_sha = sys.argv[1:]",
    "with open(manifest_path, encoding='utf-8') as handle:",
    "    record = json.load(handle)",
    "release = record.get('release', {})",
    "asset = record.get('assets', {}).get(os.path.basename(package_path), {})",
    "checks = [",
    "    release.get('version') == version,",
    "    release.get('sequence') == int(sequence),",
    "    record.get('release_key_sha256') == key_sha,",
    "    asset.get('sha256') == expected_sha,",
    "    asset.get('size_bytes') == int(expected_size),",
    "    os.path.getsize(package_path) == int(expected_size),",
    "]",
    "if not all(checks):",
    "    raise SystemExit('Signed software authorization does not match the selected package.')",
    "PY",
    "",
    'PACKAGE_ROOT=$(basename "$PACKAGE" .zip)',
    'if [ -e "$PACKAGE_ROOT" ]; then',
    '  echo "Refusing to overwrite existing directory: $PACKAGE_ROOT" >&2',
    "  exit 1",
    "fi",
    'unzip -q "$PACKAGE"',
    'chmod +x "$PACKAGE_ROOT/install.sh"',
  ];
}

function preflightLines(selectedDataset, releaseVersion) {
  const datasetDownloadBytes = selectedDataset?.size_bytes || 0;
  const datasetExpandedBytes = selectedDataset?.unpacked_size_bytes || 0;
  const datasetAssemblyBytes = selectedDataset?.delivery?.mode === "multipart"
    ? datasetDownloadBytes
    : 0;
  return [
    "for REQUIRED_COMMAND in bash curl unzip sha256sum openssl python3 awk basename uname docker df id dirname realpath install sudo tar zstd grep; do",
    '  command -v "$REQUIRED_COMMAND" >/dev/null 2>&1 || { echo "Required command is unavailable: $REQUIRED_COMMAND" >&2; exit 1; }',
    "done",
    `[ "$(uname -s)" = Linux ] || { echo ${shellQuote(`${releaseVersion} supports Linux only.`)} >&2; exit 1; }`,
    '[ "$(id -u)" -ne 0 ] || { echo "Run this command as the non-root runtime user, not root." >&2; exit 1; }',
    "sudo -v",
    "docker compose version >/dev/null",
    'docker info >/dev/null || { echo "This user cannot access the Docker daemon." >&2; exit 1; }',
    "",
    'DATA_DIR=$(realpath -m -- "$DATA_DIR")',
    'DOWNLOAD_DIR=$(realpath -m -- "$DOWNLOAD_DIR")',
    '[ "$DATA_DIR" != / ] || { echo "Node-data directory cannot be the filesystem root." >&2; exit 1; }',
    '[ "$DOWNLOAD_DIR" != / ] || { echo "Download workspace cannot be the filesystem root." >&2; exit 1; }',
    'case "$DOWNLOAD_DIR/" in "$DATA_DIR/"|"$DATA_DIR/"*) echo "Download workspace must be outside the node-data directory." >&2; exit 1 ;; esac',
    'case "$DATA_DIR/" in "$DOWNLOAD_DIR/"|"$DOWNLOAD_DIR/"*) echo "Node-data directory must be outside the download workspace." >&2; exit 1 ;; esac',
    "nearest_existing_parent() {",
    "  _candidate=$1",
    '  while [ ! -d "$_candidate" ]; do',
    '    _next=$(dirname -- "$_candidate")',
    '    [ "$_next" != "$_candidate" ] || break',
    '    _candidate="$_next"',
    "  done",
    '  printf "%s\\n" "$_candidate"',
    "}",
    'DATA_PARENT=$(nearest_existing_parent "$DATA_DIR")',
    'DOWNLOAD_PARENT=$(nearest_existing_parent "$DOWNLOAD_DIR")',
    "",
    `DATASET_DOWNLOAD_BYTES=${datasetDownloadBytes}`,
    `DATASET_ASSEMBLY_BYTES=${datasetAssemblyBytes}`,
    `DATASET_EXPANDED_BYTES=${datasetExpandedBytes}`,
    "DOWNLOAD_REQUIRED_KIB=$(( (PACKAGE_SIZE + DATASET_DOWNLOAD_BYTES + DATASET_ASSEMBLY_BYTES + 1073741824 + 1023) / 1024 ))",
    "DATA_REQUIRED_KIB=$(( (DATASET_EXPANDED_BYTES + 5368709120 + 1023) / 1024 ))",
    "DOWNLOAD_AVAILABLE_KIB=$(df -Pk \"$DOWNLOAD_PARENT\" | awk 'NR == 2 {print $4}')",
    "DATA_AVAILABLE_KIB=$(df -Pk \"$DATA_PARENT\" | awk 'NR == 2 {print $4}')",
    "DOWNLOAD_DEVICE=$(df -Pk \"$DOWNLOAD_PARENT\" | awk 'NR == 2 {print $1}')",
    "DATA_DEVICE=$(df -Pk \"$DATA_PARENT\" | awk 'NR == 2 {print $1}')",
    'if [ "$DATASET_EXPANDED_BYTES" -gt 0 ] && [ "$DOWNLOAD_DEVICE" = "$DATA_DEVICE" ]; then',
    "  COMBINED_REQUIRED_KIB=$(( DOWNLOAD_REQUIRED_KIB + DATA_REQUIRED_KIB ))",
    '  [ "$DOWNLOAD_AVAILABLE_KIB" -ge "$COMBINED_REQUIRED_KIB" ] || { echo "Insufficient free space: downloads and restored data share one filesystem." >&2; exit 1; }',
    "else",
    '  [ "$DOWNLOAD_AVAILABLE_KIB" -ge "$DOWNLOAD_REQUIRED_KIB" ] || { echo "Insufficient free space in the download workspace." >&2; exit 1; }',
    '  if [ "$DATASET_EXPANDED_BYTES" -gt 0 ]; then',
    '    [ "$DATA_AVAILABLE_KIB" -ge "$DATA_REQUIRED_KIB" ] || { echo "Insufficient free space on the node-data filesystem." >&2; exit 1; }',
    "  fi",
    "fi",
    'sudo install -d -m 0750 -o "$(id -u)" -g "$(id -g)" "$DOWNLOAD_DIR"',
    'cd "$DOWNLOAD_DIR"',
    'echo "Host preflight passed. Existing-data rollback space and future chain growth remain the operator\'s responsibility."',
  ];
}

function miningAllowlistLines() {
  return [
    "",
    'python3 - "$PACKAGE_ROOT/.env" "$POOL_ASIC_MAC_ALLOWLIST" <<\'PY\'',
    "import os",
    "import sys",
    "from pathlib import Path",
    "",
    "path = Path(sys.argv[1])",
    "value = sys.argv[2]",
    "lines = path.read_text(encoding='utf-8').splitlines()",
    "replacement = f'POOL_ASIC_MAC_ALLOWLIST={value}'",
    "updated = []",
    "replaced = False",
    "for line in lines:",
    "    if line.startswith('POOL_ASIC_MAC_ALLOWLIST='):",
    "        if not replaced:",
    "            updated.append(replacement)",
    "            replaced = True",
    "    else:",
    "        updated.append(line)",
    "if not replaced:",
    "    updated.append(replacement)",
    "temporary = path.with_name(path.name + '.mac-update')",
    "temporary.write_text('\\n'.join(updated) + '\\n', encoding='utf-8')",
    "os.chmod(temporary, 0o600)",
    "temporary.replace(path)",
    "PY",
    '(cd "$PACKAGE_ROOT" && docker compose --profile mining up -d --no-build --pull never pool)',
    'POOL_CONTAINER_ID=$(cd "$PACKAGE_ROOT" && docker compose --profile mining ps -q pool)',
    '[ -n "$POOL_CONTAINER_ID" ] || { echo "Pool container did not start after applying the ASIC MAC allowlist." >&2; exit 1; }',
    'if ! docker inspect --format \'{{range .Config.Env}}{{println .}}{{end}}\' "$POOL_CONTAINER_ID" | grep -Fqx "POOL_ASIC_MAC_ALLOWLIST=$POOL_ASIC_MAC_ALLOWLIST"; then',
    '  echo "Pool container did not receive the selected ASIC MAC allowlist." >&2',
    "  exit 1",
    "fi",
    'echo "ASIC MAC allowlist applied and verified in the running pool container."',
  ];
}

function datasetDownloadLines(dataset) {
  if (dataset.delivery.mode === "direct") {
    return directArtifactLines({ ...dataset, cid: dataset.delivery.cid }, "DATASET");
  }

  const lines = [`DATASET=${shellQuote(dataset.filename)}`];
  for (const part of dataset.delivery.parts) {
    lines.push(
      `PART=${shellQuote(part.filename)}`,
      `download_ipfs ${shellQuote(part.cid)} \"$PART.part\"`,
      `printf '%s  %s\\n' ${shellQuote(part.sha256)} \"$PART.part\" | sha256sum -c -`,
      "mv \"$PART.part\" \"$PART\"",
    );
  }
  const orderedParts = dataset.delivery.parts.map((part) => shellQuote(part.filename)).join(" ");
  lines.push(
    `cat ${orderedParts} > \"$DATASET.part\"`,
    `printf '%s  %s\\n' ${shellQuote(dataset.sha256)} \"$DATASET.part\" | sha256sum -c -`,
    "mv \"$DATASET.part\" \"$DATASET\"",
  );
  return lines;
}

function recordPathReady(manifest, path) {
  const delivery = manifest.records_delivery;
  return Boolean(
    delivery?.mode === "ipfs-directory" &&
    isCid(delivery.cid) &&
    delivery.path_prefix === "records/" &&
    isSafeRelativePath(path) &&
    path.startsWith(delivery.path_prefix) &&
    path.length > delivery.path_prefix.length
  );
}

function recordDownloadLines(path, variableName, manifest) {
  if (!recordPathReady(manifest, path)) {
    return [];
  }
  const name = basename(path);
  const relativePath = path.slice(manifest.records_delivery.path_prefix.length);
  return [
    `${variableName}=${shellQuote(name)}`,
    `download_ipfs_path ${shellQuote(manifest.records_delivery.cid)} ${shellQuote(relativePath)} \"$${variableName}.part\"`,
    `mv \"$${variableName}.part\" \"$${variableName}\"`,
  ];
}

export function resolveInstallSelection(options = {}) {
  if (options.preset === "full-archive-rpc") {
    return {
      preset: "full-archive-rpc",
      profile: "public-rpc",
      dataset: "full_archive",
      retention: "archive",
    };
  }
  return {
    preset: null,
    profile: ["mining", "public-rpc", "non-mining"].includes(options.profile) ? options.profile : "mining",
    dataset: ["none", "portable", "full_archive"].includes(options.dataset) ? options.dataset : "none",
    retention: options.retention === "archive" ? "archive" : "current",
  };
}

export function buildInstallCommand(manifest, options = {}) {
  if (!publicationReady(manifest)) {
    const version = manifest?.release?.version || "Selected release";
    return `# ${version} is not publication-ready.\n# No command is available until signed artifact identities, immutable CIDs, and publication checks are complete.`;
  }

  const selection = resolveInstallSelection(options);
  const { profile, dataset: datasetChoice, retention } = selection;
  const dataDir = String(options.dataDir || "").trim();
  if (!dataDir.startsWith("/") || /[\r\n]/.test(dataDir)) {
    return "# Enter an absolute Linux data directory before continuing.";
  }
  const downloadDir = String(options.downloadDir || "/srv/blockdag/downloads").trim();
  if (!downloadDir.startsWith("/") || /[\r\n]/.test(downloadDir)) {
    return "# Enter an absolute Linux download workspace before continuing.";
  }

  const selectedDataset = datasetChoice === "none" ? null : manifest.datasets[datasetChoice];
  if (selectedDataset && !datasetReady(selectedDataset)) {
    return "# The selected dataset is not published and cannot be installed.";
  }
  const requiredRecordPaths = [
    manifest.software.records.release_auth_manifest_path,
    manifest.software.records.release_auth_signature_path,
    manifest.trust.release_key_path,
    ...(selectedDataset ? [selectedDataset.canonical_manifest_path, manifest.trust.dataset_key_path] : []),
  ];
  if (!requiredRecordPaths.every((path) => recordPathReady(manifest, path))) {
    return "# Immutable signed-record delivery metadata is incomplete.\n# Do not install this release.";
  }
  if (profile === "mining" && !isWallet(String(options.wallet || "").trim())) {
    return "# Enter a valid public 0x payout wallet before continuing.\n# Never enter a seed phrase or private key.";
  }
  if (profile === "mining" && !isMacList(String(options.macs || "").trim())) {
    return "# Enter one or more ASIC MAC addresses before continuing.";
  }

  const lines = [
    "set -Eeuo pipefail",
    `DATA_DIR=${shellQuote(dataDir)}`,
    `DOWNLOAD_DIR=${shellQuote(downloadDir)}`,
    "",
    ...downloadFunction(manifest.download_policy.ipfs_gateways),
    "",
    ...softwareSelectionLines(manifest),
    "",
    ...preflightLines(selectedDataset, manifest.release.version),
    "",
  ];
  lines.push(...softwareDownloadLines(manifest));

  let datasetArgs = [];
  if (selectedDataset) {
    lines.push("", ...datasetDownloadLines(selectedDataset));
    lines.push(
      "",
      ...recordDownloadLines(selectedDataset.canonical_manifest_path, "DATASET_MANIFEST", manifest),
      ...recordDownloadLines(manifest.trust.dataset_key_path, "DATASET_KEY", manifest),
    );
    datasetArgs = [
      "  --dataset-archive \"$PWD/$DATASET\" \\",
      "  --dataset-manifest \"$PWD/$DATASET_MANIFEST\" \\",
      `  --dataset-trusted-key \"${manifest.trust.dataset_key_id}=$PWD/$DATASET_KEY\"`,
    ];
  }

  const releaseEnvironment = [
    `export BDAG_RELEASE_VERSION=${shellQuote(manifest.release.version)}`,
    `export BDAG_RELEASE_SEQUENCE=${shellQuote(String(manifest.release.sequence))}`,
    `export BDAG_RELEASE_KEY_SHA256=${shellQuote(manifest.trust.release_key_sha256)}`,
  ];
  const miningEnvironment = profile === "mining"
    ? [
        `export MINING_POOL_ADDRESS=${shellQuote(options.wallet.trim())}`,
        `export POOL_ASIC_MAC_ALLOWLIST=${shellQuote(normalizeMacList(options.macs))}`,
      ]
    : [];
  const archiveFlag = datasetChoice === "full_archive"
    ? "--full-archive"
    : datasetChoice === "portable"
      ? "--no-archive"
      : retention === "archive"
        ? "--archive"
        : "--no-archive";
  lines.push(
    "",
    ...releaseEnvironment,
    ...miningEnvironment,
    "",
    'bash "$PACKAGE_ROOT/install.sh" \\',
    `  --profile ${profile} \\`,
    '  --data-dir "$DATA_DIR" \\',
    `  ${archiveFlag}${datasetArgs.length ? " \\" : ""}`,
    ...datasetArgs,
  );
  if (profile === "mining") {
    lines.push(...miningAllowlistLines());
  }
  return lines.join("\n");
}

function setDot(id, state) {
  const dot = document.getElementById(id);
  dot.classList.remove("pending", "failed");
  if (state !== "ready") {
    dot.classList.add(state);
  }
}

function setLink(link, href, label) {
  link.textContent = label;
  if (href) {
    link.href = href;
    link.classList.remove("disabled");
    link.setAttribute("aria-disabled", "false");
    link.rel = "noopener";
  } else {
    link.removeAttribute("href");
    link.classList.add("disabled");
    link.setAttribute("aria-disabled", "true");
  }
}

function renderArtifactCard(key, artifact, manifest, active) {
  const card = document.querySelector(`[data-artifact="${key}"]`);
  const ready = key.startsWith("linux-") ? artifactReady(artifact) : datasetReady(artifact);
  const identityReady = key.startsWith("linux-") ? artifactIdentityReady(artifact) : datasetIdentityReady(artifact);
  const field = (name) => card.querySelector(`[data-field="${name}"]`);
  field("status").textContent = active && ready
    ? "Published and verified"
    : identityReady
      ? (key === "portable" ? "Qualified; CID pending" : "Signed; CID pending")
      : "Not available";
  field("filename").textContent = artifact.filename || "Pending final metadata";
  field("size").textContent = formatBytes(artifact.size_bytes);
  field("sha256").textContent = shortValue(artifact.sha256);
  if (field("unpacked-size")) {
    field("unpacked-size").textContent = formatBytes(artifact.unpacked_size_bytes);
  }

  let cidLabel = artifact.cid || null;
  let href = artifact.cid ? gatewayUrl(manifest.download_policy.ipfs_gateways[0], artifact.cid) : null;
  let downloadLabel = "Download from IPFS";
  if (!key.startsWith("linux-")) {
    if (artifact.delivery.mode === "direct") {
      cidLabel = artifact.delivery.cid;
      href = gatewayUrl(manifest.download_policy.ipfs_gateways[0], artifact.delivery.cid);
    } else if (artifact.delivery.mode === "multipart") {
      cidLabel = `${artifact.delivery.parts.length} individually verified IPFS parts`;
      href = resolvedRecordUrl(artifact.delivery.parts_manifest_path, window.location.href);
      downloadLabel = "Open part manifest";
    }
  }
  field("cid").textContent = active && ready ? shortValue(cidLabel) : (key === "full_archive" ? "Delivery metadata pending" : "CID pending");
  setLink(card.querySelector('[data-action="download"]'), active && ready ? href : null, active && ready ? downloadLabel : "Not yet published");

  const manifestLink = card.querySelector('[data-action="manifest"]');
  if (manifestLink) {
    const recordHref = isSafeRelativePath(artifact.canonical_manifest_path) ? artifact.canonical_manifest_path : null;
    setLink(manifestLink, recordHref, recordHref ? "Signed manifest" : "Signed manifest pending");
  }
}

function renderRecordLink(selector, path) {
  const link = document.querySelector(`[data-record="${selector}"]`);
  const code = link.parentElement.querySelector("code");
  const href = isSafeRelativePath(path) ? path : null;
  if (href) {
    link.href = href;
    link.classList.remove("disabled-link");
    link.setAttribute("aria-disabled", "false");
    code.textContent = "available";
  } else {
    link.removeAttribute("href");
    link.classList.add("disabled-link");
    link.setAttribute("aria-disabled", "true");
    code.textContent = "pending";
  }
}

function renderManifest(manifest) {
  const active = publicationReady(manifest);
  const softwareReady = artifactReady(manifest.installer) && Object.values(manifest.software.targets).every(artifactReady);
  const softwareIdentity = artifactIdentityReady(manifest.installer) && Object.values(manifest.software.targets).every(artifactIdentityReady);
  const portableReady = datasetReady(manifest.datasets.portable);
  const portableIdentity = datasetIdentityReady(manifest.datasets.portable);
  const archiveReady = datasetReady(manifest.datasets.full_archive);

  document.getElementById("releaseBadge").textContent = active ? "Published" : "Draft";
  document.getElementById("releaseBadge").classList.toggle("published", active);
  document.getElementById("releaseStatus").textContent = active ? "Published release" : "Draft release";
  document.getElementById("releaseStatusDetail").textContent = active
    ? `Sequence ${manifest.release.sequence} publication checks passed`
    : `Sequence ${manifest.release.sequence} is not yet published`;
  document.getElementById("softwareStatus").textContent = softwareReady ? "Software published" : softwareIdentity ? "Signed software recorded" : "Software pending";
  document.getElementById("softwareStatusDetail").textContent = softwareReady ? "Two signed targets are publicly downloadable from IPFS" : softwareIdentity ? "Immutable download CIDs are pending" : "Signed package records are incomplete";
  document.getElementById("datasetStatus").textContent = archiveReady ? "Portable and full archive published" : portableReady ? "Portable dataset published" : portableIdentity ? "Portable dataset recorded" : "Datasets pending";
  document.getElementById("datasetStatusDetail").textContent = archiveReady
    ? "Portable and full archive are available"
    : portableReady
      ? `Portable ${manifest.datasets.portable.version} is available; full archive is still pending`
      : portableIdentity
        ? "Portable delivery and full archive are pending"
        : "Portable and full-archive records are incomplete";
  setDot("releaseDot", active ? "ready" : "pending");
  setDot("softwareDot", softwareReady ? "ready" : "pending");
  setDot("datasetDot", portableReady ? "ready" : "pending");

  const notice = document.getElementById("draftNotice");
  notice.classList.toggle("published", active);
  notice.innerHTML = active
    ? "<strong>Published and qualified.</strong> Verify the displayed hashes and signed records before installation. Published datasets remain independently versioned from the software release."
    : "<strong>Draft preview.</strong> Artifact hashes, sizes, and immutable CIDs are pending. Download controls remain locked until signed records and publication checks are complete.";

  renderArtifactCard("linux-amd64", manifest.software.targets["linux-amd64"], manifest, active);
  renderArtifactCard("linux-arm64", manifest.software.targets["linux-arm64"], manifest, active);
  renderArtifactCard("portable", manifest.datasets.portable, manifest, active);
  renderArtifactCard("full_archive", manifest.datasets.full_archive, manifest, active);

  renderRecordLink("release-auth", manifest.software.records.release_auth_manifest_path);
  renderRecordLink("release-key", manifest.trust.release_key_path);
  renderRecordLink("release-notes", manifest.software.records.release_notes_path);
  renderRecordLink("dataset-key", manifest.trust.dataset_key_path);
  renderRecordLink("dataset-verifier", manifest.trust.dataset_verifier_path);
  renderRecordLink("portable-manifest", manifest.datasets.portable.canonical_manifest_path);
  renderRecordLink("archive-manifest", manifest.datasets.full_archive.canonical_manifest_path);

  const portableButton = document.querySelector('[data-dataset="portable"]');
  portableButton.disabled = !portableReady;
  portableButton.setAttribute("aria-disabled", String(!portableReady));
  const archiveButton = document.querySelector('[data-dataset="full_archive"]');
  archiveButton.disabled = !archiveReady;
  archiveButton.setAttribute("aria-disabled", String(!archiveReady));
  const archivePresetButton = document.querySelector('[data-preset="full-archive-rpc"]');
  archivePresetButton.disabled = !active || !archiveReady;
  archivePresetButton.setAttribute("aria-disabled", String(!active || !archiveReady));
  return active;
}

function initPage() {
  const state = {
    manifest: null,
    active: false,
    profile: "mining",
    dataset: "none",
    retention: "current",
    preset: null,
  };
  const element = (selector) => document.querySelector(selector);

  function setSegmentState(attribute, value) {
    document.querySelectorAll(`[${attribute}]`).forEach((button) => {
      const selected = button.dataset[attribute.replace("data-", "")] === value;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function setRoleState() {
    document.querySelectorAll("[data-profile]").forEach((button) => {
      const selected = state.preset === null && button.dataset.profile === state.profile;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    document.querySelectorAll("[data-preset]").forEach((button) => {
      const selected = button.dataset.preset === state.preset;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function renderCommand() {
    if (!state.manifest) {
      return;
    }
    const command = buildInstallCommand(state.manifest, {
      profile: state.profile,
      dataset: state.dataset,
      retention: state.retention,
      preset: state.preset,
      dataDir: element("#dataDir").value,
      downloadDir: element("#downloadDir").value,
      wallet: element("#wallet").value,
      macs: element("#macs").value,
    }, window.location.href);
    element("#installCommand").textContent = command;
    element("#copyCommand").disabled = !state.active || command.startsWith("#");
    const mining = state.profile === "mining";
    element("#walletLabel").hidden = !mining;
    element("#macLabel").hidden = !mining;
    element("#datasetField").hidden = state.preset !== null;
    element("#retentionField").hidden = state.preset !== null || state.dataset !== "none";

    if (state.preset === "full-archive-rpc") {
      const dataset = state.manifest.datasets.full_archive;
      element("#selectionSummary").textContent = `Full archive RPC preset: public-rpc + signed ${dataset.version} + fail-closed --full-archive retention.`;
    } else if (state.dataset === "portable") {
      const dataset = state.manifest.datasets.portable;
      element("#selectionSummary").textContent = `Portable ${dataset.version}: ${formatBytes(dataset.size_bytes)} download and ${formatBytes(dataset.unpacked_size_bytes)} expanded. Current-state retention is enforced.`;
    } else if (state.dataset === "full_archive") {
      const dataset = state.manifest.datasets.full_archive;
      element("#selectionSummary").textContent = `Full archive ${dataset.version}: ${formatBytes(dataset.size_bytes)} multipart download, ${formatBytes(dataset.unpacked_size_bytes)} expanded, and fail-closed --full-archive mode.`;
    } else if (state.retention === "archive") {
      element("#selectionSummary").textContent = "Software only: keep or synchronize node data while retaining EVM states from the current history forward.";
    } else {
      element("#selectionSummary").textContent = "Software only: keep compatible data or synchronize normally in current-state mode.";
    }

    if (state.profile === "public-rpc") {
      element("#inputNotice").textContent = "Public RPC exposes the HTTP API on all interfaces. Put it behind an independently configured TLS edge proxy with firewalling, per-client abuse controls, health checks, monitoring, and restart recovery.";
    } else if (!mining) {
      element("#inputNotice").textContent = "This role does not require a payout wallet or ASIC MAC list.";
    } else if (!isWallet(element("#wallet").value.trim())) {
      element("#inputNotice").textContent = "Enter a valid public 0x payout wallet. Never enter a seed phrase or private key.";
    } else if (!isMacList(element("#macs").value.trim())) {
      element("#inputNotice").textContent = "Enter each ASIC Ethernet MAC address, separated by commas.";
    } else {
      element("#inputNotice").textContent = "Public wallet and MAC address formats are valid. Confirm both independently before mining.";
    }
  }

  document.querySelectorAll("[data-profile]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled) {
      return;
    }
    state.preset = null;
    state.profile = button.dataset.profile;
    setRoleState();
    renderCommand();
  }));
  document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled) {
      return;
    }
    const selection = resolveInstallSelection({ preset: button.dataset.preset });
    state.preset = selection.preset;
    state.profile = selection.profile;
    state.dataset = selection.dataset;
    state.retention = selection.retention;
    setRoleState();
    setSegmentState("data-dataset", state.dataset);
    setSegmentState("data-retention", state.retention);
    renderCommand();
  }));
  document.querySelectorAll("[data-dataset]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled) {
      return;
    }
    state.dataset = button.dataset.dataset;
    if (state.dataset !== "none") {
      state.retention = "current";
      setSegmentState("data-retention", state.retention);
    }
    setSegmentState("data-dataset", state.dataset);
    renderCommand();
  }));
  document.querySelectorAll("[data-retention]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled || state.dataset !== "none") {
      return;
    }
    state.retention = button.dataset.retention;
    setSegmentState("data-retention", state.retention);
    renderCommand();
  }));
  ["#dataDir", "#downloadDir", "#wallet", "#macs"].forEach((selector) => element(selector).addEventListener("input", renderCommand));
  element("#copyCommand").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(element("#installCommand").textContent);
      element("#toast").textContent = "Command copied";
    } catch {
      element("#toast").textContent = "Copy failed. Select the command manually.";
    }
    element("#toast").classList.add("show");
    window.setTimeout(() => element("#toast").classList.remove("show"), 1800);
  });

  fetch("release-manifest.json", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`manifest request failed with status ${response.status}`);
      }
      return response.json();
    })
    .then((manifest) => {
      state.manifest = manifest;
      state.active = renderManifest(manifest);
      renderCommand();
    })
    .catch(() => {
      setDot("releaseDot", "failed");
      element("#releaseStatus").textContent = "Manifest unavailable";
      element("#releaseStatusDetail").textContent = "Do not download or install this release";
      element("#installCommand").textContent = "# Release manifest could not be loaded.\n# Do not continue with installation.";
    });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.addEventListener("DOMContentLoaded", initPage);
}
