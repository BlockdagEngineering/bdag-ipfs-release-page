# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.44`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.44/`

RC44 publishes signed AMD64 and ARM64 software, portable v27 data, and the
archive-equivalent full-archive v28 dataset through immutable IPFS CIDs. The
full-archive RPC preset uses the guarded `--full-archive` restore path.

Large software and dataset artifacts are not stored in Git. The release page
records immutable IPFS CIDs, GitHub software fallbacks, byte sizes, SHA-256
values, signing-key fingerprints, and canonical chain checkpoints.

RC44 software and both datasets are independent artifacts. Portable v27 is
published as three verified IPFS parts; full-archive v28 is published as 40
verified IPFS parts and covers every canonical EVM state root from genesis
through block 14,977,965. All documented `curl` downloads force IPv4 and
HTTP/1.1 for reliable public-gateway transfer. Generated commands fetch signed
records from a separate immutable IPFS directory, so they also work when the
setup page is opened through a service-worker gateway.
