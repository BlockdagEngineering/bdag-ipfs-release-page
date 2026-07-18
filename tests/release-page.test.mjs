import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  artifactReady,
  buildInstallCommand,
  datasetPending,
  datasetReady,
  deliveryReady,
  formatBytes,
  gatewayTemplatesReady,
  isCid,
  isMacList,
  isSha256,
  isWallet,
  normalizeMacList,
  publicationReady,
  resolveInstallSelection,
  shellQuote,
} from "../releases/2.0.0-community-rescue-rc.30-page-v2/assets/release-page.mjs";


const syntheticHash = (character) => character.repeat(64);
const syntheticCid = (character) => `b${character.repeat(59)}`;

function syntheticArtifact(character, filename) {
  return {
    status: "published",
    filename,
    cid: syntheticCid(character),
    sha256: syntheticHash(character),
    size_bytes: 4096,
  };
}

function boundary(number, character, native = false) {
  const result = {
    [native ? "order" : "number"]: number,
    hash: `0x${syntheticHash(character)}`,
  };
  if (!native) {
    result.state_root = `0x${syntheticHash(character === "a" ? "b" : "a")}`;
  }
  return result;
}

function syntheticDataset({ archive, multipart }) {
  const base = archive ? "archive" : "portable";
  const first = archive ? "c" : "d";
  const second = archive ? "e" : "f";
  const parts = multipart
    ? [
        { filename: `${base}.part-001`, cid: syntheticCid(first), sha256: syntheticHash(first), size_bytes: 2048 },
        { filename: `${base}.part-002`, cid: syntheticCid(second), sha256: syntheticHash(second), size_bytes: 2048 },
      ]
    : [];
  return {
    status: "published",
    label: archive ? "Full archive-node dataset" : "Portable current-state dataset",
    archive_node_equivalent: archive,
    version: `${base}-test-fixture`,
    filename: `${base}.tar.zst`,
    sha256: syntheticHash(archive ? "a" : "b"),
    size_bytes: 4096,
    unpacked_size_bytes: 8192,
    delivery: multipart
      ? { mode: "multipart", cid: null, parts_manifest_path: `records/dataset/${base}-parts.json`, parts }
      : { mode: "direct", cid: syntheticCid(first), parts_manifest_path: null, parts: [] },
    canonical_manifest_path: `records/dataset/${base}-manifest.json`,
    canonical_manifest_sha256: syntheticHash(archive ? "c" : "d"),
    validation_spec_path: `records/dataset/${base}-validation.json`,
    native_boundary: boundary(100, "a", true),
    evm_boundary: boundary(90, "b"),
    fixed_checkpoint: boundary(80, "c"),
    ...(archive ? { archive_audit: { status: "passed" } } : {}),
  };
}

function pendingDataset(archive) {
  return {
    status: "pending",
    label: archive ? "Full archive-node dataset" : "Portable current-state dataset",
    archive_node_equivalent: archive,
    version: null,
    filename: null,
    sha256: null,
    size_bytes: null,
    unpacked_size_bytes: null,
    delivery: { mode: null, cid: null, parts_manifest_path: null, parts: [] },
    canonical_manifest_path: null,
    canonical_manifest_sha256: null,
    validation_spec_path: null,
    native_boundary: null,
    evm_boundary: null,
    fixed_checkpoint: null,
    ...(archive ? { archive_audit: null } : {}),
  };
}

