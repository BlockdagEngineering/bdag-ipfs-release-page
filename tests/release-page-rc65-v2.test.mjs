import assert from "node:assert/strict";
import { readFile, mkdtemp, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  authenticateRelease,
  buildInstallCommand,
  formatBytes,
  isAbsoluteSafePath,
  isWallet,
  normalizeMacList,
  shellQuote,
  validateOptions,
} from "../releases/2.0.0-community-rescue-rc.65-page-v2/assets/release-page.mjs";


const releaseRoot = new URL("../releases/2.0.0-community-rescue-rc.65-page-v2/", import.meta.url);
const release = JSON.parse(await readFile(new URL("records/release.json", releaseRoot), "utf8"));
const attestation = JSON.parse(await readFile(new URL("revision/page-v2.json", releaseRoot), "utf8"));
const wallet = "0x1111111111111111111111111111111111111111";

function options(overrides = {}) {
  return {
    allowUntrustedFixture: true,
    mode: "upgrade",
    profile: "mining",
    dataDir: "/srv/blockdag/node-data",
    downloadDir: "/srv/blockdag/downloads/rc65",
    wallet,
    asicMacs: "aa:bb:cc:dd:ee:ff",
    dashboardBind: "localhost",
    ...overrides,
  };
}

async function syntaxCheck(command) {
  const root = await mkdtemp(join(tmpdir(), "rc65-page-v2-"));
  try {
    const script = join(root, "install.sh");
    await writeFile(script, `${command}\n`, { mode: 0o700 });
    const result = spawnSync("bash", ["-n", script], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("input validators preserve shell and owner-payout safety", () => {
  assert.equal(isWallet(wallet), true);
  assert.equal(isWallet("0x0000000000000000000000000000000000000000"), false);
  assert.equal(isAbsoluteSafePath("/srv/blockdag/data"), true);
  assert.equal(isAbsoluteSafePath("/srv/blockdag/../data"), false);
  assert.equal(normalizeMacList("AA:BB:CC:DD:EE:FF,aa:bb:cc:dd:ee:ff"), "aa:bb:cc:dd:ee:ff");
  assert.equal(normalizeMacList("not-a-mac"), null);
  assert.equal(shellQuote("a'b"), `'a'"'"'b'`);
  assert.equal(formatBytes(16191131162), "15.1 GiB");
});

test("existing-data upgrade has no dataset download path", async () => {
  const command = buildInstallCommand(release, attestation, options());
  assert.match(command, /--profile \"\$PROFILE\"/);
  assert.match(command, /MINING_POOL_ADDRESS="\$OWNER_PAYOUT"/);
  assert.match(command, /--asic-mac-allowlist \"\$ASIC_MACS\"/);
  assert.doesNotMatch(command, /--dataset-archive|compact-rc65|full-archive-v28|bafybeih55jggjwl/);
  await syntaxCheck(command);
});

test("compact new-node command authenticates the exact archive and admission manifest", async () => {
  const command = buildInstallCommand(release, attestation, options({ mode: "compact-miner" }));
  assert.match(command, /bafybeih55jggjwlwhdkapsb2h3cp4yx7lt3a43chiwyvuyazrh7eekm6y4/);
  assert.match(command, /bafkreie7lwh7jxxv4qsbz26kzaz4xul5e3lmilbawrwce5uigppd3jihq4/);
  assert.match(command, /canonical_data_manifest\.py.*verify/);
  assert.match(command, /--dataset-manifest \"\$DATASET_MANIFEST\" --no-archive/);
  await syntaxCheck(command);
});

test("full archive command binds all 40 parts and the older catch-up manifest", async () => {
  const command = buildInstallCommand(release, attestation, options({
    mode: "full-archive",
    profile: "public-rpc",
    wallet: "",
    asicMacs: "",
  }));
  assert.match(command, /RC65_FULL_ARCHIVE_PARTS/);
  assert.match(command, /part-001/);
  assert.match(command, /part-040/);
  assert.match(command, /--full-archive/);
  assert.doesNotMatch(command, /bafybeih55jggjwl/);
  assert.equal((command.match(/\.tar\.zst\.part-[0-9]{3}\|/g) ?? []).length, 40);
  await syntaxCheck(command);
});

test("invalid payout, paths, MACs, and incompatible presets remain locked", () => {
  assert.ok(validateOptions(options({ wallet: "0x0" })).length > 0);
  assert.ok(validateOptions(options({ dataDir: "/srv/data\nrm -rf /" })).length > 0);
  assert.ok(validateOptions(options({ asicMacs: "aa:bb" })).length > 0);
  assert.ok(validateOptions(options({ mode: "compact-miner", profile: "non-mining" })).length > 0);
  assert.match(buildInstallCommand(release, attestation, options({ wallet: "$(id)" })), /^# Command locked:/);
});

test("actual browser authentication path verifies all signed local assets", async () => {
  const previousFetch = globalThis.fetch;
  try {
    assert.ok(globalThis.crypto?.subtle, "Node WebCrypto is required for the browser trust test");
    globalThis.fetch = async (path) => {
      const bytes = await readFile(new URL(String(path), releaseRoot));
      return {
        ok: true,
        status: 200,
        async arrayBuffer() {
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      };
    };
    const authenticated = await authenticateRelease();
    assert.equal(authenticated.release.version, "2.0.0-community-rescue-rc.65");
    assert.equal(authenticated.attestation.presentation.revision, 2);
    assert.equal(authenticated.compact.signed.archive_node_equivalent, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});
