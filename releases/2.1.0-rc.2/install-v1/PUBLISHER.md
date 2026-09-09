# RC2 publication and trust statement

This companion is published through the [BlockdagEngineering/bdag-ipfs-release-page](https://github.com/BlockdagEngineering/bdag-ipfs-release-page) project. The attributed maintainer account is [jeremyharkness](https://github.com/jeremyharkness/). The final authenticated publication statement is tracked in [issue #9](https://github.com/BlockdagEngineering/bdag-ipfs-release-page/issues/9).

## What the attribution means

`publisher.json` records the exact software and dataset CIDs, the unchanged RC2 record hashes, the distribution manifest hash, the four source repositories and commits, and this companion's protocol and migration limits. It is an account-backed publication statement. It is not a cryptographic signature, a new signing key, proof of an independently verified natural-person identity, an independent reproducible-build report, or a project-wide endorsement.

No publisher account, signature, central approval or GitHub login is required to download or install the release. Compare the expected record and companion hashes through a channel you trust, inspect the helper, and verify complete downloaded bytes before execution. A hash proves content integrity; it does not prove publisher identity. The authenticated issue statement will bind the final page CID, reviewed source commit, `publisher.json` SHA-256 and `COMPANION-SHA256SUMS` SHA-256 after publication. Those values are intentionally not embedded here, so this page does not hash itself.

## Fixed trust bindings

- Software CID: `bafybeicem6wyor5s4xq7436nnhfr2uj7ydh357tfdh3nzbziw7lx5v2taq`
- Dataset CID: `bafybeigui73pb3fnbwee5jeww3bi2c2nzkjvk4ifzafky5yyjqwilpvw2u`
- Original release record SHA-256: `468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2`
- Original distribution manifest SHA-256: `54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c`
- Dataset bytes/SHA-256: `13931299738` / `8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608`
- Dataset manifest SHA-256: `eb668d4d93f7ed5d1a6f9dbf516bf00d33dc4103cfbb660790621f4e06a980a4`

The original record and source bindings remain unchanged. See `publisher.json` for the complete machine-readable list. The RC65 to RC2 migration status is **NOT QUALIFIED**; this companion supplies guidance only and does not make compatibility or rollback-by-old-binary claims.

## HTTP/1.1 and browser limits

The explicit `curl --http1.1` commands and `bdag-download.py` helper are the protocol-controlled paths. They require HTTPS, certificate verification, safe redirects, bounded retries, complete expected size and SHA-256, and a non-clobbering final rename. Native `ipfs://` retrieval is a separate transport. Ordinary browser links are convenience links and cannot force the browser's HTTP version; a successful page or HTTP 200 wrapper is not a full-byte verification.
