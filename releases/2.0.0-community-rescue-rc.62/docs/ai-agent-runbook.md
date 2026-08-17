# BlockDAG Community Rescue RC62 — AI Agent Runbook

This runbook applies only to `2.0.0-community-rescue-rc.62`, sequence `62`,
chain ID `1404`.

## Fail-closed release identity

Before any installation or host mutation, require all of the following:

- release status is `published`;
- the release authorization manifest signature verifies;
- the release-key fingerprint is computed from canonical public-key DER;
- version, sequence, source lock, architecture, byte count, SHA-256, and CID
  match the published manifest;
- source commits are exactly:
  - stack `60c3c6fd66edf24f79aff8ae8e0f91a3d01adb2e`;
  - corechain `bb0f7a6fed918e56251aa602503c90f1e1f30cb8`;
  - pool `79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50`;
  - redis-dash `f00b654f79e50346bf6e866348cf07bdcb3b44ec`.

Reject an absent, draft, stale, downgraded, mismatched, or partially populated
identity. Never substitute an RC58 or RC59 artifact, and never treat the failed
RC60 or RC61 source tags as published releases.

## Installation contract

1. Run the generated bootstrap as the non-root owner of the extracted package.
2. Preserve `.env`, `node.conf`, node identity, node data, and continuity
   volumes.
3. Select exactly one profile: `mining`, `non-mining`, or `public-rpc`.
4. Default a fresh install to sync-only/no-miner.
5. Do not edit `install.sh`, `release-lock.json`, or another signed payload.
6. Do not bypass whole-package verification, rollback, quiescence, dataset, or
   release-key checks.
7. RC62 carries no dataset. Use existing compatible data or normal genesis
   synchronization.

## Closed RC58 failure

The privileged mining profile consumes `ops/local_chain_attestation.py`.
RC62 requires `load_privileged_profile_metadata()` and verified-install
recovery to load `LOCAL_CHAIN_ATTESTATION_PAYLOAD_FILES` before staging.
The regression contract requires every staged privileged file to have one
authenticated digest and forbids extra or duplicate inventory entries.

## Retry-safe local-peer controller

The installed service must execute:

`/usr/local/sbin/bdag-local-peers`

It reads `/etc/blockdag-pool/project-root`, validates the root-owned record and
non-symlink active stack files, then executes the active
`ops/update-local-peers.py`. The systemd unit must not embed a release-specific
working directory or script path.

When discovery finds an interrupted candidate with `adopted_from`, accept the
prior runtime only after authenticating both payload roots and proving exact
Compose, node-data, release-lock, chain, fork, and checkpoint identity.
Changed locks, identity mismatch, unsafe paths, symlinks, and arbitrary custom
`bdag-*` units must fail before service mutation.

## Bash 5.2-safe authenticated rollback

Candidate and authenticated prior-runtime repair locks must run as independent
private-FIFO background holders, not simultaneous Bash coprocesses. Each holder
must close the other plane's inherited writer before invoking its signed
watchdog. Controller rollback must propagate a real guard failure and return
explicit success only after the synchronous rollback command succeeds.

## Post-install evidence

Require:

- chain ID `0x57c`;
- advancing native and EVM heads;
- fresh peers and no canonical mismatch;
- the exact installed release lock and image identities;
- preserved Postgres and node-data continuity;
- no installer quarantine, incomplete transaction, or controlled-stop state;
- for mining, fresh template/submit readiness and an accepted block whose gross
  reward retains exact arbitrary-precision accounting.

If a gate fails, preserve the installer journal and signed evidence. Do not
delete databases, merge chain stores, modify a signed file, or guess a
workaround.
