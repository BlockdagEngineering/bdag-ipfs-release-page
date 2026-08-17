const EXPECTED = Object.freeze({
  version: "2.0.0-community-rescue-rc.65",
  sequence: 65,
  tag: "jeremy-community-rescue-rc.65.6",
  chainId: 1404,
  protocol: 46,
  releaseJsonSha256: "4f1c1962edb90dd99f4286d58507ed2216ea47f7bc83ccb055072269731b1335",
  recordsCid: "bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe",
  predecessorCid: "bafybeiet53pfpyf52mmbqwqg6qapxueblqhyqyit6f5zyfaotunpwtgweq",
  outerKeySha256: "9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66",
  softwareKeySha256: "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb",
  datasetKeySha256: "f9f2f7df88d43c8d51df8bdc2a369601ff0b4b9de224e8ab9b609b423b203d24",
  compact: Object.freeze({
    name: "blockdag-chain1404-compact-data-2.0.0-community-rescue-rc.65-evm17884079.tar.zst",
    cid: "bafybeih55jggjwlwhdkapsb2h3cp4yx7lt3a43chiwyvuyazrh7eekm6y4",
    sha256: "0939750a68afe7bec90774a48985f1ae5cdc734fc61364247296f32bd3a5eb92",
    bytes: 16191131162,
    unpackedBytes: 32618071094,
  }),
});

const GATEWAYS = Object.freeze([
  "https://dweb.link/ipfs",
  "https://ipfs.io/ipfs",
  "https://w3s.link/ipfs",
]);

const state = {
  ready: false,
  release: null,
  attestation: null,
  compact: null,
};

export function isSha256(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

export function isCid(value) {
  return typeof value === "string" && /^b[a-z2-7]{20,}$/.test(value);
}

export function isWallet(value) {
  return typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value) && !/^0x0{40}$/.test(value);
}

export function isAbsoluteSafePath(value) {
  return typeof value === "string" && value.startsWith("/") && value !== "/" && value.length <= 512 &&
    !/[\0\r\n]/.test(value) && !/(^|\/)\.\.(\/|$)/.test(value) && !value.endsWith("/..");
}

export function normalizeMacList(value) {
  if (typeof value !== "string" || value.trim() === "") return "";
  const items = value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean);
  if (items.length > 64 || items.some((item) => !/^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$/.test(item))) return null;
  return [...new Set(items)].join(",");
}

export function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

export function formatBytes(value) {
  if (!Number.isFinite(value) || value < 0) return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount >= 10 || unit === 0 ? amount.toFixed(unit === 0 ? 0 : 1) : amount.toFixed(2)} ${units[unit]}`;
}

function canonicalize(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function canonicalBytes(value) {
  return new TextEncoder().encode(`${canonicalize(value)}\n`);
}

function bytesToHex(bytes) {
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(bytes) {
  return bytesToHex(await crypto.subtle.digest("SHA-256", bytes));
}

function pemToDer(bytes) {
  const text = new TextDecoder().decode(bytes);
  const body = text.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, "");
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(body)) throw new Error("public key is not valid PEM");
  const decoded = atob(body);
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0));
}

function base64Bytes(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) throw new Error("signature is not valid base64");
  const decoded = atob(value);
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0));
}

async function importEd25519(pemBytes, expectedFingerprint) {
  if (!globalThis.crypto?.subtle) throw new Error("this browser cannot perform local signature verification");
  const der = pemToDer(pemBytes);
  if (await sha256Hex(der) !== expectedFingerprint) throw new Error("public-key fingerprint mismatch");
  const key = await crypto.subtle.importKey("spki", der, { name: "Ed25519" }, false, ["verify"]);
  return key;
}

async function verifySignature(key, signature, payload) {
  if (signature.byteLength !== 64 || !(await crypto.subtle.verify({ name: "Ed25519" }, key, signature, payload))) {
    throw new Error("Ed25519 signature verification failed");
  }
}

async function fetchBytes(path) {
  const response = await fetch(path, { cache: "no-store", credentials: "omit" });
  if (!response.ok) throw new Error(`unable to fetch ${path}: HTTP ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
}

function parseJson(bytes, label) {
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    throw new Error(`${label} is not valid JSON`);
  }
}

function exactSoftware(release, platform, expected) {
  const actual = release?.software?.targets?.[platform];
  return Boolean(actual && actual.name === expected.name && actual.cid === expected.cid && actual.sha256 === expected.sha256 && actual.bytes === expected.bytes);
}

