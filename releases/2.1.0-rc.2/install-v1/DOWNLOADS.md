# RC2 downloads: native IPFS or anonymous HTTP

This companion describes the unchanged **2.1.0-rc.2** release. You do not need
a GitHub account, publisher signing key, signed manifest or central approval.
You do need an expected SHA-256 obtained through a channel you trust. Hashes
check bytes; they do not tell you whether a publisher deserves your trust.

## Native IPFS

Use an installed Kubo/IPFS command-line client with a running daemon:

```sh
ipfs get /ipfs/bafybeicem6wyor5s4xq7436nnhfr2uj7ydh357tfdh3nzbziw7lx5v2taq -o rc2-software
cd rc2-software
printf '%s  %s\n' '233ac434c70efa6f928ddb1ceb21bb4862cba73ef1bd27ca918ea17370620c3b' SHA256SUMS | sha256sum -c -
sha256sum -c SHA256SUMS
```

The page's native links also work in IPFS-capable browsers. Ordinary HTTP IPFS
gateways are optional and may throttle or challenge requests. A gateway error
does not mean the CID has changed. Use another transport, not a different hash.

## HTTP software mirror with resume

Download `bdag-download.py`, `downloads.json` and `COMPANION-SHA256SUMS` from this
directory. Inspect the small helper before running it. Check the helper against
the companion checksums and select the published manifest hash below. Python 3
on Linux is sufficient; no package manager or login is needed for downloads.

```sh
sha256sum -c COMPANION-SHA256SUMS --ignore-missing
python3 bdag-download.py \
  --manifest downloads.json \
  --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
  --output-dir rc2-software --select software --transport http
cd rc2-software
sha256sum -c SHA256SUMS
```

This fetches the complete 26-file software tree, including all ten archives,
both architectures and their release metadata. Re-running resumes partial
transfers and skips already verified complete files. A mismatched existing
destination is reported, never silently overwritten. Preserve it as evidence
or choose a fresh output directory.

To fetch just one file, add `--file artifacts/NAME_FROM_THE_MANIFEST`. For
installation, use the complete metadata tree and your architecture's full ZIP,
not just a component tarball. AMD64 means x86-64; ARM64 means AArch64. The helper
can also use `--transport ipfs` with the same pinned manifest and expected bytes.

Direct browser mirror downloads have an `artifacts__` filename prefix because
GitHub Release assets are a flat directory. Rename a browser-downloaded archive
to the original name displayed on the page before using a name-based checksum
command. The helper restores the correct filenames and directories automatically.

The HTTP mirror is a free public GitHub Release asset store. It is not GitHub
Packages, Git LFS or a mandatory trust service. Native IPFS remains independent.

## Optional dataset, resumable in 13 parts

```sh
python3 bdag-download.py \
  --manifest downloads.json \
  --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
  --output-dir rc2-dataset --select dataset --transport http
```

There is **one accepted bootstrap dataset**, not thirteen datasets. The pieces
are numbered in order; twelve are 1 GiB and the last is 1,046,397,850 bytes. The
helper verifies each piece, retains it for resume, assembles one `.bdsnap`, then
checks the original full SHA-256. It also downloads the separate dataset records.
Do not import an individual part or merely concatenate files in wildcard order.

Native IPFS supplies the same snapshot as one file:

```sh
ipfs get /ipfs/bafybeigui73pb3fnbwee5jeww3bi2c2nzkjvk4ifzafky5yyjqwilpvw2u/blockdag-chain1404-order20821036-20260907.bdsnap -o blockdag-chain1404-order20821036-20260907.bdsnap
printf '%s  %s\n' '8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608' blockdag-chain1404-order20821036-20260907.bdsnap | sha256sum -c -
```

Allow about 28 GB for HTTP parts plus the assembled archive. Import needs
additional working space: the snapshot records contain about 45.7 GB of
uncompressed key/value data; database compression, compaction and subsequent
chain growth change the final disk requirement. Budget at least 90 GB free for
download/import workspace **in addition to** your filesystem reserve and any
retained rollback. This is an estimate, not an upper bound for future chain growth.

Continue with [dataset validation](DATASETS.md). Downloading is not installation,
activation, peer synchronization or permission to overwrite existing data.
