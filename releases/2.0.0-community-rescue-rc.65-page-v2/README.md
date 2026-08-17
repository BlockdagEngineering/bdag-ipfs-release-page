# BlockDAG Community Rescue RC65 page v2

This immutable presentation revision adds the guided community release
experience and an installer-compatible compact-data admission manifest. It
does not change or replace the signed RC65 software, compact snapshot, full
archive, bootstrap peers, or original `records/` subtree.

Run `verify-load-v2.sh` before using generated commands. It first authenticates
the byte-identical original RC65 records, then verifies the separately signed
page revision, presentation assets, and compact canonical-data manifest.

Existing qualified nodes reuse their current data and download no chain
snapshot. New normal mining nodes may use the compact snapshot. New archive
operators may use the signed 40-part v28 archive through EVM block 14,977,965
and then catch up from ordinary Chain ID 1404 peers.

The release page contains compiled assets and reviewed verification utilities,
but no corechain, pool, or dashboard implementation source and no source maps.
IPFS gateways and bdag.community are not trust authorities or runtime
dependencies.
