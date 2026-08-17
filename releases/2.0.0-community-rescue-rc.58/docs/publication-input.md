# RC58 Signed Publication Record

RC58 is a software-only pool coinbase-accounting correction for BlockDAG
mainnet chain ID `1404`. Release sequence is `58`.

## Source And Artifact Identity

The release tag is `2.0.0-community-rescue-rc.58`.

The protected build run `30288138797`, attempt `2`, completed successfully at
stack commit `7642805f2a6c3195707985a2ca8a997cddbe04c6`. Its signed publication
attestation SHA-256 is
`109310bce3e8518690a759eae1ce9ee7fded549146b92d491db37f2e33f63929`.
The protected export tree SHA-256 is
`7f5edae07ee9d8393520c530715f44736f469205356055b1463d50e9d447dee7`.

Final software identities:

- release-key DER SHA-256:
  `26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb`
- source-lock SHA-256:
  `e7dadc8afac1592f9a22d2cbcd02bb7e0ce086577612b79e4af8bbb327f36f17`
- signed-record directory CID:
  `bafybeic5r7t5y6dpoprjbjps2yehjq2d4ovilsnv6ss4ixo45v3tu2zd6a`
- installer: `6,223` bytes, SHA-256
  `a946233e4de939a8fc5b41b7dc2a0d62e95db4cbda1d704789f2781bb5384d15`,
  CID `bafkreifjiyrt4tpjhgupyw2bw7ocudlc5fo3js62dvyepcpspan3kocncu`
- Linux AMD64 package: `480,461,478` bytes, SHA-256
  `8f0b544a3682e79e283be296a3f148d9121139236c4ffbcc2152f51fded25eb0`,
  CID `bafybeid3wexawynj3cnef7gy6jtewqo3fiaycs2bslz74tyd53rboqlbhm`
- Linux ARM64 package: `455,939,492` bytes, SHA-256
  `2e40729208f90a24a9b3de9e853bfd6400d1e6c3682ee28f54d8c36c82aa57c4`,
  CID `bafybeifv2bjsgovh6ze2iupq2ykaf3soqtoen7pr5x5mq3b7qob3g5ebsq`

All three software roots and every signed-record path passed local IPFS
readback before the release page was frozen. No artifact identity from RC52,
RC55, or another release was copied into RC58.

Four source commits are already fixed:

- stack commit: `7642805f2a6c3195707985a2ca8a997cddbe04c6`
- corechain commit: `bb0f7a6fed918e56251aa602503c90f1e1f30cb8`
- pool commit: `79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50`
- redis-dash commit: `f00b654f79e50346bf6e866348cf07bdcb3b44ec`

The stack commit has the exact RC55 tree. Corechain and redis-dash are intentionally
unchanged. RC58 makes no stack-source change; its software difference is the
pinned pool reward-accounting tree. The signed source-lock hash above binds
those exact clean repository states.

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

Both architecture builds passed native execution and ABI checks, package
privacy audits, deterministic installer smoke tests, signed-lock verification,
and independent archive readback. Production rollout still requires a
post-upgrade mature-block check against the exact regression vector.
