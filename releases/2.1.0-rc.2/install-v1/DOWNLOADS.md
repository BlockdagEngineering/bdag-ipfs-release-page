# RC2 downloads: HTTPS IPFS first, explicit HTTP/1.1 mirror fallback

This companion describes the unchanged **2.1.0-rc.2** release. You do not need
a GitHub account, publisher signing key, signed manifest or central approval.
You do need an expected SHA-256 obtained through a channel you trust. Hashes
check complete bytes; they do not establish publisher identity or migration
compatibility. See [publisher attribution](PUBLISHER.md) and the prominently
**NOT QUALIFIED** [RC65 migration guide](MIGRATION.md).

## HTTPS IPFS first

Open the HTTPS IPFS/IPNS release page first:
`https://dweb.link/ipns/k51qzi5uqu5di3hhaj5p3etixlote527k0yqvxyq83j3yyo0anf8tan8e462tn/index.html`.
Its browser convenience links cannot force an HTTP version; use the explicit
HTTP/1.1 command or helper below when the request protocol must be controlled.

## Native IPFS: separate client transport

Use an installed Kubo/IPFS command-line client with a running daemon. This is a
separate transport from HTTPS and requires an IPFS client:

```sh
ipfs get /ipfs/bafybeicem6wyor5s4xq7436nnhfr2uj7ydh357tfdh3nzbziw7lx5v2taq -o rc2-software
cd rc2-software
printf '%s  %s\n' '233ac434c70efa6f928ddb1ceb21bb4862cba73ef1bd27ca918ea17370620c3b' SHA256SUMS | sha256sum -c -
sha256sum -c SHA256SUMS
```

The companion page's native `ipfs://` buttons remain the immutable-object path.
The HTTPS gateway convenience link is optional and may throttle or challenge
requests. A gateway error does not mean the CID changed.

## Fallback: direct HTTPS mirror with forced HTTP/1.1

The page's direct HTTPS mirror is a labelled fallback to the HTTPS IPFS page.
The mirror URL and expected hash must come from the separately validated
`downloads.json`; do not invent a release URL. Ordinary browser links are only
convenience links and cannot force an HTTP version. Every `curl` example below
uses explicit HTTP/1.1, HTTPS-only redirects, bounded time/retries, a fresh
`.partial` destination, complete size/hash verification, and a non-clobbering
final rename. A HTTP 200 page, service-worker shell or same-size wrong payload
fails the expected full-byte check.

Bootstrap the helper and manifest from the visible HTTPS IPFS/mirror page, then
inspect the helper before running it:

```sh
(
  set -eu
  mkdir rc2-tools
  cd rc2-tools
  BASE='https://blockdagengineering.github.io/bdag-ipfs-release-page/releases/2.1.0-rc.2/install-v1'
  fetch() {
    name=$1; expected_bytes=$2; expected_sha=$3
    if [ -e "$name" ] || [ -L "$name" ] || [ -e "$name.partial" ] || [ -L "$name.partial" ]; then
      printf 'Refusing existing destination or partial: %s\n' "$name" >&2
      return 2
    fi
    curl --http1.1 --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --retry 2 --max-filesize "$expected_bytes" --output "$name.partial" "$BASE/$name"
    test "$(wc -c < "$name.partial" | tr -d '[:space:]')" = "$expected_bytes"
    printf '%s  %s\n' "$expected_sha" "$name.partial" | sha256sum -c -
    mv -n -- "$name.partial" "$name"
    if [ -e "$name.partial" ] || [ -L "$name.partial" ]; then
      printf 'Partial remained after rename: %s\n' "$name.partial" >&2
      return 2
    fi
  }
  fetch bdag-download.py 23973 57580591bb62ef724f66fddca0f050c9610843103c724d1c09cc2f6357099174
  fetch downloads.json 23024 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c
)
```

After reviewing the fetched files, execute the helper in a separate bounded
shell with both pinned inputs rechecked:

```sh
(
  set -eu
  cd rc2-tools
  if [ ! -f bdag-download.py ] || [ -L bdag-download.py ] || [ ! -f downloads.json ] || [ -L downloads.json ]; then
    printf '%s\n' 'Missing or unsafe helper/manifest' >&2
    exit 2
  fi
  printf '%s  %s\n' '57580591bb62ef724f66fddca0f050c9610843103c724d1c09cc2f6357099174' bdag-download.py | sha256sum -c -
  printf '%s  %s\n' '54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c' downloads.json | sha256sum -c -
  python3 bdag-download.py \
    --manifest downloads.json \
    --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
    --output-dir rc2-software --select software --transport http
  cd rc2-software
  sha256sum -c SHA256SUMS
)
```

The manifest's software and dataset URLs are the exact GitHub Release assets.
The pinned manifest SHA-256 is
`54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c`; the
bounded execution block above runs the helper and checks the resulting
`SHA256SUMS`.

