#!/usr/bin/env sh
set -eu

VERSION="v6.3.20"
RELEASE_NAME="pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64"
ZIP_NAME="$RELEASE_NAME.zip"
ZIP_CID="bafybeigpe7s3yd4vk6u6fba56stusoxqalob6oi2rm5tbbpc5aqzu7mn2i"
ZIP_SHA256="ecbf300959402815f8c3dd1d5334af927385766dae5c527ec202040e2a49f39c"
GATEWAYS="${BDAG_IPFS_GATEWAYS:-https://ipfs.io https://dweb.link https://gateway.pinata.cloud http://127.0.0.1:8081}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    echo "Ubuntu install: sudo apt-get update && sudo apt-get install -y curl unzip coreutils" >&2
    exit 1
  fi
}

need curl
need unzip
need sha256sum

if [ -e "$RELEASE_NAME" ]; then
  echo "Refusing to overwrite existing directory: $RELEASE_NAME" >&2
  echo "Move it aside or run from a clean install directory." >&2
  exit 1
fi

rm -f "$ZIP_NAME.part"
if [ ! -f "$ZIP_NAME" ]; then
  ok=0
  for gw in $GATEWAYS; do
    url="${gw%/}/ipfs/$ZIP_CID"
    echo "Downloading $ZIP_NAME from $url"
    if curl -fL --retry 3 --connect-timeout 20 --output "$ZIP_NAME.part" "$url"; then
      mv "$ZIP_NAME.part" "$ZIP_NAME"
      ok=1
      break
    fi
    rm -f "$ZIP_NAME.part"
  done
  if [ "$ok" != "1" ]; then
    echo "Could not download $ZIP_NAME from any configured gateway." >&2
    exit 1
  fi
fi

printf '%s  %s\n' "$ZIP_SHA256" "$ZIP_NAME" | sha256sum -c -
unzip -q "$ZIP_NAME"
cd "$RELEASE_NAME"

cat <<'MSG'

BlockDAG pool stack payload extracted.

For node-only install:
  BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh

For pool install, use your own wallet address and keep the private key secret:
  MINING_POOL_ADDRESS=0xYOUR_PUBLIC_ADDRESS POOL_PRIVATE_KEY=YOUR_PRIVATE_KEY BDAG_DEPLOY_KIND=pool BDAG_CHAIN_MODE=non-archive bash ./install.sh

Running the packaged installer now with your current environment.
MSG

exec bash ./install.sh "$@"
