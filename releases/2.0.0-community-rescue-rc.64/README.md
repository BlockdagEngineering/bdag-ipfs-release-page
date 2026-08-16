# BlockDAG community rescue RC64

RC64 supersedes RC63 for new installations and upgrades. RC63 remains
immutable as historical verification and rollback provenance.

RC64 is the fleet-qualified, AMD64-only community release for BlockDAG Chain
ID 1404. ARM64 is explicitly deferred. It publishes exact node and pool image
bytes, signed fallback peers, a signed identity-free data snapshot for empty
installations, and backup-backed divergent-node recovery guidance. It contains
no corechain, pool, or dashboard implementation source.

Qualified identities:

- node runtime: `sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02`
- node config: `sha256:7127ca53142c63e8061dc5cae218ccb84218f3130541ea58c344eabdfc55a38b`
- node binary: `3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19`
- pool runtime: `sha256:118bfca120162191449c6cca0e703815b365c2b0dbf4ad9732d69a3a151747ba`
- pool config: `sha256:eb4f110fab8b96be3225a172ff6bdfca50e1605270f66af8119eeb8bd7cc3646`
- platform: `linux/amd64`

Mining continuity and the ASIC owner's payout identity are release
properties. Stage and authenticate replacements while the serving stack mines.
Keep the existing Stratum endpoint, PostgreSQL accounting, payout mapping,
chain data, and rollback lane. Cut over only after native-safe readiness and
prove accepted-share growth immediately afterward.

`POOL_RPC_ROUTER_EVM_HEAD_GUARD_ENABLED=false` makes EVM health advisory only
while independent native evidence remains safe and fresh. It does not disable
EVM observation or permit a divergent, stale, peerless, submission-incapable,
or payout-incorrect node to mine. Setting the flag to `true` retains strict EVM
veto behavior.

`POOL_RPC_ROUTER_EVM_REFERENCE_URLS` defaults to empty. RC64 never silently
adds public RPC providers, so DNS, TLS, rate limits, provider outages, or a
provider observing another fork cannot become an undeclared mining dependency.
Explicit operator references remain advisory with the guard disabled and
strict with the guard enabled; no reference is a canonical oracle.

The signed `bootstrap-peers.txt` is discovery input only. Existing peerstore
and operator peers remain first; signed fallback peers are merged and
deduplicated when discovery is below threshold. They are not consensus
authorities or mining-readiness voters. Public, LAN, and explicitly configured
VPN dialing remain available. Automatic Headscale enrollment is deferred.

Normal upgrades reuse existing canonical data and make no snapshot request.
Only an empty installation uses the signed IPFS snapshot automatically.
Divergent, corrupt, latched, or stalled data follows the isolated, one-way,
backup-backed recovery procedure.

Every install or upgrade starts with a storage-impact forecast and preserves
the active stack, evidence, one known-good rollback, and the larger of 20 GiB
or 15% filesystem reserve. The empty-data helper checks download, extraction,
and staging headroom before contacting a gateway. Cleanup is limited to exact,
inactive, reproducible superseded artifacts after reference checks; RC64 never
performs a broad image prune or guesses that operator data is disposable.

Start with `verify-load-amd64.sh`, then follow `docs/install-amd64.md` or
`docs/recover-divergent-node.md`. Detached Ed25519 signatures and the pinned
public-key fingerprint are authority; a mirror, gateway, tag, or web page alone
is not.
