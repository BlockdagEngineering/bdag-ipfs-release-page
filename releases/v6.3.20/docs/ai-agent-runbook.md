# AI Agent Runbook: BlockDAG Community Pool Stack v6.3.20

Goal: install node-only or full pool stack from the IPFS release, preferably after restoring the chain-data archive so the node only catches up the final blocks.

Rules:

- Never reveal, log, commit, or echo private keys. If a user supplies `POOL_PRIVATE_KEY`, treat it as secret.
- Do not configure ASIC miners unless the user explicitly asks and provides credentials. Read-only LAN discovery is acceptable.
- Use this ARM64 payload only on `aarch64`/`arm64` Linux hosts.
- Download and verify the stack zip and chain-data archive before extraction.
- Extract the chain archive into `<release-root>/data/node/mainnet` before starting the node when the user wants fast catch-up.

Procedure:

```bash
uname -m
sudo apt-get update
sudo apt-get install -y ca-certificates curl unzip zstd tar python3 iproute2 net-tools arp-scan nmap
mkdir -p ~/bdag-v6.3.20 && cd ~/bdag-v6.3.20
curl -fL https://ipfs.io/ipfs/bafybeigpe7s3yd4vk6u6fba56stusoxqalob6oi2rm5tbbpc5aqzu7mn2i -o pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64.zip
echo "ecbf300959402815f8c3dd1d5334af927385766dae5c527ec202040e2a49f39c  pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64.zip" | sha256sum -c -
unzip pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64.zip
cd pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64
mkdir -p chain-download data/node/mainnet
curl -fL https://ipfs.io/ipfs/bafybeieyhcnszf7ksylee5dsdktkdgm5q45fiuaqjrqxmfsbksafs3crny -o chain-download/blockdag-mainnet-20260614-100022Z.tar.zst
echo "074d1cba6ae7ad3384157befe9527e38daa048348fdd6e3a22d05024e5e8d8b5  chain-download/blockdag-mainnet-20260614-100022Z.tar.zst" | sha256sum -c -
tar --zstd -xf chain-download/blockdag-mainnet-20260614-100022Z.tar.zst -C data/node/mainnet
```

For node-only:

```bash
BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

For pool mode, collect from the human first:

- Public payout/mining address: `MINING_POOL_ADDRESS`.
- Whether they want to provide `POOL_PRIVATE_KEY` now. Prefer hidden prompt over command history.
- Pool host LAN IP for ASICs, usually the wired IP shown by `ip -4 route get 1.1.1.1`.
- ASIC scan CIDR, usually `<first-three-octets>.0/24`.

Then run:

```bash
export MINING_POOL_ADDRESS='0xREPLACE_WITH_USER_PUBLIC_ADDRESS'
export BDAG_POOL_HOST='192.168.1.REPLACE'
export BDAG_MINER_SCAN_TARGET='192.168.1.0/24'
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

Validation:

```bash
curl -s http://127.0.0.1:9280/api/status | python3 -m json.tool
curl -s http://127.0.0.1:8088/ >/dev/null && echo dashboard-ok
ss -ltnp | grep -E '(:8150|:3334|:8088|:9280|:38131|:18545)'
```

Expected successful states: `overall=ok`, `sync_progress.status=synced`, `can_accept_shares=true`, and miners appear once ASICs point to `stratum+tcp://<pool-host-ip>:3334`.
