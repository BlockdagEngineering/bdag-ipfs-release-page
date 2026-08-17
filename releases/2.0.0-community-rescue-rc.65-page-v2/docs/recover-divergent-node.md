# Recover a divergent Chain ID 1404 node

Do not let a divergent, latched, corrupt, or stalled database serve the network
or mine. Recovery is authenticated, one-way, fail-closed, backup-backed, and
rollback-safe.

1. Stop the affected node's serving and mining paths. Preserve the old images,
   configuration, payout accounting, node identity, and a checksum-bound
   external backup of the complete divergent data.
2. Quarantine the divergent data read-only. Never use it as a donor or as a
   rollback target for a canonical serving state.
3. Create a separate writable successor directory. Exclude donor identity,
   peerstore, credentials, and recovery latch files.
4. Admit data only from an authenticated canonical donor or a signed RC65
   latest-data snapshot. Keep the successor isolated from untrusted peers and
   prevent reverse serving while it indexes and validates.
5. Independently validate Chain ID 1404, genesis, fixed native anchors, native
   hash and state root, EVM block hash and state root, latch state, and tip
   progress. Open ordinary peering only after those checks agree.
6. Sustain convergence against independent canonical hosts. Require no
   contradictory fixed-height hash, no reverse contamination, stable peer
   discovery, and normally closing head differences.
7. Stage the exact RC65 pool without changing the ASIC owner's payout identity.
   Enable mining only after native-safe template and submission readiness, then
   prove accepted-share growth.

Do not insert a data-backend migration into an ordinary image upgrade: reuse
the qualified serving directory so cutover is only a normal restart. If an
exceptional recovery also requires moving canonical data, make the first copy
while the serving rollback lane remains available, then run repeated warm deltas
and measure each transferred byte count. Quiesce the node only after the
projected final delta fits the declared downtime budget. Run one final delta
against the stopped database, require a zero-byte verification pass, and bind
or switch the new backend only after that check. Keep the untouched prior
backend immediately mountable until the new node passes identity, anchor,
health, peer, capacity, and tip-progress checks.

If any authentication, backup, anchor, convergence, payout, or readiness check
fails, stop the successor and retain the last canonical serving state and prior
image for rollback. Never roll back to the quarantined divergent state.
