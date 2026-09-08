# RC2 companion instructions for AI agents

Read INSTALL.md, DOWNLOADS.md and DATASETS.md before acting. This versioned guide
supersedes legacy v1/catalog-signature instructions and older dataset choices
inside the immutable RC2 archives. Do not modify the original archives to make
their historical documentation agree with this later companion.

1. Ask which role is intended only if unclear: `node`, `pool`, `redis-dash` or
   `all-in-one`. These are lifecycle modes, not interchangeable tarballs.
2. Verify native architecture, exact downloaded manifest SHA, every selected
   archive SHA and the unchanged release tuple before extraction/execution.
   No publisher signature, account or central approval is mandatory. Do not
   reintroduce `--allow-unsigned-catalog` or v1 signature override flags.
3. Inventory existing services and data read-only. Fresh helper installation
   requires a new target and isolated project. Do not turn an existing system
   into a fresh install by deleting data, PostgreSQL or ownership records.
4. Use owner-local settings only. Never reuse an example payout address, another
   node's credentials, pool accounting, worker identity or ASIC lease. Never
   print secrets, signed redirect URLs, private environment files or wallet keys.
5. Node-only runs Core; pool-only runs Pool plus its own PostgreSQL and requires
   an explicit compatible Core endpoint; dashboard-only runs Dashboard/Redis
   with read-only observers and no Core lifecycle or Docker control authority.
6. Use the real companion runner and shipped v2 verify/plan/install/apply/boot.
   Staging is not boot. A running supervisor waiting for chain sync is not
   mining-ready. Report installed, running, syncing and mining separately.
7. Dataset choice is independent: retain valid local bytes, sync empty from
   peers, or import/verify an owner-selected copy. Hashes and native/EVM semantic
   consistency are both needed. No path-name or numeric-UID provenance rule
   confers chain validity. Capability, safe paths and database locking still do.
8. Import only into a new empty writable candidate. Use `snap`, not legacy
   `snapshot`. No skip-EVM/network bypass. Do not attach two writers or replace
   a serving dataset automatically. Retain predecessor and repair evidence.
9. Check disk reserve before download/import/build. Standard public hosted test
   runners do not have room for the full dataset. Do not claim a HEAD/Range probe
   or a mock hook proves a full download or real installation.
10. Accept according to exact test receipts. Native VM install/boot checks do not
    prove physical ASIC acceptance, block/accounting progression, reboot or soak.
    The original AMD64 mining receipt is separate and retains its 120-second
    claim ceiling. Do not rewrite historic immutable records to claim later work.

Use finite commands, resume verified downloads after interruption, and diagnose
the first failing layer. Do not retry unchanged failed mutations, continuously
restart healthy services, or rebuild unchanged qualified binary sources.
