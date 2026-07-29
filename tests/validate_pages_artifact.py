#!/usr/bin/env python3
"""Fail closed if the staged GitHub Pages tree contains non-public material."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PRIVATE_IPV4 = re.compile(
    r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}|"
    r"169\.254(?:\.\d{1,3}){2})(?![\d.])"
)
PRIVATE_IPV6 = re.compile(
    r"(?<![0-9A-Fa-f:])(?:f[cd][0-9A-Fa-f]{2}|fe[89abAB][0-9A-Fa-f])"
    r"(?::[0-9A-Fa-f]{0,4}){1,7}(?![0-9A-Fa-f:])",
    re.IGNORECASE,
)
PRIVATE_PATH = re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\Users\\)")
MAC_ADDRESS = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}:){5}"
    r"[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"
)
SECRET_TOKEN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|"
    r"xox[baprs]-[A-Za-z0-9-]{20,})"
)
APPROVED_PUBLIC_EXAMPLES = (
    "172.16.0.0/12",
    "172.17.0.0/16",
    "192.168.1.0/24",
    "192.168.1.50",
    "aa:bb:cc:dd:ee:ff",
    "11:22:33:44:55:66",
)
EXPECTED_BINARY_SIGNATURES = {
    Path(
        "releases/2.0.0-community-rescue-rc.24/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.30-page-v2/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.30/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.32/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.44/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.52/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.58/records/software/"
        "release-auth-manifest.json.sig"
    ),
    Path(
        "releases/2.0.0-community-rescue-rc.62/records/software/"
        "release-auth-manifest.json.sig"
    ),
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_pages_artifact.py STAGED_TREE")
    root = Path(sys.argv[1])
    if not root.is_dir() or root.is_symlink():
        raise SystemExit("staged Pages root is missing or unsafe")
    top_level = {path.name for path in root.iterdir()}
    if top_level != {"index.html", "releases"}:
        raise SystemExit(f"unexpected staged Pages inventory: {sorted(top_level)}")

    findings: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            findings.append(f"{relative}: symlink")
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if relative in EXPECTED_BINARY_SIGNATURES:
            if len(raw) != 64:
                findings.append(f"{relative}: invalid Ed25519 signature size")
            text = raw.decode("latin-1")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                findings.append(f"{relative}: unexpected binary file")
                text = raw.decode("latin-1")
        for example in APPROVED_PUBLIC_EXAMPLES:
            text = text.replace(example, "")
        checks = (
            (PRIVATE_IPV4, "private IPv4 address"),
            (PRIVATE_IPV6, "private IPv6 address"),
            (PRIVATE_PATH, "private filesystem path"),
            (MAC_ADDRESS, "hardware address"),
            (PRIVATE_KEY, "private key material"),
            (SECRET_TOKEN, "credential-shaped token"),
        )
        for pattern, label in checks:
            if pattern.search(text):
                findings.append(f"{relative}: {label}")

    if findings:
        print("staged Pages privacy validation failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        raise SystemExit(1)
    print("staged Pages tree is exact and privacy-clean")


if __name__ == "__main__":
    main()
