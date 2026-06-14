#!/usr/bin/env sh
set -eu

VERSION="v6.3.20"
ARM64_NAME="pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-arm64"
ARM64_CID="bafybeif4zj4nyz7ykag3ttohkq3sirmo4ceacyz6whbpvc56ui6jhwt4uy"
ARM64_SHA256="287e78efe1ad4b718186b8745d57cfb223c25f29abc96469a10f544fcebe78f2"
AMD64_NAME="pool-stack-docker-v6.3.20-jeremy-dev-release.20260614-linux-amd64"
AMD64_CID="bafybeiafmnd5admxhhwdg6qjkhrpzwsc5lkvnr2mu7c45p3reqov5thkim"
AMD64_SHA256="b3ebac71da5e3019339d3a93d163cbb5965e1adad628631a5173d851f77320ce"
GATEWAYS="${BDAG_IPFS_GATEWAYS:-https://ipfs.io https://dweb.link https://gateway.pinata.cloud http://127.0.0.1:8081}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    echo "Ubuntu install: sudo apt-get update && sudo apt-get install -y curl unzip coreutils" >&2
    exit 1
  fi
}

case "$(uname -m 2>/dev/null || echo unknown)" in
  aarch64|arm64)
    RELEASE_NAME="$ARM64_NAME"
    ZIP_CID="$ARM64_CID"
    ZIP_SHA256="$ARM64_SHA256"
    ;;
  x86_64|amd64)
    RELEASE_NAME="$AMD64_NAME"
    ZIP_CID="$AMD64_CID"
    ZIP_SHA256="$AMD64_SHA256"
    ;;
  *)
    echo "Unsupported CPU architecture: $(uname -m 2>/dev/null || echo unknown)" >&2
    echo "This release publishes linux-arm64 and linux-amd64 payloads only." >&2
    exit 1
    ;;
esac
ZIP_NAME="$RELEASE_NAME.zip"

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

cat <<MSG

BlockDAG pool stack payload extracted:
  $RELEASE_NAME

Next, follow the Intermediate flow from the IPFS page:
  1. Download and verify the chain-data archive.
  2. Extract it into $RELEASE_NAME/data/node/mainnet.
  3. Run node-only or pool mode from inside $RELEASE_NAME.

Node-only after chain restore:
  cd $RELEASE_NAME
  BDAG_DEPLOY_KIND=node BDAG_CHAIN_MODE=non-archive bash ./install.sh

Pool mode requires your own public mining address. Enter the private key only
through the hidden prompt or a secure local environment, never in public chat.
MSG

if [ "${BDAG_RUN_INSTALL:-0}" = "1" ]; then
  cd "$RELEASE_NAME"
  exec bash ./install.sh "$@"
fi
