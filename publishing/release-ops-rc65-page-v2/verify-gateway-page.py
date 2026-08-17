#!/usr/bin/env python3
"""Verify exact page bytes while allowing one known dweb Cloudflare injection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


CID = re.compile(r"^b[a-z2-7]{20,}$")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def regular(path: Path) -> bytes:
    info = path.lstat()
    if path.is_symlink() or not path.is_file() or info.st_nlink != 1 or info.st_size < 1:
        raise SystemExit(f"unsafe page proof input: {path}")
    return path.read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--gateway", type=Path, required=True)
    parser.add_argument("--cid", required=True)
    args = parser.parse_args()
    if not CID.fullmatch(args.cid):
        raise SystemExit("invalid expected page CID")
    local = regular(args.local)
    gateway = regular(args.gateway)
    normalized = gateway
    injection_count = 0
    if gateway != local:
        pattern = re.compile(
            rb'<a href="https://'
            + re.escape(args.cid.encode("ascii"))
            + rb'[.]ipfs[.]dweb[.]link/cdn-cgi/content[?]id=[^"<>]+" '
            rb'aria-hidden="true" rel="nofollow noopener" '
            rb'style="display: none !important; visibility: hidden !important"></a>'
        )
        normalized, injection_count = pattern.subn(b"", gateway)
    if normalized != local or injection_count not in (0, 1):
        raise SystemExit("gateway page differs beyond the single allowed CID-bound transport injection")
    print(json.dumps({
        "schema": "bdag.ipfs-gateway-page-proof/v1",
        "status": "passed",
        "cid": args.cid,
        "localSha256": sha256(local),
        "gatewaySha256": sha256(gateway),
        "normalizedSha256": sha256(normalized),
        "allowedTransportInjectionCount": injection_count,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