function validateRelease(release) {
  const amd64 = {
    name: "pool-stack-docker-jeremy-community-rescue-rc.65.6-linux-amd64.zip",
    cid: "bafybeiaar3zvj7wpr4snugwmln4fn25hvey4y5tbn536p6oha4ljcemooi",
    sha256: "6b06b9823b02b91e770de25d6f294b7e43ef17408d73d5d2829e779e544402ee",
    bytes: 630586909,
  };
  const arm64 = {
    name: "pool-stack-docker-jeremy-community-rescue-rc.65.6-linux-arm64.zip",
    cid: "bafybeibisqkztkok5pxedpeztelruzkqpda5u62dfp5ctwvr2odymhrz74",
    sha256: "4dfa46478fedf49f91a74915f94f11ee2fecd9c9cd92e1b86ace5eadf68e1b17",
    bytes: 593591386,
  };
  if (release?.schema !== "bdag.community-release-index.v3" || release.status !== "published" ||
      release.version !== EXPECTED.version || release.sequence !== EXPECTED.sequence || release.network?.chainId !== EXPECTED.chainId ||
      release.network?.protocol !== EXPECTED.protocol || release.provenance?.softwareTag !== EXPECTED.tag ||
      JSON.stringify(release.platforms) !== JSON.stringify(["linux/amd64", "linux/arm64"]) ||
      release.trust?.outerReleaseKeySha256 !== EXPECTED.outerKeySha256 ||
      release.trust?.softwareReleaseKeySha256 !== EXPECTED.softwareKeySha256 ||
      release.trust?.fullArchiveDatasetKeySha256 !== EXPECTED.datasetKeySha256 ||
      !exactSoftware(release, "linux-amd64", amd64) || !exactSoftware(release, "linux-arm64", arm64)) {
    throw new Error("original RC65 release identity is not exact");
  }
  const compact = release.datasets?.compactMiningNode?.artifact;
  if (!compact || compact.name !== EXPECTED.compact.name || compact.cid !== EXPECTED.compact.cid ||
      compact.sha256 !== EXPECTED.compact.sha256 || compact.bytes !== EXPECTED.compact.bytes ||
      release.existingDataUpgrade?.downloadsCompact !== false || release.existingDataUpgrade?.downloadsFullArchive !== false ||
      release.existingDataUpgrade?.reusesQualifiedData !== true) {
    throw new Error("RC65 data or existing-upgrade policy is not exact");
  }
  const full = release.datasets?.fullArchive;
  if (!full || full.status !== "published" || full.inheritedFrom !== "2.0.0-community-rescue-rc.44" ||
      full.catchUpRequiredFromPublishedBoundary !== true || full.delivery?.parts?.length !== 40) {
    throw new Error("full-archive publication identity is not exact");
  }
}

function validateAttestation(attestation) {
  if (attestation?.schema !== "bdag.community-page-revision.v2" || attestation.status !== "published" ||
      attestation.release?.version !== EXPECTED.version || attestation.release?.sequence !== EXPECTED.sequence ||
      attestation.release?.softwareTag !== EXPECTED.tag || attestation.presentation?.revision !== 2 ||
      attestation.presentation?.predecessorCid !== EXPECTED.predecessorCid ||
      attestation.originalRecords?.cid !== EXPECTED.recordsCid ||
      attestation.originalRecords?.releaseJsonSha256 !== EXPECTED.releaseJsonSha256 ||
      attestation.trust?.outerReleaseKeySha256 !== EXPECTED.outerKeySha256 ||
      attestation.trust?.datasetKeySha256 !== EXPECTED.datasetKeySha256 ||
      attestation.unchangedBytes?.software !== true || attestation.unchangedBytes?.compactDataset !== true ||
      attestation.unchangedBytes?.fullArchive !== true || attestation.unchangedBytes?.originalRecords !== true) {
    throw new Error("signed page-v2 attestation is not exact");
  }
  const admission = attestation.compactAdmission;
  if (!admission || admission.artifact?.cid !== EXPECTED.compact.cid || admission.artifact?.sha256 !== EXPECTED.compact.sha256 ||
      admission.artifact?.bytes !== EXPECTED.compact.bytes || admission.artifact?.unpackedBytes !== EXPECTED.compact.unpackedBytes ||
      !isCid(admission.manifestCid) || !isSha256(admission.manifestSha256)) {
    throw new Error("signed compact admission is not exact");
  }
}

