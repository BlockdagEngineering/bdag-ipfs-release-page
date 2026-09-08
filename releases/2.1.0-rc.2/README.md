# BlockDAG 2.1.0-rc.2 consolidated develop prerelease

The exact downloads, sizes, SHA-256 values and native/EVM dataset boundary are in
`records/release.json`. The previous RC65 page and immutable artifacts are retained.
This release integrates Jeremy-owned work into `develop`; it does not promote
the four source repositories to `main`.

## Using the community page

Start with the [versioned installation companion](install-v1/index.html),
[operator commands](install-v1/INSTALL.md), [download guide](install-v1/DOWNLOADS.md)
or [AI-agent instructions](install-v1/AGENTS.md). These later instructions
supersede legacy signature/v1 and older dataset choices in the unchanged ZIP.
The three independent roles are **node-only**, **pool-only** (with its own
PostgreSQL and a compatible remote node), and **dashboard-only** (with Redis
and read-only observation endpoints). All-in-one is also supported.

Choose **Existing node** for the full runtime package, **New node** for optional
bootstrap data, or **One component** for a focused download. Match AMD64 or
ARM64 to your Linux machine. The generated commands require a native IPFS
command-line client and `sha256sum`; they download and check files only.
The browser gateway buttons are optional, best-effort alternatives.

This page retains RC65's community design while using the unchanged RC2
software and dataset records. Its own IPFS page CID changes when the
presentation changes; that does not change the software or dataset CIDs.

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
rate-limited; a native IPFS client uses the peer network directly. The separate
`install-v1/downloads.json` manifest describes the later anonymous HTTP mirror
and resumable dataset pieces. It does not alter the historical release record.
Hashes identify bytes, not a publisher: choose your expected hashes through a
channel you trust. No compulsory publisher signature or account is required.

Use the full runtime ZIP for `linux-amd64` (x86-64) or `linux-arm64` (AArch64),
with the versioned companion guide and its role-aware service runner.
Inspect `.env.example`, `node.conf.example`, compose files and scripts
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

Use `--mode all-in-one`, `node`, `pool` or `redis-dash`. The companion supplies a
working service runner while keeping configuration owner-local. `install`
stages verified components; `apply` selects them; `boot` starts services and
checks live identity. A component archive is not itself a complete PostgreSQL
deployment. Do not use historical
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
