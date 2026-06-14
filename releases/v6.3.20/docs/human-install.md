# BlockDAG Community Pool Stack v6.3.20 Human Install Guide

This release publishes two payloads: `linux-arm64` for Raspberry Pi/ARM servers and `linux-amd64` for ordinary x86_64 Ubuntu hosts. Start by checking the host architecture:

Permanent latest release page:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

This is an IPNS name, not a registered domain. It can be updated to point at newer release CIDs while exact payloads, checksums, docs, and blockchain data remain immutable IPFS CIDs.

```bash
uname -m
```

Use the matching payload only. The packaged installer now refuses host/payload mismatches unless `BDAG_ALLOW_CROSS_ARCH_PAYLOAD=1` is set for an intentionally configured Docker QEMU/binfmt environment.

## Required inputs

For node-only mode, no wallet or private key is required.

For pool mode, prepare these before running `install.sh`:

- `MINING_POOL_ADDRESS`: your public payout/mining wallet address.
- Pool operator private key: enter through the hidden prompt or a secure local environment only.
- Pool host LAN IP for ASICs, for example `192.168.1.50`.
- ASIC scan CIDR, for example `192.168.1.0/24`.

## Recommended install: download payload, restore chain data, then start

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl unzip zstd tar python3 iproute2 arp-scan nmap
mkdir -p ~/bdag-v6.3.20 && cd ~/bdag-v6.3.20
curl -fL https://ipfs.io/ipfs/bafkreigtyo4a37blqw5wqeryzaxs547u7zar3o7b2jophzqw627hewypva -o install-v6.3.20.sh
chmod +x install-v6.3.20.sh
./install-v6.3.20.sh
```

The helper selects the correct ARM64 or AMD64 zip, verifies it, extracts it, and stops. Then restore chain data:

```bash
cd ~/bdag-v6.3.20/pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
mkdir -p chain-download data/node/mainnet
curl -fL https://ipfs.io/ipfs/bafkreihsxroiysvfb2dhbjq3dggqiorqil22r6vryywuo3plh3hp6uubnm -o chain-download/latest.json
curl -fL https://ipfs.io/ipfs/bafybeieyhcnszf7ksylee5dsdktkdgm5q45fiuaqjrqxmfsbksafs3crny -o chain-download/blockdag-mainnet-20260614-100022Z.tar.zst
echo "074d1cba6ae7ad3384157befe9527e38daa048348fdd6e3a22d05024e5e8d8b5  chain-download/blockdag-mainnet-20260614-100022Z.tar.zst" | sha256sum -c -
tar --zstd -xf chain-download/blockdag-mainnet-20260614-100022Z.tar.zst -C data/node/mainnet
```

Start node-only:

```bash
BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

Start pool mode:

```bash
export MINING_POOL_ADDRESS='0xYOUR_PUBLIC_ADDRESS'
export BDAG_POOL_HOST='192.168.1.50'
export BDAG_MINER_SCAN_TARGET='192.168.1.0/24'
BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh
```

## Success checklist

```bash
curl -s http://127.0.0.1:9280/api/status | python3 -m json.tool
ss -ltnp | grep -E '(:8150|:3334|:8088|:9280|:38131|:18545)'
```

Expected: dashboard reachable on `8088`, sync status eventually `synced`, remaining blocks `0`, `can_accept_shares=true`, and ASICs visible after they point to `stratum+tcp://<pool-host-lan-ip>:3334`.
