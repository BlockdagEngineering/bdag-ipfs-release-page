# RC58 Draft Publication Record

RC58 is a software-only pool coinbase-accounting correction for BlockDAG
mainnet chain ID `1404`. Release sequence is `58`.

## Source And Artifact Identity

The release tag is `2.0.0-community-rescue-rc.58`.

The source lock, package hashes, sizes, signatures, release-key fingerprint,
records-directory CID, installer CID, and architecture package CIDs are
intentionally unset while the release is a draft. Publication must remain
locked until they are derived from the final build and verified. No artifact
identity from RC52, RC55, or another release may be copied into RC58.

Four source commits are already fixed:

- stack commit: `7642805f2a6c3195707985a2ca8a997cddbe04c6`
- corechain commit: `bb0f7a6fed918e56251aa602503c90f1e1f30cb8`
- pool commit: `79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50`
- redis-dash commit: `f00b654f79e50346bf6e866348cf07bdcb3b44ec`

The stack commit has the exact RC55 tree. Corechain and redis-dash are intentionally
unchanged. RC58 makes no stack-source change; its software difference is the
pinned pool reward-accounting tree. The derived source-lock hash stays unset
until confirmed by the final build record.

RC58 publishes no portable or full-archive dataset and therefore has no
dataset key, verifier, manifest, artifact, record, or pin.

## Reward Regression Vector

```text
input reward         23,983,626,033 atomic units
correct gross        239,836,260,330,000,000,000 Wei
correct gross               239.83626033 BDAG
fee at 1%              2,398,362,603,300,000,000 Wei
fee at 1%                    2.3983626033 BDAG
sole-account credit  237,437,897,726,700,000,000 Wei
sole-account credit          237.4378977267 BDAG
old uint64 residue        28,587,371,775,828,992 Wei
```

The prior pool performed atomic-to-Wei multiplication inside `uint64`, which
wrapped the valid mainnet reward. RC58 moves the conversion and downstream
fee, PPLNS, database, maturity, and payout calculations to arbitrary-precision
integers.

## Publication Boundaries

- Only pool coinbase reward accounting changes.
- Consensus subsidy and block-header validation remain unchanged.
- Protocol distribution, the 1% pool fee, PPLNS proportions, and maturity
  remain unchanged.
- Miner eligibility remains unchanged.
- Newly accepted blocks use corrected accounting; historical rows are not
  automatically changed.
- Automatic payouts remain disabled until corrected ledger credits reconcile
  with liquid and staked protocol receipts.
- No RC58 dataset or dataset pin may be added.

Final publication requires deterministic package tests, cryptographic
verification, public IPFS readback, and a post-upgrade mature-block check
against the exact regression vector.
