# AI Agent Runbook: BlockDAG Community Rescue RC24

Use this runbook when assisting a non-technical operator. Treat
`release-manifest.json`, the signed software records, and the signed canonical
dataset manifest as the authority for artifact identity.

## Safety Rules

1. Never request, display, store, or transmit a wallet seed phrase or private
   key. The pool needs only a public payout address.
2. Confirm the host architecture, available storage, Docker Engine, and Docker
   Compose v2 before downloading large files.
3. Force HTTP/1.1 on every `curl` download. Use resume, retry, and checksum
   verification for the dataset.
4. Verify the installer SHA-256 before execution, the software archive SHA-256
   before extraction, the release signature/key fingerprint, and the dataset
   signed manifest before restore.
5. Do not combine native, EVM, freezer, or database directories from different
   histories. Use the transactional installer.
6. Do not use v26 with archive mode. The signed manifest states
   `archive_node_equivalent=false`.
7. Preserve an existing installation until the replacement passes health,
   checkpoint, peer-current, and mining checks.

## Release Identity

- Version: `2.0.0-community-rescue-rc.24`
- Release sequence: `24`
- Release key fingerprint:
  `26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb`
- Dataset: `v26`
- Dataset archive SHA-256:
  `90c86826ef59a300698a788ffc9555be1c2ca1adb7c8b02c0c230bda07738118`

## Workflow

1. Read `release-manifest.json` and `docs/human-install.md` completely.
2. Inventory CPU architecture, Linux distribution, free space, mounted data
   drives, Docker/Compose versions, and existing BlockDAG containers/data.
3. Ask for only the public payout address and ASIC MAC addresses when the
   operator chooses the mining profile.
4. Prefer the release helper. It selects AMD64/ARM64, downloads through IPFS or
   GitHub using HTTP/1.1, checks the exact package hash, and invokes the packaged
   installer.
5. If restoring v26, download the archive separately, verify its hash and
   signed canonical-data manifest, then pass all signed restore arguments to
   the installer.
6. Let one install attempt expose recoverable host issues. Fix safe host-local
   prerequisites in situ, record every issue, and continue far enough to expose
   downstream blockers before restarting the cycle.
7. After startup, verify all expected Compose services, dashboard version,
   native/EVM RPC, fixed EVM checkpoint, current peers, pool Stratum, valid
   shares, and accepted blocks when available.

## Required Post-Install Checks

```bash
docker compose ps
curl --http1.1 -fsS http://127.0.0.1:8088/ >/dev/null
curl --http1.1 -fsS -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_syncing","params":[]}' \
  http://127.0.0.1:18545
```

Use the packaged status and readiness tools for authoritative checkpoint and
mining-state checks. Do not declare success from container status alone.

## Handoff Report

Report the release version, package hash, dataset hash/version if used, data
directory, service health, native/EVM heights, checkpoint result, peer-current
state, valid-share count, and accepted-block evidence. Redact RPC passwords,
database passwords, node identity keys, public IP addresses when not needed,
and all operator-specific identifiers.
