# Publishing Notes

1. Build and validate the release zip outside this repo.
2. Add the zip and checksum to IPFS first; record CIDs in `release-manifest.json` and `index.html`.
3. Add the bootstrap script to IPFS; record its CID.
4. Copy `releases/<version>/` plus the zip/checksum into a publish directory.
5. Run `ipfs add -r --cid-version=1 --pin=true <publish-directory>`.
6. Verify local gateway and at least one public gateway.

For v6.3.20:

- Zip CID: `bafybeigpe7s3yd4vk6u6fba56stusoxqalob6oi2rm5tbbpc5aqzu7mn2i`
- Zip SHA256: `ecbf300959402815f8c3dd1d5334af927385766dae5c527ec202040e2a49f39c`
- Bootstrap script CID: `bafkreihatnjexyshvvbv44vvbuoyusu6nrbivtzdypivuxlungowtpyroa`
- Chain data IPNS: `k51qzi5uqu5dky5euzcduak3t08egbx2duts9z3y0jfq4e6iavjld43ojkk1bi`
- Chain archive CID: `bafybeieyhcnszf7ksylee5dsdktkdgm5q45fiuaqjrqxmfsbksafs3crny`
