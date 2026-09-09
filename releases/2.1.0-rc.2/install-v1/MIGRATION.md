# RC65 to 2.1.0-rc.2 migration: NOT QUALIFIED

> **NOT QUALIFIED.** Maintainer migration testing was not performed. This guide is documentation only. Community experimentation is at the owner's discretion; there is no promise of compatibility, safe in-place upgrade, or rollback by swapping back to an old binary.

The RC65 archive and this RC2 develop release are distinct. Do not treat RC2 fresh-install or TesterD mining evidence as RC65 migration evidence. Identify the exact RC65 variant and role before making any decision:

If an investigation needs RC2 bytes, bootstrap them through the verified
[download helper](DOWNLOADS.md) and companion checksum manifest first. Download
and hash verification are prerequisites only; they do not qualify a migration.

- **Node:** Core, native/EVM data, network identity, RPC and local configuration.
- **Pool:** Pool binary, PostgreSQL ledger/schema, payout/accounting settings, worker identity and the compatible Core endpoint.
- **Dashboard:** Dashboard/Redis observers and read-only endpoints; it must not gain Core, pool accounting or Docker lifecycle authority.

## Safe investigation outline

1. Inventory the exact RC65 variant, source/image/binary identities, role, owner-local settings, database/schema, data layout and free capacity read-only. Do not print credentials.
2. Make independently restorable, internally consistent backups of binaries, configuration and matching data. Include target-local payout, accounting, worker and identity state. Check backup capacity and restoration before proceeding.
3. Work only in a copied, isolated candidate with distinct paths, ports, project/network and test identities. Disable mining and payout automation, and fence access to live RPC and accounting. Never attach two writers to one dataset or ledger.
4. Investigate each role and each native/EVM/network/state boundary separately. Verify exact hashes, Chain ID/genesis, schema and ledger semantics. Process health is not chain, mining or payout acceptance.
5. An existing pool requires an exact compatible ledger/schema migration supplied by its owner and reviewed for that exact version. Do not invent generic SQL and never delete PostgreSQL to satisfy a fresh installer. Reusing old data with a new binary is not assumed safe.
6. Permit an intentional owner cutover only after the owner's exact checks pass, with one accounting writer and a retained compatible rollback state. Keep the old binaries/configuration **and their matching pre-migration data**. Retaining an old binary alone does not make candidate-mutated state safe to reopen; restore only a matching verified set.
7. If checks fail or assumptions change, stop and restore the appropriate compatible state. Preserve evidence and publish only redacted findings with exact versions, hashes, roles and observed results.

The following are read-only examples for an owner-approved inventory. They are
not migration commands, do not open databases, and deliberately avoid printing
environment values or secrets:

```sh
uname -m
df -h -- "$TARGET_ROOT"
docker ps --no-trunc --format '{{.ID}} {{.Image}} {{.Names}} {{.Status}}'
docker inspect --format '{{.Name}} image={{.Image}} mounts={{range .Mounts}}{{.Source}}:{{.Destination}};{{end}}' "$CONTAINER_NAME"
```

Replace the placeholders only with owner-selected, read-only targets. A private
inventory worksheet should capture: exact RC65 variant and source/image IDs;
role and architecture; binary/config/data paths (not secret contents); native
and EVM network/genesis identifiers; database engine and schema version;
owner-local payout/accounting/worker identity ownership; active writers and
ports; backup location, restore proof and free capacity; and the precise
compatibility questions still unanswered. Keep the worksheet private.

For a redacted finding, report the date, exact versions and hashes, role,
isolated candidate identity, checks performed, expected versus observed
results, backup/restore evidence, and next owner decision. Remove credentials,
wallets, payout addresses, private URLs, hostnames where sensitive and raw
environment files. Do not fill an unknown schema mapping with guessed SQL:
the owner must obtain and review the exact compatible migration for that Pool
version before any candidate mutation. No migration test is authorized by this
companion.

There is no one-command upgrade here, no automatic dataset activation and no migration test in this release work. The safe alternatives are to stay on RC65 or perform a separate fresh RC2 installation in a new target with owner-local identity, payout and accounting.

## Trust boundaries

Content integrity, attributed publisher identity and migration compatibility are separate claims. Hashes do not authorize a migration. A guide or another agent's PASS is not migration acceptance. Never disclose secrets, broad-reset a host, delete live data, overwrite a serving database or copy another operator's payout/accounting state.
