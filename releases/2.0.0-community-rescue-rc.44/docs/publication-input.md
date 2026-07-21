# RC44 Published Software Release

`release-manifest.json` is the machine-readable published index for RC44. Exact
software identities come from the signed qualification build. Portable v27
remains an independently signed dataset. Software and data are not made
equivalent by appearing on the same page.

Published components:

- Signed RC44 AMD64 and ARM64 software with immutable CIDs.
- Signed bootstrap and release records with immutable records-directory delivery.
- Portable v27 current-state dataset in three immutable IPFS parts.
- Human and AI-assisted installation guidance.
- A locked command builder with exact `public-rpc + full archive +
  --full-archive` preset mapping.

The full archive dataset remains `pending`. Its unavailable fields and download
control intentionally remain empty until the separate archive audit,
qualification, signing, pinning, and public readback complete.

## Qualification Evidence

- Source revisions and source lock match the signed release lock.
- Package ZIPs, embedded binaries, signatures, hashes, and architectures passed
  release-archive validation.
- AMD64 and ARM64 packages reproduce byte-for-byte from their extracted ZIP
  contents and pass native-architecture installer smoke tests.
- The exact AMD64 package writes the bounded public-RPC and fail-closed
  full-archive configuration.
- Full-archive proof, bootstrap, publication, and release-build tests pass.
- The exact AMD64 package passed a transactional handoff on the isolated
  full-archive qualifier, retained its existing state, recovered from clean
  stop/restart tests, and remained canonically aligned with the local public
  RPC plus both external public witnesses at all sampled heights.
- Portable v27 parts and assembled archive match recorded byte sizes and
  SHA-256 values.

## Reproduction Checks

From the repository root:

```bash
python3 tests/validate_rc44_release.py
node --test tests/release-page.test.mjs
openssl pkeyutl -verify -rawin -pubin \
  -inkey releases/2.0.0-community-rescue-rc.44/records/software/release-key.pem \
  -in releases/2.0.0-community-rescue-rc.44/records/software/release-auth-manifest.json \
  -sigfile releases/2.0.0-community-rescue-rc.44/records/software/release-auth-manifest.json.sig
python3 releases/2.0.0-community-rescue-rc.44/records/dataset/verify-canonical-manifest.py verify \
  --envelope releases/2.0.0-community-rescue-rc.44/records/dataset/portable-v27-canonical-manifest.json \
  --trusted-key-dir releases/2.0.0-community-rescue-rc.44/records/dataset
```

The command-builder test must cover mining, public RPC, node-only, portable,
software-only current state, software-only archive retention, and synthetic
full archive selections. Every generated command must pass `bash -n`; the
pending full archive must remain unselectable. Signed-record
downloads must use `records_delivery.cid` rather than the page origin.

The software and portable-v27 release is published while the independently
versioned full archive remains unavailable. A later additive page update may
enable that option only after recording its signed manifest and immutable
delivery CIDs and passing the archive-specific validation path.

Publication is additive: prior immutable release directories remain available.
The mutable root page points to RC44; prior immutable release directories remain
available for audit and rollback.

Runtime policy remains fail closed: transient peer-readiness may use only the
bounded startup window, while any canonical checkpoint or boundary mismatch
fails immediately.