After the guarded review/execution block succeeds, enter the tool directory
before running the later helper or dataset examples:

```sh
cd rc2-tools
```

The helper explicitly issues HTTP/1.1 for HTTP and HTTPS, limits HTTPS ALPN to
`http/1.1`, validates certificates, rejects HTTPS-to-HTTP redirects, resumes
only a valid range, checks the complete expected size and SHA-256, and refuses
to overwrite an existing mismatched file. It downloads the complete 26-file
software tree, including all ten archives and both architectures. Dataset
selection and all thirteen pieces use the same bounded HTTP/1.1 helper.

For a single software selection, the generated page command uses the validated
manifest URL and this shape (replace the URL, filename, size and hash only from
that manifest; never copy a browser URL by hand):

```sh
(
  set -eu
  name='corechain-2.1.0-rc.2-linux-amd64.tar.gz'; partial="$name.partial"; expected_bytes=67154971
  if [ -e "$name" ] || [ -L "$name" ] || [ -e "$partial" ] || [ -L "$partial" ]; then
    printf 'Refusing existing destination or partial: %s\n' "$name" >&2
    exit 2
  fi
  curl --http1.1 --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 14400 --retry 4 --max-filesize "$expected_bytes" --output "$partial" 'https://github.com/BlockdagEngineering/bdag-ipfs-release-page/releases/download/jeremy%2Fdistribution%2F2.1.0-rc.2-install-v1/artifacts__corechain-2.1.0-rc.2-linux-amd64.tar.gz'
  test "$(wc -c < "$partial" | tr -d '[:space:]')" = "$expected_bytes"
  printf '%s  %s\n' '3f0e50181c5d45c6ff8d4e0ad8892db930a08e26484f6949fe6cec3e2e011c0d' "$partial" | sha256sum -c -
  mv -n -- "$partial" "$name"
  if [ -e "$partial" ] || [ -L "$partial" ]; then
    printf 'Partial remained after rename: %s\n' "$partial" >&2
    exit 2
  fi
)
```

The page generates the same safe form for all ten architecture/component
selections and displays the original filename and expected SHA-256. A browser
download may use a flat `artifacts__` name; the explicit command restores the
manifest filename before checksum use. The helper is preferred for the complete
tree and for resumable transfers.

## Optional dataset: one snapshot in thirteen ordered parts

```sh
(
  set -eu
  if [ ! -f bdag-download.py ] || [ -L bdag-download.py ] || [ ! -f downloads.json ] || [ -L downloads.json ]; then
    printf '%s\n' 'Missing or unsafe helper/manifest' >&2
    exit 2
  fi
  printf '%s  %s\n' '57580591bb62ef724f66fddca0f050c9610843103c724d1c09cc2f6357099174' bdag-download.py | sha256sum -c -
  printf '%s  %s\n' '54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c' downloads.json | sha256sum -c -
  python3 bdag-download.py \
    --manifest downloads.json \
    --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
    --output-dir rc2-dataset --select dataset --transport http
  SNAP='rc2-dataset/blockdag-chain1404-order20821036-20260907.bdsnap'
  test "$(wc -c < "$SNAP" | tr -d '[:space:]')" = 13931299738
  printf '%s  %s\n' '8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608' "$SNAP" | sha256sum -c -
)
```

There is **one accepted bootstrap dataset**, not thirteen datasets. The pieces
are numbered in order; twelve are 1 GiB and the last is 1,046,397,850 bytes.
The helper verifies each piece, retains it for resume, assembles one `.bdsnap`,
then checks the original full SHA-256. It also downloads separate dataset
records. Do not import an individual part or concatenate files in wildcard
order. The generated page provides the helper invocation and final exact
snapshot size/SHA check; it does not pretend to provide a one-file per-part
browser command.

Native IPFS supplies the same snapshot as one file:

```sh
ipfs get /ipfs/bafybeigui73pb3fnbwee5jeww3bi2c2nzkjvk4ifzafky5yyjqwilpvw2u/blockdag-chain1404-order20821036-20260907.bdsnap -o blockdag-chain1404-order20821036-20260907.bdsnap
printf '%s  %s\n' '8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608' blockdag-chain1404-order20821036-20260907.bdsnap | sha256sum -c -
```

Allow about 28 GB for HTTP parts plus the assembled archive. Import needs
additional working space: the snapshot records contain about 45.7 GB of
uncompressed key/value data; database compression, compaction and subsequent
chain growth change the final disk requirement. Budget at least 90 GB free for
download/import workspace in addition to filesystem reserve and retained
rollback. This is an estimate, not an upper bound for future growth.

Continue with [dataset validation](DATASETS.md). Downloading is not
installation, activation, peer synchronization or permission to overwrite
existing data. For role-specific installation see [INSTALL.md](INSTALL.md),
and for AI planning see [MIGRATION-AGENTS.md](MIGRATION-AGENTS.md).
