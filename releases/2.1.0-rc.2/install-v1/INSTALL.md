# RC2 independent installation companion v1

This guide supersedes older installation instructions inside the unchanged RC2
archives. It supplies a real service runner for the shipped v2 lifecycle. No
mandatory publisher signature, signing key, GitHub account or central approval
is required. SHA-256 and chain identity checks are still required. Transaction
and consensus signatures are unchanged.

## Scope and prerequisites

Use a native Linux AMD64/x86-64 or ARM64/AArch64 host with Python 3, Docker
Engine, the Docker Compose v2 plugin, and `sha256sum`. The operator needs access
to Docker; do not expose its socket to the dashboard. Runtime image assembly
uses the verified prebuilt RC2 binaries and the unchanged release Dockerfile,
not a source rebuild. Docker base images/OS packages require network access.

This helper is for a **fresh target directory and fresh role-specific storage**.
It is not an arbitrary older-pool-ledger migration, an in-place updater or an
automatic dataset activation tool. Existing systems keep their effective local
settings, data, accounting and rollback; do not delete them to satisfy a fresh
install check. Stop and plan an explicit compatible migration if needed.

The three independent modes are:

| Mode | Services started | Owner supplies | Chain dataset needed here? |
| --- | --- | --- | --- |
| `node` | Core + nodeworker | Private RPC credentials; local node/network settings | Yes: start empty, keep a valid local copy, or import a bootstrap |
| `pool` | Pool + PostgreSQL | Compatible Core endpoint, private RPC credentials, payout and new local accounting settings | No: use the selected node's RPC |
| `redis-dash` | Dashboard + managed Redis | Read-only node/pool/EVM monitoring endpoints and limited RPC credentials | No |
| `all-in-one` | Node, Pool, PostgreSQL, Dashboard/Redis | All applicable owner-local settings | Only for the node |

Dashboard-only does not start a local node or acquire node lifecycle authority.
Pool-only does not silently deploy a node. Neither copies a remote pool's
accounting, identity or ASIC assignments.

## 1. Get the companion and exact software

The following commands only download and check files. Review the expected
checksums through a channel you trust, and inspect scripts before executing them.

```sh
mkdir rc2-tools
(
  set -eu
  cd rc2-tools
  BASE='https://blockdagengineering.github.io/bdag-ipfs-release-page/releases/2.1.0-rc.2'
  fetch() {
    name=$1; expected_bytes=$2; expected_sha=$3; url=$4
    test ! -e "$name" && test ! -L "$name"
    test ! -e "$name.partial" && test ! -L "$name.partial"
    curl --http1.1 --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 120 --retry 2 --max-filesize "$expected_bytes" --output "$name.partial" "$url"
    test "$(wc -c < "$name.partial" | tr -d '[:space:]')" = "$expected_bytes"
    printf '%s  %s\n' "$expected_sha" "$name.partial" | sha256sum -c -
    mv -n -- "$name.partial" "$name"
    test ! -e "$name.partial" && test ! -L "$name.partial"
  }
  fetch bdag-download.py 23973 57580591bb62ef724f66fddca0f050c9610843103c724d1c09cc2f6357099174 "$BASE/install-v1/bdag-download.py"
  fetch bdag-install.py 37462 aee626023ed2e41ddf8a2abb0eb936ae6e98de0477d49014c45c7a26e3a1b0e5 "$BASE/install-v1/bdag-install.py"
  fetch service-runner.py 14102 9c53d41f7f06ec833442350d444822f598217c61c2772a77891ffaa08962efc6 "$BASE/install-v1/service-runner.py"
  fetch downloads.json 23024 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c "$BASE/install-v1/downloads.json"
  fetch release.json 6456 468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2 "$BASE/records/release.json"
)
cd rc2-tools
python3 bdag-download.py \
  --manifest downloads.json \
  --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
  --output-dir rc2-software --select software --transport http
```

Native IPFS is an independent alternative; see [DOWNLOADS.md](DOWNLOADS.md).
Ordinary browser links are convenience links and cannot force HTTP/1.1. Use the
explicit commands above or the helper for the guaranteed request policy.
The full ZIP supplies binaries and build templates even when only one service
role will run. The helper selects your native architecture automatically and
checks exact archive identity before extraction.

## 2. Write your private owner settings

Create a private plain `KEY=value` environment file, readable only by you
(`chmod 600 owner.env`). Do not execute/source a downloaded environment file.
Replace values with your own credentials/endpoints; do not paste secrets into
issues, chats, CI or the community page. Use a unique target directory/project
and unoccupied local ports. Default native RPC is loopback port 38131; nodeworker
uses 6061. Multiple local nodes need an explicit port plan outside this helper's
default fresh-install path.

