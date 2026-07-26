# BlockDAG Community Rescue RC52

BlockDAG `2.0.0-community-rescue-rc.52`, release sequence `52`, is a focused
software correction for mainnet chain ID `1404`.

## What It Fixes

The pool receives the block reward from the node in 1e8 atomic units and
converts it to Wei for accounting. The previous code performed that
multiplication in a 64-bit integer. A normal mainnet reward is larger than the
maximum 64-bit value after conversion, so the value wrapped before the pool
fee, PPLNS credits, database, and payout stages.

For the observed era-26 reward:

```text
node reward:       23,983,626,033 atomic units
correct gross:     239,836,260,330,000,000,000 Wei
old wrapped value:      28,587,371,775,828,992 Wei
```

RC52 carries the reward with arbitrary-precision integers through conversion,
the configured 1% pool fee, PPLNS distribution, Postgres, and wallet payout.
It does not change the node's subsidy calculation, block-header validation,
staking policy, miner-access policy, pool fee, PPLNS proportions, or maturity
depths. Stack, corechain, and dashboard remain pinned to their exact RC44
commits; only the pool accounting revision advances.

RC52 corrects new accepted blocks. It deliberately does not rewrite historical
blocks or credits because safe reconciliation requires the original block
headers, fees, PPLNS snapshots, payment history, and spendable coinbase
receipts.

## Before Upgrading

- Preserve a database backup and the current chain data.
- Record the last accepted block, credit, and payout.
- Pause automated payouts until the first post-upgrade reward is checked.
- Use a public `0x...` payout address only. Never provide a seed phrase or
  private key.
- Use 64-bit AMD64 or ARM64 Linux with Docker Engine and Docker Compose v2.

RC52 is software-only. It does not publish replacement chain data. Keep
compatible existing native and EVM data in place.

## Install

Open the release page, confirm it reports sequence `52`, choose the node role,
enter the public wallet when mining, and review the generated command.

The command:

1. checks the host and available space;
2. downloads the architecture-specific package from its immutable IPFS CID;
3. verifies SHA-256 and the release authorization signature;
4. checks the pinned release-key fingerprint and sequence;
5. runs the guarded installer from the signed package while keeping existing
   chain data.

All public downloads use IPv4, HTTP/1.1, retries, and resumable partial files.

## Verify Before Resuming Mining

After installation:

```bash
docker compose ps
curl -4 --http1.1 -fsS http://localhost:8088/ >/dev/null
curl -4 --http1.1 -fsS -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' \
  http://localhost:18545
```

Require all of the following:

- chain ID is `0x57c` (`1404`);
- native and EVM heads advance on the canonical chain;
- the pool accepts valid shares and submits accepted blocks;
- the first new `blocks.reward` equals the complete node template reward plus
  transaction fees, rather than a 64-bit remainder;
- `blocks.fees` equals the configured pool fee;
- PPLNS credits equal the distributable reward;
- the spendable coinbase receipt and protocol-level reward distribution are
  sufficient for the recorded credits before automated payouts resume.

At the observed reward, the gross block value should be approximately
`239.83626033 BDAG` before transaction fees. A sole PPLNS account receives
approximately `237.4378977267 BDAG` after the 1% pool fee. Actual daily results
still depend on accepted blocks and the network's consensus-level reward
distribution.

## Historical Reconciliation

Do not multiply old rows in place and do not pay a guessed difference.
Preserve the original ledger. Reconcile historical blocks in a separate,
reviewable process using canonical headers, transaction fees, PPLNS snapshots,
already-paid credits, and actual coinbase/staking receipts. Keep automated
payouts paused if those sources do not reconcile.

For assisted operation, use `docs/ai-agent-runbook.md`. Redact credentials,
private addresses, wallet/miner identifiers, and unrelated host data from any
support bundle.
