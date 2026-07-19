# RC32 Publication Candidate

`release-manifest.json` is the machine-readable draft index for RC32. Exact
software identities come from the signed qualification build. Portable v27
remains an independently signed dataset. Software and data are not made
equivalent by appearing on the same page.

Prepared components:

- Signed RC32 AMD64 and ARM64 software identities; immutable CIDs are pending.
- Signed bootstrap and release records; immutable records-directory delivery is
  pending.
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
- Runtime source revisions are live-proven, but the RC32 package remains a
  qualification candidate until the final exact-package runtime gate passes.
- Portable v27 parts and assembled archive match recorded byte sizes and
  SHA-256 values.

## Reproduction Checks

From the repository root:

```bash
python3 tests/validate_rc32_release.py
node --test tests/release-page.test.mjs
openssl pkeyutl -verify -rawin -pubin \
  -inkey releases/2.0.0-community-rescue-rc.32/records/software/release-key.pem \
  -in releases/2.0.0-community-rescue-rc.32/records/software/release-auth-manifest.json \
  -sigfile releases/2.0.0-community-rescue-rc.32/records/software/release-auth-manifest.json.sig
python3 releases/2.0.0-community-rescue-rc.32/records/dataset/verify-canonical-manifest.py verify \
  --envelope releases/2.0.0-community-rescue-rc.32/records/dataset/portable-v27-canonical-manifest.json \
  --trusted-key-dir releases/2.0.0-community-rescue-rc.32/records/dataset
```

The command-builder test must cover mining, public RPC, node-only, portable,
software-only current state, software-only archive retention, and synthetic
full archive selections. Every generated command must pass `bash -n`; the
pending full archive must remain unselectable. Signed-record
downloads must use `records_delivery.cid` rather than the page origin.

Before changing the draft to `published` or changing mutable pointers, record
the software, records-directory, and full-archive CIDs, complete runtime
qualification, and rerun the publication-ready validator. Then run a real
browser against the exact
immutable CID at desktop and mobile sizes. Exercise every selector, validate
the copied command, open every local link, check for console and network
errors, and confirm no layout overflow or accessibility violations. Then use a
cold public-gateway request to fetch the HTML, manifest, module, stylesheet,
and favicon, and run the provider and complete-DAG availability check. Repeat
the browser check after updating IPNS and the stable web page.

Publication is additive: prior immutable release directories remain available.
The mutable root page must continue to point to RC30 until every RC32
publication and public-retrieval check passes.

Runtime policy remains fail closed: transient peer-readiness may use only the
bounded startup window, while any canonical checkpoint or boundary mismatch
fails immediately.
