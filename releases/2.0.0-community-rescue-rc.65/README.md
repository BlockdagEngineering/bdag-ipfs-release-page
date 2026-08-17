# BlockDAG Community Rescue RC65

RC65 is the authenticated dual-architecture publication for Chain ID 1404. It
provides signed `linux/amd64` and `linux/arm64` software, plus two separately
authenticated new-install data choices: compact normal mining-node data and a
full archiver dataset.

The exact software, data CIDs, checksums, signatures, bootstrap peers, source
locks and provenance are bound by `records/release.json`. Run `verify-load.sh`
before selecting any software or dataset.

Existing qualified installations reuse their existing chain data. An upgrade
does not download either dataset. Only an empty new installation may select
one signed dataset. A missing, invalid, unsigned, or hash-mismatched input is
fail-closed before installation.

The full-archive v28 option is the previously signed archive-equivalent restore
through EVM block 14,977,965; an archiver catches up normally after restore.
The release contains no corechain, pool, or dashboard implementation source or
source maps. Unsupported architectures are rejected by the loader.
