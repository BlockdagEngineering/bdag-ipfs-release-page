# RC52 Publication Record

RC52 is a software-only reward-accounting correction for BlockDAG mainnet
chain ID `1404`.

## Source Identity

| Component | Commit |
| --- | --- |
| stack | `bda8cf1e5c73a8e0316ce302650310feb0538939` |
| blockdag-corechain | `bb0f7a6fed918e56251aa602503c90f1e1f30cb8` |
| pool | `79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50` |
| redis-dash | `f00b654f79e50346bf6e866348cf07bdcb3b44ec` |

Release tag: `2.0.0-community-rescue-rc.52`
Release sequence: `52`

Stack, corechain, and dashboard are the exact RC44 revisions. The sole runtime
component delta is the pool reward-accounting commit.

## Reward Regression Vector

```text
input reward:        23,983,626,033 atomic units
correct gross:       239,836,260,330,000,000,000 Wei
old uint64 residue:       28,587,371,775,828,992 Wei
fee at 1%:             2,398,362,603,300,000,000 Wei
sole-miner credit:   237,437,897,726,700,000,000 Wei
```

The pool test suite, static analysis, race checks, signed cross-architecture
release gates, package validation, and public IPFS readback form the release
evidence. Exact artifact identities and immutable delivery CIDs are recorded
in `release-manifest.json`.

## Publication Boundaries

- Consensus subsidy and staking policy are unchanged.
- No replacement chain dataset is published.
- Existing chain data is retained.
- New accepted blocks use corrected reward accounting.
- Historical credits are not automatically mutated.
- Automated payouts should resume only after the first post-upgrade block,
  ledger credit, and spendable protocol reward reconcile.
