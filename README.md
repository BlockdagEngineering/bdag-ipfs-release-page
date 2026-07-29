# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.62`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.62/`

RC62 publishes signed AMD64 and ARM64 software that corrects the complete
mining-profile digest inventory, makes the local-peer controller
release-independent, and makes interrupted-upgrade rollback deterministic on
Bash 5.2. It retains RC58's arbitrary-precision reward accounting.
RC62 is software-only: compatible existing chain data is retained or
synchronized normally, and prior dataset publications remain independent.

Large software artifacts are not stored in Git. The release page records
immutable IPFS CIDs, byte sizes, SHA-256 values, signing-key fingerprints,
source revisions, and operator verification guidance.

RC62 does not change consensus, chain ID, P2P rules, block production, miner
eligibility, or the consensus subsidy schedule. All documented `curl`
downloads force IPv4 and HTTP/1.1 for reliable public-gateway transfer.
Generated commands fetch signed records from a separate immutable IPFS
directory, so they also work when the setup page is opened through a
service-worker gateway.