function syntheticPublishedManifest({ portable = true, archive = true } = {}) {
  const anyDataset = portable || archive;
  return {
    schema: "bdag.community-release-index.v2",
    release: {
      version: "2.0.0-community-rescue-rc.30",
      sequence: 30,
      channel: "community-rescue",
      status: "published",
      chain_id: 1404,
      published_at: new Date(0).toISOString(),
    },
    runtime_change: {
      transient_startup_canonical_boundary_rpc: "bounded-retry",
      transient_startup_peer_readiness: "bounded-retry",
      canonical_mismatch: "fail-immediately",
    },
    source: {
      repository: "https://source.invalid/stack",
      release_url: "https://source.invalid/stack/releases/rc30",
      tag: "2.0.0-community-rescue-rc.30",
      stack_commit: "a0fb1ef7b979e5977728d6c6cb38f56d215fd719",
      corechain_commit: "b".repeat(40),
      pool_commit: "c".repeat(40),
      dashboard_commit: "d".repeat(40),
      source_lock_sha256: syntheticHash("e"),
    },
    trust: {
      release_key_path: "records/software/release-key.pem",
      release_key_sha256: syntheticHash("a"),
      dataset_key_path: anyDataset ? "records/dataset/dataset-key.pem" : null,
      dataset_key_id: anyDataset ? "dataset-test-key" : null,
      dataset_key_sha256: anyDataset ? syntheticHash("b") : null,
      dataset_verifier_path: "records/dataset/verify-manifest.py",
    },
    download_policy: {
      requires_ipv4: true,
      requires_http_version: "HTTP/1.1",
      ipfs_gateways: [
        "https://gateway-one.invalid/ipfs/{cid}",
        "https://gateway-two.invalid/ipfs/{cid}",
      ],
      software_http_fallback_base: null,
    },
    records_delivery: {
      mode: "ipfs-directory",
      cid: syntheticCid("g"),
      path_prefix: "records/",
    },
    installer: syntheticArtifact("c", "install-rc30.sh"),
    software: {
      independent_from_datasets: true,
      targets: {
        "linux-amd64": syntheticArtifact("d", "stack-linux-amd64.zip"),
        "linux-arm64": syntheticArtifact("e", "stack-linux-arm64.zip"),
      },
      records: {
        release_auth_manifest_path: "records/software/release-auth.json",
        release_auth_signature_path: "records/software/release-auth.json.sig",
        release_notes_path: "records/software/release-notes.md",
      },
    },
    datasets: {
      independent_from_software: true,
      portable: portable ? syntheticDataset({ archive: false, multipart: false }) : pendingDataset(false),
      full_archive: archive ? syntheticDataset({ archive: true, multipart: true }) : pendingDataset(true),
    },
    qualification: {
      status: "passed",
      signed_package_integrity_verified: true,
      portable_dataset_verified: portable,
      full_archive_dataset_verified: archive,
      restore_path_verified: true,
      runtime_path_verified: true,
    },
  };
}

test("published RC30 manifest unlocks a software-only installation", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.30-page-v2/release-manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  assert.equal(publicationReady(manifest), true);
  const command = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.doesNotMatch(command, /still a draft/);
  assert.match(command, /BDAG_RELEASE_SEQUENCE='30'/);
  assert.match(command, /case "\$\(uname -m\)"/);
  assert.match(command, /download_ipfs "\$PACKAGE_CID"/);
  assert.match(command, /openssl pkeyutl -verify/);
  assert.match(command, /Signed software authorization/);
  assert.match(command, /--profile non-mining/);
  assert.match(command, /^  --no-archive$/m);
  assert.match(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
  assert.doesNotMatch(command, /MINING_POOL_ADDRESS|POOL_ASIC_MAC_ALLOWLIST/);
  assert.doesNotMatch(command, /github\.com\/BlockdagEngineering/);
});

test("identity and transport validators reject malformed values", () => {
  assert.equal(isSha256(syntheticHash("a")), true);
  assert.equal(isSha256("not-a-hash"), false);
  assert.equal(isCid(syntheticCid("a")), true);
  assert.equal(isCid("cid-placeholder"), false);
  assert.equal(isWallet(`0x${"1".repeat(40)}`), true);
  assert.equal(isWallet("0x1234"), false);
  assert.equal(isMacList("aa:bb:cc:dd:ee:ff,11:22:33:44:55:66"), true);
  assert.equal(isMacList("not-a-mac"), false);
  assert.equal(normalizeMacList("AA:BB:CC:DD:EE:FF, 11:22:33:44:55:66"), "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66");
  assert.equal(gatewayTemplatesReady(["https://one.invalid/ipfs/{cid}", "https://two.invalid/ipfs/{cid}"]), true);
  assert.equal(gatewayTemplatesReady(["http://one.invalid/ipfs/{cid}"]), false);
});

test("direct and multipart artifact contracts are independently supported", () => {
  const direct = syntheticDataset({ archive: false, multipart: false });
  const multipart = syntheticDataset({ archive: true, multipart: true });
  assert.equal(deliveryReady(direct.delivery), true);
  assert.equal(deliveryReady(multipart.delivery), true);
  assert.equal(datasetReady(direct), true);
  assert.equal(datasetReady(multipart), true);
  assert.equal(datasetPending(pendingDataset(false), false), true);
  assert.equal(datasetPending(pendingDataset(true), true), true);
  assert.equal(artifactReady(syntheticArtifact("a", "software.zip")), true);

  const broken = structuredClone(multipart);
  broken.delivery.parts[0].sha256 = "broken";
  assert.equal(datasetReady(broken), false);
});

