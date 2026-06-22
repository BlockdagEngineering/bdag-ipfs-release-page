#!/usr/bin/env sh
set -eu

VERSION="pool-v6.5.7"
REPOSITORY="BlockdagEngineering/stack"
PACKAGE_NAME="pool-stack-docker"
RAW_SNAPSHOT_ARCHIVE_URL="${BDAG_RAW_SNAPSHOT_ARCHIVE_URL:-https://blockchain-state-backup.s3.us-west-1.amazonaws.com/blockdag-miner-backups/ipfs-snapshots/latest/bdag-latest-snapshot.tar.gz}"
RAW_SNAPSHOT_ARCHIVE_NAME="${BDAG_RAW_SNAPSHOT_ARCHIVE_NAME:-bdag-latest-snapshot.tar.gz}"

AMD64_SHA256="8d292703d77b656d85bfabf16df7b4ce4f86454a5c075a3c292a5b00f08bd852"
ARM64_SHA256="53ac85c8f6337fd1d0cebbc17c3cf17804f371dcaf2270515e196c4223e50c6c"
AMD64_CID="bafybeibc562phfnizztpulf76p57dvhw3xl7kv6zwmhjwu37iglk4sizua"
ARM64_CID="bafybeibobaofgsdlingiday5ea3hf62rludb4u5n6lgxaj3mgjbv35goqe"
AMD64_FILEBASE_CID="QmVYwag8QduE1JTJV7U6Y2m23C3GGhfHMQEzzxhsUuedAy"
ARM64_FILEBASE_CID="QmfXXCaWfxGjfRSaxG4cBYU43H61XHafeFxGZmMhtSTbX4"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    echo "Ubuntu install: sudo apt-get update && sudo apt-get install -y curl unzip coreutils" >&2
    exit 1
  fi
}

release_bootstrap_peers() {
  cat <<'PEERS'
/ip4/3.126.64.13/tcp/8152/p2p/16Uiu2HAmEFxRaBbbf3sRi43CCvMk5Y6zPkuGY9s4uRK2FKJVJkqo
/ip4/63.182.36.180/tcp/8150/p2p/16Uiu2HAmP8HsTF9ks8JjFamzT9JBZb3ymSiCJ8rkzXBZqYj4yKtP
/ip4/16.28.133.168/tcp/8150/p2p/16Uiu2HAm9UcTayJDSajjJYsWwVaN2qqGeczcs9kXse3dMdvGDRjz
/ip4/169.0.254.182/tcp/8150/p2p/16Uiu2HAmGsEDGnDGhvziZR1UQSELTDihXRKYMB6SrbEQ6NsWBVqD
/ip4/13.140.165.186/tcp/8150/p2p/16Uiu2HAm4hHD7Ht5LJrLgaKXr7YP2RzHHjrrCLNt8zv8FQ9s3gBU
/ip4/102.39.221.179/tcp/8152/p2p/16Uiu2HAm8ebvL9NTNwgLYwm8LEEXSY7QKQhQ7YVcAV7PR6ymsrTm
/ip4/80.141.136.179/tcp/8151/p2p/16Uiu2HAmMZNeDNLgfLXFKzEiWZHFjdDejLSCzhunJMYWoYhdT3gv
/ip4/102.39.221.179/tcp/8150/p2p/16Uiu2HAmNQznwWPjuAUhXnTkP6EuWsEHa4eRnb1aTm3WcZQKsrFn
/ip4/47.156.6.142/tcp/8151/p2p/16Uiu2HAmJz7PTCxSWTnuJhvbf4oXEffFZ1KAE3yNBX9SY72jS1ta
/ip4/218.32.84.82/tcp/8150/p2p/16Uiu2HAmNjFKhP3945Az3afdBSUSRwhgDw1uGRBDsqSvSduStbWJ
/ip4/5.78.193.245/tcp/8150/p2p/16Uiu2HAkwosZsQdtgAQHoJ57MFKpWnyfGJtSpt2R2aJMgR6ywGME
PEERS
}

