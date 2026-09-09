# AI runbook: RC65 to 2.1.0-rc.2 migration is NOT QUALIFIED

**STOP CONDITION:** RC65 to RC2 migration is **NOT QUALIFIED**. Maintainer migration testing was not performed. This document is a planning prompt, not executable migration authority. Never treat this guide, a package check, or another agent's PASS as migration acceptance.

Use this runbook only for a bounded, owner-authorized investigation of the exact RC65 variant and role (`node`, `pool`, or `dashboard`). Default to read-only discovery:

If RC2 bytes are needed for comparison, use the verified [HTTP/1.1 download
helper and checksum workflow](DOWNLOADS.md) first. That proves bytes only; it
does not grant migration authority or compatibility acceptance.

```text
Read the exact versions, source/image/binary identities, role, owner-local configuration names (not values), database/schema, data paths, network identity and capacity. Record evidence separately from hypotheses. Do not print secrets.

Before any mutation, ask the owner to confirm the exact target paths, backups, isolated ports/project/network, distinct test identity, disabled mining and payout automation, and fenced live RPC/accounting access. Refuse broad resets, deletes, guessed SQL, in-place writes, two writers, or any target that is not demonstrably isolated.

Require independently restorable backups of binaries, configuration and matching node/pool data, including payout/accounting state. For pools, require an exact reviewed compatible ledger/schema migration; never delete PostgreSQL to make a fresh installer pass. For nodes, verify native/EVM/network identity and state independently. For dashboards, preserve observer-only authority.

Make only the smallest explicitly authorized change to the named candidate. Re-read hashes, identity, schema, ownership, single-writer state and rollback evidence after each change. Stop immediately when an assumption, identity, compatibility result or rollback condition is uncertain. Never claim mining, payout, canonicality, compatibility or rollback from process health.

Allow owner cutover only after exact owner checks pass and matching rollback data remains available. An old binary retained on disk must not be run against candidate-mutated state. Otherwise restore the matching verified state, leave the live system untouched, and report precise redacted findings and versions.
```

The owner may instead retain RC65 or choose a separate fresh RC2 installation. No migration command, automatic update, live-data overwrite or migration test is supplied by this companion.
