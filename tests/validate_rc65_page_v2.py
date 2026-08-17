#!/usr/bin/env python3
"""Fail-closed static and cryptographic gate for the RC65 rich page revision."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "releases/2.0.0-community-rescue-rc.65"
RELEASE = ROOT / "releases/2.0.0-community-rescue-rc.65-page-v2"
EXPECTED_RECORDS_CID = "bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe"
EXPECTED_RELEASE_SHA = "4f1c1962edb90dd99f4286d58507ed2216ea47f7bc83ccb055072269731b1335"
EXPECTED_PAGE_CID = "bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku"


def fail(message: str) -> None:
    raise SystemExit(f"RC65 page-v2 validation failed: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def main() -> None:
    if not RELEASE.is_dir() or RELEASE.is_symlink():
        fail("release directory is missing or unsafe")
    if any(path.is_symlink() for path in RELEASE.rglob("*")):
        fail("release directory contains a symlink")
    if inventory(ORIGINAL / "records") != inventory(RELEASE / "records"):
        fail("original RC65 signed records changed while creating page v2")
    if sha256(RELEASE / "records/release.json") != EXPECTED_RELEASE_SHA:
        fail("original release.json digest changed")

    subprocess.run(
        [str(RELEASE / "verify-load-v2.sh"), str(RELEASE)],
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.DEVNULL,
    )
    attestation = json.loads((RELEASE / "revision/page-v2.json").read_text(encoding="utf-8"))
    if attestation.get("originalRecords", {}).get("cid") != EXPECTED_RECORDS_CID:
        fail("signed original records CID mismatch")
    if attestation.get("presentation", {}).get("revision") != 2:
        fail("presentation revision mismatch")
    if attestation.get("presentation", {}).get("externalRuntimeDependencies") is not False:
        fail("release page declares an external runtime dependency")

    html = (RELEASE / "index.html").read_text(encoding="utf-8")
    css = (RELEASE / "assets/release.css").read_text(encoding="utf-8")
    module = (RELEASE / "assets/release-page.mjs").read_text(encoding="utf-8")
    required_html = (
        "https://bdag.community/",
        "https://bdag.community/community#participate",
        "Support the developers by supporting the community",
        "Generated Bash",
        "Existing node upgrade — no dataset",
        "New normal mining node — compact data",
        "New full archive / RPC node",
        "bafybeiavwpvhacxznesv5imjuqdcb2g6idrnqalor6kf7fr3pjq3tmatky",
        "bafybeibmkyhqwqz26t3lb6w7dp6sjqe2i4goyiopsn6ppfwnf4rrtryjwi",
        "bafybeidbsqv7elxbvs5gna33oj47jhynjaqvwt7wesunfew5jct66zhtiy",
        "bafybeiblqxf7d5cyqmapcpccpvaupatoydxsqceswm4taimqs247ux32ji",
    )
    for expected in required_html:
        if expected not in html:
            fail(f"missing required rich-page content: {expected}")
    for external in re.findall(r"<(?:script|link|img)[^>]+(?:src|href)=\"(https?://[^\"]+)", html):
        fail(f"unexpected runtime external asset: {external}")
    for token in ("#0e0715", "#170f23", "#a856fb", "#d33aee", "#f45fc4", "#2ce0ce"):
        if token not in css.lower():
            fail(f"missing community design token: {token}")
    if "prefers-reduced-motion" not in css or ":focus-visible" not in css:
        fail("accessibility motion or focus treatment is missing")
    for behavior in ("crypto.subtle.verify", "Ed25519", "buildInstallCommand", "existingDataUpgrade"):
        if behavior not in module:
            fail(f"browser trust or command behavior missing: {behavior}")

    page_bytes = 0
    for path in RELEASE.rglob("*"):
        if not path.is_file():
            continue
        page_bytes += path.stat().st_size
        relative = str(path.relative_to(RELEASE)).lower()
        if relative.endswith((".go", ".ts", ".tsx", ".jsx", ".map")):
            fail(f"component source or source map present: {relative}")
        raw = path.read_bytes()
        if b"PRIVATE KEY" in raw or b"/home/jeremy" in raw:
            fail(f"private material present: {relative}")
    if page_bytes >= 50 * 1024 * 1024:
        fail("release page unexpectedly contains large payload bytes")
    if (RELEASE / "install-or-reuse-data.sh").exists():
        fail("obsolete pre-admission dataset helper remains in page v2")

    workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    branch = "jeremy/release/2026-08-17-rc65-rich-ipfs-page-v2"
    if branch not in workflow or "tests/validate_rc65_page_v2.py" not in workflow:
        fail("Pages workflow does not admit and validate the Jeremy page-v2 branch")
    root_page = (ROOT / "index.html").read_text(encoding="utf-8")
    if "2.0.0-community-rescue-rc.65-page-v2/index.html" not in root_page:
        fail("Pages root does not target the rich RC65 page revision")

    rendered_pins = subprocess.run(
        ["python3", str(ROOT / "publishing/render-rc65-page-v2-pins.py")],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    ).stdout
    pin_path = ROOT / "publishing/free-pinning-cids.json"
    if rendered_pins.encode("utf-8") != pin_path.read_bytes():
        fail("checked-in IPFS pin inventory is not the deterministic RC65 rendering")
    pins = json.loads(rendered_pins)
    if pins.get("pageCid") != EXPECTED_PAGE_CID or len(pins.get("pins", [])) != 47:
        fail("IPFS pin inventory does not bind the rich page and all release roots")
    if len(pins.get("ipns", [])) != 2:
        fail("IPFS pin inventory does not declare both mutable latest pointers")
    print("RC65 rich page, immutable records, signatures, design, and source exclusion passed")


if __name__ == "__main__":
    main()