function validateCompactPayload(envelope) {
  const signed = envelope?.signed;
  const signature = envelope?.signature;
  if (envelope?.schema !== "bdag.canonical-data-manifest.v3" || signature?.algorithm !== "ed25519" ||
      signature?.key_id !== "qualification-v2-20260711" || signature?.public_key_sha256 !== EXPECTED.datasetKeySha256 ||
      signed?.network !== "mainnet" || signed?.chain_id !== EXPECTED.chainId || signed?.dataset_class !== "verified-tip-state" ||
      signed?.archive_node_equivalent !== false || signed?.artifact?.name !== EXPECTED.compact.name ||
      signed?.artifact?.sha256 !== EXPECTED.compact.sha256 || signed?.artifact?.size_bytes !== EXPECTED.compact.bytes ||
      signed?.artifact?.unpacked_size_bytes !== EXPECTED.compact.unpackedBytes || signed?.evm?.number !== 17884079 ||
      signed?.native?.order !== 18289992 || signed?.fixed_checkpoint?.number !== 13863411) {
    throw new Error("compact canonical-data manifest is not exact");
  }
}

async function verifyPresentationAssets(attestation) {
  const assets = attestation.presentation?.assets;
  if (!assets || typeof assets !== "object") throw new Error("signed presentation asset inventory is missing");
  for (const [path, identity] of Object.entries(assets)) {
    if (!/^(?:assets|revision)\/[A-Za-z0-9._/-]+$/.test(path) && !/^verify-load(?:-v2)?[.]sh$/.test(path)) throw new Error("unsafe attested asset path");
    if (!isSha256(identity?.sha256) || !Number.isInteger(identity?.bytes) || identity.bytes <= 0) throw new Error("invalid attested asset identity");
    const bytes = await fetchBytes(path);
    if (bytes.byteLength !== identity.bytes || await sha256Hex(bytes) !== identity.sha256) throw new Error(`presentation asset differs from signed identity: ${path}`);
  }
}

export async function authenticateRelease() {
  const [releaseBytes, releaseSignature, outerPem, attestationBytes, attestationSignature, compactBytes, datasetPem] = await Promise.all([
    fetchBytes("records/release.json"),
    fetchBytes("records/release.json.sig"),
    fetchBytes("records/release-public.pem"),
    fetchBytes("revision/page-v2.json"),
    fetchBytes("revision/page-v2.json.sig"),
    fetchBytes("revision/compact-canonical-manifest.json"),
    fetchBytes("records/dataset/qualification-v2-20260711.pem"),
  ]);
  const outerKey = await importEd25519(outerPem, EXPECTED.outerKeySha256);
  await verifySignature(outerKey, releaseSignature, releaseBytes);
  await verifySignature(outerKey, attestationSignature, attestationBytes);
  if (await sha256Hex(releaseBytes) !== EXPECTED.releaseJsonSha256) throw new Error("release.json digest mismatch");
  const release = parseJson(releaseBytes, "release.json");
  const attestation = parseJson(attestationBytes, "page-v2.json");
  const compact = parseJson(compactBytes, "compact-canonical-manifest.json");
  validateRelease(release);
  validateAttestation(attestation);
  if (await sha256Hex(compactBytes) !== attestation.compactAdmission.manifestSha256) throw new Error("compact manifest digest mismatch");
  validateCompactPayload(compact);
  const datasetKey = await importEd25519(datasetPem, EXPECTED.datasetKeySha256);
  await verifySignature(datasetKey, base64Bytes(compact.signature.value), canonicalBytes(compact.signed));
  await verifyPresentationAssets(attestation);
  return { release, attestation, compact };
}

function downloadFunction() {
  return [
    "download_ipfs() {",
    "  local cid_path=$1 output=$2",
    "  [[ $cid_path =~ ^b[a-z2-7]{20,}(/[A-Za-z0-9._/-]+)?$ ]]",
    "  [[ $output == \"$DOWNLOAD_DIR/\"* && ! -L $output && ! -L $output.part ]]",
    "  if [[ -f $output ]]; then return 0; fi",
    "  for gateway in https://dweb.link/ipfs https://ipfs.io/ipfs https://w3s.link/ipfs; do",
    "    if curl --fail --location --proto '=https' --tlsv1.2 --connect-timeout 20 --max-time 21600 --retry 3 --retry-all-errors --continue-at - --output \"$output.part\" \"$gateway/$cid_path\"; then",
    "      mv -T -- \"$output.part\" \"$output\"",
    "      return 0",
    "    fi",
    "  done",
    "  printf 'Unable to download %s from the configured IPFS gateways.\\n' \"$cid_path\" >&2",
    "  return 1",
    "}",
  ];
}

