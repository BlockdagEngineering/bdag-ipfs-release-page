# Community Rescue IPFS Publishing

Current release: `2.0.0-community-rescue-rc.24`

Immutable setup page:

`https://dweb.link/ipfs/bafybeicrryxoxeg3kn4zuopoc7vwzf3ovytjhuidijbfoumad3xum2zany/index.html`

Mutable latest-release IPNS name:

`k51qzi5uqu5dgijozv3dne65cp7iqv96tpsa8dflmwmqvdw9oxx4w3gsvt0ctl`

The immutable CID is the authoritative page identity. IPNS is a convenience
pointer and can take longer to resolve through public gateways.

## Reproduce The Page CID

From the repository root:

```bash
ipfs add -r --cid-version=1 --raw-leaves=true --pin=true -Q \
  releases/2.0.0-community-rescue-rc.24
```

Expected CID:

`bafybeicrryxoxeg3kn4zuopoc7vwzf3ovytjhuidijbfoumad3xum2zany`

## Community Mirroring

Pin the records in `free-pinning-cids.json`. The dataset and both software
archives are independent roots, so mirrors can choose what they have capacity
to serve. Keep at least the setup page and installer pinned together.

Do not modify a published release directory after recording its CID. Create a
new versioned directory, verify every link/hash/signature, add it to IPFS, then
publish the new immutable root through IPNS and update the GitHub Pages root.
