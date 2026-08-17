#!/usr/bin/env python3
"""Render the complete, deterministic RC65 page-v2 IPFS pin inventory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases/2.0.0-community-rescue-rc.65-page-v2"
PAGE_CID = "bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku"
RECORDS_CID = "bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe"
PREDECESSOR_CID = "bafybeiet53pfpyf52mmbqwqg6qapxueblqhyqyit6f5zyfaotunpwtgweq"
ADMISSION_CID = "bafkreie7lwh7jxxv4qsbz26kzaz4xul5e3lmilbawrwce5uigppd3jihq4"
IPNS_NAMES = [
    "k51qzi5uqu5dgijozv3dne65cp7iqv96tpsa8dflmwmqvdw9oxx4w3gsvt0ctl",
    "12D3KooWD3c6UAMwSBjuPbYinx4mJMTsEBK1kNjW9s5TtZL8L6Gi",
]


def load(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SystemExit(f"expected a JSON object: {path}")
    return value


def pin(name: str, cid: str, *, recursive: bool = True) -> dict[str, object]:
    if not name or not cid.startswith("baf"):
        raise SystemExit(f"invalid pin: {name} {cid}")
    return {"name": name, "cid": cid, "recursive": recursive}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    release = load(RELEASE / "records/release.json")
    parts = load(RELEASE / "records/dataset/full-archive-v28-parts.json")
    targets = release["software"]["targets"]
    compact = release["datasets"]["compactMiningNode"]["artifact"]

    pins = [
        pin("release-page-root", PAGE_CID),
        pin("release-records-root", RECORDS_CID),
        pin("predecessor-page-root", PREDECESSOR_CID),
        pin("compact-canonical-admission-manifest", ADMISSION_CID, recursive=False),
        pin("linux-amd64-software", targets["linux-amd64"]["cid"]),
        pin("linux-arm64-software", targets["linux-arm64"]["cid"]),
        pin("compact-mining-node-data", compact["cid"]),
    ]
    for index, part in enumerate(parts["parts"], start=1):
        pins.append(pin(f"full-archive-part-{index:03d}", part["cid"]))

    if len(pins) != 47 or len({item["cid"] for item in pins}) != len(pins):
        raise SystemExit("RC65 page-v2 pin inventory is incomplete or contains duplicate CIDs")

    output = {
        "schema": "bdag.community-ipfs-pins.v2",
        "release": "2.0.0-community-rescue-rc.65",
        "pageRevision": 2,
        "pageCid": PAGE_CID,
        "ipns": IPNS_NAMES,
        "pins": pins,
    }
    payload = (json.dumps(output, indent=2, sort_keys=False) + "\n").encode("utf-8")
    if args.output is None:
        print(payload.decode("utf-8"), end="")
        return
    destination = args.output.resolve()
    expected = (ROOT / "publishing/free-pinning-cids.json").resolve()
    if destination != expected or destination.is_symlink():
        raise SystemExit(f"refusing unexpected output path: {destination}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    main()
