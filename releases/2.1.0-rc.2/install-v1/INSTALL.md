# RC2 independent installation companion v1

This guide supersedes older installation instructions inside the unchanged RC2
archives. It supplies a real service runner for the shipped v2 lifecycle. No
mandatory publisher signature, signing key, GitHub account or central approval
is required. SHA-256 and chain identity checks are still required.

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
cd rc2-tools
BASE='https://blockdagengineering.github.io/bdag-ipfs-release-page/releases/2.1.0-rc.2'
for name in bdag-download.py bdag-install.py service-runner.py downloads.json COMPANION-SHA256SUMS; do
  curl --fail --location --proto '=https' "$BASE/install-v1/$name" --output "$name"
done
curl --fail --location --proto '=https' "$BASE/records/release.json" --output release.json
printf '%s  %s\n' '468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2' release.json | sha256sum -c -
sha256sum -c COMPANION-SHA256SUMS --ignore-missing
python3 bdag-download.py \
  --manifest downloads.json \
  --expect-manifest-sha256 54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c \
  --output-dir rc2-software --select software --transport http
```

Native IPFS is an independent alternative; see [DOWNLOADS.md](DOWNLOADS.md).
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
(or matching `MINING_POOL_ADDRESS`). Set `POOL_FEE_PERCENTAGE` intentionally;
never inherit someone else's fee or payout by accident. Set the same intended
Core backend for `NODE_RPC_URLS`, `POOL_SUBMIT_RPC_URLS` and related backend
selection. Set your matching EVM endpoint as `WALLET_RPC_URL` when needed.
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
