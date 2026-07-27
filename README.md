# BlockDAG Community Rescue Release Page

Static setup page, signed verification records, and operator guidance for the
BlockDAG community rescue releases.

Current release: `2.0.0-community-rescue-rc.58`

Public setup page:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Current release directory:

`releases/2.0.0-community-rescue-rc.58/`

RC58 publishes signed AMD64 and ARM64 software that restores full coinbase
reward precision through pool fee, PPLNS, database, and payout accounting.
It is a software-only correction: compatible existing chain data is retained,
and prior dataset publications keep their independent signatures and CIDs.

Large software artifacts are not stored in Git. The release page records
immutable IPFS CIDs, byte sizes, SHA-256 values, signing-key fingerprints,
source revisions, and operator verification guidance.

RC58 does not silently rewrite historical ledger rows and does not change the
consensus subsidy schedule. All documented `curl` downloads force IPv4 and
HTTP/1.1 for reliable public-gateway transfer. Generated commands fetch signed
records from a separate immutable IPFS directory, so they also work when the
setup page is opened through a service-worker gateway.
