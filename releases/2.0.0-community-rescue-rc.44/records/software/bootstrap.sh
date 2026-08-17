#!/usr/bin/env sh
set -eu

if [ "$(id -u)" -eq 0 ]; then
  echo "Do not run the BlockDAG bootstrap as root or through sudo." >&2
  echo "Run it as the non-root installation user; bounded host changes elevate later." >&2
  exit 2
fi

VERSION='2.0.0-community-rescue-rc.44'
REPOSITORY='BlockdagEngineering/stack'
PACKAGE_NAME='pool-stack-docker'
DOWNLOAD_BASE='https://github.com/'"$REPOSITORY"'/releases/download/'"$VERSION"
EXPECTED_RELEASE_KEY_SHA256='26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb'
EXPECTED_RELEASE_SEQUENCE='44'

OS_NAME=$(uname -s 2>/dev/null || echo unknown)
ARCH_NAME=$(uname -m 2>/dev/null || echo unknown)

case "$OS_NAME" in
  Linux) ;;
  *)
    echo "Unsupported operating system: $OS_NAME. Only Linux is currently supported." >&2
    exit 1
    ;;
esac

case "$ARCH_NAME" in
  x86_64|amd64)
    PAYLOAD_TARGET='linux-amd64'
    EXPECTED_SHA256='8713bf3035ecabe2867492a60214fcabfe16c257c9575d939da2b35984e445bd'
    ;;
  arm64|aarch64)
    PAYLOAD_TARGET='linux-arm64'
    EXPECTED_SHA256='f96fd9f4e35b83e2fe052914dbe5f85626c672d9caf7d8886aecb1458e39388c'
    ;;
  *)
    echo "Unsupported CPU architecture: $ARCH_NAME" >&2
    exit 1
    ;;
esac

ASSET="$PACKAGE_NAME-$VERSION-$PAYLOAD_TARGET.zip"
ROOT="$PACKAGE_NAME-$VERSION-$PAYLOAD_TARGET"
URL="$DOWNLOAD_BASE/$ASSET"
CHECKSUM_ASSET="$ASSET.sha256"
CHECKSUM_URL="$DOWNLOAD_BASE/$CHECKSUM_ASSET"
INSTALL_DIR="${BDAG_INSTALL_DIR:-$ROOT}"
ZIP_PATH="$ASSET"
CHECKSUM_PATH="$CHECKSUM_ASSET"

if [ -z "${BDAG_RELEASE_VERSION:-}" ]; then
  echo "BDAG_RELEASE_VERSION must be set from the operator-controlled release trust record." >&2
  exit 1
fi
if [ "$BDAG_RELEASE_VERSION" != "$VERSION" ]; then
  echo "The supplied release tag does not match this release." >&2
  exit 1
fi
if [ -z "${BDAG_RELEASE_KEY_SHA256:-}" ]; then
  echo "BDAG_RELEASE_KEY_SHA256 must be set from the operator-controlled release trust record." >&2
  exit 1
fi
if [ "$BDAG_RELEASE_KEY_SHA256" != "$EXPECTED_RELEASE_KEY_SHA256" ]; then
  echo "The supplied release public-key fingerprint does not match this release." >&2
  exit 1
fi
if [ -z "${BDAG_RELEASE_SEQUENCE:-}" ]; then
  echo "BDAG_RELEASE_SEQUENCE must be set from the operator-controlled release trust record." >&2
  exit 1
fi
if [ "$BDAG_RELEASE_SEQUENCE" != "$EXPECTED_RELEASE_SEQUENCE" ]; then
  echo "The supplied release sequence does not match this release." >&2
  exit 1
fi

if [ "$INSTALL_DIR" != "$ROOT" ]; then
  echo "BDAG_INSTALL_DIR is not supported by this pinned bootstrap; remove it and re-run." >&2
  exit 1
fi

if [ -e "$ROOT" ]; then
  echo "Refusing to overwrite existing directory: $ROOT" >&2
  exit 1
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command missing: $1" >&2
    exit 1
  fi
}

print_docker_install_instructions() {
  cat >&2 <<'DOCKER_INSTRUCTIONS'

Install Docker Engine first, then re-run this installer.

Quick install (most Linux distros):

  curl -fsSL https://get.docker.com | sh

Then enable the daemon and let your user run docker without sudo:

  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  newgrp docker   # or log out and back in

Verify everything works:

  docker run --rm hello-world
  docker compose version

Notes:
  - Avoid your distro's docker.io package; it is often outdated.
  - Membership in the docker group is root-equivalent on this host. On a
    multi-admin box, skip the usermod step and run the installer with a
    user that can sudo docker instead.
DOCKER_INSTRUCTIONS
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed." >&2
  print_docker_install_instructions
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: Docker is installed but the Docker Compose v2 plugin is missing." >&2
  echo "Install/update Docker Engine (includes docker-compose-plugin):" >&2
  print_docker_install_instructions
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is installed but this user cannot reach the Docker daemon." >&2
  cat >&2 <<'DOCKER_ACCESS'

Fix daemon access, then re-run this installer:

  sudo systemctl enable --now docker     # make sure the daemon is running
  sudo usermod -aG docker "$USER"        # allow docker without sudo
  newgrp docker                          # or log out and back in
DOCKER_ACCESS
  exit 1
fi

require_command curl
require_command unzip
require_command bash
require_command sha256sum

echo "Downloading $ASSET"
rm -f "$ZIP_PATH" "$ZIP_PATH.part" "$CHECKSUM_PATH" "$CHECKSUM_PATH.part"
curl --fail --location --show-error --silent -o "$CHECKSUM_PATH.part" "$CHECKSUM_URL"
mv "$CHECKSUM_PATH.part" "$CHECKSUM_PATH"
curl --fail --location --show-error --progress-bar -o "$ZIP_PATH.part" "$URL"
mv "$ZIP_PATH.part" "$ZIP_PATH"

EXPECTED_CHECKSUM_LINE="$EXPECTED_SHA256  $ASSET"
ACTUAL_CHECKSUM_LINE=$(cat "$CHECKSUM_PATH")
if [ "$ACTUAL_CHECKSUM_LINE" != "$EXPECTED_CHECKSUM_LINE" ]; then
  echo "Attached checksum does not match the signed bootstrap digest for $ASSET" >&2
  rm -f "$ZIP_PATH" "$CHECKSUM_PATH"
  exit 1
fi
sha256sum -c "$CHECKSUM_PATH"

echo "Extracting $ASSET"
unzip -q "$ZIP_PATH"
rm -f "$ZIP_PATH" "$CHECKSUM_PATH"

if [ ! -f "$ROOT/install.sh" ]; then
  echo "Payload did not contain expected installer: $ROOT/install.sh" >&2
  exit 1
fi

chmod +x "$ROOT/install.sh" 2>/dev/null || true
exec bash "$ROOT/install.sh" "$@"
