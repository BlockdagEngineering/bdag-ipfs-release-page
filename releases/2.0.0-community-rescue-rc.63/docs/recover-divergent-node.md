# Recover a divergent protocol-45 node

This is a one-way, fail-closed AMD64 successor procedure.

1. Run `verify-load-amd64.sh` and require the exact signed node runtime
   `sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02`.
2. Record the current container/image/configuration/data identities and create a
   complete off-host backup or authenticated snapshot. Prove it is readable.
   Preserve peer identity keys separately. Do not stop a mining pool until the
   successor preparation and rollback proof are complete.
3. Stop all writers to the divergent database. Never merge files from divergent
   and canonical stores. Quarantine the old store intact, then use either an
   authenticated canonical snapshot or a fresh empty successor directory.
4. Start the exact RC63 node with mining disabled. During initial recovery,
   accept canonical data only from independently authenticated Chain ID 1404
   sources and do not expose the recovering node as a checkpoint, snapshot,
   mining, or recovery authority.
5. Require these settled anchors:

   - native order `17750631`, hash
     `0x444121faebccaa1422ddc773487c10912abf135de2847be422d715ab7663889c`,
     state root
     `0xadbfc8f92b484e10476fc1718f223f561bf9c8032626cf4ed22c6077b89a622c`
   - EVM block `0x108d0ee`, hash
     `0xc935d81d9d3956cbeabe5d3874e9a008c604b6ed320c0ed20781e3e448930ed1`,
     state root
     `0x9aa4e9e9e5af5734cc94e87ae9384747e7b383886ae5683d4c419ee93a1a6c5e`

6. Require advancing native/EVM heads, fresh peers, no recovery latch, and no
   restart/OOM. Independently compare with at least two canonical producers.
   A stale or divergent legacy relay is advisory only and cannot withdraw local
   canonical readiness.
7. For a mining host, keep its ASICs on the same Stratum endpoint and explicit
   payout address. Enable the pool only after owner-correct jobs are visible;
   require physical authorized miners and increasing accepted shares. If no
   owner-safe shadow path exists, a brief final restart is safer than redirecting
   rewards to another account.
8. On any signature, identity, anchor, containment, or liveness failure, stop
   the successor and restore the complete backup. Never combine failed successor
   data with rollback data.

RC63 records stock-v45 negative evidence honestly: data transfer occurred, but
ordinary v45 catch-up did not replace the divergent DAG/EVM selection. Recovery
therefore requires the authenticated successor boundary above.
