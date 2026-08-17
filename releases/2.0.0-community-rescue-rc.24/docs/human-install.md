# BlockDAG Community Rescue RC24

This is a best-effort community rescue release for Linux AMD64 and ARM64.
The signed software and canonical v26 dataset are independent artifacts. You
can install the software without the dataset, restore v26 into a compatible
existing node, or use both together for the shortest path to a known state.

## Prepare First

For a mining pool, have these ready before starting:

- A public `0x...` BlockDAG payout wallet address. Never enter a seed phrase or
  private key into this installer or page.
- Every ASIC Ethernet MAC address, normally printed on the miner label or shown
  by the router. Use the form `aa:bb:cc:dd:ee:ff`.
- A 64-bit Linux host, Docker Engine, Docker Compose v2, `curl`, `unzip`,
  `sha256sum`, Python 3, `tar`, and `zstd`.
- At least 100 GB free for a mining node. The v26 download is 10.66 GB and
  expands to 19.32 GB before normal chain growth and operational headroom.

## Install Docker

Use Docker's current Linux packages for your distribution. Confirm:

```bash
docker --version
docker compose version
docker info
```

The installing account must be able to run Docker. Docker group membership is
equivalent to root access on that host.

## Download The Installer

All HTTP examples force HTTP/1.1 because some gateways and networks have been
unreliable with HTTP/2 for large release files.

```bash
curl -4 --http1.1 -fL --retry 8 --retry-all-errors \
  https://dweb.link/ipfs/bafkreiakbtrjskuchga5nx5gwamdhnh7gkouuqn63s33hoxfv424ywjhzi \
  -o install-community-rescue-rc24.sh
printf '%s  %s\n' \
  0a0ce2992a823981d6dfa6b01833b4ff329d4a41bedcb7b3bae5af35cc5927ca \
  install-community-rescue-rc24.sh | sha256sum -c -
chmod +x install-community-rescue-rc24.sh
```

## Mining Pool Without Dataset Restore

This starts from the selected empty or existing data directory and synchronizes
normally. Replace the example values.

```bash
export MINING_POOL_ADDRESS='0xYOUR_PUBLIC_PAYOUT_ADDRESS'
export POOL_ASIC_MAC_ALLOWLIST='aa:bb:cc:dd:ee:ff,11:22:33:44:55:66'
./install-community-rescue-rc24.sh \
  --profile mining \
  --data-dir /srv/blockdag/node-data \
  --no-archive
```

## Restore Canonical Dataset v26

Download with resume support. Re-running the command resumes the `.part` file.

```bash
DATASET=blockdag-evm-dataset-v26-20260714T115749Z.tar.zst
curl -4 --http1.1 -fL --retry 12 --retry-all-errors -C - \
  https://dweb.link/ipfs/bafybeicl52ju56z4gx4ph5b7lyw4stkuvsukmeykqfufw7w5nwvgrb6gru \
  -o "$DATASET.part"
mv "$DATASET.part" "$DATASET"
printf '%s  %s\n' \
  90c86826ef59a300698a788ffc9555be1c2ca1adb7c8b02c0c230bda07738118 \
  "$DATASET" | sha256sum -c -
```

Download the small verification records from the same release page, then check
the signed manifest:

```bash
python3 verify-canonical-manifest.py verify \
  --schema bdag.canonical-data-manifest.v3 \
  --envelope CANONICAL-DATA-MANIFEST.json \
  --trusted-key-dir dataset-trust
```

Install with authenticated restore:

```bash
export MINING_POOL_ADDRESS='0xYOUR_PUBLIC_PAYOUT_ADDRESS'
export POOL_ASIC_MAC_ALLOWLIST='aa:bb:cc:dd:ee:ff,11:22:33:44:55:66'
./install-community-rescue-rc24.sh \
  --profile mining \
  --data-dir /srv/blockdag/node-data \
  --no-archive \
  --dataset-archive "$PWD/$DATASET" \
  --dataset-manifest "$PWD/CANONICAL-DATA-MANIFEST.json" \
  --dataset-trusted-key qualification-v2-20260711="$PWD/dataset-trust/qualification-v2-20260711.pem"
```

Dataset v26 is producer-pruned and is not archive-node equivalent. Do not use
`--archive` with this dataset.

## Existing Node Restore

The dataset does not require a full stack reinstall. Use the signed installer
from any compatible release to perform a guarded restore into the chosen data
directory. Stop the existing stack first, keep a rollback copy until the new
node passes checkpoint checks, and never manually merge LevelDB or freezer
directories from different histories.

## Network And Dashboard

- Dashboard: `http://HOST:8088`
- BlockDAG P2P: TCP `8150`
- Pool Stratum: TCP `3334`
- Native RPC: TCP `38131`
- EVM HTTP RPC: TCP `18545`

Expose P2P publicly when required. Keep database, Docker socket, and internal
control endpoints private. Restrict RPC and dashboard access to trusted
networks unless you have deliberately configured a secure reverse proxy.

## What Success Looks Like

The node containers remain healthy, EVM checkpoint verification passes, peer
counts become current, the dashboard displays
`2.0.0-community-rescue-rc.24`, and a mining pool reports valid shares. Block
acceptance can take time and depends on connected hash power.

For assisted installation, give an AI coding agent the AI runbook from this
release page. Do not give any agent a wallet seed phrase or private key.
