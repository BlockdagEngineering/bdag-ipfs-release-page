# Publishing Notes

1. Build architecture-specific payload zips outside this repo.
2. Validate each payload with architecture, installer smoke, and release archive checks.
3. Add zips and checksum files to IPFS and record CIDs in `release-manifest.json`.
4. Add `install-v6.3.20.sh` to IPFS and record its CID.
5. Build a publish directory containing the generated page/docs/manifest plus the payload zips/checksums if desired.
6. Run `ipfs add -r --cid-version=1 --pin=true <publish-directory>`.
7. Verify local gateway and at least one public gateway.

Current payload CIDs:

- linux-arm64: `bafybeif4zj4nyz7ykag3ttohkq3sirmo4ceacyz6whbpvc56ui6jhwt4uy`
- linux-amd64: `bafybeiafmnd5admxhhwdg6qjkhrpzwsc5lkvnr2mu7c45p3reqov5thkim`
- bootstrap: `bafkreidvo6thfpmzxgm7rvzr3cyrywuhyczt7chzqdcbnwhbcl5spynu34`
