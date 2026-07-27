import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  artifactIdentityReady,
  artifactReady,
  buildInstallCommand as productionBuildInstallCommand,
  datasetPending,
  datasetReady,
  deliveryReady,
  EXPECTED_RELEASE_IDENTITY,
  formatBytes,
  fullArchivePending,
  gatewayTemplatesReady,
  immutableRecordUrl,
  isCid,
  isSha256,
  isWallet,
  publicationReady as productionPublicationReady,
  resolveInstallSelection,
  shellQuote,
} from "../releases/2.0.0-community-rescue-rc.58/assets/release-page.mjs";


const syntheticHash = (character) => character.repeat(64);
const SYNTHETIC_CIDS = Object.freeze({
  a: "bafkreigks6arfsq3xxfpvqrrwonchxcnu6do76auprhhfomao6c273sixm",
  b: "bafkreib6epubmabzlffdhckpmvsodmjuro6xuaei2qwevs3t52xnlhaatu",
  c: "bafkreibopuwahkkqplrgl3hvwu2wrbnfgoj2eau5eqjzjglsmwq2ewxpyy",
  d: "bafkreiayvq7hgq7qc2eqyuiosp4tkjqrnhm6h5lfinsctaypv4etj5hy4q",
  e: "bafkreib7pg5xwq23auzbmuo257jxjtogqhoan6vgly3u4obtpoemubdn5i",
  f: "bafkreibff4imqnqq5pfbubm4boxievplul4vxzgr266pvcoxesfifwprce",
  g: "bafkreignbkuykykhw3c3j7zlpx7olwravi4ckmez54nuuzfm5urtzgx6fe",
  h: "bafkreifkvfacmzhruqpub254klezspvwnlvtmzqcswh57krihny6mtnrem",
  i: "bafkreig6punxegq6ayzlptye5x2qgleoz75j7gqijeqvfojg6gs2pz3f24",
});
const syntheticCid = (character) => SYNTHETIC_CIDS[character];
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

const TEST_EXPECTED_RELEASE_IDENTITY = Object.freeze({
  ...EXPECTED_RELEASE_IDENTITY,
  publicationFinalized: true,
  stackCommit: "a".repeat(40),
  corechainCommit: "b".repeat(40),
  poolCommit: "c".repeat(40),
  dashboardCommit: "d".repeat(40),
  sourceLockSha256: syntheticHash("e"),
  recordsCid: SYNTHETIC_CIDS.g,
  installer: Object.freeze({
    status: "published",
    filename: "bootstrap.sh",
    cid: SYNTHETIC_CIDS.h,
    sha256: syntheticHash("a"),
    size_bytes: 4096,
  }),
  targets: Object.freeze({
    "linux-amd64": Object.freeze({
      status: "published",
      filename: "pool-stack-docker-2.0.0-community-rescue-rc.58-linux-amd64.zip",
      cid: SYNTHETIC_CIDS.i,
      sha256: syntheticHash("b"),
      size_bytes: 4096,
    }),
    "linux-arm64": Object.freeze({
      status: "published",
      filename: "pool-stack-docker-2.0.0-community-rescue-rc.58-linux-arm64.zip",
      cid: SYNTHETIC_CIDS.a,
      sha256: syntheticHash("c"),
      size_bytes: 4096,
    }),
  }),
  releaseKeySha256: syntheticHash("f"),
});

const publicationReady = (manifest) => (
  productionPublicationReady(manifest, TEST_EXPECTED_RELEASE_IDENTITY)
);
const buildInstallCommand = (manifest, options = {}) => (
  productionBuildInstallCommand(
    manifest,
    options,
    TEST_EXPECTED_RELEASE_IDENTITY,
  )
);

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