Node-only requires your own `NODE_RPC_USER` and `NODE_RPC_PASS`. It does not
require PostgreSQL, a wallet key or a payout address. New empty data can begin
normal peer synchronization. Optional copied data is a separate reviewed path
in [DATASETS.md](DATASETS.md).

Pool-only additionally requires an explicit `NODE_RPC_URL`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB`, and your non-zero `POOL_COINBASE_ADDRESS`
(or use `MINING_POOL_ADDRESS` as its default). Set `POOL_FEE_PERCENTAGE` intentionally;
never inherit someone else's fee or payout by accident. Set the same intended
Core backend for any explicit `NODE_RPC_URLS`, `POOL_SUBMIT_RPC_URLS` and related
backend selection; omitted lists default to your selected `NODE_RPC_URL`, not a
different local node. Set your matching EVM endpoint as `WALLET_RPC_URL` when needed.
Only a compatible, current, correctly identified Core can supply mining work.

Dashboard-only requires `BDAG_NODE_RPC_URL`, `NODE_RPC_LIMIT_USER` and
`NODE_RPC_LIMIT_PASS` for read-only observation. Set `BDAG_EVM_HTTP_URL`,
`BDAG_POOL_METRICS_URL`, `BDAG_POOL_URL` and `DASHBOARD_LISTEN` for the services
you actually observe. It does not receive a Core lifecycle endpoint or Docker
socket. Keep observer polling bounded and do not give it RPC admin credentials.

All-in-one requires both the node/pool owner settings and limited dashboard RPC
credentials. The node starts first; the other selected services follow. Keep
RPC listeners private and allow miner access only through your intended network
policy. No host firewall or ASIC controller is automatically reconfigured.

No example payout or credentials are embedded here. Existing owner peer choices
remain authoritative configuration; dated bootstrap observations are only
discovery hints. Mining still needs current native/EVM state, compatible fresh
peers, template/submission readiness and the exact intended payout contract.

## 3. Prepare, then start your selected role

Choose one `MODE`: `node`, `pool`, `redis-dash`, or `all-in-one`. Select a new
target path; paths with spaces must remain quoted. Set `OWNER_ENV` to your private
file. `prepare` verifies, plans, stages and selects files; it does **not** mean
the node is running or synchronized.

```sh
MODE=node
TARGET="$PWD/rc2-node"
OWNER_ENV="$PWD/owner.env"
python3 bdag-install.py prepare \
  --mode "$MODE" --record-root "$PWD/rc2-software" \
  --release-record "$PWD/release.json" \
  --target "$TARGET" --owner-env "$OWNER_ENV"

python3 bdag-install.py start \
  --record-root "$PWD/rc2-software" --release-record "$PWD/release.json" \
  --target "$TARGET"
python3 bdag-install.py status --target "$TARGET"
```

For another independent role, change `MODE` and choose a **different fresh**
`TARGET` and suitable owner settings. Do not run competing services on the same
ports. Pool-only needs a real existing Core endpoint; dashboard-only needs
real observer endpoints. This is not permission to point at someone else's
private RPC service or pool.

The generated runner uses shipped v2 `verify`, `plan`, `install`, `apply` and
`boot`, maps logical PostgreSQL to the actual service, and excludes unselected
services. It pins the selected archives and generated configuration. It does
not add dashboard-api, watch/repair automation or a Docker control socket to the
dashboard. Do not bypass a pin mismatch by editing the receipt.

## 4. Read the real state and retain rollback

Installed, running, syncing and mining-ready are different states. Fresh Core
starts at genesis or the imported boundary and catches up. The pool supervisor
may correctly wait for Core readiness. A running container or healthy dashboard
does not prove accepted shares, accepted blocks or accounting progression.

Before directing physical miners at a pool, independently verify current
compatible peers, native/EVM currentness, template/submission readiness, exact
payout and fee, then advancing accepted shares, block submissions and accounting.
The companion does not automatically assign ASICs or erase their existing setup.

## RC65 migration boundary

RC65 to RC2 migration is prominently **NOT QUALIFIED**. Maintainer migration
testing was not performed. Read [MIGRATION.md](MIGRATION.md) before considering
any owner-authorized investigation; [MIGRATION-AGENTS.md](MIGRATION-AGENTS.md)
is a read-only AI planning guide. Staying on RC65 or making a separate fresh
RC2 installation are the supported alternatives in this companion.

```sh
python3 bdag-install.py status --target "$TARGET"
python3 bdag-install.py stop --target "$TARGET"
```

Stop preserves containers and volumes; it does not run `down -v`, erase a chain
or delete PostgreSQL. Retain the predecessor until your own activation and
rollback test passes. Original TesterD physical-mining evidence remains a
separate 120-second AMD64 receipt, not a promise that your fresh node is already
synced. Native VM service tests do not claim a reboot, six-hour soak or ARM ASIC
qualification.
