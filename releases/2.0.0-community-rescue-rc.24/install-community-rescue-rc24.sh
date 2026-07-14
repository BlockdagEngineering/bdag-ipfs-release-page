#!/usr/bin/env sh
set -eu

VERSION='2.0.0-community-rescue-rc.24'
SEQUENCE='24'
PACKAGE_NAME='pool-stack-docker'
RELEASE_KEY_SHA256='26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb'
GITHUB_BASE='https://github.com/BlockdagEngineering/stack/releases/download/2.0.0-community-rescue-rc.24'

case "$(uname -s 2>/dev/null || true)" in
  Linux) ;;
  *) printf 'This release supports Linux only.\n' >&2; exit 1 ;;
esac

case "$(uname -m 2>/dev/null || true)" in
  x86_64|amd64)
    TARGET='linux-amd64'
    CID='bafybeigpo7hyqw66hpsdlm7jvwibvtn5cepieeeg6ukoo2dxtpbd57g73a'
    SHA256='98fd017437ee8e2285b34448d53919b6ce92e76e20c626ad316653af0d1bfaf7'
    ;;
  aarch64|arm64)
    TARGET='linux-arm64'
    CID='bafybeia5hwjuaiubcyz6i5ncrqakgbwzi6o3sw2nx4waybtscgchlhqn3a'
    SHA256='74f6695d8954725907b75a0947c48385ae953f6f2973c08ed5e2e61c677fac7a'
    ;;
  *) printf 'Unsupported CPU architecture.\n' >&2; exit 1 ;;
esac

for command_name in curl unzip sha256sum bash; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$command_name" >&2
    exit 1
  }
done

ASSET="$PACKAGE_NAME-$VERSION-$TARGET.zip"
ROOT="$PACKAGE_NAME-$VERSION-$TARGET"
PART="$ASSET.part"

if [ -e "$ROOT" ]; then
  printf 'Refusing to overwrite existing directory: %s\n' "$ROOT" >&2
  exit 1
fi

downloaded=0
for url in \
  "https://dweb.link/ipfs/$CID" \
  "https://ipfs.io/ipfs/$CID" \
  "$GITHUB_BASE/$ASSET"
do
  printf 'Downloading %s via %s\n' "$ASSET" "$url"
  if curl -4 --http1.1 --fail --location --show-error \
    --connect-timeout 20 --retry 8 --retry-delay 3 --retry-all-errors \
    --speed-limit 1024 --speed-time 90 -C - -o "$PART" "$url"; then
    downloaded=1
    break
  fi
done

if [ "$downloaded" -ne 1 ]; then
  printf 'All download sources failed. Re-run to resume the partial file.\n' >&2
  exit 1
fi

mv "$PART" "$ASSET"
printf '%s  %s\n' "$SHA256" "$ASSET" | sha256sum -c -
unzip -q "$ASSET"

if [ "${BDAG_KEEP_PACKAGE:-0}" != 1 ]; then
  rm -f "$ASSET"
fi

export BDAG_RELEASE_VERSION="$VERSION"
export BDAG_RELEASE_SEQUENCE="$SEQUENCE"
export BDAG_RELEASE_KEY_SHA256="$RELEASE_KEY_SHA256"

exec bash "$ROOT/install.sh" "$@"
