# BlockDAG community rescue RC63

RC63 is the fleet-qualified AMD64 successor for BlockDAG Chain ID 1404. ARM64
is explicitly deferred. The release record binds the exact node and pool
Docker/OCI archives, the recovery operations source, the owner-safe pool
cutover tool, fixed native/EVM anchors, and the final nine-host acceptance.

Qualified identities:

- node runtime: `sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02`
- node config: `sha256:7127ca53142c63e8061dc5cae218ccb84218f3130541ea58c344eabdfc55a38b`
- node binary: `3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19`
- pool runtime: `sha256:db0b7376d39e44dfbf35ced780fc2349e95f9bb197bc4ac8628de02e2c17c62c`
- pool config: `sha256:7aa238ff12706037f9064ecb22cedec8ae22dd42b216bd96efe88a53f0cc66fb`
- platform: `linux/amd64`

Mining continuity is a release invariant. Stage and authenticate replacements
while the current stack runs. Keep every ASIC on its existing Stratum endpoint
and explicit owner payout lane. A node-backend handoff must retain the same pool
and accounting database, pin the qualified backend identity, prove an
owner-address template before cutover, and prove accepted-share growth after
cutover. It is not an ASIC pool failover. If an owner-safe shadow path is
unavailable, use one bounded restart at final cutover rather than redirecting
the ASIC to an unverified payout account.

An already-divergent protocol-45 database must use the authenticated,
backup-backed successor procedure. Ordinary peer sync is not claimed to rewrite
divergent DAG selection metadata. Legacy peers may receive canonical relay data,
but their state cannot influence mining readiness or canonical selection.

Start with `verify-load-amd64.sh`, then follow the install or divergent-node
guide. The detached Ed25519 signature and pinned public-key fingerprint are
authority; a web page, mutable tag, build, or mirror alone is not.
