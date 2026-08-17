#!/usr/bin/env sh
set -eu
umask 077

if [ "$(id -u)" -eq 0 ]; then
  echo "Do not run the BlockDAG bootstrap as root or through sudo." >&2
  echo "Run it as the non-root installation user; bounded host changes elevate later." >&2
  exit 2
fi

VERSION='jeremy-community-rescue-rc.65.6'
REPOSITORY='BlockdagEngineering/stack'
PACKAGE_NAME='pool-stack-docker'
DOWNLOAD_BASE='https://github.com/'"$REPOSITORY"'/releases/download/'"$VERSION"
EXPECTED_RELEASE_KEY_SHA256='26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb'
EXPECTED_RELEASE_SEQUENCE='65'

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
    EXPECTED_SHA256='6b06b9823b02b91e770de25d6f294b7e43ef17408d73d5d2829e779e544402ee'
    ;;
  arm64|aarch64)
    PAYLOAD_TARGET='linux-arm64'
    EXPECTED_SHA256='4dfa46478fedf49f91a74915f94f11ee2fecd9c9cd92e1b86ace5eadf68e1b17'
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
RESUME_MARKER=".${ROOT}.bootstrap-resume"
RESUME_MARKER_PART="$RESUME_MARKER.part"
EXPECTED_RESUME_LINE="$VERSION $PAYLOAD_TARGET $EXPECTED_SHA256"

if [ -n "${BDAG_RELEASE_VERSION:-}" ] && [ "$BDAG_RELEASE_VERSION" != "$VERSION" ]; then
  echo "The supplied release tag does not match this release." >&2
  exit 1
fi
if [ -n "${BDAG_RELEASE_KEY_SHA256:-}" ]   && [ "$BDAG_RELEASE_KEY_SHA256" != "$EXPECTED_RELEASE_KEY_SHA256" ]; then
  echo "The supplied release public-key fingerprint does not match this release." >&2
  exit 1
fi
if [ -n "${BDAG_RELEASE_SEQUENCE:-}" ]   && [ "$BDAG_RELEASE_SEQUENCE" != "$EXPECTED_RELEASE_SEQUENCE" ]; then
  echo "The supplied release sequence does not match this release." >&2
  exit 1
fi

if [ "$INSTALL_DIR" != "$ROOT" ]; then
  echo "BDAG_INSTALL_DIR is not supported by this pinned bootstrap; remove it and re-run." >&2
  exit 1
fi

if [ -L "$ROOT" ]; then
  echo "Refusing existing symlink installation root: $ROOT" >&2
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

Use Docker's signed official package repository instructions for your Linux
distribution:

  https://docs.docker.com/engine/install/

Choose your distribution and follow its repository setup and signing-key
verification steps. Install Docker Engine and the docker-compose-plugin from
that repository. Do not use a downloaded convenience script for production.

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
require_command find
require_command mktemp
require_command cmp
require_command openssl
require_command python3
require_command sync

echo "Downloading $ASSET"
rm -f "$CHECKSUM_PATH" "$CHECKSUM_PATH.part"
curl --fail --location --show-error --silent   --retry 5 --retry-delay 2 --retry-connrefused   -o "$CHECKSUM_PATH.part" "$CHECKSUM_URL"
mv "$CHECKSUM_PATH.part" "$CHECKSUM_PATH"

EXPECTED_CHECKSUM_LINE="$EXPECTED_SHA256  $ASSET"
ACTUAL_CHECKSUM_LINE=$(cat "$CHECKSUM_PATH")
if [ "$ACTUAL_CHECKSUM_LINE" != "$EXPECTED_CHECKSUM_LINE" ]; then
  echo "Attached checksum does not match the signed bootstrap digest for $ASSET" >&2
  rm -f "$CHECKSUM_PATH"
  exit 1
fi

part_matches() {
  candidate="$1"
  [ -f "$candidate" ]     && [ ! -L "$candidate" ]     && printf '%s  %s\n' "$EXPECTED_SHA256" "$candidate"       | sha256sum -c - >/dev/null 2>&1
}

fresh_download() {
  fresh_path="$ZIP_PATH.part.fresh"
  rm -f -- "$fresh_path"
  echo "Retrying one fresh download for $ASSET"
  if curl --fail --location --show-error --progress-bar     --retry 5 --retry-delay 2 --retry-connrefused     -o "$fresh_path" "$URL"; then
    if part_matches "$fresh_path"; then
      mv "$fresh_path" "$ZIP_PATH"
      return 0
    fi
    echo "Fresh download digest did not match $ASSET" >&2
    rm -f -- "$fresh_path"
    return 1
  fi
  if [ -f "$fresh_path" ] && [ ! -L "$fresh_path" ]; then
    mv "$fresh_path" "$ZIP_PATH.part"
  fi
  return 1
}

if part_matches "$ZIP_PATH"; then
  echo "Using previously completed $ASSET"