function softwareSetupLines(release) {
  const amd = release.software.targets["linux-amd64"];
  const arm = release.software.targets["linux-arm64"];
  return [
    "case \"$(uname -s)/$(uname -m)\" in",
    `  Linux/x86_64|Linux/amd64) SOFTWARE_NAME=${shellQuote(amd.name)}; SOFTWARE_CID=${shellQuote(amd.cid)}; SOFTWARE_SHA256=${shellQuote(amd.sha256)}; SOFTWARE_BYTES=${amd.bytes}; PLATFORM=linux-amd64 ;;`,
    `  Linux/aarch64|Linux/arm64) SOFTWARE_NAME=${shellQuote(arm.name)}; SOFTWARE_CID=${shellQuote(arm.cid)}; SOFTWARE_SHA256=${shellQuote(arm.sha256)}; SOFTWARE_BYTES=${arm.bytes}; PLATFORM=linux-arm64 ;;`,
    "  *) printf 'RC65 supports Linux AMD64 and ARM64 only.\\n' >&2; exit 1 ;;",
    "esac",
    "readonly SOFTWARE_NAME SOFTWARE_CID SOFTWARE_SHA256 SOFTWARE_BYTES PLATFORM",
    "readonly SOFTWARE_ARCHIVE=\"$DOWNLOAD_DIR/$SOFTWARE_NAME\"",
    "download_ipfs \"$SOFTWARE_CID\" \"$SOFTWARE_ARCHIVE\"",
    "[[ $(stat -c %s \"$SOFTWARE_ARCHIVE\") == \"$SOFTWARE_BYTES\" ]]",
    "printf '%s  %s\\n' \"$SOFTWARE_SHA256\" \"$SOFTWARE_ARCHIVE\" | sha256sum -c -",
    "readonly PACKAGE_NAME=${SOFTWARE_NAME%.zip}",
    "readonly PACKAGE_ROOT=\"$DOWNLOAD_DIR/$PACKAGE_NAME\"",
    "if [[ ! -d $PACKAGE_ROOT ]]; then",
    "  [[ ! -e $PACKAGE_ROOT && ! -L $PACKAGE_ROOT ]]",
    "  extract=$(mktemp -d \"$DOWNLOAD_DIR/.rc65-software.XXXXXX\")",
    "  unzip -q \"$SOFTWARE_ARCHIVE\" -d \"$extract\"",
    "  [[ -d $extract/$PACKAGE_NAME && ! -L $extract/$PACKAGE_NAME ]]",
    "  [[ $(find \"$extract\" -mindepth 1 -maxdepth 1 -printf '%f\\n') == \"$PACKAGE_NAME\" ]]",
    "  mv -T -- \"$extract/$PACKAGE_NAME\" \"$PACKAGE_ROOT\"",
    "  rmdir \"$extract\"",
    "fi",
    `python3 "$PACKAGE_ROOT/scripts/release_lock.py" verify --lock "$PACKAGE_ROOT/release-lock.json" --trusted-key-dir "$PACKAGE_ROOT/trust/release" --trusted-key-sha256 ${shellQuote(EXPECTED.softwareKeySha256)} --expected-release-version ${shellQuote(EXPECTED.tag)} --expected-release-sequence 65 --target "$PLATFORM" --package-root "$PACKAGE_ROOT" >/dev/null`,
  ];
}

