# BlockDAG Community Rescue RC58

BlockDAG `2.0.0-community-rescue-rc.58`, release sequence `58`, corrects the
pool's coinbase reward accounting on mainnet chain ID `1404`.

This page is a draft until the manifest contains final signed software
records, SHA-256 values, sizes, and immutable IPFS CIDs. Do not install the
draft.

## What It Fixes

The node reports reward in 1e8 atomic units. The old pool multiplied that
`uint64` value by `10^10` to convert it to Wei. A normal mainnet reward
overflows 64 bits after the multiplication, so the pool stored and credited a
small wrapped remainder.

RC58 converts the reward to arbitrary precision before scaling and preserves
exact values through the 1% fee, PPLNS allocation, Postgres, maturity, and
payout calculations.

```text
node reward          23,983,626,033 atomic units
correct gross           239.83626033 BDAG
1% pool fee               2.3983626033 BDAG
sole-account credit     237.4378977267 BDAG
old wrapped gross         0.028587371775828992 BDAG
```

At the demonstrated `4,259` accepted blocks/day, the corrected sole-account
credit is approximately `1,011,248.01 BDAG/day` per X100 after the unchanged
1% pool fee. Two X100s at the same individual accepted-block rate would total
approximately `2,022,496.01 BDAG/day`. Actual results depend on accepted block
count and network conditions.

The change does not alter the consensus subsidy formula, header validation,
protocol reward distribution, pool fee, PPLNS proportions, maturity, or miner
eligibility. RC58 publishes no dataset.

RC58 uses the exact RC55 stack tree
`7642805f2a6c3195707985a2ca8a997cddbe04c6`, with corechain and redis-dash
unchanged. Only the pool source pin changes, to
`79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50`.

## Before Upgrading

- Preserve the pool database and current chain data.
- Record the last accepted block, reward, fee, credits, and payouts.
- Keep automated payouts disabled until liquid and staked protocol receipts
  reconcile with corrected credits.
- Use only a public `0x...` payout address; never provide a seed phrase or
  private key.
- Confirm a supported 64-bit AMD64 or ARM64 Linux host with Docker Engine and
  Docker Compose v2.

## Install

After the release is finalized, open the release page and confirm sequence
`58`. Verify the signed authorization record, release-key fingerprint,
package SHA-256, immutable CID, architecture, and chain ID before using its
generated command.

Choose `Keep / sync`. RC58 publishes neither a portable dataset nor a full
archive, so preserve compatible data or let the node synchronize normally.
IPFS provides content-addressed transport; signed release records and
deterministic chain validation provide authority.

## Verify Before Restoring Hash Power

Require chain ID `0x57c`, advancing canonical heads, healthy services, ready
miners, and accepted blocks. For the regression input above, one mature block
must show:

- `239.83626033 BDAG` gross reward before transaction fees;
- `2.3983626033 BDAG` pool fee at 1%;
- `237.4378977267 BDAG` credited to a sole PPLNS account.

Actual daily earnings still depend on accepted block count and the network's
protocol-level reward distribution. Do not resume automatic payouts until
liquid and staked receipts fund the corrected ledger.

Do not multiply old rows or pay a guessed difference. Reconcile historical
rows separately from canonical headers, transaction fees, PPLNS snapshots,
payment history, and actual protocol receipts.
