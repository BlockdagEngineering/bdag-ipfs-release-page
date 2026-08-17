#!/usr/bin/env python3
"""Fail-closed structural and cryptographic RC65 publication gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases/2.0.0-community-rescue-rc.65"
RECORDS = RELEASE / "records"
TAG = "jeremy-community-rescue-rc.65.6"
OUTER_KEY_SHA = "9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66"
SOFTWARE_KEY_SHA = "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb"


def fail(message: str) -> None:
    raise SystemExit(f"RC65 validation failed: {message}")


def fingerprint(path: Path) -> str:
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(path), "-outform", "DER"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def main() -> None:
    actual_files = {
        str(path.relative_to(ROOT))
        for path in RELEASE.rglob("*")
        if path.is_file()
    }
    tracked_files = {
        entry
        for entry in subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--", str(RELEASE.relative_to(ROOT))]
        ).decode("utf-8").split("\0")
        if entry
    }
    if actual_files != tracked_files:
        fail(
            "release working-tree and tracked inventories differ: "
            f"untracked={sorted(actual_files - tracked_files)}, "
            f"missing={sorted(tracked_files - actual_files)}"
        )

    manifest_path = RECORDS / "release.json"
    if not manifest_path.is_file():
        fail("missing release manifest")
    raw = manifest_path.read_text(encoding="utf-8")
    if "PLACEHOLDER" in raw or "publication-pending" in raw:
        fail("publication placeholders remain")
    record = json.loads(raw)
    if record.get("schema") != "bdag.community-release-index.v3" or record.get("status") != "published":
        fail("release is not published under the accepted schema")
    if record.get("version") != "2.0.0-community-rescue-rc.65" or record.get("sequence") != 65:
        fail("release identity mismatch")
    if record.get("platforms") != ["linux/amd64", "linux/arm64"]:
        fail("dual-architecture set is wrong")
    if record.get("provenance", {}).get("softwareTag") != TAG:
        fail("software tag mismatch")
    if record.get("existingDataUpgrade") != {
        "downloadsCompact": False,
        "downloadsFullArchive": False,
        "reusesQualifiedData": True,
    }:
        fail("existing-data reuse policy drift")

    targets = record.get("software", {}).get("targets", {})
    if set(targets) != {"linux-amd64", "linux-arm64"}:
        fail("software target coverage is incomplete")
    for platform, artifact in targets.items():
        if (not artifact.get("name", "").endswith(f"-{platform}.zip") or
                artifact.get("bytes", 0) <= 0 or
                not artifact.get("cid", "").startswith("b") or
                len(artifact.get("sha256", "")) != 64):
            fail(f"incomplete {platform} software artifact")
    if len(record.get("software", {}).get("records", {})) != 6:
        fail("authenticated software record inventory is incomplete")

    compact = record.get("datasets", {}).get("compactMiningNode", {})
    if (compact.get("status") != "published" or compact.get("artifact", {}).get("bytes", 0) <= 0 or
            not compact.get("artifact", {}).get("cid", "").startswith("b") or
            len(compact.get("artifact", {}).get("sha256", "")) != 64 or
            not compact.get("cleanShutdown")):
        fail("compact mining-node dataset is incomplete")
    full = record.get("datasets", {}).get("fullArchive", {})
    if (full.get("status") != "published" or full.get("inheritedFrom") != "2.0.0-community-rescue-rc.44" or
            full.get("catchUpRequiredFromPublishedBoundary") is not True or
            len(full.get("delivery", {}).get("parts", [])) != 40 or
            full.get("size_bytes") != 170210502672 or
            full.get("sha256") != "bf71ff3ce7d29dca5c0b0c9f9f376d713c0029fdbabb76919929293073472f74"):
        fail("full archive option is incomplete or falsely presented as current")
    runtime = record.get("runtimePolicy", {})
    if runtime != {
        "evmAdvisoryWhenGuardDisabled": True,
        "evmReferenceUrlsDefaultEmpty": True,
        "legacyV45NoiseCannotBlockNativeSafeMining": True,
        "ownerPayoutIdentityPreserved": True,
    }:
        fail("miner-friendly runtime policy drift")
    if record.get("sourceExclusion") != {
        "corechainImplementation": True,
        "dashboardImplementation": True,
        "poolImplementation": True,
        "sourceMaps": True,
    }:
        fail("component-source exclusion declaration is incomplete")

    if fingerprint(RECORDS / "release-public.pem") != OUTER_KEY_SHA:
        fail("outer release key fingerprint mismatch")
    if fingerprint(RECORDS / "software/release-key.pem") != SOFTWARE_KEY_SHA:
        fail("software release key fingerprint mismatch")
    subprocess.run([str(RELEASE / "verify-load.sh"), str(RELEASE)], check=True, stdout=subprocess.DEVNULL)
    installer = RELEASE / "install-or-reuse-data.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    installer_text = installer.read_text(encoding="utf-8")
    reuse_exit = installer_text.find("Existing non-empty data directory detected")
    empty_tool_gate = installer_text.find("required empty-install command unavailable")
    if reuse_exit < 0 or empty_tool_gate < 0 or empty_tool_gate < reuse_exit:
        fail("existing-data reuse is blocked by empty-install tooling")

    page_bytes = 0
    for path in RELEASE.rglob("*"):
        if not path.is_file():
            continue
        page_bytes += path.stat().st_size
        name = str(path.relative_to(RELEASE)).lower()
        if name.endswith((".go", ".ts", ".tsx", ".jsx", ".map")):
            fail(f"component implementation source or source map present: {name}")
        payload = path.read_bytes()
        if b"PRIVATE KEY" in payload or b"/home/jeremy" in payload:
            fail(f"private material present: {name}")
    if page_bytes >= 50 * 1024 * 1024:
        fail("large software or dataset payload was committed into the page repository")
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    if "jeremy/release/2026-08-16-rc65-dual-arch-full-data-ipfs" not in pages:
        fail("Jeremy RC65 Pages branch is not explicitly admitted")
    print("RC65 publication-ready structure and signatures passed")


if __name__ == "__main__":
    main()
