# Install or stage RC63 on AMD64

1. Download `verify-load-amd64.sh` from this release and inspect it. Run it as
   the ordinary Docker-capable operator, not as root:

   ```sh
   chmod 0755 verify-load-amd64.sh
   BDAG_RC63_BASE_URL=https://w3s.link/ipfs/bafybeic6lrevdxfv3tnv2tm6uktk7muleqg5iz3v3cigt3yq7qq2dzvrp4 \
     ./verify-load-amd64.sh "$PWD/blockdag-community-rescue-rc63-amd64"
   ```

   The public immutable install bundle contains the signed record, pinned
   public key, detached signature, and exact Docker archives. The loader
   downloads these files from the selected
   transport, then verifies the key fingerprint, signature, Chain ID, AMD64 scope, archive
   bytes and hashes, image labels, manifests, and node binary before loading
   either image. It does not restart containers or reconfigure ASICs.

2. Keep the serving stack live while staging. Preserve the current image IDs,
   Compose inputs, configuration, chain data, PostgreSQL data, owner payout
   address, Stratum endpoint, and a tested rollback path.

   If the local node needs an extended upgrade or catch-up, keep the same pool,
   PostgreSQL accounting, Stratum endpoint, and ASIC configuration. Qualify a
   parallel exact node first, pin its live peer identity, and require a block
   template whose coinbase is the existing owner's address. Switch only the
   pool's read and submission RPC backend, prove increasing accepted shares,
   and retain the local node for rollback. Do not configure an implicit ASIC
   failover pool.

3. For a pool-only image upgrade, use the signed
   `records/tools/cutover-pool-image-owner-safe.sh`. Supply the exact expected
   miner count and current owner payout address. The controller recreates only
   the existing pool container, keeps its backend and accounting topology,
   requires every live `authorized_worker` to equal the owner address, and
   proves increasing accepted shares. With zero miners it requires the exact
   `no_active_miners` state. Any failure restores the predecessor image.

4. For an already-divergent node, do not reuse or merge its writable database.
   Follow `recover-divergent-node.md`. A fresh compatible node may start from an
   empty successor data directory and sync normally after the signed image and
   fixed anchors are verified.

5. Cut over only after the successor is Chain ID 1404, has fresh peers, matches
   both fixed anchors, and advances without restart/OOM. Mining hosts must also
   show authorized physical miners, owner-correct jobs, and increasing accepted
   shares. Keep the predecessor and backup until sustained acceptance passes.

The release is AMD64-only. Do not substitute an ARM64 build or rebuild from a
moving branch and call it RC63.
