# Choosing and checking chain data

The software and chain data are separate. Choose one of these data paths:

1. **Keep existing valid data.** A normal reinstall does not require a new
   dataset. Keep target-local configuration and a compatible rollback.
2. **Start empty and synchronize from peers.** No dataset download is mandatory.
3. **Import this optional bootstrap or use your own valid copy.** The owner
   selects the expected hash/checkpoint. No publisher signature, official path,
   special `scratch` name, source identity or matching numeric UID makes copied
   bytes more or less authoritative. Actual read/write access and locking matter.

These data choices are distinct from the three service roles: node, pool and
dashboard. Pool-only and dashboard-only need remote service endpoints, not a
private copy of the blockchain database.

## What this published snapshot contains

`blockdag-chain1404-order20821036-20260907.bdsnap` is a format-4 full-bootstrap
snapshot containing **native chain plus EVM state** for mainnet, Chain ID 1404.
It is not a database of pool accounting, keys, workers or ASIC configuration,
and it is not a promise of complete historical archive state. This release does
not provide a second compact or archive variant. Older archive choices in
unchanged packaged documents refer to other releases and do not apply here.

- Size: 13,931,299,738 bytes.
- SHA-256: `8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608`.
- Native order: 20,821,036; hash: `0x5b1ba629a19da29e2a192fc59adc9a6d11d42f9dade40ae575f524988dc12209`.
- Native state root: `0x3026c846e8e7d4cfebbc35102ac0fc50231c3669d2d53281ae29d01aabc2db7f`.
- EVM number: 20,374,135; hash: `0x4845e973c4d5b7e3e8898d392e68bcef9e0f7cd6b6ed896be28f7e7d15a250cf`.
- EVM root: `0xbf50546f039605788b0fdeb1800aad765ae6da64e43afb313505a527770c7fdb`.

The snapshot is frozen at that boundary. Ordinary compatible-peer catch-up is
still required before mining. Advertised bootstrap peers are dated observations,
not consensus authority or an uptime guarantee. Preserve owner-configured peers,
normal discovery and all Chain ID/genesis and mining payout checks.

## Safe import and semantic verification

First follow [DOWNLOADS.md](DOWNLOADS.md) and verify the complete archive SHA-256.
Select `CORE_BIN` from the verified Core/full-ZIP payload for your architecture.
Set `SNAP` to the downloaded snapshot and `CANDIDATE` to a **new empty writable
network directory**. Quote paths, including paths with spaces. Never run import
against a directory opened by a node or an existing ledger.

```sh
"$CORE_BIN" snap verify --path "$SNAP"
"$CORE_BIN" snap import --datadir "$CANDIDATE" --path "$SNAP" --batch-size 16777216
"$CORE_BIN" dataset inspect --datadir "$CANDIDATE"
"$CORE_BIN" dataset manifest create --datadir "$CANDIDATE" --include-current-checkpoint
"$CORE_BIN" dataset verify --datadir "$CANDIDATE"
```

Use **`snap`**, not the different legacy `snapshot` command. Do not use
`--skip-evm`, `--no-network-check`, or weakened semantic checks. Compare the
reported chain/genesis and full native/EVM boundary with the owner-selected
record. Hashes alone do not establish that databases form a coherent chain.

`CANDIDATE` contains `BdagChain` and `bdageth/chaindata` directly after import.
Check the node's configured appdata/network-directory relationship before
mounting it; do not accidentally add a second `mainnet` directory. The CLI path
itself need not contain that name. Import is not an atomic live-node switch.
The companion's fresh-install path does not activate an existing dataset or
perform arbitrary ledger migrations.

If verification fails, keep the source and failed candidate separate. Report
the exact classification, expected/observed hashes and non-secret paths. Do not
erase markers, invent missing state, change Chain ID/genesis or weaken mining
gates to get a green status. Activation remains prohibited until applicable
interrupted operations and native/EVM mismatches are resolved.

An owner-selected existing copy may be verified using its own manifest and
trusted checkpoint instead of this published snapshot. Publisher provenance
is useful information, not mandatory permission. Two writers must never open
one dataset. Pool payout, PostgreSQL accounting, RPC authority, node identity
and ASIC ownership remain local to the receiving operator.
