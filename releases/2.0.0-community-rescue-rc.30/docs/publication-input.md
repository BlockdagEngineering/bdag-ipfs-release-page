# RC30 Publication Record

`release-manifest.json` is the machine-readable public index for RC30. Exact
software identities came from the signed qualified build. Portable v27
identities came from its signed canonical-data envelope and independently
verified multipart files.

Published components:

- Signed RC30 AMD64 and ARM64 software packages.
- Signed bootstrap identity and a public command path that downloads the signed
  architecture package directly from IPFS.
- Portable v27 current-state dataset in three immutable IPFS parts.
- Human and AI-assisted installation guidance.

The full archive dataset remains `pending`. Its unavailable fields and download
control intentionally remain empty until the separate archive audit,
qualification, signing, pinning, and public readback complete.

## Qualification Evidence

- Source revisions and source lock match the signed release lock.
- Package ZIPs, embedded binaries, signatures, hashes, and architectures passed
  release-archive validation.
- The exact AMD64 public package completed a guarded upgrade against signed
  portable data on mainnet chain ID `1404`.
- Dashboard, node, sentinel, watchdog, and support services passed runtime
  checks, including canonical fixed-checkpoint verification and no-rewind EVM
  startup.
- Portable v27 parts and assembled archive match recorded byte sizes and
  SHA-256 values.
- Public downloads require IPv4 and HTTP/1.1 and are independently seeded.

## Reproduction Checks

From the repository root:

```bash
python3 tests/validate_rc30_release.py --publication-ready
node --test tests/release-page.test.mjs
openssl pkeyutl -verify -rawin -pubin \
  -inkey releases/2.0.0-community-rescue-rc.30/records/software/release-key.pem \
  -in releases/2.0.0-community-rescue-rc.30/records/software/release-auth-manifest.json \
  -sigfile releases/2.0.0-community-rescue-rc.30/records/software/release-auth-manifest.json.sig
python3 releases/2.0.0-community-rescue-rc.30/records/dataset/verify-canonical-manifest.py verify \
  --envelope releases/2.0.0-community-rescue-rc.30/records/dataset/portable-v27-canonical-manifest.json \
  --trusted-key-dir releases/2.0.0-community-rescue-rc.30/records/dataset
```

Publication is additive: prior immutable release directories remain available.
The mutable root page points to RC30 only after the final public retrieval
checks pass.

Runtime policy remains fail closed: transient peer-readiness may use only the
bounded startup window, while any canonical checkpoint or boundary mismatch
fails immediately.
