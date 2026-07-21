# AI Agent Runbook: BlockDAG Community Rescue RC44

Use this runbook to install or diagnose `2.0.0-community-rescue-rc.44` for a
non-technical operator. `release-manifest.json`, the signed software
authorization record, and the signed canonical-data manifest are authoritative.

## Fixed Identity

- Version: `2.0.0-community-rescue-rc.44`
- Release sequence: `44`
- Publication state: draft; do not install until the manifest is published
- Stack revision: `bda8cf1e5c73a8e0316ce302650310feb0538939`
- Corechain revision: `bb0f7a6fed918e56251aa602503c90f1e1f30cb8`
- Pool revision: `80774b865b60e695b6e91a817013d9aeffc03271`
- Dashboard revision: `f00b654f79e50346bf6e866348cf07bdcb3b44ec`
- Network: BlockDAG mainnet, chain ID `1404`
- Software targets: `linux-amd64`, `linux-arm64`
- Published data: portable v27, not archive-node equivalent
- Full archive data: pending and unavailable

RC44 waits only for temporary committed-EVM-head and peer-readiness states
within bounded windows. A canonical checkpoint or boundary mismatch, hash
mismatch, state-root mismatch, or network mismatch is terminal and must not be
retried or overridden.

## Safety Rules

1. Never request or expose a seed phrase, private key, node identity key, or
   service credential. Mining requires only a public payout address.
2. Collect ASIC Ethernet MAC addresses only for mining configuration.
3. Inventory CPU architecture, Linux, Docker, free space, mounts, current stack,
   data mode, and service state before changing anything. The generated command
   performs a minimum preflight but does not replace rollback-capacity planning.
4. Use absolute installer paths. Do not pass `~` in path arguments.
5. Force `curl -4 --http1.1`, retry and resume large downloads, then verify
   exact SHA-256 values.
6. Verify the release signature, release-key fingerprint, dataset envelope, and
   dataset-key fingerprint before extraction.
7. Preserve a rollback copy and never merge database subdirectories manually.
8. Do not weaken ownership, signature, checkpoint, archive-mode, or rollback
   protections to make an install proceed.
9. A draft manifest is terminal for installation. Do not invent missing CIDs,
   bypass the page lock, or substitute RC31 artifacts.

## Installation Choice

- **Software only:** retain compatible healthy data and install RC44.
- **Portable v27:** for mining pools and current-state RPC nodes; require
  `archive_node_equivalent=false` and use `--no-archive`.
- **Full archive:** pending and locked in this draft. Do not improvise an
  archive restore from portable data or enable it before publication gates pass.

For software-only installs, select `--no-archive` for current-state retention
or `--archive` when deliberately retaining compatible archive history. A
future signed archive-equivalent restore must use `--full-archive`, not
`--archive`.

Use the release-page command builder when possible. Software and data are
independently versioned; compatibility comes from signed records and installer
preflight, not matching filenames. The public command downloads the selected
software package directly from its IPFS CID and does not require repository
credentials. The generated command must obtain signed software and dataset
records through `records_delivery.cid`, not by applying shell `curl` directly
to the current page origin. This is required for service-worker IPFS gateways.

For mining, require a non-empty MAC list. Confirm that the command persists
`POOL_ASIC_MAC_ALLOWLIST` in the installed `.env`, recreates the pool service,
and verifies the exact value through the running container configuration. For
public RPC, require an independently configured TLS edge proxy, host firewall,
per-client abuse controls, semantic health checks, monitoring, and restart
recovery before internet exposure.

## Download And Verify

For every IPFS object:

```bash
curl -4 --http1.1 --fail --location --show-error \
  --connect-timeout 20 --retry 12 --retry-delay 3 --retry-all-errors \
  --speed-limit 1024 --speed-time 90 -C - \
  '<GATEWAY>/<CID>' -o '<FILE>.part'
printf '%s  %s\n' '<EXPECTED_SHA256>' '<FILE>.part' | sha256sum -c -
```

For portable v27, verify all three parts, concatenate them in manifest order,
and verify the complete archive SHA-256 and size. Verify software authorization
with `openssl pkeyutl`, and verify the dataset with:

```bash
python3 records/dataset/verify-canonical-manifest.py verify \
  --envelope records/dataset/portable-v27-canonical-manifest.json \
  --trusted-key-dir records/dataset
```

Stop before extraction on any mismatch.

## In-Place Upgrade Handling

Use one pass to expose and record non-destructive host prerequisites, but never
continue through a chain-history or trust refusal. Known RC44 upgrade behavior:

- The stack root must be owned by the non-root runtime user.
- An interrupted bootstrap will not overwrite its extracted directory; resume
  with the existing extracted installer.
- Non-interactive sessions may lack a user D-Bus. Record the support-service
  warning and verify required system services directly.
- A legacy system-controller ownership check can reject
  `bdag-local-peers.timer` or `bdag-node-child-guard.timer`.

For the legacy controller case, inspect `sudo systemctl cat UNIT`. Proceed only
if the unit's commands reference the existing BlockDAG installation or
`/etc/blockdag-pool/project-root`. Back up that exact unit file, disable and
remove only the verified legacy BlockDAG unit, run
`sudo systemctl daemon-reload`, and rerun the installer. Never delete unrelated
or unverified units.

## Required Validation

```bash
docker compose ps
curl -4 --http1.1 -fsS http://localhost:8088/ >/dev/null
curl -4 --http1.1 -fsS -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' \
  http://localhost:18545
curl -4 --http1.1 -fsS -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":2,"method":"eth_syncing","params":[]}' \
  http://localhost:18545
```

Confirm chain ID `1404`, fixed checkpoint, native and EVM head advancement,
current compatible peers, dashboard RC44 identity, no repeated fatal recovery
loop, valid pool shares, and accepted-block evidence when available. Containers
being up is insufficient.

On a repeated fatal startup, stop restart pressure, preserve logs and state,
and use the signed guarded dataset restore path. Report artifact hashes,
signature results, dataset version, checkpoint status, heads, peers, service
health, shares, and any in-place host corrections. Redact operator identity,
credentials, wallet/miner identifiers, private addresses, and unrelated paths.
