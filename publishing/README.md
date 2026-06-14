# Publishing Notes

1. Build architecture-specific payload zips outside this repo.
2. Validate each payload with architecture, installer smoke, and release archive checks.
3. Add zips and checksum files to IPFS and record CIDs in `release-manifest.json`.
4. Add `install-v6.3.20.sh` to IPFS and record its CID.
5. Build a publish directory containing the generated page/docs/manifest plus the payload zips/checksums if desired.
6. Run `ipfs add -r --cid-version=1 --pin=true <publish-directory>`.
7. Publish the new root CID to the permanent release IPNS key:

   ```bash
   ipfs name publish --key=bdag-pool-release-latest --ttl=10m --lifetime=8760h /ipfs/<new-root-cid>
   ```

8. Verify local IPNS resolution, the direct immutable CID URL, and at least one public IPNS gateway.

Permanent latest-release IPNS name:

`k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg`

Primary latest-page gateway:

`https://ipfs.io/ipns/k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg/index.html`

In-browser gateway:

`https://k51qzi5uqu5di0diurqi5rquevlgj4fv4ykm67tgovktd8vtnlimcvqywk1jhg.ipns.inbrowser.link/index.html`

Do not use DNSLink or a registered domain as the canonical release pointer. The release model is permissionless: IPNS is the mutable latest pointer, and immutable IPFS CIDs are the verifiable records for exact release content.

Current payload CIDs:

- linux-arm64: `bafybeif4zj4nyz7ykag3ttohkq3sirmo4ceacyz6whbpvc56ui6jhwt4uy`
- linux-amd64: `bafybeiafmnd5admxhhwdg6qjkhrpzwsc5lkvnr2mu7c45p3reqov5thkim`
- bootstrap: `bafkreidvo6thfpmzxgm7rvzr3cyrywuhyczt7chzqdcbnwhbcl5spynu34`
