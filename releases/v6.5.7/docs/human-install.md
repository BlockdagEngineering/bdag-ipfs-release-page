# BlockDAG Community Pool Stack pool-v6.5.7 Human Install Guide

This release publishes two Linux payloads pinned to immutable IPFS CIDs. The helper and payloads also have Filebase-pinned IPFS mirrors for gateway fallback.

- `linux-amd64` for `x86_64` or `amd64` hosts.
- `linux-arm64` for `aarch64` or `arm64` hosts.

Release metadata is in `release-manifest.json` on the setup page.
The bootstrap peer list is in `peer-seeds.json`; the helper installs operator seeds plus live public service-port peers, preserves packaged seeds, excludes temporary high-port observed peers, and writes the deduplicated list into `node.conf` and `BOOTSTRAP_PEER_ADDRESSES`.

Run this first:

```bash
uname -s
uname -m
```

Only Linux is supported by this release bootstrap.

## Prerequisites

On a clean Ubuntu host, install Docker and the required command-line tools first:

```bash
printf 'net.ipv6.conf.all.disable_ipv6 = 1\nnet.ipv6.conf.default.disable_ipv6 = 1\n' | sudo tee /etc/sysctl.d/99-bdag-disable-ipv6.conf >/dev/null
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 ca-certificates curl unzip zstd tar python3 iproute2 arp-scan nmap coreutils
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in, then verify:

```bash
docker --version
docker compose version
docker info
command -v curl unzip sha256sum zstd python3
```

## Required Inputs

For node-only mode, no wallet or private key is required.

For pool mode, prepare these before running the payload installer:

- `MINING_POOL_ADDRESS`: your public payout/mining wallet address.
- Pool operator private key: enter through a hidden prompt or secure local environment only.
- Pool host LAN IP for ASICs, for example `192.168.1.50`.
- ASIC scan CIDR, for example `192.168.1.0/24`.

## Pinned Payloads

The helper below selects the matching pinned payload CID, verifies the published SHA256 digest, extracts it, and runs the payload installer.
It also installs the pruned stable-port peer overlay before starting Docker. The v6.5.7 payload contributes 12 unique packaged seeds, and the helper adds 11 overlay seeds for 21 expected merged peers after dedupe.

## Verified Helper

This repository also includes a helper that verifies the published SHA256 digest before extraction:

```bash
mkdir -p ~/bdag-pool-v6.5.7 && cd ~/bdag-pool-v6.5.7
rm -f install-v6.5.7.sh
curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://ipfs.filebase.io/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh ||
  curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://ipfs.io/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh ||
  curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://dweb.link/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh
test -s install-v6.5.7.sh
chmod +x install-v6.5.7.sh
BDAG_CHAIN_MODE=non-archive ./install-v6.5.7.sh
```

To download, verify, and extract without starting the packaged installer:

```bash
BDAG_SKIP_PAYLOAD_INSTALL=1 ./install-v6.5.7.sh
```

Then enter the extracted payload directory:

```bash
cd pool-stack-docker-pool-v6.5.7-linux-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
```

## Manual Verification

AMD64:

```bash
curl -4 --http1.1 -fL --connect-timeout 20 --speed-limit 1024 --speed-time 60 https://ipfs.filebase.io/ipfs/QmVYwag8QduE1JTJV7U6Y2m23C3GGhfHMQEzzxhsUuedAy -o pool-stack-docker-pool-v6.5.7-linux-amd64.zip ||
  curl -4 --http1.1 -fL --connect-timeout 20 --speed-limit 1024 --speed-time 60 https://ipfs.io/ipfs/bafybeibc562phfnizztpulf76p57dvhw3xl7kv6zwmhjwu37iglk4sizua -o pool-stack-docker-pool-v6.5.7-linux-amd64.zip
echo "8d292703d77b656d85bfabf16df7b4ce4f86454a5c075a3c292a5b00f08bd852  pool-stack-docker-pool-v6.5.7-linux-amd64.zip" | sha256sum -c -
```

ARM64:

```bash
curl -4 --http1.1 -fL --connect-timeout 20 --speed-limit 1024 --speed-time 60 https://ipfs.filebase.io/ipfs/QmfXXCaWfxGjfRSaxG4cBYU43H61XHafeFxGZmMhtSTbX4 -o pool-stack-docker-pool-v6.5.7-linux-arm64.zip ||
  curl -4 --http1.1 -fL --connect-timeout 20 --speed-limit 1024 --speed-time 60 https://ipfs.io/ipfs/bafybeibobaofgsdlingiday5ea3hf62rludb4u5n6lgxaj3mgjbv35goqe -o pool-stack-docker-pool-v6.5.7-linux-arm64.zip
echo "53ac85c8f6337fd1d0cebbc17c3cf17804f371dcaf2270515e196c4223e50c6c  pool-stack-docker-pool-v6.5.7-linux-arm64.zip" | sha256sum -c -
```

## Restore-First Install

Use a host with at least 120 GB of disk. This command reads SHA256 and size from the S3 latest snapshot metadata, downloads the archive with resume/retry, verifies it, extracts it into `data/node/mainnet`, and starts the installer:

```bash
BDAG_RESTORE_SNAPSHOT=1 BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive ./install-v6.5.7.sh
```

Snapshot source:

- S3 URL: `https://blockchain-state-backup.s3.us-west-1.amazonaws.com/blockdag-miner-backups/ipfs-snapshots/latest/bdag-latest-snapshot.tar.gz`
- Archive: `bdag-latest-snapshot.tar.gz`
- Current size: `9,977,967,053 bytes`
- Current SHA256: `40bce74b03d08f68dd97c466b174cbcb65f96500a48b9a028743007f48d66595`

Node-only restore:

```bash
BDAG_RESTORE_SNAPSHOT=1 BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive ./install-v6.5.7.sh
```

Start pool mode:

```bash
export MINING_POOL_ADDRESS='0xYOUR_PUBLIC_ADDRESS'
export BDAG_POOL_HOST='192.168.1.50'
export BDAG_MINER_SCAN_TARGET='192.168.1.0/24'
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

## Success Checklist

```bash
curl -s http://127.0.0.1:9280/api/status | python3 -m json.tool
ss -ltnp | grep -E '(:8150|:3334|:8088|:9280|:38131|:18545)'
```

Expected: dashboard reachable on `8088`, sync status eventually `synced`, remaining blocks `0`, `can_accept_shares=true`, and ASICs visible after they point to `stratum+tcp://<pool-host-lan-ip>:3334`.
