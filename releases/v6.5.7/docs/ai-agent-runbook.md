# AI Agent Runbook: BlockDAG Community Pool Stack pool-v6.5.7

Use the IPFS-pinned payload CIDs for this release. The helper and payloads also have Filebase-pinned IPFS mirrors for gateway fallback. Do not assume GitHub assets exist for `pool-v6.5.7`.

Release metadata is in `release-manifest.json` on the setup page.
The bootstrap peer list is recorded in `peer-seeds.json`; the helper installs operator seeds plus live public service-port peers, preserves packaged seeds, excludes temporary high-port observed peers, and writes the deduplicated list into `node.conf` plus `BOOTSTRAP_PEER_ADDRESSES`.

## Rules

- Never print, store, commit, or echo private keys.
- First run `uname -s` and `uname -m`.
- Continue only on Linux.
- Use `linux-amd64` for `x86_64/amd64` and `linux-arm64` for `aarch64/arm64`.
- Prefer the release helper when digest verification is required before extraction.
- Do not replace packaged bootstrap peers; prepend only operator seeds and live public TCP 8150/8151/8152 Full|CF peers with matching peer IDs unless the operator explicitly supplies a different peer set.
- Ask directly for missing pool inputs; do not rely on a popup/modal tool being available.

## Verified Install

```bash
printf 'net.ipv6.conf.all.disable_ipv6 = 1\nnet.ipv6.conf.default.disable_ipv6 = 1\n' | sudo tee /etc/sysctl.d/99-bdag-disable-ipv6.conf >/dev/null
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 ca-certificates curl unzip zstd tar python3 iproute2 arp-scan nmap coreutils
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
docker --version
docker compose version
docker info
command -v curl unzip sha256sum zstd python3
mkdir -p ~/bdag-pool-v6.5.7 && cd ~/bdag-pool-v6.5.7
rm -f install-v6.5.7.sh
curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://ipfs.filebase.io/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh ||
  curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://ipfs.io/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh ||
  curl -4 --http1.1 -fsSL --connect-timeout 20 --speed-limit 1024 --speed-time 60 "https://dweb.link/ipfs/QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS" -o install-v6.5.7.sh
test -s install-v6.5.7.sh
chmod +x install-v6.5.7.sh
BDAG_CHAIN_MODE=non-archive ./install-v6.5.7.sh
```

## Restore-First Install

Use a host with at least 120 GB of disk. This reads SHA256 and size from the S3 latest snapshot metadata, downloads the archive with resume/retry, verifies it, extracts it into `data/node/mainnet`, and starts the installer:

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

Pool mode: collect `MINING_POOL_ADDRESS`, optional private key entry preference, `BDAG_POOL_HOST`, and `BDAG_MINER_SCAN_TARGET`. Prefer a hidden prompt for the private key.

```bash
export MINING_POOL_ADDRESS='0xREPLACE_WITH_USER_PUBLIC_ADDRESS'
export BDAG_POOL_HOST='192.168.1.REPLACE'
export BDAG_MINER_SCAN_TARGET='192.168.1.0/24'
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

Validate with collector status and dashboard reachability. If `sync_progress.status` is not `synced`, keep pool mining paused until gates pass.
For this helper revision, the peer overlay was pruned to remove high-port observed peers. Eleven release overlay seeds remain, and the v6.5.7 payload contributes 12 unique packaged seeds for 21 expected merged peers after dedupe.