apply_release_bootstrap_peers() {
  release_dir="$1"
  peer_file="$release_dir/release-bootstrap-peers.txt"
  release_bootstrap_peers | awk 'NF && !seen[$0]++ { print }' > "$peer_file"

  python3 - "$release_dir" "$peer_file" <<'PY'
from pathlib import Path
import sys

release_dir = Path(sys.argv[1])
peer_file = Path(sys.argv[2])
release_peers = [line.strip() for line in peer_file.read_text().splitlines() if line.strip()]
peers = []
seen = set()

def add_peer(peer):
    peer = peer.strip()
    if peer and peer not in seen:
        seen.add(peer)
        peers.append(peer)

node_conf = release_dir / "node.conf.example"
if node_conf.exists():
    lines = node_conf.read_text().splitlines()
    for peer in release_peers:
        add_peer(peer)
    for line in lines:
        if line.startswith("addpeer="):
            add_peer(line.split("=", 1)[1])
    peer_file.write_text("\n".join(peers) + "\n")
    output = []
    inserted = False
    for line in lines:
        if line.startswith("addpeer="):
            if not inserted:
                output.extend(f"addpeer={peer}" for peer in peers)
                inserted = True
            continue
        output.append(line)
    if not inserted:
        output.extend(f"addpeer={peer}" for peer in peers)
    node_conf.write_text("\n".join(output) + "\n")
else:
    for peer in release_peers:
        add_peer(peer)
    peer_file.write_text("\n".join(peers) + "\n")

csv = ",".join(peers)

env_example = release_dir / ".env.example"
if env_example.exists():
    lines = env_example.read_text().splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("BOOTSTRAP_PEER_ADDRESSES="):
            lines[index] = "BOOTSTRAP_PEER_ADDRESSES=" + csv
            replaced = True
            break
    if not replaced:
        lines.append("BOOTSTRAP_PEER_ADDRESSES=" + csv)
    env_example.write_text("\n".join(lines) + "\n")
PY
}

sudo_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

download_file() {
  download_url="$1"
  download_path="$2"
  resume="${3:-0}"
  attempt=1
  max_attempts="${4:-${BDAG_DOWNLOAD_MAX_ATTEMPTS:-50}}"

  while [ "$attempt" -le "$max_attempts" ]; do
    if [ "$resume" = "1" ]; then
      if curl -4 -fL --http1.1 --connect-timeout 20 --speed-limit 1024 --speed-time 120 --continue-at - --output "$download_path.part" "$download_url"; then
        mv "$download_path.part" "$download_path"
        return 0
      fi
    else
      rm -f "$download_path.part"
      if curl -4 -fL --http1.1 --connect-timeout 20 --speed-limit 1024 --speed-time 120 --output "$download_path.part" "$download_url"; then
        mv "$download_path.part" "$download_path"
        return 0
      fi
    fi

    echo "Download failed, retrying ($attempt/$max_attempts): $download_url" >&2
    attempt=$((attempt + 1))
    sleep 5
  done

  echo "Download failed after $max_attempts attempts: $download_url" >&2
  return 1
}

download_ipfs_cid() {
  primary_cid="$1"
  download_path="$2"
  resume="${3:-0}"
  attempts="${4:-${BDAG_GATEWAY_DOWNLOAD_ATTEMPTS:-8}}"
  if [ "$#" -gt 4 ]; then
    shift 4
  else
    shift "$#"
  fi

  for cid in "$primary_cid" "$@"; do
    [ -n "$cid" ] || continue
    for download_url in "https://ipfs.io/ipfs/$cid" "https://ipfs.filebase.io/ipfs/$cid" "https://$cid.ipfs.inbrowser.link/" "https://$cid.ipfs.dweb.link/" "https://dweb.link/ipfs/$cid"; do
      echo "Trying IPFS gateway: $download_url"
      if download_file "$download_url" "$download_path" "$resume" "$attempts"; then
        return 0
      fi
    done
  done

  echo "All IPFS gateways failed for CID(s): $primary_cid $*" >&2
  return 1
}

snapshot_header_value() {
  key="$1"
  headers="$2"
  awk -v key="$key" '
    {
      line = $0
      sub(/\r$/, "", line)
      lower = tolower(line)
      if (index(lower, tolower(key) ":") == 1) {
        sub(/^[^:]*:[ \t]*/, "", line)
        value = line
      }
    }
    END { print value }
  ' "$headers"
}

fetch_snapshot_headers() {
  headers="$1"
  rm -f "$headers"
  curl -4 -fsSLI --http1.1 --connect-timeout 20 --speed-limit 1024 --speed-time 120 \
    -D "$headers" -o /dev/null "$RAW_SNAPSHOT_ARCHIVE_URL"
}

