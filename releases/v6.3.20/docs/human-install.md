# BlockDAG Community Pool Stack v6.3.20 Human Install Guide

This guide installs the BlockDAG node or full mining pool stack from the IPFS release. It assumes Ubuntu Linux and little prior knowledge.

## What you need before starting

- Ubuntu 22.04 or 24.04 on ARM64/aarch64 hardware for this payload.
- Stable wired network, reliable power, and at least 80 GB free disk. Keep extra space because the chain grows.
- Docker Engine with Docker Compose v2. The installer can bootstrap Docker on Ubuntu when non-interactive sudo is available.
- For pool mode: your own public payout wallet address and the private key for the pool operator address. Never share the private key in chat or screenshots.
- For ASIC mining: the pool host LAN IP, ASIC web login, and Stratum URL `stratum+tcp://<pool-host-ip>:3334`.

## Fast node-only install

```bash
mkdir -p ~/bdag-v6.3.20 && cd ~/bdag-v6.3.20
curl -fL https://ipfs.io/ipfs/bafkreihatnjexyshvvbv44vvbuoyusu6nrbivtzdypivuxlungowtpyroa -o install-v6.3.20.sh
chmod +x install-v6.3.20.sh
BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive ./install-v6.3.20.sh
```

Dashboard: `http://<host-lan-ip>:8088` or `http://localhost:8088` on the host.

## Recommended pool install with restored chain data

Download and verify the stack zip, extract it, download the chain-data archive, extract that into `data/node/mainnet`, then run the installer.

```bash
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

Then start either node or pool:

```bash
# Node plus dashboard only.
BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh

# Full pool stack. Type the private key at the hidden prompt when asked.
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

For non-interactive pool installs, export `MINING_POOL_ADDRESS`, `BDAG_POOL_HOST`, and `BDAG_MINER_SCAN_TARGET` first. Provide `POOL_PRIVATE_KEY` only through a secure local secret process; do not paste it into public chat.

## ASIC setup

1. Find the ASIC IP from your router DHCP leases, `ip neigh`, `sudo arp-scan --localnet`, or `sudo nmap -sn <lan-cidr>`.
2. Open the ASIC web UI in a browser.
3. Set Pool URL to `stratum+tcp://<pool-host-lan-ip>:3334`.
4. Set Worker/User to your payout wallet address, for example `0xYOUR_PUBLIC_ADDRESS.worker1` if the miner supports worker suffixes.
5. Set Password to `x` unless your firmware requires another value.
6. Save/apply and reboot the miner if the firmware asks.
7. Open the dashboard at `http://<pool-host-lan-ip>:8088` and check the Miners or Earnings tab.

## Router P2P forwarding

Forward TCP port `8150` from the internet to the pool/node host LAN IP. Reserve the host IP in DHCP first. On Ubuntu with UFW: `sudo ufw allow 8150/tcp`. Do not expose dashboard `8088`, Stratum `3334`, collector `9280`, chain RPC `38131`, or EVM RPC `18545` to the internet.
