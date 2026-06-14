# AI Agent Runbook: BlockDAG Community Pool Stack v6.3.20

Use the restore-first flow. Do not run a sync-only shortcut unless the human explicitly asks.

Permanent latest release page:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

Treat the IPNS name as the canonical mutable release pointer. Treat all payloads, checksums, helper scripts, docs, manifests, and chain-data archives as immutable IPFS CIDs that must be verified before use.

## Rules

- Never print, store, commit, or echo private keys.
- First run `uname -m`; use `linux-amd64` for `x86_64/amd64` and `linux-arm64` for `aarch64/arm64`.
- If using the bootstrap script, it downloads only the matching payload and stops. Restore chain data before `install.sh`.
- Ask directly for missing pool inputs; do not rely on a popup/modal tool being available.

## Commands

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl unzip zstd tar python3 iproute2 arp-scan nmap
mkdir -p ~/bdag-v6.3.20 && cd ~/bdag-v6.3.20
curl -fL https://ipfs.io/ipfs/bafkreidvo6thfpmzxgm7rvzr3cyrywuhyczt7chzqdcbnwhbcl5spynu34 -o install-v6.3.20.sh
chmod +x install-v6.3.20.sh
./install-v6.3.20.sh
cd pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
mkdir -p chain-download data/node/mainnet
curl -fL https://ipfs.io/ipfs/bafybeieyhcnszf7ksylee5dsdktkdgm5q45fiuaqjrqxmfsbksafs3crny -o chain-download/blockdag-mainnet-20260614-100022Z.tar.zst
echo "074d1cba6ae7ad3384157befe9527e38daa048348fdd6e3a22d05024e5e8d8b5  chain-download/blockdag-mainnet-20260614-100022Z.tar.zst" | sha256sum -c -
tar --zstd -xf chain-download/blockdag-mainnet-20260614-100022Z.tar.zst -C data/node/mainnet
```

Node-only:

```bash
BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

Pool mode: collect `MINING_POOL_ADDRESS`, optional private key entry preference, `BDAG_POOL_HOST`, and `BDAG_MINER_SCAN_TARGET`. Prefer hidden prompt for private key.

```bash
export MINING_POOL_ADDRESS='0xREPLACE_WITH_USER_PUBLIC_ADDRESS'
export BDAG_POOL_HOST='192.168.1.REPLACE'
export BDAG_MINER_SCAN_TARGET='192.168.1.0/24'
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

Validate with collector status and dashboard reachability. If `sync_progress.status` is not `synced`, keep pool mining paused until gates pass.