disable_ipv6_for_docker_pulls() {
  if [ "${BDAG_DISABLE_IPV6:-1}" != "1" ]; then
    return 0
  fi

  if [ ! -d /proc/sys/net/ipv6 ]; then
    return 0
  fi

  if [ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6 2>/dev/null || echo 0)" = "1" ]; then
    return 0
  fi

  if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is not available; cannot disable IPv6 before Docker pulls." >&2
    echo "Set BDAG_DISABLE_IPV6=0 to skip this guard, or run the prerequisite command as documented." >&2
    return 1
  fi

  echo "Disabling host IPv6 for this install to avoid Docker Hub IPv6 fallback timeouts."
  printf 'net.ipv6.conf.all.disable_ipv6 = 1\nnet.ipv6.conf.default.disable_ipv6 = 1\n' |
    sudo_cmd tee /etc/sysctl.d/99-bdag-disable-ipv6.conf >/dev/null
  sudo_cmd sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
  sudo_cmd sysctl -w net.ipv6.conf.default.disable_ipv6=1 >/dev/null
}

docker_pull_with_retry() {
  image="$1"
  case "$image" in
    ""|scratch|*'$'*)
      return 0
      ;;
    *:*|*/*)
      ;;
    *)
      echo "Skipping local Docker stage/image: $image"
      return 0
      ;;
  esac

  attempt=1
  max_attempts="${BDAG_DOCKER_PULL_MAX_ATTEMPTS:-8}"

  while [ "$attempt" -le "$max_attempts" ]; do
    echo "Pre-pulling Docker image ($attempt/$max_attempts): $image"
    if docker pull "$image"; then
      return 0
    fi

    sleep_seconds=$((attempt * 5))
    if [ "$sleep_seconds" -gt 30 ]; then
      sleep_seconds=30
    fi
    echo "Docker image pull failed, retrying in ${sleep_seconds}s: $image" >&2
    attempt=$((attempt + 1))
    sleep "$sleep_seconds"
  done

  echo "Docker image pull failed after $max_attempts attempts: $image" >&2
  return 1
}

collect_dockerfile_images() {
  find "$RELEASE_NAME" -maxdepth 4 -type f \( -iname 'Dockerfile' -o -iname 'dockerfile' -o -iname 'Dockerfile.*' \) -print |
    while IFS= read -r dockerfile; do
      awk '
        tolower($1) == "from" {
          image = $2
          if (image ~ /^--/) {
            image = $3
          }
          gsub(/"/, "", image)
          gsub(/\047/, "", image)
          print image
        }
      ' "$dockerfile"
    done
}

prepull_container_images() {
  if [ "${BDAG_PREPULL_DOCKER_IMAGES:-1}" != "1" ]; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not available yet; skipping pre-pull retry step." >&2
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but not usable by this user." >&2
    echo "Run the prerequisite command, then log out and back in so Docker group access applies." >&2
    return 1
  fi

  image_list="$RELEASE_NAME/.bdag-prepull-images"
  {
    collect_dockerfile_images
    for image in ${BDAG_PREPULL_EXTRA_IMAGES:-postgres:15-bookworm}; do
      echo "$image"
    done
  } | sed '/^$/d' | sort -u > "$image_list"

  if [ ! -s "$image_list" ]; then
    rm -f "$image_list"
    return 0
  fi

  while IFS= read -r image; do
    docker_pull_with_retry "$image" || {
      rm -f "$image_list"
      return 1
    }
  done < "$image_list"
  rm -f "$image_list"
}

restore_raw_snapshot() {
  need tar
  need zstd

  snapshot_dir="$RELEASE_NAME/chain-download"
  snapshot_headers="$snapshot_dir/snapshot.headers"
  mkdir -p "$snapshot_dir"

  echo "Reading snapshot metadata from S3"
  fetch_snapshot_headers "$snapshot_headers"

  archive_name="$RAW_SNAPSHOT_ARCHIVE_NAME"
  archive_sha="$(snapshot_header_value "x-amz-meta-sha256" "$snapshot_headers")"
  archive_size="$(snapshot_header_value "content-length" "$snapshot_headers" | tr -d ' ')"
  archive_created="$(snapshot_header_value "x-amz-meta-created-at" "$snapshot_headers")"

  if [ -z "$archive_sha" ]; then
    echo "Snapshot metadata did not include x-amz-meta-sha256; refusing unverified restore." >&2
    exit 1
  fi

  case "$archive_name" in
    ""|*/*|*\\*) echo "Invalid snapshot archive name: $archive_name" >&2; exit 1 ;;
  esac

  archive_path="$snapshot_dir/$archive_name"
  if [ ! -f "$archive_path" ]; then
    echo "Downloading snapshot archive from S3"
    download_file "$RAW_SNAPSHOT_ARCHIVE_URL" "$archive_path" 1 "${BDAG_SNAPSHOT_DOWNLOAD_ATTEMPTS:-8}"
  fi

  if [ -n "$archive_size" ]; then
    actual_size="$(wc -c < "$archive_path" | tr -d ' ')"
    if [ "$actual_size" != "$archive_size" ]; then
      echo "Snapshot size mismatch: expected $archive_size, got $actual_size" >&2
      exit 1
    fi
  fi

  printf '%s  %s\n' "$archive_sha" "$archive_path" | sha256sum -c -

  target_dir="$RELEASE_NAME/data/node/mainnet"
  mkdir -p "$target_dir"
  if [ -n "$(find "$target_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "Refusing to restore into non-empty directory: $target_dir" >&2
    exit 1
  fi

  echo "Extracting snapshot into $target_dir"
  tar --zstd -xf "$archive_path" -C "$target_dir"
  if [ -n "$archive_created" ]; then
    echo "Snapshot restore complete. Created: ${archive_created:-unknown}."
  else
    echo "Snapshot restore complete."
  fi
}

OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
ARCH_NAME="$(uname -m 2>/dev/null || echo unknown)"

case "$OS_NAME" in
  Linux) ;;
  *)
    echo "Unsupported operating system: $OS_NAME. This release publishes Linux payloads only." >&2
    exit 1
    ;;
esac

case "$ARCH_NAME" in
  x86_64|amd64)
    TARGET="linux-amd64"
    ZIP_SHA256="$AMD64_SHA256"
    ZIP_CID="$AMD64_CID"
    ZIP_FALLBACK_CIDS="$AMD64_FILEBASE_CID"
    ;;
  aarch64|arm64)
    TARGET="linux-arm64"
    ZIP_SHA256="$ARM64_SHA256"
    ZIP_CID="$ARM64_CID"
    ZIP_FALLBACK_CIDS="$ARM64_FILEBASE_CID"
    ;;
  *)
    echo "Unsupported CPU architecture: $ARCH_NAME" >&2
    echo "This release publishes linux-amd64 and linux-arm64 payloads only." >&2
    exit 1
    ;;
esac

RELEASE_NAME="$PACKAGE_NAME-$VERSION-$TARGET"
ZIP_NAME="$RELEASE_NAME.zip"

need curl
need unzip
need sha256sum
need python3

PRESERVED_CHAIN_DOWNLOAD=""
if [ -e "$RELEASE_NAME" ]; then
  if [ "${BDAG_RESTORE_SNAPSHOT:-0}" = "1" ] && [ -d "$RELEASE_NAME/chain-download" ] && [ ! -f "$RELEASE_NAME/.env" ] && [ ! -d "$RELEASE_NAME/data" ]; then
    PRESERVED_CHAIN_DOWNLOAD="$RELEASE_NAME.chain-download.resume"
    rm -rf "$PRESERVED_CHAIN_DOWNLOAD"
    mv "$RELEASE_NAME/chain-download" "$PRESERVED_CHAIN_DOWNLOAD"
    rm -rf "$RELEASE_NAME"
  else
    echo "Refusing to overwrite existing directory: $RELEASE_NAME" >&2
    echo "Move it aside or run from a clean install directory." >&2
    exit 1
  fi
fi

rm -f "$ZIP_NAME.part"
if [ ! -f "$ZIP_NAME" ]; then
  echo "Downloading $ZIP_NAME from IPFS CID $ZIP_CID"
  download_ipfs_cid "$ZIP_CID" "$ZIP_NAME" 1 "${BDAG_GATEWAY_PAYLOAD_ATTEMPTS:-8}" $ZIP_FALLBACK_CIDS
fi

printf '%s  %s\n' "$ZIP_SHA256" "$ZIP_NAME" | sha256sum -c -
unzip -q "$ZIP_NAME"

if [ -n "$PRESERVED_CHAIN_DOWNLOAD" ]; then
  rm -rf "$RELEASE_NAME/chain-download"
  mv "$PRESERVED_CHAIN_DOWNLOAD" "$RELEASE_NAME/chain-download"
