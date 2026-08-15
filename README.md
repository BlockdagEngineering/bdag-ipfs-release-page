# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.63`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.63/`

RC63 publishes the exact fleet-qualified AMD64 canonical-recovery image for
Chain ID 1404. It requires backup-backed successor installation for an
already-divergent protocol-45 database. ARM64 is explicitly deferred and is not
authorized by RC63.

Large software artifacts are not stored in Git. The release page records
immutable IPFS CIDs, byte sizes, SHA-256 values, signing-key fingerprints,
source revisions, and operator verification guidance.

RC63 records its stock-v45 negative qualification evidence instead of claiming
ordinary peer sync can rewrite divergent DAG metadata. The signed record binds
the exact node and pool images, source commits, immutable artifact CIDs, fleet
acceptance, fixed native/EVM anchors, and explicit platform scope.