function fullArchiveLines(release) {
  const full = release.datasets.fullArchive;
  const partRows = full.delivery.parts.map((part) => `${part.filename}|${part.cid}|${part.sha256}|${part.size_bytes}`).join("\n");
  return [
    `readonly DATASET_NAME=${shellQuote(full.filename)}`,
    `readonly DATASET_SHA256=${shellQuote(full.sha256)}`,
    `readonly DATASET_BYTES=${full.size_bytes}`,
    "readonly DATASET_ARCHIVE=\"$DOWNLOAD_DIR/$DATASET_NAME\"",
    "readonly DATASET_MANIFEST=\"$DOWNLOAD_DIR/full-archive-v28-canonical-manifest.json\"",
    `download_ipfs ${shellQuote(`${EXPECTED.recordsCid}/dataset/full-archive-v28-canonical-manifest.json`)} "$DATASET_MANIFEST"`,
    "if [[ ! -f $DATASET_ARCHIVE ]]; then",
    "  [[ ! -e $DATASET_ARCHIVE && ! -L $DATASET_ARCHIVE && ! -L $DATASET_ARCHIVE.part ]]",
    "  : >\"$DATASET_ARCHIVE.part\"",
    "  while IFS='|' read -r part_name part_cid part_sha part_bytes; do",
    "    [[ $part_name =~ ^[A-Za-z0-9][A-Za-z0-9._+-]+$ && $part_sha =~ ^[0-9a-f]{64}$ && $part_bytes =~ ^[0-9]+$ ]]",
    "    part_path=\"$DOWNLOAD_DIR/$part_name\"",
    "    download_ipfs \"$part_cid\" \"$part_path\"",
    "    [[ $(stat -c %s \"$part_path\") == \"$part_bytes\" ]]",
    "    printf '%s  %s\\n' \"$part_sha\" \"$part_path\" | sha256sum -c -",
    "    dd if=\"$part_path\" of=\"$DATASET_ARCHIVE.part\" oflag=append conv=notrunc status=none",
    "    rm -- \"$part_path\"",
    "  done <<'RC65_FULL_ARCHIVE_PARTS'",
    partRows,
    "RC65_FULL_ARCHIVE_PARTS",
    "  mv -T -- \"$DATASET_ARCHIVE.part\" \"$DATASET_ARCHIVE\"",
    "fi",
    "[[ $(stat -c %s \"$DATASET_ARCHIVE\") == \"$DATASET_BYTES\" ]]",
    "printf '%s  %s\\n' \"$DATASET_SHA256\" \"$DATASET_ARCHIVE\" | sha256sum -c -",
  ];
}

export function validateOptions(options) {
  const errors = [];
  if (!state.ready && !options?.allowUntrustedFixture) errors.push("Signed release records are not authenticated yet.");
  if (!isAbsoluteSafePath(options?.dataDir)) errors.push("Use an absolute, non-root canonical data directory.");
  if (!isAbsoluteSafePath(options?.downloadDir)) errors.push("Use an absolute, non-root download workspace.");
  if (options?.dataDir === options?.downloadDir) errors.push("Data and download directories must be different.");
  if (!["upgrade", "compact-miner", "full-archive"].includes(options?.mode)) errors.push("Choose a supported install path.");
  if (!["mining", "non-mining", "public-rpc"].includes(options?.profile)) errors.push("Choose a supported runtime profile.");
  if (!["localhost", "lan"].includes(options?.dashboardBind)) errors.push("Choose a supported dashboard binding.");
  if (options?.profile === "mining" && !isWallet(options?.wallet)) errors.push("Mining requires the owner’s non-zero 0x payout address.");
  if (normalizeMacList(options?.asicMacs ?? "") === null) errors.push("ASIC MAC entries must be full comma-separated six-byte addresses.");
  if (options?.mode === "compact-miner" && options?.profile !== "mining") errors.push("The compact mining-node preset requires the mining profile.");
  if (options?.mode === "full-archive" && options?.profile === "mining") errors.push("Use public-rpc or non-mining for the full-archive preset.");
  return errors;
}