fi

if [ ! -f "$RELEASE_NAME/install.sh" ]; then
  echo "Payload did not contain expected installer: $RELEASE_NAME/install.sh" >&2
  exit 1
fi

if [ -f "$RELEASE_NAME/dockerfile" ] && ! grep -Eq '^ARG SNAPSHOT_PATH=' "$RELEASE_NAME/dockerfile"; then
  tmp_dockerfile="$RELEASE_NAME/dockerfile.tmp"
  awk '
    /^COPY \$\{SNAPSHOT_PATH\}/ && !inserted {
      print "ARG SNAPSHOT_PATH=docker/no-snapshot.marker"
      inserted=1
    }
    { print }
  ' "$RELEASE_NAME/dockerfile" > "$tmp_dockerfile"
  mv "$tmp_dockerfile" "$RELEASE_NAME/dockerfile"
fi

INSTALLER="$RELEASE_NAME/installers/install-unix-common.sh"
if [ -f "$INSTALLER" ] && grep -q 'postgres node dashboard' "$INSTALLER"; then
  sed -i 's/postgres node dashboard/pool-db node dashboard/g' "$INSTALLER"
fi
if [ -f "$INSTALLER" ] && grep -q -- '--pull never pool-db node dashboard' "$INSTALLER"; then
  sed -i 's/--pull never pool-db node dashboard/--pull missing pool-db node dashboard/g' "$INSTALLER"
fi
if [ -f "$INSTALLER" ] && grep -q 'if download_snapshot; then' "$INSTALLER"; then
  sed -i 's/if download_snapshot; then/if [[ "${BDAG_SKIP_BDSNAP_DOWNLOAD:-0}" != "1" ]] \&\& download_snapshot; then/g' "$INSTALLER"
fi
if [ -f "$INSTALLER" ] && grep -q 'openssl rand -base64 32' "$INSTALLER"; then
  sed -i 's/openssl rand -base64 32/openssl rand -hex 32/g' "$INSTALLER"
fi
if [ -f "$INSTALLER" ] && grep -q 'set_env_value .env BDAG_NODE_ARCHIVAL' "$INSTALLER"; then
  sed -i '/set_env_value .env BDAG_NODE_ARCHIVAL/a set_env_value .env NODE_DATA_DIR "./data/node"' "$INSTALLER"
fi
apply_release_bootstrap_peers "$RELEASE_NAME"
if [ -f "$INSTALLER" ] && grep -Fq '172\.(1[6-9]|2[0-9]|3[0-1])\.' "$INSTALLER"; then
  # The packaged installer treats all 172.16.0.0/12 addresses as Docker bridge
  # space, which rejects real AWS VPC host addresses such as 172.31.x.x.
  python3 - "$INSTALLER" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace('[[ "$1" =~ ^172\\.(1[6-9]|2[0-9]|3[0-1])\\. ]]', '[[ "$1" =~ ^172\\.17\\. ]]')
text = text.replace('172\\.(1[6-9]|2[0-9]|3[0-1])\\.', '172\\.17\\.')
text = text.replace('172.16.0.0/12', '172.17.0.0/16')
path.write_text(text)
PY
fi

chmod +x "$RELEASE_NAME/install.sh" "$RELEASE_NAME/installers/"*.sh 2>/dev/null || true

if [ "${BDAG_SKIP_PAYLOAD_INSTALL:-0}" != "1" ]; then
  disable_ipv6_for_docker_pulls
  prepull_container_images
fi

if [ "${BDAG_RESTORE_SNAPSHOT:-0}" = "1" ]; then
  restore_raw_snapshot
  export BDAG_SKIP_BDSNAP_DOWNLOAD=1
fi

cat <<MSG

BlockDAG pool stack payload verified and extracted:
  $RELEASE_NAME

Starting the packaged installer now. To only download and extract, set:
  BDAG_SKIP_PAYLOAD_INSTALL=1
MSG

if [ "${BDAG_SKIP_PAYLOAD_INSTALL:-0}" = "1" ]; then
  exit 0
fi

export BDAG_CHAIN_MODE="${BDAG_CHAIN_MODE:-non-archive}"
export BDAG_SKIP_BDSNAP_DOWNLOAD="${BDAG_SKIP_BDSNAP_DOWNLOAD:-1}"

cd "$RELEASE_NAME"
exec sh ./install.sh "$@"
