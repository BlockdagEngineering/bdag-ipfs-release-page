# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.44`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.44/`

RC44 publishes signed AMD64 and ARM64 software and portable v27 data through
immutable IPFS CIDs. Its fail-closed full-archive RPC preset remains visible but
locked until the separately signed full-archive dataset is published.

Large software and dataset artifacts are not stored in Git. The release page
records immutable IPFS CIDs, GitHub software fallbacks, byte sizes, SHA-256
values, signing-key fingerprints, and canonical chain checkpoints.

RC44 software and portable v27 data are independent artifacts. Portable data
is published as three verified IPFS parts; the separately qualified full
archive dataset remains pending. All documented `curl` downloads force IPv4
and HTTP/1.1 for reliable public-gateway transfer. Generated commands fetch
signed records from a separate immutable IPFS directory, so they also work
when the setup page is opened through a service-worker gateway.
