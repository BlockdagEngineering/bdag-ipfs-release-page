# BlockDAG Community Rescue RC32

BlockDAG `2.0.0-community-rescue-rc.32`, release sequence `32`, is currently a
draft qualification candidate for mainnet chain ID `1404`. Its software
identities are signed, but public download CIDs and the final runtime gate are
still pending. Do not install it until the page reports **Published release**.

RC32 uses bounded waits for temporary committed-EVM-head and peer-readiness
conditions. A canonical checkpoint, boundary, state-root, or network mismatch
still fails immediately.

The RC32 software and portable v27 chain dataset are separate artifacts. You
may install RC32 while keeping compatible existing data, or restore portable
v27 independently through a compatible guarded installer. The full archive
dataset is not part of this publication and remains unavailable until its
separate audit and publication finish.

## Prepare

For a mining pool, have these ready:

- A public `0x...` BlockDAG payout address. Never provide a seed phrase or
  private key.
- Each ASIC Ethernet MAC address in `aa:bb:cc:dd:ee:ff` form.
- A 64-bit AMD64 or ARM64 Linux host with Docker Engine and Docker Compose v2.
- `curl`, `unzip`, `sha256sum`, Python 3, `tar`, `zstd`, `grep`, and OpenSSL.
- Free space for downloads, extraction, chain growth, and a rollback copy.
- Reliable outbound HTTPS and BlockDAG P2P connectivity.

Run the installer as a non-root account that can use `sudo` and Docker. Use
absolute paths for the data directory, dataset archive, manifest, and trusted
key. Do not use `~` in installer path arguments.

## Installation After Publication

1. Open the published release page.
2. Confirm it reports **Published release** and sequence `32`.
3. Select the node role and chain-data option. The command detects AMD64 or
   ARM64 automatically.
4. For mining, enter only the public payout address and ASIC MAC addresses.
5. Review and run the generated command.

The generated command first checks Linux, required tools, non-root ownership,
`sudo`, Docker access, Docker Compose v2, and minimum download and restore
space. It then verifies the signed release records, downloads every artifact
with IPv4 and HTTP/1.1, verifies each SHA-256, assembles the portable dataset
in order, verifies the complete archive, and invokes the guarded installer
inside the selected signed package. The public path downloads software
directly from IPFS and requires no source-repository account or access token.
Signed software and dataset records are fetched from their own immutable IPFS
directory root, so the command remains valid when the page is opened through
a service-worker gateway such as `inbrowser.link`.

The data selections map to installer modes as follows:

| Page selection | Installer mode |
| --- | --- |
| Keep / sync, current state | `--no-archive` |
| Keep / sync, retain archive | `--archive` |
| Portable restore | `--no-archive` |
| Full archive restore, when published | `--full-archive` |

Portable data cannot be used to claim full archive status. The full archive
control remains disabled until a separately signed archive-equivalent dataset
is published.

For a mining selection, the command normalizes the entered MAC addresses,
persists `POOL_ASIC_MAC_ALLOWLIST` in the installed stack `.env`, recreates the
pool service, and verifies that the running container received the exact
allowlist. An empty allowlist is not generated. For a public RPC selection,
place the node behind an independently configured TLS edge proxy with
firewalling, per-client abuse controls, health checks, monitoring, and restart
recovery before exposing the HTTP API.

## Reliable IPFS Downloads

Public IPFS gateways may time out while locating large blocks. Keep partial
files, resume them, and retry through another listed gateway. The stable web
copy is `https://blockdagengineering.github.io/bdag-ipfs-release-page/`.
Always force IPv4 and HTTP/1.1:

```bash
curl -4 --http1.1 --fail --location --show-error \
  --connect-timeout 20 --retry 12 --retry-delay 3 --retry-all-errors \
  --speed-limit 1024 --speed-time 90 -C - \
  "https://dweb.link/ipfs/$CID" -o "$FILE.part"
```

Try `https://ipfs.io/ipfs/$CID` or `https://w3s.link/ipfs/$CID` with the same
partial filename if needed. A successful download is not integrity proof:

```bash
printf '%s  %s\n' "$EXPECTED_SHA256" "$FILE.part" | sha256sum -c -
mv "$FILE.part" "$FILE"
```

Portable v27 is delivered as three immutable parts. Verify each part against
`records/dataset/portable-v27-parts.json`, concatenate them in listed order,
then verify the assembled archive SHA-256:

```bash
cat blockdag-mainnet-portable-v27-20260715T2000Z.tar.zst.part-* \
  > blockdag-mainnet-portable-v27-20260715T2000Z.tar.zst
printf '%s  %s\n' \
  '00441e50d58bc84263cf5ab40ab0f7bd7f21b758809630a66c5d7deab04fc972' \
  'blockdag-mainnet-portable-v27-20260715T2000Z.tar.zst' | sha256sum -c -
```

## Trust Verification

Verify the software authorization signature and release-key fingerprint:

```bash
openssl pkeyutl -verify -rawin -pubin \
  -inkey records/software/release-key.pem \
  -in records/software/release-auth-manifest.json \
  -sigfile records/software/release-auth-manifest.json.sig
openssl pkey -pubin -in records/software/release-key.pem \
  -pubout -outform DER | sha256sum
```

The fingerprint must be:
`26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb`.
The signed record must identify RC32, sequence `32`, the selected architecture,
and the downloaded package SHA-256.

Verify the portable dataset envelope:

```bash
python3 records/dataset/verify-canonical-manifest.py verify \
  --envelope records/dataset/portable-v27-canonical-manifest.json \
  --trusted-key-dir records/dataset
```

Confirm mainnet chain ID `1404`, `archive_node_equivalent=false`, archive
SHA-256 and size, native and EVM boundaries, state root, and fixed checkpoint.
Never merge native, EVM, freezer, or database directories from different data
sets by hand.

## Existing Installations

Keep a rollback copy until post-install checks pass. Stop the stack cleanly
before a dataset restore. Use the installer restore path rather than copying
selected database directories.

One legacy upgrade issue can stop before installation with:

```text
refusing unowned system controller unit bdag-local-peers.timer
refusing unowned system controller unit bdag-node-child-guard.timer
```

Do not remove arbitrary systemd units. First inspect the named unit with
`sudo systemctl cat UNIT` and confirm its commands reference the existing
BlockDAG stack or `/etc/blockdag-pool/project-root`. Back up the verified legacy
unit file, disable and remove only that verified BlockDAG unit, run
`sudo systemctl daemon-reload`, and rerun the installer. Ask a capable system
administrator or AI coding agent to perform this guarded check when uncertain.

The installer also requires the extracted stack directory to be owned by the
non-root runtime account. If the bootstrap was interrupted after extraction,
continue from the existing extracted directory instead of overwriting it.

## Post-Install Checks

```bash
docker compose ps
curl -4 --http1.1 -fsS http://localhost:8088/ >/dev/null
curl -4 --http1.1 -fsS -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' \
  http://localhost:18545
```

Confirm the dashboard displays RC32, chain ID is `0x57c` (`1404`), canonical
checkpoint checks pass, native and EVM heads advance, compatible peers become
current, and the pool accepts valid shares. Running containers alone do not
prove that the node is healthy or on the intended history.

For assisted installation, use `docs/ai-agent-runbook.md`. Do not share wallet
secrets, node identity keys, RPC/database passwords, or unrelated host data.
