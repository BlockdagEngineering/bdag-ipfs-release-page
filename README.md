# BDAG IPFS Release Page

Maintainable IPFS release page, branding, manifests, runbooks, and publishing notes for BDAG Community pool stack releases.

Current branch: `jeremy-dev-release`.

Current release: `v6.3.20` with `linux-arm64` and `linux-amd64` payloads.

Permanent latest-release IPNS name:

`k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg`

Primary latest-page gateway:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

This project intentionally uses IPNS for the mutable public release entry point instead of DNSLink or a registered domain. Exact releases, payloads, checksums, scripts, manifests, docs, and chain-data archives remain immutable IPFS CIDs that users can verify and pin.

Large payload zips are not stored in Git. They are regenerated during release packaging, pinned to IPFS, and referenced by CID/SHA256 in `releases/v6.3.20/release-manifest.json`.
