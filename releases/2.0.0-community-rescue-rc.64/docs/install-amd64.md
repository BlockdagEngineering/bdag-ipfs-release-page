# Install or upgrade RC64 on AMD64

RC64 supports `linux/amd64` only. ARM64 is deferred. Authenticate the signed
release record, bootstrap file, latest-data manifest, and exact image bytes with
`verify-load-amd64.sh` before changing a serving stack.

The GitHub release is an immutable archival mirror, while anonymous image
transport uses a pinned IPFS directory. Download the signed loader from this
Pages site and pass the public transport explicitly:

```bash
curl --fail --location --proto '=https' --tlsv1.2 \
  -o verify-load-amd64.sh \
  https://blockdagengineering.github.io/bdag-ipfs-release-page/releases/2.0.0-community-rescue-rc.64/verify-load-amd64.sh
chmod 0700 verify-load-amd64.sh
BDAG_RC64_BASE_URL=https://bafybeiavz3mso2z7kc2cfittkn3lfgjz7t7xvuarkrmo4ll6pccbzzjk4a.ipfs.dweb.link \
  ./verify-load-amd64.sh "$PWD/blockdag-community-rescue-rc64-amd64"
```

The directory CID is transport only. The loader pins the public-key
fingerprint and verifies the signed release, bootstrap and data manifests plus
the exact archive hashes, byte sizes, AMD64 image identities, and node binary.
It fails closed before stack changes on any mismatch.

## Existing canonical installation

Keep the current node, pool, Stratum endpoint, accounting database, peerstore,
chain data, payout mapping, and rollback images in service while staging RC64.
Run `install-or-reuse-data-amd64.sh` against the existing data directory. A
non-empty qualified directory is reused and no snapshot request is made.

Before staging images or data, forecast the peak filesystem impact. Retain the
larger of 20 GiB or 15% of that filesystem after the forecasted change. Preserve
the active data and images, release evidence, and one known-good rollback. If
space is short, identify exact inactive consumers and verify that no running
container, mount, process, or rollback references them before reclaiming them.
Never use a broad Docker prune, wildcard data deletion, or automatic cleanup of
operator-owned paths during an upgrade. Recheck capacity after any cleanup and
before cutover.

Prepare the replacement backend beside the live stack when host resources
permit. Require matching Chain ID 1404 genesis and fixed anchors, a clear
recovery latch, current native tip progress, a fresh native block template,
available submission, and the owner-correct payout identity. Cut over only at
readiness, then require increasing accepted shares. Roll back immediately if
native readiness or share growth fails.

`POOL_RPC_ROUTER_EVM_REFERENCE_URLS` is empty unless the operator explicitly
sets it. Empty means no external EVM request is made; local EVM telemetry and
fixed-anchor checks continue.

With `POOL_RPC_ROUTER_EVM_HEAD_GUARD_ENABLED=false`, the guard disabled mode
makes EVM or explicit-reference trouble advisory only while independently
native-safe evidence stays fresh. With the guard enabled, EVM readiness and
every explicit reference are strict mining prerequisites. Legacy-v45 relay
state is served canonical data but cannot make otherwise native-safe mining
unready.

The signed bootstrap list is a low-peer discovery fallback. Existing peerstore
and operator peers remain first. The loader merges and deduplicates fallback
addresses; discovery peers are not consensus authorities or readiness voters.
Public, LAN, and explicitly configured VPN dialing remain available.

## Empty installation

Only a genuinely empty data directory may use the signed latest-data snapshot.
Run `install-or-reuse-data-amd64.sh`. Before making a network request, it
requires enough free space for the signed archive, a conservative 32 GiB
extraction allowance, a 2 GiB staging margin, and the larger of 20 GiB or 15%
filesystem reserve. It then verifies the downloaded byte count, SHA-256,
signature, Chain ID, genesis, native/EVM checkpoint anchors, and clean shutdown
marker before starting the node. If IPFS transport is unavailable, leave the
directory empty and use ordinary authenticated peer synchronization.

Do not use the empty-install path to overwrite, merge, or reinterpret existing
data. Divergent or latched data requires the separate recovery procedure.