export function buildInstallCommand(release, attestation, options = {}) {
  const errors = validateOptions(options);
  if (errors.length) return `# Command locked: ${errors.join(" ")}`;
  const macs = normalizeMacList(options.asicMacs ?? "");
  const lines = [
    "set -Eeuo pipefail",
    "umask 077",
    "export LANG=C LC_ALL=C",
    `readonly DATA_DIR=${shellQuote(options.dataDir)}`,
    `readonly DOWNLOAD_DIR=${shellQuote(options.downloadDir)}`,
    `readonly PROFILE=${shellQuote(options.profile)}`,
    `readonly DASHBOARD_BIND=${shellQuote(options.dashboardBind)}`,
    `readonly OWNER_PAYOUT=${shellQuote(options.profile === "mining" ? options.wallet : "")}`,
    `readonly ASIC_MACS=${shellQuote(macs ?? "")}`,
    "[[ $DATA_DIR == /* && $DATA_DIR != / && $DOWNLOAD_DIR == /* && $DOWNLOAD_DIR != / && $DATA_DIR != $DOWNLOAD_DIR ]]",
    "for command in curl find jq mktemp openssl python3 sha256sum stat unzip; do command -v \"$command\" >/dev/null || { printf 'Required command unavailable: %s\\n' \"$command\" >&2; exit 1; }; done",
    "install -d -m 0700 \"$DOWNLOAD_DIR\"",
    ...downloadFunction(),
    ...softwareSetupLines(release),
  ];

  const installArgs = ["--profile", '"$PROFILE"', "--data-dir", '"$DATA_DIR"', "--dashboard-bind", '"$DASHBOARD_BIND"'];
  if (macs) installArgs.push("--asic-mac-allowlist", '"$ASIC_MACS"');

  if (options.mode === "compact-miner") {
    const compact = release.datasets.compactMiningNode.artifact;
    lines.push(
      `readonly DATASET_NAME=${shellQuote(compact.name)}`,
      `readonly DATASET_CID=${shellQuote(compact.cid)}`,
      `readonly DATASET_SHA256=${shellQuote(compact.sha256)}`,
      `readonly DATASET_BYTES=${compact.bytes}`,
      "readonly DATASET_ARCHIVE=\"$DOWNLOAD_DIR/$DATASET_NAME\"",
      "readonly DATASET_MANIFEST=\"$DOWNLOAD_DIR/compact-rc65.CANONICAL-DATA-MANIFEST.json\"",
      "download_ipfs \"$DATASET_CID\" \"$DATASET_ARCHIVE\"",
      `download_ipfs ${shellQuote(attestation.compactAdmission.manifestCid)} "$DATASET_MANIFEST"`,
      "[[ $(stat -c %s \"$DATASET_ARCHIVE\") == \"$DATASET_BYTES\" ]]",
      "printf '%s  %s\\n' \"$DATASET_SHA256\" \"$DATASET_ARCHIVE\" | sha256sum -c -",
      `[[ $(sha256sum "$DATASET_MANIFEST" | awk '{print $1}') == ${shellQuote(attestation.compactAdmission.manifestSha256)} ]]`,
      "python3 \"$PACKAGE_ROOT/ops/canonical_data_manifest.py\" verify --schema bdag.canonical-data-manifest.v3 --envelope \"$DATASET_MANIFEST\" --trusted-key-dir \"$PACKAGE_ROOT/trust/dataset\" >/dev/null",
    );
    installArgs.push("--dataset-archive", '"$DATASET_ARCHIVE"', "--dataset-manifest", '"$DATASET_MANIFEST"', "--no-archive");
  } else if (options.mode === "full-archive") {
    lines.push(...fullArchiveLines(release));
    installArgs.push("--dataset-archive", '"$DATASET_ARCHIVE"', "--dataset-manifest", '"$DATASET_MANIFEST"', "--full-archive");
  } else {
    installArgs.push("--no-archive");
  }

  const invocation = `bash \"$PACKAGE_ROOT/install.sh\" ${installArgs.join(" ")}`;
  if (options.profile === "mining") lines.push(`MINING_POOL_ADDRESS=\"$OWNER_PAYOUT\" ${invocation}`);
  else lines.push(invocation);
  return lines.join("\n");
}

function artifactLink(cid) {
  return `${GATEWAYS[0]}/${cid}`;
}

function fillArtifact(key, artifact, extra = {}) {
  const card = document.querySelector(`[data-artifact="${key}"]`);
  if (!card) return;
  card.querySelector('[data-field="size"]')?.replaceChildren(formatBytes(artifact.bytes ?? artifact.size_bytes));
  card.querySelector('[data-field="sha256"]')?.replaceChildren(artifact.sha256);
  card.querySelector('[data-field="cid"]')?.replaceChildren(artifact.cid ?? "multipart");
  if (extra.unpacked) card.querySelector('[data-field="unpacked"]')?.replaceChildren(formatBytes(extra.unpacked));
  if (extra.parts) card.querySelector('[data-field="parts"]')?.replaceChildren(String(extra.parts));
  const download = card.querySelector('[data-action="download"]');
  if (download && artifact.cid) download.href = artifactLink(artifact.cid);
}