function syntheticPublishedManifest({ portable = false, archive = false } = {}) {
  const anyDataset = portable || archive;
  const expected = TEST_EXPECTED_RELEASE_IDENTITY;
  return {
    schema: "bdag.community-release-index.v2",
    release: {
      version: expected.version,
      sequence: expected.sequence,
      channel: expected.channel,
      status: "published",
      chain_id: expected.chainId,
      published_at: new Date(0).toISOString(),
    },
    runtime_change: {
      transient_startup_canonical_boundary_rpc: "bounded-retry",
      transient_startup_peer_readiness: "bounded-retry",
      canonical_mismatch: "fail-immediately",
    },
    reward_safety: {
      coinbase_accounting: "arbitrary-precision-wei",
      automatic_payouts: "disabled-pending-staking-reconciliation",
    },
    source: {
      repository: expected.repository,
      release_url: expected.releaseUrl,
      tag: expected.version,
      stack_commit: expected.stackCommit,
      corechain_commit: expected.corechainCommit,
      pool_commit: expected.poolCommit,
      dashboard_commit: expected.dashboardCommit,
      source_lock_sha256: expected.sourceLockSha256,
    },
    trust: {
      release_key_path: "records/software/release-key.pem",
      release_key_sha256: expected.releaseKeySha256,
      dataset_key_path: anyDataset ? "records/dataset/dataset-key.pem" : null,
      dataset_key_id: anyDataset ? "dataset-test-key" : null,
      dataset_key_sha256: anyDataset ? syntheticHash("b") : null,
      dataset_verifier_path: anyDataset ? "records/dataset/verify-manifest.py" : null,
      dataset_verifier_sha256: anyDataset ? syntheticHash("c") : null,
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
      cid: expected.recordsCid,
      path_prefix: "records/",
    },
    installer: structuredClone(expected.installer),
    software: {
      independent_from_datasets: true,
      targets: structuredClone(expected.targets),
      records: {
        release_auth_manifest_path: "records/software/release-auth-manifest.json",
        release_auth_signature_path: "records/software/release-auth-manifest.json.sig",
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

test("a foreign published RC30 manifest cannot unlock the RC58 client", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.30-page-v2/release-manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  assert.equal(productionPublicationReady(manifest), false);
  const command = productionBuildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.match(command, /is not publication-ready/);
  assert.doesNotMatch(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
});

test("the real RC58 manifest is draft-locked now and must exactly unlock at finalization", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.58/release-manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const ready = productionPublicationReady(manifest);
  const command = productionBuildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.equal(ready, EXPECTED_RELEASE_IDENTITY.publicationFinalized);
  if (EXPECTED_RELEASE_IDENTITY.publicationFinalized) {
    assert.equal(manifest.release.version, EXPECTED_RELEASE_IDENTITY.version);
    assert.match(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
  } else {
    assert.match(command, /is not publication-ready/);
    assert.doesNotMatch(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
  }
});

test("identity and transport validators reject malformed values", () => {
  assert.equal(isSha256(syntheticHash("a")), true);
  assert.equal(isSha256("not-a-hash"), false);
  assert.equal(isCid(syntheticCid("a")), true);
  assert.equal(isCid(`b${"a".repeat(59)}`), false);
  assert.equal(isCid(`${syntheticCid("a")}a`), false);
  assert.equal(isCid("cid-placeholder"), false);
  assert.equal(isWallet(`0x${"1".repeat(40)}`), true);
  assert.equal(isWallet("0x1234"), false);
  assert.equal(gatewayTemplatesReady(["https://one.invalid/ipfs/{cid}", "https://two.invalid/ipfs/{cid}"]), true);
  assert.equal(gatewayTemplatesReady(["http://one.invalid/ipfs/{cid}"]), false);
});

test("the Pages privacy gate scans binary bytes and all private-key PEM headers", async () => {
  const root = await mkdtemp(join(tmpdir(), "rc58-pages-privacy-"));
  try {
    await writeFile(join(root, "index.html"), "<!doctype html>\n");
    await mkdir(join(root, "releases"));
    await writeFile(
      join(root, "releases", "binary-record.bin"),
      Buffer.concat([
        Buffer.from([0xff, 0xfe, 0x00]),
        Buffer.from("-----BEGIN ENCRYPTED PRIVATE KEY-----\n"),
        Buffer.from("-----BEGIN PGP PRIVATE KEY BLOCK-----\n"),
      ]),
    );
    const result = spawnSync(
      "python3",
      ["tests/validate_pages_artifact.py", root],
      { encoding: "utf8" },
    );
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /private key material/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
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

test("RC58 requires software-only publication with both datasets pending", () => {
  const softwareOnly = syntheticPublishedManifest({ portable: false, archive: false });
  assert.equal(publicationReady(softwareOnly), true);

  const wrongRetryPolicy = structuredClone(softwareOnly);
  wrongRetryPolicy.runtime_change.canonical_mismatch = "retry";
  assert.equal(publicationReady(wrongRetryPolicy), false);

  const missingPeerReadinessPolicy = structuredClone(softwareOnly);
  delete missingPeerReadinessPolicy.runtime_change.transient_startup_peer_readiness;
  assert.equal(publicationReady(missingPeerReadinessPolicy), false);

  const overclaimedPortable = syntheticPublishedManifest({ portable: true, archive: false });
  assert.equal(publicationReady(overclaimedPortable), false);

  const overclaimedArchive = syntheticPublishedManifest({ portable: false, archive: true });
  assert.equal(publicationReady(overclaimedArchive), false);
});

test("publication checks reject release identity drift", () => {
  const manifest = syntheticPublishedManifest();
  manifest.release.version = "2.0.0-community-rescue-rc.56";
  manifest.release.sequence = 56;
  manifest.source.tag = manifest.release.version;
  manifest.source.stack_commit = "f".repeat(40);

  assert.equal(publicationReady(manifest), false);
  const command = buildInstallCommand(manifest, {
    profile: "non-mining",
    dataset: "none",
    dataDir: "/srv/blockdag/node-data",
  });
  assert.match(command, /is not publication-ready/);
  assert.doesNotMatch(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
});

test("a complete synthetic manifest unlocks only valid operator input", () => {
  const manifest = syntheticPublishedManifest();
  assert.equal(publicationReady(manifest), true);

  const missingWallet = buildInstallCommand(manifest, {
    profile: "mining",
    dataset: "none",
    dataDir: "/srv/blockdag/node-data",
    wallet: "",
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

test("generated software-only command is resumable, verified, and shell-valid", () => {
  const command = buildInstallCommand(syntheticPublishedManifest(), {
    profile: "mining",
    dataset: "none",
    retention: "current",
    dataDir: "/srv/blockdag/node-data",
    wallet: `0x${"1".repeat(40)}`,
  }, "https://release.invalid/index.html");

  assert.match(command, /curl -4 --http1\.1/);
  assert.match(command, /gateway-one\.invalid/);
  assert.match(command, /gateway-two\.invalid/);
  assert.match(command, /-C -/);
  assert.match(command, /sha256sum -c -/);
  assert.match(command, /DOWNLOAD_DIR='\/srv\/blockdag\/downloads'/);
  assert.match(command, /DATASET_ASSEMBLY_BYTES=0/);
  assert.match(command, /DATASET_DOWNLOAD_BYTES \+ DATASET_ASSEMBLY_BYTES/);
  assert.match(command, /Download workspace must be outside the node-data directory/);
  assert.match(command, /Download workspace cannot be the filesystem root/);
  assert.match(command, /sudo install -d -m 0750/);
  assert.match(command, /cd "\$DOWNLOAD_DIR"/);
  assert.match(command, /^  --no-archive$/m);
  assert.doesNotMatch(command, /^  --(?:archive|full-archive)(?: |$)/m);
  assert.doesNotMatch(command, /--dataset-(?:archive|manifest|trusted-key)/);
  assert.match(command, /BDAG_RELEASE_VERSION='2\.0\.0-community-rescue-rc\.58'/);
  assert.match(command, /BDAG_RELEASE_SEQUENCE='58'/);
  assert.doesNotMatch(command, /POOL_ASIC_MAC_ALLOWLIST|ASIC MAC allowlist/);
  assert.match(command, /openssl pkeyutl -verify/);
  assert.match(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
  assert.doesNotMatch(command, /YOUR_PUBLIC|CID_FROM|SHA256_FROM/);

  const syntax = spawnSync("bash", ["-n"], { input: command, encoding: "utf8" });
  assert.equal(syntax.status, 0, syntax.stderr);
});

test("the RC58 full archive RPC preset remains unavailable and fail closed", async () => {
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
  assert.equal(command, "# The selected dataset is not published and cannot be installed.");

  const pendingManifest = syntheticPublishedManifest({ archive: false });
  const pageUrl = new URL("../releases/2.0.0-community-rescue-rc.58/index.html", import.meta.url);
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
  const cases = [
    {
      label: "mining current-state software-only",
      options: { profile: "mining", dataset: "none", retention: "current", wallet },
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
      label: "node-only current-state software-only",
      options: { profile: "non-mining", dataset: "none", retention: "current" },
      expectedMode: "--no-archive",
      expectsDataset: false,
      expectsMining: false,
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
    assert.equal(command.includes("MINING_POOL_ADDRESS"), entry.expectsMining, entry.label);
    assert.doesNotMatch(command, /POOL_ASIC_MAC_ALLOWLIST|ASIC MAC allowlist/, entry.label);
    assert.match(command, new RegExp(`--profile ${entry.options.profile.replace("-", "\\-")}`), entry.label);
    assert.match(command, /Host preflight passed/, entry.label);
    assert.match(command, /Required command is unavailable/, entry.label);
    const syntax = spawnSync("bash", ["-n"], { input: command, encoding: "utf8" });
    assert.equal(syntax.status, 0, `${entry.label}: ${syntax.stderr}`);
  }
});

test("neither pending RC58 dataset can produce an install command", () => {
  const manifest = syntheticPublishedManifest();
  for (const dataset of ["portable", "full_archive"]) {
    const command = buildInstallCommand(manifest, {
      profile: "non-mining",
      dataset,
      retention: "archive",
      dataDir: "/srv/blockdag/node-data",
    });
    assert.equal(command, "# The selected dataset is not published and cannot be installed.");
  }
});

test("signed records always use their immutable IPFS root regardless of page origin", () => {
  const manifest = syntheticPublishedManifest();
  const recordUrl = immutableRecordUrl(
    manifest,
    manifest.software.records.release_auth_manifest_path,
  );
  assert.match(recordUrl, new RegExp(manifest.records_delivery.cid));
  assert.match(recordUrl, /software\/release-auth-manifest\.json$/);
  assert.equal(immutableRecordUrl(manifest, "../foreign-record"), null);
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
  assert.match(command, /'software\/release-auth-manifest\.json'/);
  assert.match(command, /RELEASE_AUTH_MANIFEST=/);
  assert.doesNotMatch(command, /inbrowser\.link|release\.invalid/);
});

test("shell quoting and byte formatting remain stable", () => {
  assert.equal(shellQuote("plain"), "'plain'");
  assert.equal(shellQuote("a'b"), `'a'"'"'b'`);
  assert.equal(formatBytes(null), "Pending");
  assert.match(formatBytes(4096), /4\.00 KiB/);
});

test("the RC32 signed draft records exact software identities while every install path stays locked", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.32/release-manifest.json", import.meta.url);
  const pageUrl = new URL("../releases/2.0.0-community-rescue-rc.32/index.html", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const page = await readFile(pageUrl, "utf8");

  assert.equal(manifest.release.version, "2.0.0-community-rescue-rc.32");
  assert.equal(manifest.release.sequence, 32);
  assert.equal(manifest.release.status, "draft");
  assert.equal(manifest.records_delivery.cid, null);
  assert.equal(publicationReady(manifest), false);
  assert.equal(artifactIdentityReady(manifest.installer), true);
  assert.equal(artifactReady(manifest.installer), false);
  assert.equal(artifactIdentityReady(manifest.software.targets["linux-amd64"]), true);
  assert.equal(artifactIdentityReady(manifest.software.targets["linux-arm64"]), true);
  assert.equal(fullArchivePending(manifest.datasets.full_archive), true);
  assert.equal(manifest.qualification.full_archive_dataset_verified, false);
  assert.equal(manifest.qualification.runtime_path_verified, true);
  assert.equal(manifest.qualification.restore_path_verified, false);
  assert.match(
    page,
    /data-preset="full-archive-rpc"[^>]*aria-disabled="true"[^>]*disabled/,
  );

  const command = buildInstallCommand(manifest, {
    preset: "full-archive-rpc",
    dataDir: "/srv/blockdag/node-data",
    downloadDir: "/srv/blockdag/downloads",
  });
  assert.match(command, /is not publication-ready/);
  assert.doesNotMatch(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
});

test("a foreign published RC44 release cannot unlock the RC58 client", async () => {
  const manifestUrl = new URL("../releases/2.0.0-community-rescue-rc.44/release-manifest.json", import.meta.url);
  const pageUrl = new URL("../releases/2.0.0-community-rescue-rc.44/index.html", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const page = await readFile(pageUrl, "utf8");

  assert.equal(manifest.release.version, "2.0.0-community-rescue-rc.44");
  assert.equal(manifest.release.sequence, 44);
  assert.equal(manifest.release.status, "published");
  assert.equal(isCid(manifest.records_delivery.cid), true);
  assert.equal(publicationReady(manifest), false);
  assert.equal(artifactIdentityReady(manifest.installer), true);
  assert.equal(artifactReady(manifest.installer), true);
  assert.equal(artifactIdentityReady(manifest.software.targets["linux-amd64"]), true);
  assert.equal(artifactIdentityReady(manifest.software.targets["linux-arm64"]), true);
  assert.equal(datasetReady(manifest.datasets.full_archive), true);
  assert.equal(fullArchivePending(manifest.datasets.full_archive), false);
  assert.equal(manifest.datasets.full_archive.delivery.parts.length, 40);
  assert.equal(manifest.qualification.full_archive_dataset_verified, true);
  assert.equal(manifest.qualification.runtime_path_verified, true);
  assert.equal(manifest.qualification.restore_path_verified, true);
  assert.match(
    page,
    /data-preset="full-archive-rpc"[^>]*aria-disabled="false"/,
  );

  const command = buildInstallCommand(manifest, {
    preset: "full-archive-rpc",
    dataDir: "/srv/blockdag/node-data",
    downloadDir: "/srv/blockdag/downloads",
  });
  assert.match(command, /is not publication-ready/);
  assert.doesNotMatch(command, /bash "\$PACKAGE_ROOT\/install\.sh"/);
});
