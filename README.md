# BDAG IPFS Release Page

Maintainable IPFS release page, branding, manifests, runbooks, and publishing notes for BDAG Community pool stack releases.

Current release tag: `pool-v6.5.7`.

Current release page: `releases/v6.5.7/index.html` with `linux-arm64` and `linux-amd64` payload metadata.

Release source:

`C:\Users\Work\Downloads\stack-v6.5.7`

Pinned release-page root CID:

`bafybeidykr7ca7fyikmkoftremsum7sekjjd4txhjysokdim6cuaxoyou4`

Published IPNS page:

`https://ipfs.io/ipns/k51qzi5uqu5djmbejujmyth6ge34vgo4q06dq7m1e2m74szri274yv7fttdusn/index.html`

GitHub Pages fallback:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Permanent latest-release IPNS name:

`k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg`

Primary latest-page gateway:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

This project intentionally uses IPNS for the mutable public release entry point instead of DNSLink or a registered domain. Exact releases, payloads, checksums, scripts, manifests, docs, and chain-data archives remain immutable IPFS CIDs that users can verify and pin.

Large payload zips are not stored in Git. For `pool-v6.5.7`, this repo records the IPFS-pinned payload CIDs and SHA256 values in `releases/v6.5.7/release-manifest.json`. The release page is pinned and published to IPNS.
Filebase mirrors are recorded for the helper and payload zips so installs can continue when public IPFS gateways are slow.
