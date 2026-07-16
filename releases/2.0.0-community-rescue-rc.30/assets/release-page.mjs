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
    manifest.release.version === "2.0.0-community-rescue-rc.30" &&
    manifest.release.sequence === 30 &&
    manifest.release.chain_id === 1404 &&
    manifest.runtime_change?.transient_startup_canonical_boundary_rpc === "bounded-retry" &&
    manifest.runtime_change?.transient_startup_peer_readiness === "bounded-retry" &&
    manifest.runtime_change?.canonical_mismatch === "fail-immediately" &&
    typeof manifest.release.published_at === "string" &&
    !Number.isNaN(Date.parse(manifest.release.published_at)) &&
    isHttpsUrl(source.release_url) &&
    source.tag === manifest.release.version &&
    [source.stack_commit, source.corechain_commit, source.pool_commit, source.dashboard_commit].every((value) => COMMIT_PATTERN.test(value)) &&
    source.stack_commit === "a0fb1ef7b979e5977728d6c6cb38f56d215fd719" &&
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
    return candidate.protocol === "https:" ? candidate.href : null;
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

function softwareDownloadLines(manifest, pageUrl) {
  const amd64 = manifest.software.targets["linux-amd64"];
  const arm64 = manifest.software.targets["linux-arm64"];
  const records = manifest.software.records;
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
    "  *) echo 'Unsupported CPU architecture; RC30 supports AMD64 and ARM64 Linux.' >&2; exit 1 ;;",
    "esac",
    "",
    ...recordDownloadLines(records.release_auth_manifest_path, "RELEASE_AUTH_MANIFEST", pageUrl),
    ...recordDownloadLines(records.release_auth_signature_path, "RELEASE_AUTH_SIGNATURE", pageUrl),
    ...recordDownloadLines(manifest.trust.release_key_path, "RELEASE_KEY", pageUrl),
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

function recordDownloadLines(path, variableName, pageUrl) {
  const url = resolvedRecordUrl(path, pageUrl);
  if (!url) {
    return [];
  }
  const name = basename(path);
  return [
    `${variableName}=${shellQuote(name)}`,
    `curl -4 --http1.1 --fail --location --show-error --retry 8 --retry-all-errors ${shellQuote(url)} -o \"$${variableName}.part\"`,
    `mv \"$${variableName}.part\" \"$${variableName}\"`,
  ];
}

export function buildInstallCommand(manifest, options, pageUrl = "https://release.invalid/index.html") {
  if (!publicationReady(manifest)) {
    return "# RC30 is still a draft.\n# No command is available until signed artifact identities, immutable CIDs, and publication checks are complete.";
  }

  const profile = ["mining", "public-rpc", "non-mining"].includes(options.profile) ? options.profile : "mining";
  const datasetChoice = ["none", "portable", "full_archive"].includes(options.dataset) ? options.dataset : "none";
  const dataDir = String(options.dataDir || "").trim();
  if (!dataDir.startsWith("/") || /[\r\n]/.test(dataDir)) {
    return "# Enter an absolute Linux data directory before continuing.";
  }
  if (profile === "mining" && !isWallet(String(options.wallet || "").trim())) {
    return "# Enter a valid public 0x payout wallet before continuing.\n# Never enter a seed phrase or private key.";
  }
  if (profile === "mining" && !isMacList(String(options.macs || "").trim())) {
    return "# Enter one or more ASIC MAC addresses before continuing.";
  }

  const selectedDataset = datasetChoice === "none" ? null : manifest.datasets[datasetChoice];
  if (selectedDataset && !datasetReady(selectedDataset)) {
    return "# The selected dataset is not ready for a verified download.";
  }

  const lines = ["set -eu", "", ...downloadFunction(manifest.download_policy.ipfs_gateways), ""];
  lines.push(...softwareDownloadLines(manifest, pageUrl));

  let datasetArgs = [];
  if (selectedDataset) {
    lines.push("", ...datasetDownloadLines(selectedDataset));
    lines.push(
      "",
      ...recordDownloadLines(selectedDataset.canonical_manifest_path, "DATASET_MANIFEST", pageUrl),
      ...recordDownloadLines(manifest.trust.dataset_key_path, "DATASET_KEY", pageUrl),
    );
    datasetArgs = [
      "  --dataset-archive \"$PWD/$DATASET\" \\",
      "  --dataset-manifest \"$PWD/$DATASET_MANIFEST\" \\",
      `  --dataset-trusted-key \"${manifest.trust.dataset_key_id}=$PWD/$DATASET_KEY\"`,
    ];
  }

  const releaseEnvironment = [
    `BDAG_RELEASE_VERSION=${shellQuote(manifest.release.version)}`,
    `BDAG_RELEASE_SEQUENCE=${shellQuote(String(manifest.release.sequence))}`,
    `BDAG_RELEASE_KEY_SHA256=${shellQuote(manifest.trust.release_key_sha256)}`,
  ];
  const miningEnvironment = profile === "mining"
    ? [
        `MINING_POOL_ADDRESS=${shellQuote(options.wallet.trim())}`,
        `POOL_ASIC_MAC_ALLOWLIST=${shellQuote(options.macs.trim())}`,
      ]
    : [];
  const environment = `${[...releaseEnvironment, ...miningEnvironment].join(" ")} `;
  const archiveFlag = datasetChoice === "full_archive" ? "--archive" : "--no-archive";
  lines.push(
    "",
    `${environment}bash "$PACKAGE_ROOT/install.sh" \\`,
    `  --profile ${profile} \\`,
    `  --data-dir ${shellQuote(dataDir)} \\`,
    `  ${archiveFlag}${datasetArgs.length ? " \\" : ""}`,
    ...datasetArgs,
  );
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
    code.textContent = "available";
  } else {
    link.removeAttribute("href");
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
  document.getElementById("releaseStatusDetail").textContent = active ? "Sequence 30 publication checks passed" : "Sequence 30 is not yet published";
  document.getElementById("softwareStatus").textContent = softwareReady ? "Software published" : softwareIdentity ? "Signed software recorded" : "Software pending";
  document.getElementById("softwareStatusDetail").textContent = softwareReady ? "Two signed targets are publicly downloadable from IPFS" : softwareIdentity ? "Immutable download CIDs are pending" : "Signed package records are incomplete";
  document.getElementById("datasetStatus").textContent = portableReady ? "Portable dataset published" : portableIdentity ? "Portable dataset recorded" : "Datasets pending";
  document.getElementById("datasetStatusDetail").textContent = archiveReady ? "Portable and full archive are available" : portableReady ? "Portable v27 is available; full archive is still pending" : portableIdentity ? "Portable delivery and full archive are pending" : "Portable and full-archive records are incomplete";
  setDot("releaseDot", active ? "ready" : "pending");
  setDot("softwareDot", softwareReady ? "ready" : "pending");
  setDot("datasetDot", portableReady ? "ready" : "pending");

  const notice = document.getElementById("draftNotice");
  notice.classList.toggle("published", active);
  notice.innerHTML = active
    ? "<strong>Published and qualified.</strong> Verify the displayed hashes and signed records before installation."
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
  return active;
}

function initPage() {
  const state = {
    manifest: null,
    active: false,
    profile: "mining",
    dataset: "none",
  };
  const element = (selector) => document.querySelector(selector);

  function renderCommand() {
    if (!state.manifest) {
      return;
    }
    const command = buildInstallCommand(state.manifest, {
      profile: state.profile,
      dataset: state.dataset,
      dataDir: element("#dataDir").value,
      wallet: element("#wallet").value,
      macs: element("#macs").value,
    }, window.location.href);
    element("#installCommand").textContent = command;
    element("#copyCommand").disabled = !state.active || command.startsWith("#");
    const mining = state.profile === "mining";
    element("#walletLabel").hidden = !mining;
    element("#macLabel").hidden = !mining;
    if (!mining) {
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
    state.profile = button.dataset.profile;
    document.querySelectorAll("[data-profile]").forEach((item) => item.classList.toggle("active", item === button));
    renderCommand();
  }));
  document.querySelectorAll("[data-dataset]").forEach((button) => button.addEventListener("click", () => {
    state.dataset = button.dataset.dataset;
    document.querySelectorAll("[data-dataset]").forEach((item) => item.classList.toggle("active", item === button));
    renderCommand();
  }));
  ["#dataDir", "#wallet", "#macs"].forEach((selector) => element(selector).addEventListener("input", renderCommand));
  element("#copyCommand").addEventListener("click", async () => {
    await navigator.clipboard.writeText(element("#installCommand").textContent);
    element("#toast").classList.add("show");
    window.setTimeout(() => element("#toast").classList.remove("show"), 1400);
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
