Offline BlockDAG community rescue RC52 from one signed four-repository source lock.

RC52 fixes one pool-side coinbase accounting overflow. The node supplies reward in 1e8 atomic units, but the previous pool multiplied that value by 10^10 inside uint64 when converting it to Wei. Normal mainnet rewards exceed uint64 after conversion, so the ledger and payout path retained only the wrapped remainder.

For the observed era-26 input of 23,983,626,033 atomic units, the correct gross value is 239,836,260,330,000,000,000 Wei (239.83626033 BDAG). The old uint64 residue was 28,587,371,775,828,992 Wei. RC52 carries arbitrary-precision integers through reward conversion, the unchanged 1 percent pool fee, PPLNS credits, Postgres, maturity, and wallet payout.

The stack, corechain, and dashboard revisions are the exact RC44 revisions. The only advanced runtime source is the pool reward-accounting commit. Consensus subsidy calculation, header validation, staking distribution, the pool fee, PPLNS proportions, and maturity depths are unchanged.

RC52 applies prospectively to newly accepted blocks. It does not rewrite historical rows or guess an unpaid difference. Preserve Postgres and reconcile old blocks separately against canonical headers, transaction fees, PPLNS snapshots, payment history, and actual spendable coinbase or staking receipts.

Back up the ledger, authenticate the release key and signed manifests, verify the first post-upgrade block reward and fee, and confirm the protocol-level spendable receipt before resuming automated payouts.