else
  rm -f -- "$ZIP_PATH"
  if part_matches "$ZIP_PATH.part"; then
    echo "Using completed resumable download for $ASSET"
    mv "$ZIP_PATH.part" "$ZIP_PATH"
  elif [ -f "$ZIP_PATH.part" ] && [ ! -L "$ZIP_PATH.part" ]; then
    echo "Resuming $ASSET"
    if curl --fail --location --show-error --progress-bar       --retry 5 --retry-delay 2 --retry-connrefused       --continue-at - -o "$ZIP_PATH.part" "$URL"       && part_matches "$ZIP_PATH.part"; then
      mv "$ZIP_PATH.part" "$ZIP_PATH"
    else
      echo "Resumed data was unusable; discarding it before one fresh retry." >&2
      rm -f -- "$ZIP_PATH.part"
      fresh_download
    fi
  else
    if [ -e "$ZIP_PATH.part" ] || [ -L "$ZIP_PATH.part" ]; then
      echo "Refusing unsafe resumable download path: $ZIP_PATH.part" >&2
      exit 1
    fi
    echo "Downloading $ASSET"
    if ! curl --fail --location --show-error --progress-bar       --retry 5 --retry-delay 2 --retry-connrefused       --continue-at - -o "$ZIP_PATH.part" "$URL"; then
      exit 1
    fi
    if part_matches "$ZIP_PATH.part"; then
      mv "$ZIP_PATH.part" "$ZIP_PATH"
    else
      echo "Downloaded asset digest did not match $ASSET" >&2
      rm -f -- "$ZIP_PATH.part"
      exit 1
    fi
  fi
fi
sha256sum -c "$CHECKSUM_PATH"

echo "Extracting $ASSET"
EXTRACT_DIR=''
cleanup_extract() {
  status=$1
  trap - EXIT HUP INT TERM
  if [ -n "$EXTRACT_DIR" ] && [ -d "$EXTRACT_DIR" ]; then
    rm -rf -- "$EXTRACT_DIR"
  fi
  exit "$status"
}
trap 'cleanup_extract "$?"' EXIT
trap 'cleanup_extract 129' HUP
trap 'cleanup_extract 130' INT
trap 'cleanup_extract 143' TERM
EXTRACT_DIR=$(mktemp -d ".${ROOT}.extract.XXXXXX")
unzip -q "$ZIP_PATH" -d "$EXTRACT_DIR"
PAYLOAD_ROOT="$EXTRACT_DIR/$ROOT"
TOP_LEVEL=$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -printf '%f
')
if [ "$TOP_LEVEL" != "$ROOT" ]   || [ ! -d "$PAYLOAD_ROOT" ]   || [ -L "$PAYLOAD_ROOT" ]   || [ ! -f "$PAYLOAD_ROOT/install.sh" ]   || [ -L "$PAYLOAD_ROOT/install.sh" ]; then
  echo "Payload did not contain exactly the expected installer root: $ROOT" >&2
  exit 1
fi

python3 "$PAYLOAD_ROOT/scripts/release_lock.py" verify   --lock "$PAYLOAD_ROOT/release-lock.json"   --trusted-key-dir "$PAYLOAD_ROOT/trust/release"   --trusted-key-sha256 "$EXPECTED_RELEASE_KEY_SHA256"   --expected-release-version "$VERSION"   --expected-release-sequence "$EXPECTED_RELEASE_SEQUENCE"   --target "$PAYLOAD_TARGET"   --package-root "$PAYLOAD_ROOT" >/dev/null

resume_marker_valid() {
  [ -f "$RESUME_MARKER" ]     && [ ! -L "$RESUME_MARKER" ]     && printf '%s\n' "$EXPECTED_RESUME_LINE" | cmp -s - "$RESUME_MARKER"
}

if [ -e "$ROOT" ]; then
  if [ ! -d "$ROOT" ] || [ -L "$ROOT" ] || ! resume_marker_valid; then
    echo "Refusing unauthenticated existing installation root: $ROOT" >&2
    exit 1
  fi
  python3 "$PAYLOAD_ROOT/scripts/release_lock.py" verify     --lock "$ROOT/release-lock.json"     --trusted-key-dir "$PAYLOAD_ROOT/trust/release"     --trusted-key-sha256 "$EXPECTED_RELEASE_KEY_SHA256"     --expected-release-version "$VERSION"     --expected-release-sequence "$EXPECTED_RELEASE_SEQUENCE"     --target "$PAYLOAD_TARGET"     --package-root "$ROOT" >/dev/null
  rm -rf -- "$EXTRACT_DIR"
  EXTRACT_DIR=''
  echo "Resuming the authenticated promoted installer root: $ROOT"
else
  if [ -e "$RESUME_MARKER" ] || [ -L "$RESUME_MARKER" ]; then
    if ! resume_marker_valid; then
      echo "Refusing unexpected bootstrap resume marker: $RESUME_MARKER" >&2
      exit 1
    fi
    rm -f -- "$RESUME_MARKER"
  fi
  rm -f -- "$RESUME_MARKER_PART"
  printf '%s\n' "$EXPECTED_RESUME_LINE" >"$RESUME_MARKER_PART"
  chmod 0600 "$RESUME_MARKER_PART"
  mv "$RESUME_MARKER_PART" "$RESUME_MARKER"
  sync -f "$RESUME_MARKER"
  sync -f .
  if [ -e "$ROOT" ] || [ -L "$ROOT" ]; then
    echo "Refusing to overwrite directory created during extraction: $ROOT" >&2
    exit 1
  fi
  mv -T -- "$PAYLOAD_ROOT" "$ROOT"
  rmdir -- "$EXTRACT_DIR"
  EXTRACT_DIR=''
  sync -f .
fi
trap - EXIT HUP INT TERM

chmod +x "$ROOT/install.sh" 2>/dev/null || true
if bash "$ROOT/install.sh" "$@"; then
  rm -f -- "$ZIP_PATH" "$CHECKSUM_PATH" "$RESUME_MARKER"
  sync -f .
  exit 0
else
  status=$?
  echo "Installer exited unsuccessfully; authenticated resume material was retained." >&2
  exit "$status"
fi
