#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
manifest=${1:-}
kubo_binary=${2:-$(command -v ipfs || true)}
storage_max=${BDAG_IPFS_STORAGE_MAX:-250GB}
expected_kubo_sha256=${BDAG_IPFS_KUBO_SHA256:-}
force_upnp_refresh=${BDAG_IPFS_FORCE_UPNP_REFRESH:-0}

if [[ -z "$manifest" || ! -f "$manifest" ]]; then
  echo "usage: $0 <free-pinning-cids.json> [ipfs-binary]" >&2
  exit 2
fi

for command in jq systemctl systemd-run; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required command not found: $command" >&2
    exit 1
  fi
done

if [[ -z "$kubo_binary" || ! -x "$kubo_binary" ]]; then
  echo "a Kubo ipfs binary is required" >&2
  exit 1
fi

if [[ "$force_upnp_refresh" != 0 && "$force_upnp_refresh" != 1 ]]; then
  echo "BDAG_IPFS_FORCE_UPNP_REFRESH must be 0 or 1" >&2
  exit 2
fi

if [[ "$force_upnp_refresh" == 1 ]] && ! command -v upnpc >/dev/null 2>&1; then
  echo "BDAG_IPFS_FORCE_UPNP_REFRESH=1 requires miniupnpc/upnpc" >&2
  exit 1
fi

if [[ -n "$expected_kubo_sha256" ]]; then
  printf '%s  %s\n' "$expected_kubo_sha256" "$kubo_binary" | sha256sum -c -
fi

if [[ $(readlink -f "$kubo_binary") != /usr/local/bin/ipfs ]]; then
  sudo install -m 0755 "$kubo_binary" /usr/local/bin/ipfs
fi

if [[ ! -f ${IPFS_PATH:-$HOME/.ipfs}/config ]]; then
  /usr/local/bin/ipfs init
fi

/usr/local/bin/ipfs config Datastore.StorageMax "$storage_max"
/usr/local/bin/ipfs config --json Swarm.DisableNatPortMap false
/usr/local/bin/ipfs config Provide.DHT.Interval 6h

install -D -m 0644 \
  "$script_dir/systemd/ipfs-community-seeder.service" \
  "$HOME/.config/systemd/user/ipfs.service"

if [[ "$force_upnp_refresh" == 1 ]]; then
  install -m 0644 \
    "$script_dir/systemd/ipfs-upnp-refresh.service" \
    "$HOME/.config/systemd/user/ipfs-upnp-refresh.service"
  install -m 0644 \
    "$script_dir/systemd/ipfs-upnp-refresh.timer" \
    "$HOME/.config/systemd/user/ipfs-upnp-refresh.timer"
fi

sudo loginctl enable-linger "$(id -un)"
systemctl --user daemon-reload

if [[ "$force_upnp_refresh" == 1 ]]; then
  systemctl --user enable --now ipfs-upnp-refresh.timer
  systemctl --user start ipfs-upnp-refresh.service
fi

systemctl --user enable --now ipfs.service

state_dir=$HOME/.local/share/bdag-ipfs-release
install -d -m 0755 "$state_dir"
install -m 0755 "$script_dir/replicate-release-pins.sh" "$state_dir/"
install -m 0644 "$manifest" "$state_dir/free-pinning-cids.json"

release=$(jq -er '.release' "$manifest")
release_slug=$(printf '%s' "$release" | tr -cs '[:alnum:]' '-' | tr '[:upper:]' '[:lower:]')
unit=bdag-ipfs-${release_slug}-replicate

if systemctl --user is-active --quiet "$unit.service"; then
  echo "replication is already running in $unit.service"
  exit 0
fi

systemd-run --user \
  --unit="$unit" \
  --collect \
  --property=Nice=10 \
  --property=IOSchedulingClass=idle \
  "$state_dir/replicate-release-pins.sh" \
  "$state_dir/free-pinning-cids.json"

echo "replication started in $unit.service"
echo "monitor with: journalctl --user -fu $unit.service"