test("software publication does not require either dataset", () => {
  const softwareOnly = syntheticPublishedManifest({ portable: false, archive: false });
  assert.equal(publicationReady(softwareOnly), true);

  const wrongRetryPolicy = structuredClone(softwareOnly);
  wrongRetryPolicy.runtime_change.canonical_mismatch = "retry";
  assert.equal(publicationReady(wrongRetryPolicy), false);

  const missingPeerReadinessPolicy = structuredClone(softwareOnly);
  delete missingPeerReadinessPolicy.runtime_change.transient_startup_peer_readiness;
  assert.equal(publicationReady(missingPeerReadinessPolicy), false);
});

test("publication checks generalize to a later signed release identity", () => {
  const manifest = syntheticPublishedManifest();
  manifest.release.version = "2.0.0-community-rescue-rc.31";
  manifest.release.sequence = 31;
  manifest.source.tag = manifest.release.version;
  manifest.source.stack_commit = "f".repeat(40);

  assert.equal(publicationReady(manifest), true);
  const command = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.match(command, /BDAG_RELEASE_VERSION='2\.0\.0-community-rescue-rc\.31'/);
  assert.match(command, /BDAG_RELEASE_SEQUENCE='31'/);
  assert.match(command, /rc\.31 supports AMD64 and ARM64 Linux/);
});

test("a complete synthetic manifest unlocks only valid operator input", () => {
  const manifest = syntheticPublishedManifest();
  assert.equal(publicationReady(manifest), true);

  const missingWallet = buildInstallCommand(manifest, {
    profile: "mining",
    dataset: "none",
    dataDir: "/srv/blockdag/node-data",
    wallet: "",
    macs: "aa:bb:cc:dd:ee:ff",
  });
  assert.match(missingWallet, /valid public 0x payout wallet/);

  const badPath = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    dataDir: "relative/path",
  });
  assert.match(badPath, /absolute Linux data directory/);

  const badDownloadPath = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    dataDir: "/srv/blockdag/node-data",
    downloadDir: "relative/downloads",
  });
  assert.match(badDownloadPath, /absolute Linux download workspace/);
});

