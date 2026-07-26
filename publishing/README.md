# Community Rescue IPFS Publishing

Current release: `2.0.0-community-rescue-rc.52`

Immutable setup page:

`https://dweb.link/ipfs/bafybeidbsqv7elxbvs5gna33oj47jhynjaqvwt7wesunfew5jct66zhtiy/index.html`

Mutable latest-release IPNS name:

`k51qzi5uqu5dgijozv3dne65cp7iqv96tpsa8dflmwmqvdw9oxx4w3gsvt0ctl`

The immutable CID is the authoritative page identity. IPNS is a convenience
pointer and can take longer to resolve through public gateways.

Generated install commands fetch signed records from a separate immutable
`release-records-root`. This avoids depending on the HTML gateway origin,
including service-worker gateways that do not return IPFS file bytes to shell
clients.

## Reproduce The Page CID

From the repository root:

```bash
ipfs add -r --cid-version=1 --raw-leaves=true --chunker=size-262144 \
  --hash=sha2-256 --pin=true -Q \
  releases/2.0.0-community-rescue-rc.52
```

Expected CID:

`bafybeidbsqv7elxbvs5gna33oj47jhynjaqvwt7wesunfew5jct66zhtiy`

The signed-record directory must independently reproduce as:

```bash
ipfs add -r --cid-version=1 --raw-leaves=true --chunker=size-262144 \
  --hash=sha2-256 --pin=true -Q \
  releases/2.0.0-community-rescue-rc.52/records
```

Expected records CID:

`bafybeifh7va3f7d4qxe3tawns4pmbzxpthyake5florlrgvd5dicmwvud4`

## Community Mirroring

Pin the five RC52 roots in `free-pinning-cids.json`. The page, signed records,
installer, and both software archives are independently addressable. RC52 does
not publish or replace any chain dataset; earlier dataset publications retain
their own immutable CIDs and signatures.

## Durable Public Seeders

A local pin is not sufficient when the node is behind carrier-grade NAT. The
delegated router can discover the provider record while public gateways still
cannot open a Bitswap connection to retrieve the blocks. Run at least two
seeders on independent networks with a public WAN address and either UPnP or a
static TCP/UDP port forward for the Kubo swarm port.

Each seeder needs:

- Linux on `amd64` with the release Kubo binary available locally.
- At least 5 GB free for the RC52 software and operating headroom.
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
enables router port mapping, limits the datastore to 40 GB, installs the
low-priority persistent user service, enables login lingering, and starts an
idempotent background replication unit. The source node must remain connected
to the new seeder until all roots are pinned.

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
python3 tests/validate_rc52_release.py --publication-ready
node --test tests/release-page.test.mjs
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
