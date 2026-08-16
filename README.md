# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.64`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.64/`

RC64 publishes the exact fleet-qualified AMD64 canonical-recovery node and
miner-friendly pool images for Chain ID 1404. It requires backup-backed,
one-way successor installation for an already-divergent protocol-45 database.
ARM64 is explicitly deferred and is not authorized by RC64.

Large software artifacts are not stored in Git. The release page records
immutable IPFS CIDs, byte sizes, SHA-256 values, signing-key fingerprints,
source revisions, and operator verification guidance.

RC64 keeps legacy-v45 observations out of native-safe mining readiness while
continuing the canonical feed. The signed record binds the exact node and pool
images, source commits, immutable artifact CIDs, signed discovery fallback,
fleet acceptance, fixed native/EVM anchors, and explicit platform scope.

Empty installs should pass the qualified snapshot transport explicitly as
`BDAG_RC64_SNAPSHOT_URL=https://ipfs.orbitor.dev/ipfs/bafybeibh3uotj3gz3rjyipnp6xrq5xekrqft7i2bjs5ypid7fv453p6twa`.
The signed CID, SHA-256, byte count, and checkpoints remain authoritative; the
gateway is transport only. Existing-data upgrades make no snapshot request.
