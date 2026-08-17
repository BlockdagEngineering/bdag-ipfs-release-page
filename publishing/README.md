# Community Rescue IPFS Publishing

Current release: `2.0.0-community-rescue-rc.65`, rich page revision 2.

Immutable setup page:

`https://dweb.link/ipfs/bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku/index.html`

Mutable latest-release IPNS names:

`k51qzi5uqu5dgijozv3dne65cp7iqv96tpsa8dflmwmqvdw9oxx4w3gsvt0ctl`

`12D3KooWD3c6UAMwSBjuPbYinx4mJMTsEBK1kNjW9s5TtZL8L6Gi`

The immutable CID is the authoritative page identity. IPNS is a convenience
pointer and can take longer to resolve through public gateways.

Generated install commands fetch signed records from a separate immutable
`release-records-root`. This avoids depending on the HTML gateway origin,
including service-worker gateways that do not return IPFS file bytes to shell
clients.

## Reproduce The Page CID

From the repository root:

```bash
ipfs add -r --hidden=true --empty-dirs=true --cid-version=1 \
  --raw-leaves=true --chunker=size-262144 --hash=sha2-256 \
  --preserve-mode=false --preserve-mtime=false --pin=true -Q \
  releases/2.0.0-community-rescue-rc.65-page-v2
```

Expected CID:

`bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku`

The signed-record directory must independently reproduce as:

```bash
ipfs add -r --hidden=true --empty-dirs=true --cid-version=1 \
  --raw-leaves=true --chunker=size-262144 --hash=sha2-256 \
  --preserve-mode=false --preserve-mtime=false --pin=true -Q \
  releases/2.0.0-community-rescue-rc.65-page-v2/records
```

Expected records CID:

`bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe`

## Community Mirroring

Regenerate `free-pinning-cids.json` with
`python3 publishing/render-rc65-page-v2-pins.py`. Its 47 immutable roots cover
the rich page, unchanged signed records, predecessor page, signed compact-data
admission manifest, AMD64 and ARM64 software, compact mining-node data, and all
40 inherited full-archive parts. Existing RC65 software and dataset bytes are
not replaced by page revision 2.

## Durable Public Seeders

A local pin is not sufficient when the node is behind carrier-grade NAT. The
delegated router can discover the provider record while public gateways still
cannot open a Bitswap connection to retrieve the blocks. Run at least two
seeders on independent networks with a public WAN address and either UPnP or a
static TCP/UDP port forward for the Kubo swarm port.

Each seeder needs:

- Linux on `amd64` with the release Kubo binary available locally.
- Enough free storage for whichever RC65 roots the operator chooses to mirror;
  the full 47-root inventory includes about 188 GB of release payloads.
- `jq`, `systemd`, passwordless administrative access, and outbound internet.
- A public router mapping for TCP and UDP. Confirm `ipfs swarm addrs autonat`
  reports `Reachability: Public` before relying on the node.

Copy this `publishing/` directory and the verified Kubo binary to the host,
then run:

```bash
export BDAG_IPFS_KUBO_SHA256=<expected-ipfs-binary-sha256>
./publishing/provision-public-seeder.sh \
  ./publishing/free-pinning-cids.json \
  ./ipfs
```

The provisioner initializes Kubo without the restrictive server profile,
enables router port mapping, limits the datastore to 250 GB by default, installs the
low-priority persistent user service, enables login lingering, and starts an
idempotent background replication unit. The source node must remain connected
to the new seeder until all roots are pinned.

Set `BDAG_IPFS_STORAGE_MAX` explicitly when mirroring a selected subset. Do not
use a datastore limit below the retained roots plus garbage-collection and
operating headroom.

Some networks expose more than one UPnP gateway and Kubo may select the wrong
one. If the public WAN address is valid but `ipfs swarm addrs autonat` remains
private, install `miniupnpc`, confirm TCP and UDP port 4001 can be mapped to the
host, and provision with the optional refresh timer enabled:

```bash
export BDAG_IPFS_FORCE_UPNP_REFRESH=1
./publishing/provision-public-seeder.sh \
  ./publishing/free-pinning-cids.json \
  ./ipfs
```

The timer refreshes both mappings every 15 minutes. Do not enable it when port
4001 belongs to another host or when the router has a deliberate static port
forward on a different external port.

Monitor replication with the unit name printed by the provisioner. When it
finishes, verify every root independently of the source node:

```bash
./publishing/check-public-availability.sh \
  ./publishing/free-pinning-cids.json
```

The availability check performs cache-bypassing raw-block reads through the
public trustless gateway, requires at least two delegated providers per root,
and fetches the complete release-page DAG as a CAR. Override the redundancy
gate only when intentionally testing with `BDAG_IPFS_MIN_PROVIDERS`. Do not
declare a release publicly available based only on `ipfs pin ls`, a DHT
provider record, or a successful fetch through a caching HTTP gateway.

Do not modify a published release directory after recording its CID. Create a
new versioned directory, verify every link/hash/signature, add it to IPFS, then
publish the new immutable root through IPNS and update the GitHub Pages root.

## Mandatory Release Gate

Before adding a new release-page directory to IPFS:

```bash
./releases/2.0.0-community-rescue-rc.65-page-v2/verify-load-v2.sh
python3 tests/validate_rc65_release.py --publication-ready
python3 tests/validate_rc65_page_v2.py --publication-ready
node --test tests/*.test.mjs
```

The command tests must cover every selectable role, dataset, and state-retention
mode, reject unavailable datasets, and pass every generated command through
`bash -n`.

After computing and seeding the immutable CID, browse that exact CID at desktop
and mobile sizes. Exercise every selector and the copy control, open every
local document and record link, and inspect browser console, failed requests,
layout overflow, and accessibility results. Fetch the HTML, manifest, module,
stylesheet, and favicon through a cold public gateway. Run
`check-public-availability.sh` and require the configured provider count and
complete release-page DAG before updating IPNS or the stable web-page pointer.
Repeat the browser checks against both mutable pointers after publication.
