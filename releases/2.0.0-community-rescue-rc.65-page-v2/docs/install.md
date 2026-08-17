# Install or upgrade RC65

Open `index.html`, wait for browser-side signature verification to pass, choose
the intended runtime, and inspect the generated Bash before running it. The
same release can be verified locally with:

```bash
./verify-load-v2.sh /absolute/path/to/2.0.0-community-rescue-rc.65-page-v2
```

The generated command detects Linux AMD64 or ARM64, downloads the matching
immutable software CID through interchangeable IPFS gateways, checks its exact
SHA-256 and size, and verifies the package's signed release lock before calling
`install.sh`.

Existing qualified nodes reuse their data, peerstore, accounting, Stratum
identity, and owner payout. The upgrade command contains no compact or full
archive CID. Stage beside the live stack, preserve the prior stack for rollback,
and keep the final mining interruption to the ordinary restart-length cutover.

New normal mining nodes use the compact snapshot and its signed
`bdag.canonical-data-manifest.v3` admission. The payout input must be the
ASIC owner's non-zero address. The installer authenticates the manifest with
the dataset key bound into the RC65 release lock before extraction.

The full-archive option downloads 40 authenticated parts totalling
170,210,502,672 bytes, restores the previously qualified v28 archive through
EVM block 14,977,965, and catches up from ordinary Chain ID 1404 peers. It is
not presented as a current-tip snapshot.

Gateways provide transport only. Bootstrap peers provide discovery only.
Signatures, hashes, fixed anchors, the signed release lock, and ordinary
Chain ID 1404 consensus establish trust.