test("generated full-archive command is resumable, verified, and shell-valid", () => {
  const command = buildInstallCommand(syntheticPublishedManifest(), {
    profile: "mining",
    dataset: "full_archive",
    dataDir: "/srv/blockdag/node-data",
    wallet: `0x${"1".repeat(40)}`,
    macs: "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66",
  }, "https://release.invalid/index.html");

  assert.match(command, /curl -4 --http1\.1/);
  assert.match(command, /gateway-one\.invalid/);
  assert.match(command, /gateway-two\.invalid/);
  assert.match(command, /-C -/);
  assert.match(command, /sha256sum -c -/);
  assert.match(command, /cat 'archive\.part-001' 'archive\.part-002'/);
  assert.match(command, /DOWNLOAD_DIR='\/srv\/blockdag\/downloads'/);
  assert.match(command, /DATASET_ASSEMBLY_BYTES=4096/);
  assert.match(command, /DATASET_DOWNLOAD_BYTES \+ DATASET_ASSEMBLY_BYTES/);
  assert.match(command, /Download workspace must be outside the node-data directory/);
  assert.match(command, /Download workspace cannot be the filesystem root/);
  assert.match(command, /sudo install -d -m 0750/);
  assert.match(command, /cd "\$DOWNLOAD_DIR"/);
  assert.match(command, /^  --full-archive \\$/m);
  assert.doesNotMatch(command, /^  --archive(?: |$)/m);
  assert.match(command, /--dataset-trusted-key/);
  assert.match(command, /BDAG_RELEASE_VERSION='2\.0\.0-community-rescue-rc\.30'/);
  assert.match(command, /BDAG_RELEASE_SEQUENCE='30'/);
  assert.match(command, /export POOL_ASIC_MAC_ALLOWLIST='aa:bb:cc:dd:ee:ff,11:22:33:44:55:66'/);
  assert.match(command, /temporary\.replace\(path\)/);
  assert.match(command, /docker compose --profile mining up -d --no-build --pull never pool/);
  assert.match(command, /docker inspect/);
  assert.match(command, /grep -Fqx/);
  assert.match(command, /openssl pkeyutl -verify/);
  assert.match(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
  assert.doesNotMatch(command, /YOUR_PUBLIC|CID_FROM|SHA256_FROM/);

  const syntax = spawnSync("bash", ["-n"], { input: command, encoding: "utf8" });
  assert.equal(syntax.status, 0, syntax.stderr);
});

test("the full archive RPC preset is an exact fail-closed mapping", async () => {
  assert.deepEqual(
    resolveInstallSelection({
      preset: "full-archive-rpc",
      profile: "mining",
      dataset: "none",
      retention: "current",
    }),
    {
      preset: "full-archive-rpc",
      profile: "public-rpc",
      dataset: "full_archive",
      retention: "archive",
    },
  );

  const command = buildInstallCommand(syntheticPublishedManifest(), {
    preset: "full-archive-rpc",
    profile: "mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
    downloadDir: "/srv/blockdag/downloads",
  });
  assert.match(command, /--profile public-rpc/);
  assert.match(command, /^  --full-archive \\$/m);
  assert.match(command, /--dataset-archive/);
  assert.doesNotMatch(command, /MINING_POOL_ADDRESS|POOL_ASIC_MAC_ALLOWLIST/);
  const syntax = spawnSync("bash", ["-n"], { input: command, encoding: "utf8" });
  assert.equal(syntax.status, 0, syntax.stderr);

  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.30-page-v2/release-manifest.json", import.meta.url);
  const pendingManifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const pageUrl = new URL("../releases/2.0.0-community-rescue-rc.30-page-v2/index.html", import.meta.url);
  const page = await readFile(pageUrl, "utf8");
  assert.match(
    page,
    /data-preset="full-archive-rpc"[^>]*aria-disabled="true"[^>]*disabled/,
  );
  const pendingCommand = buildInstallCommand(pendingManifest, {
    preset: "full-archive-rpc",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.equal(pendingCommand, "# The selected dataset is not published and cannot be installed.");
});

test("every selectable role, dataset, and retention combination maps to the intended installer mode", () => {
  const manifest = syntheticPublishedManifest();
  const wallet = `0x${"1".repeat(40)}`;
  const macs = "AA:BB:CC:DD:EE:FF";
  const cases = [
    {
      label: "mining current-state software-only",
      options: { profile: "mining", dataset: "none", retention: "current", wallet, macs },
      expectedMode: "--no-archive",
      expectsDataset: false,
      expectsMining: true,
    },
    {
      label: "public RPC retaining compatible archive history",
      options: { profile: "public-rpc", dataset: "none", retention: "archive" },
      expectedMode: "--archive",
      expectsDataset: false,
      expectsMining: false,
    },
    {
      label: "node-only portable restore",
      options: { profile: "non-mining", dataset: "portable", retention: "archive" },
      expectedMode: "--no-archive",
      expectsDataset: true,
      expectsMining: false,
    },
    {
      label: "mining full archive restore",
      options: { profile: "mining", dataset: "full_archive", retention: "current", wallet, macs },
      expectedMode: "--full-archive",
      expectsDataset: true,
      expectsMining: true,
    },
  ];

  for (const entry of cases) {
    const command = buildInstallCommand(manifest, {
      ...entry.options,
      dataDir: "/srv/blockdag/node-data",
    }, "https://release.invalid/index.html");
    const modeFlags = command
      .split("\n")
      .map((line) => line.trim().split(/\s+/)[0])
      .filter((token) => ["--archive", "--no-archive", "--full-archive"].includes(token));

    assert.deepEqual(modeFlags, [entry.expectedMode], entry.label);
    assert.equal(command.includes("--dataset-archive"), entry.expectsDataset, entry.label);
    assert.equal(command.includes("POOL_ASIC_MAC_ALLOWLIST"), entry.expectsMining, entry.label);
    assert.match(command, new RegExp(`--profile ${entry.options.profile.replace("-", "\\-")}`), entry.label);
    assert.match(command, /Host preflight passed/, entry.label);
    assert.match(command, /Required command is unavailable/, entry.label);
    const syntax = spawnSync("bash", ["-n"], { input: command, encoding: "utf8" });
    assert.equal(syntax.status, 0, `${entry.label}: ${syntax.stderr}`);
  }
});

test("a pending dataset cannot produce an install command", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.30-page-v2/release-manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const command = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "full_archive",
    retention: "archive",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.equal(command, "# The selected dataset is not published and cannot be installed.");
});

test("signed records always use their immutable IPFS root regardless of page origin", () => {
  const manifest = syntheticPublishedManifest();
  const options = {
    profile: "non-mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
  };
  const command = buildInstallCommand(
    manifest,
    options,
    "https://example.ipfs.inbrowser.link/index.html",
  );
  assert.match(command, /download_ipfs_path/);
  assert.match(command, new RegExp(manifest.records_delivery.cid));
  assert.match(command, /'software\/release-auth\.json'/);
  assert.match(command, /RELEASE_AUTH_MANIFEST=/);
  assert.doesNotMatch(command, /inbrowser\.link|release\.invalid/);
});

test("shell quoting and byte formatting remain stable", () => {
  assert.equal(shellQuote("plain"), "'plain'");
  assert.equal(shellQuote("a'b"), `'a'"'"'b'`);
  assert.equal(formatBytes(null), "Pending");
  assert.match(formatBytes(4096), /4\.00 KiB/);
});
