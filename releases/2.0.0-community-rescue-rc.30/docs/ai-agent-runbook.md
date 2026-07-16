# AI Agent Runbook: BlockDAG Community Rescue RC30

Use this runbook to install or diagnose `2.0.0-community-rescue-rc.30` for a
non-technical operator. `release-manifest.json`, the signed software
authorization record, and the signed canonical-data manifest are authoritative.

## Fixed Identity

- Version: `2.0.0-community-rescue-rc.30`
- Release sequence: `30`
- Stack revision: `a0fb1ef7b979e5977728d6c6cb38f56d215fd719`
- Network: BlockDAG mainnet, chain ID `1404`
- Software targets: `linux-amd64`, `linux-arm64`
- Published data: portable v27, not archive-node equivalent
- Full archive data: pending and unavailable

RC30 retries only temporary startup RPC and peer-readiness states within a
bounded window. A canonical checkpoint or boundary mismatch, hash mismatch,
state-root mismatch, or network mismatch is terminal and must not be retried or
overridden.

## Safety Rules

1. Never request or expose a seed phrase, private key, node identity key, or
   service credential. Mining requires only a public payout address.
2. Collect ASIC Ethernet MAC addresses only for mining configuration.
3. Inventory CPU architecture, Linux, Docker, free space, mounts, current stack,
   data mode, and service state before changing anything.
4. Use absolute installer paths. Do not pass `~` in path arguments.
5. Force `curl -4 --http1.1`, retry and resume large downloads, then verify
   exact SHA-256 values.
6. Verify the release signature, release-key fingerprint, dataset envelope, and
   dataset-key fingerprint before extraction.
7. Preserve a rollback copy and never merge database subdirectories manually.
8. Do not weaken ownership, signature, checkpoint, archive-mode, or rollback
   protections to make an install proceed.

## Installation Choice

- **Software only:** retain compatible healthy data and install RC30.
- **Portable v27:** for mining pools and current-state RPC nodes; require
  `archive_node_equivalent=false` and use `--no-archive`.
- **Full archive:** unavailable in this publication. Do not improvise an
  archive restore from portable data.

Use the release-page command builder when possible. Software and data are
independently versioned; compatibility comes from signed records and installer
preflight, not matching filenames. The public command downloads the selected
software package directly from its IPFS CID and does not require repository
credentials.

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
continue through a chain-history or trust refusal. Known RC30 upgrade behavior:

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
current compatible peers, dashboard RC30 identity, no repeated fatal recovery
loop, valid pool shares, and accepted-block evidence when available. Containers
being up is insufficient.

On a repeated fatal startup, stop restart pressure, preserve logs and state,
and use the signed guarded dataset restore path. Report artifact hashes,
signature results, dataset version, checkpoint status, heads, peers, service
health, shares, and any in-place host corrections. Redact operator identity,
credentials, wallet/miner identifiers, private addresses, and unrelated paths.