function selectedOptions() {
  return {
    mode: document.getElementById("installMode").value,
    profile: document.getElementById("profile").value,
    dataDir: document.getElementById("dataDir").value.trim(),
    downloadDir: document.getElementById("downloadDir").value.trim(),
    wallet: document.getElementById("wallet").value.trim(),
    asicMacs: document.getElementById("asicMacs").value.trim(),
    dashboardBind: document.getElementById("dashboardBind").value,
  };
}

function updateFormForSelection() {
  const options = selectedOptions();
  const mining = options.profile === "mining";
  document.getElementById("walletField").hidden = !mining;
  document.getElementById("macField").hidden = !mining;
  const notice = document.getElementById("selectionNotice");
  if (options.mode === "upgrade") {
    notice.textContent = "Existing-data upgrade: downloads only the selected software package. It reuses the canonical data directory and downloads neither chain dataset.";
  } else if (options.mode === "compact-miner") {
    notice.textContent = `New mining node: allow at least ${formatBytes(EXPECTED.compact.bytes + EXPECTED.compact.unpackedBytes)} plus the filesystem reserve before starting.`;
  } else {
    notice.textContent = "Full archive: downloads 40 parts totalling 158.5 GiB, expands to about 254 GiB, and must catch up from EVM block 14,977,965.";
  }
}

function applyPreset(name) {
  const mode = document.getElementById("installMode");
  const profile = document.getElementById("profile");
  mode.value = name;
  profile.value = name === "full-archive" ? "public-rpc" : "mining";
  updateFormForSelection();
  document.getElementById("install")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTrustedRelease() {
  const release = state.release;
  const full = release.datasets.fullArchive;
  fillArtifact("linux-amd64", release.software.targets["linux-amd64"]);
  fillArtifact("linux-arm64", release.software.targets["linux-arm64"]);
  fillArtifact("compact", release.datasets.compactMiningNode.artifact, { unpacked: EXPECTED.compact.unpackedBytes });
  fillArtifact("full-archive", { bytes: full.size_bytes, sha256: full.sha256 }, { unpacked: full.unpacked_size_bytes, parts: full.delivery.parts.length });
  document.getElementById("trustDot").className = "status-dot ready";
  document.getElementById("trustStatus").textContent = "Signed RC65 records verified";
  document.getElementById("trustDetail").textContent = "The original release, page revision, presentation assets, and compact installer admission all match their approved trust roots.";
  document.getElementById("generateCommand").disabled = false;
  document.getElementById("installCommand").textContent = "Choose your path and generate the authenticated command.";
}

function renderFailure(error) {
  state.ready = false;
  document.getElementById("trustDot").className = "status-dot failed";
  document.getElementById("trustStatus").textContent = "Verification failed closed";
  document.getElementById("trustDetail").textContent = error instanceof Error ? error.message : String(error);
  document.getElementById("generateCommand").disabled = true;
  document.getElementById("copyCommand").disabled = true;
  document.getElementById("installCommand").textContent = "No command is available because signed release verification did not complete.";
}

async function initialize() {
  updateFormForSelection();
  document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => applyPreset(button.dataset.preset)));
  document.getElementById("installMode").addEventListener("change", updateFormForSelection);
  document.getElementById("profile").addEventListener("change", updateFormForSelection);
  document.getElementById("installForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const options = selectedOptions();
    const errors = validateOptions(options);
    const errorBox = document.getElementById("inputError");
    errorBox.hidden = errors.length === 0;
    errorBox.textContent = errors.join(" ");
    for (const input of document.querySelectorAll("input")) input.removeAttribute("aria-invalid");
    if (errors.length) return;
    const command = buildInstallCommand(state.release, state.attestation, options);
    document.getElementById("installCommand").textContent = command;
    document.getElementById("copyCommand").disabled = false;
  });
  document.getElementById("copyCommand").addEventListener("click", async () => {
    const command = document.getElementById("installCommand").textContent;
    try {
      await navigator.clipboard.writeText(command);
      document.getElementById("copyToast").textContent = "Authenticated command copied.";
    } catch {
      document.getElementById("copyToast").textContent = "Copy was blocked by the browser. Select the command text manually.";
    }
  });
  try {
    const authenticated = await authenticateRelease();
    Object.assign(state, authenticated, { ready: true });
    renderTrustedRelease();
  } catch (error) {
    renderFailure(error);
  }
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.addEventListener("DOMContentLoaded", initialize);
}
