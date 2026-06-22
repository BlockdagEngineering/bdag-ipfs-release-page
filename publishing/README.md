# Publishing Notes

1. Build architecture-specific payload zips outside this repo.
2. Validate each payload with architecture, installer smoke, and release archive checks.
3. Refresh `peer-seeds.json`: preserve the payload's packaged `addpeer` seeds, append the operator AWS nodes, dedupe, and validate by starting a clean node until it connects to peers and imports chain segments. Do not treat a TCP-open port scan alone as a valid peer check.
4. Add zips and checksum files to IPFS and record CIDs in `release-manifest.json`.
5. Add the release helper script to IPFS and record its CID. Also upload the helper and payload zips to Filebase S3 to create public Filebase IPFS mirror CIDs.
6. Build a publish directory containing the generated page/docs/manifest plus the payload zips/checksums if desired.
7. Run `ipfs add -r --cid-version=1 --pin=true <publish-directory>`.
8. Publish the new root CID to the permanent release IPNS key:

   ```bash
   ipfs name publish --key=bdag-pool-release-latest --ttl=10m --lifetime=8760h /ipfs/<new-root-cid>
   ```

9. Verify local IPNS resolution, the direct immutable CID URL, at least one public IPNS gateway, and the GitHub Pages fallback.

Permanent latest-release IPNS name:

`k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg`

Primary latest-page gateway:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

GitHub Pages fallback:

`https://blockdagengineering.github.io/bdag-ipfs-release-page/`

Inbrowser gateway note:

Do not use `.ipns.inbrowser.link` for the mutable IPNS pointer. Its browser-side IPNS resolver can reject otherwise valid Kubo-published records. Use `ipfs.io/ipns/...` for mutable IPNS and `.ipfs.inbrowser.link` only for immutable CIDs.

Do not use DNSLink or a registered domain as the canonical release pointer. The release model is permissionless: IPNS is the mutable latest pointer, and immutable IPFS CIDs are the verifiable records for exact release content.

Current release asset records:

- release: `pool-v6.5.7` from `C:\Users\Work\Downloads\stack-v6.5.7`
- pinned release-page root: `bafybeidykr7ca7fyikmkoftremsum7sekjjd4txhjysokdim6cuaxoyou4`
- published IPNS: `k51qzi5uqu5djmbejujmyth6ge34vgo4q06dq7m1e2m74szri274yv7fttdusn`
- linux-arm64 CID: `bafybeibobaofgsdlingiday5ea3hf62rludb4u5n6lgxaj3mgjbv35goqe`
- linux-arm64 Filebase mirror CID: `QmfXXCaWfxGjfRSaxG4cBYU43H61XHafeFxGZmMhtSTbX4`
- linux-arm64 SHA256: `53ac85c8f6337fd1d0cebbc17c3cf17804f371dcaf2270515e196c4223e50c6c`
- linux-amd64 CID: `bafybeibc562phfnizztpulf76p57dvhw3xl7kv6zwmhjwu37iglk4sizua`
- linux-amd64 Filebase mirror CID: `QmVYwag8QduE1JTJV7U6Y2m23C3GGhfHMQEzzxhsUuedAy`
- linux-amd64 SHA256: `8d292703d77b656d85bfabf16df7b4ce4f86454a5c075a3c292a5b00f08bd852`
- helper Filebase mirror CID: `QmZpCSyhG8e15UqNhjaKyUGyFTrNhPsFqauSC3bBjDpXaS`

Free external pinning list:

`publishing/free-pinning-cids.json`

Pin only those CIDs on Filebase, 4EVERLAND, or another pinning service. Do not pin the old IPFS chain-data snapshot; restore uses the S3 snapshot URL in `releases/v6.5.7/release-manifest.json`.

Filebase free-tier note: the Pinning Service API and HTML uploads are not available on this account. Use Filebase S3 uploads for helper and payload mirror CIDs, and use GitHub Pages or IPNS for the styled HTML setup page.

Payload IPFS CIDs for `pool-v6.5.7` are recorded in `releases/v6.5.7/release-manifest.json`.
