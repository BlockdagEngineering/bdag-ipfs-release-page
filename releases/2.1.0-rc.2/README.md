# BlockDAG 2.1.0-rc.2 consolidated develop prerelease

The exact downloads, sizes, SHA-256 values and native/EVM dataset boundary are in
`records/release.json`. The previous RC65 page and immutable artifacts are retained.
This release integrates Jeremy-owned work into `develop`; it does not promote
the four source repositories to `main`.

## Qualification

AMD64 passed a nominal 120-second test on TesterD (120.442 seconds observed).
All three physical ASICs advanced accepted work: 80 additional shares and 15
accepted block submissions. Target-local payout and accounting checks passed;
an independent node confirmed the selected block on its canonical chain.
The hash-bound summary is `records/mining-acceptance.json`.
ARM64 packages were built and their architecture/contents checked; ARM64
hardware, additional fleet, reboot and six-hour-soak qualification are not claimed.
Brief bounded parent-transition readiness pauses are expected and were recorded.

The separately published dataset passed full native+EVM byte verification, a
fresh independent import and semantic reinspection. This is a bootstrap dataset,
not a claim of complete historical archive state; ordinary catch-up remains
necessary.

## Download software

Use the software directory CID in the release record:

```sh
ipfs get /ipfs/bafybeicem6wyor5s4xq7436nnhfr2uj7ydh357tfdh3nzbziw7lx5v2taq -o blockdag-software-2.1.0-rc.2
cd blockdag-software-2.1.0-rc.2
sha256sum -c SHA256SUMS
```

The web page and record bind this exact CID. Public gateways may be slow or
rate-limited; a native IPFS client uses the peer network directly. No binary
mirror is published.
Hashes identify bytes, not a publisher: choose your expected hashes through a
channel you trust. No compulsory publisher signature or account is required.

Unpack the full runtime ZIP for `linux-amd64` (x86-64) or `linux-arm64` (AArch64).
Review its README, `.env.example`, `node.conf.example`, compose files and scripts
before configuring or starting services. Do not copy another operator's payout,
RPC authority, network identity, pool database, workers or ASIC configuration.

For a reinstall, preserve effective settings from every active compose override,
not only the base `.env`. The local redeploy helper stages files but does not
start services. Avoid historical duplicate compose labels when selecting the
current node; use exact container identity and keep the predecessor for rollback.

Independent component archives and v2 records are supplied for Core, Pool,
Dashboard and Stack. Explicit v2 commands start with, for example:

```sh
./scripts/bdag-stack verify --help
./scripts/bdag-stack install --root /your/downloaded/record-root --help
```

Use `--mode all-in-one`, `node`, `pool` or `redis-dash`. The explicit v2 lifecycle
requires your own configuration and service runner. `install` stages verified
components; `apply` activates through those owner-defined hooks. A component
archive is not itself a complete PostgreSQL deployment. Do not use historical
v1 signature/override flags or `--allow-unsigned-catalog` for this release.

## Bootstrap an independent dataset

Download the `.bdsnap` and compare its SHA-256 with the release record. Select
`CORE_BIN` from the verified Core payload for your architecture. Select a NEW,
EMPTY, writable `CANDIDATE` directory that is not opened by a node.

```sh
"$CORE_BIN" snap verify --path "$SNAP"
"$CORE_BIN" snap import --datadir "$CANDIDATE" --path "$SNAP"
"$CORE_BIN" dataset inspect --datadir "$CANDIDATE"
"$CORE_BIN" dataset manifest create --datadir "$CANDIDATE" --include-current-checkpoint
"$CORE_BIN" dataset verify --datadir "$CANDIDATE"
```

Use the `snap` alias: this binary also retains a different legacy `snapshot`
command. Do not use `--skip-evm`, `--no-network-check`, or relaxed semantic gates.
The candidate path is the network directory containing `BdagChain` and
`bdageth/chaindata`; it may have any usable owner-selected name. Import is not
atomic and must never run against an existing live dataset. Keep a failed
candidate separate for diagnosis. Connect only your chosen successfully
validated dataset to the target node, retaining the predecessor for rollback.
Existing valid chain data need not be replaced or downloaded again.

## Accounting and rollback

Pool53 supports fresh empty database initialization or unchanged Pool53 binary
reinstallation against an independently qualified compatible V2 ledger. This
release does not qualify generic older-ledger migration or old-schema downgrade.
`sql/pool-schema.sql` is the exact fresh schema; the fresh-only initializer
refuses an existing application database. Never erase PostgreSQL to pass that
guard. Retain the pool's own accounting history and compatible rollback.

Recent public bootstrap peers are advisory. Preserve owner-configured peers,
normal discovery, Chain ID 1404/genesis checks, payout protection and RPC access
controls. Their observation date is not a guarantee of future uptime.
