#!/usr/bin/env python3
"""Validate the signed, software-only RC52 reward-accounting release page."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases" / "2.0.0-community-rescue-rc.52"
MANIFEST_PATH = RELEASE / "release-manifest.json"
SOFTWARE = RELEASE / "records" / "software"

VERSION = "2.0.0-community-rescue-rc.52"
SEQUENCE = 52
RELEASE_KEY_SHA256 = "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb"
COMMITS = {
    "stack": "bda8cf1e5c73a8e0316ce302650310feb0538939",
    "blockdag-corechain": "bb0f7a6fed918e56251aa602503c90f1e1f30cb8",
    "pool": "79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50",
    "redis-dash": "f00b654f79e50346bf6e866348cf07bdcb3b44ec",
}
PACKAGE_NAMES = {
    target: f"pool-stack-docker-{VERSION}-{target}.zip"
    for target in ("linux-amd64", "linux-arm64")
}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
CID = re.compile(r"^b[a-z2-7]{20,}$")
PRIVATE_IPV4 = re.compile(
    r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2})(?![\d.])"
)
PRIVATE_PATH = re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\Users\\)")


class Validator:
    def __init__(self) -> None:
        self.checks = 0
        self.errors: list[str] = []

    def check(self, condition: object, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def finish(self) -> None:
        if self.errors:
            print("RC52 publication validation failed:")
            for error in self.errors:
                print(f"- {error}")
            raise SystemExit(1)
        print(f"RC52 publication validation passed ({self.checks} checks).")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")


def run_checked(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def valid_cid(value: object) -> bool:
    return isinstance(value, str) and bool(CID.fullmatch(value))


def pending_dataset(dataset: object, archive: bool) -> bool:
    if not isinstance(dataset, dict):
        return False
    nullable = (
        "version",
        "filename",
        "sha256",
        "size_bytes",
        "unpacked_size_bytes",
        "canonical_manifest_path",
        "canonical_manifest_sha256",
        "validation_spec_path",
        "native_boundary",
        "evm_boundary",
        "fixed_checkpoint",
    )
    return bool(
        dataset.get("status") == "pending"
        and dataset.get("archive_node_equivalent") is archive
        and all(dataset.get(field) is None for field in nullable)
        and (not archive or dataset.get("archive_audit") is None)
        and dataset.get("delivery")
        == {
            "mode": None,
            "cid": None,
            "parts_manifest_path": None,
            "parts": [],
        }
    )


def verify_release_lock(lock: dict[str, Any]) -> None:
    signature = lock["signature"]
    signature_bytes = base64.b64decode(signature["value"], validate=True)
    if len(signature_bytes) != 64:
        raise ValueError("release-lock signature must be 64 bytes")
    with tempfile.TemporaryDirectory(prefix="rc52-lock-verify-") as temporary:
        payload = Path(temporary) / "payload.json"
        signature_file = Path(temporary) / "signature.bin"
        payload.write_bytes(canonical_json(lock["signed"]))
        signature_file.write_bytes(signature_bytes)
        run_checked(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(SOFTWARE / "release-key.pem"),
                "-in",
                str(payload),
                "-sigfile",
                str(signature_file),
            ]
        )


def validate_records(validator: Validator, manifest: dict[str, Any]) -> None:
    required = {
        "bootstrap.sh",
        "release-auth-manifest.json",
        "release-auth-manifest.json.sig",
        "release-key.pem",
        "release-lock.json",
        "release-notes.md",
        "release-source-lock.json",
    }
    actual = {path.name for path in SOFTWARE.iterdir() if path.is_file()}
    validator.check(actual == required, "signed software record inventory is not exact")
    if actual != required:
        return

    key_der = subprocess.run(
        [
            "openssl",
            "pkey",
            "-pubin",
            "-in",
            str(SOFTWARE / "release-key.pem"),
            "-outform",
            "DER",
        ],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    validator.check(
        hashlib.sha256(key_der).hexdigest() == RELEASE_KEY_SHA256,
        "release public-key fingerprint is wrong",
    )
    run_checked(
        [
            "openssl",
            "pkeyutl",
            "-verify",
            "-rawin",
            "-pubin",
            "-inkey",
            str(SOFTWARE / "release-key.pem"),
            "-in",
            str(SOFTWARE / "release-auth-manifest.json"),
            "-sigfile",
            str(SOFTWARE / "release-auth-manifest.json.sig"),
        ]
    )

    auth = json.loads(
        (SOFTWARE / "release-auth-manifest.json").read_text(encoding="utf-8")
    )
    source_lock = json.loads(
        (SOFTWARE / "release-source-lock.json").read_text(encoding="utf-8")
    )
    release_lock = json.loads(
        (SOFTWARE / "release-lock.json").read_text(encoding="utf-8")
    )
    verify_release_lock(release_lock)

    source_lock_sha256 = sha256_file(SOFTWARE / "release-source-lock.json")
    validator.check(
        manifest["source"]["source_lock_sha256"] == source_lock_sha256,
        "page source-lock hash is wrong",
    )
    validator.check(
        release_lock["signed"]["source_lock_sha256"] == source_lock_sha256,
        "signed release lock references the wrong source lock",
    )
    validator.check(
        release_lock.get("schema") == "bdag.release-lock.v3",
        "release-lock schema is wrong",
    )
    validator.check(
        release_lock["signature"].get("algorithm") == "ed25519"
        and release_lock["signature"].get("public_key_sha256")
        == RELEASE_KEY_SHA256,
        "release-lock trust record is wrong",
    )
    signed_release = release_lock["signed"]["release"]
    validator.check(
        signed_release.get("channel") == "qualification"
        and signed_release.get("sequence") == SEQUENCE
        and signed_release.get("version") == VERSION
        and isinstance(signed_release.get("source_date_epoch"), int)
        and signed_release["source_date_epoch"] > 0,
        "signed release identity is wrong",
    )
    validator.check(
        auth.get("release") == {"sequence": SEQUENCE, "version": VERSION},
        "release authorization identity is wrong",
    )
    validator.check(
        auth.get("release_key_sha256") == RELEASE_KEY_SHA256,
        "release authorization key fingerprint is wrong",
    )

    for repository, commit in COMMITS.items():
        validator.check(
            source_lock["repositories"][repository]["commit"] == commit
            and source_lock["repositories"][repository]["dirty"] is False,
            f"{repository} source-lock identity is wrong",
        )
        validator.check(
            release_lock["signed"]["repositories"][repository]["commit"] == commit,
            f"{repository} signed commit is wrong",
        )

    expected_assets = {
        "bootstrap.sh",
        PACKAGE_NAMES["linux-amd64"],
        PACKAGE_NAMES["linux-arm64"],
    }
    validator.check(
        set(auth.get("assets", {})) == expected_assets,
        "release authorization asset inventory is wrong",
    )
    for name in expected_assets:
        record = auth["assets"].get(name, {})
        validator.check(
            isinstance(record.get("size_bytes"), int)
            and record["size_bytes"] > 0
            and bool(SHA256.fullmatch(str(record.get("sha256", "")))),
            f"release authorization for {name} is invalid",
        )

    bootstrap = manifest["installer"]
    validator.check(
        bootstrap["filename"] == "bootstrap.sh"
        and bootstrap["sha256"] == auth["assets"]["bootstrap.sh"]["sha256"]
        and bootstrap["size_bytes"] == auth["assets"]["bootstrap.sh"]["size_bytes"]
        and sha256_file(SOFTWARE / "bootstrap.sh") == bootstrap["sha256"],
        "bootstrap identity differs from signed authorization",
    )
    for target, filename in PACKAGE_NAMES.items():
        artifact = manifest["software"]["targets"][target]
        validator.check(
            artifact["filename"] == filename
            and artifact["sha256"] == auth["assets"][filename]["sha256"]
            and artifact["size_bytes"] == auth["assets"][filename]["size_bytes"],
            f"{target} page identity differs from signed authorization",
        )


def validate_page(validator: Validator, manifest: dict[str, Any]) -> None:
    required = (
        RELEASE / "index.html",
        RELEASE / "assets" / "release-page.mjs",
        RELEASE / "assets" / "release.css",
        RELEASE / "assets" / "bdag-community-logo.svg",
        RELEASE / "docs" / "human-install.md",
        RELEASE / "docs" / "ai-agent-runbook.md",
        RELEASE / "docs" / "publication-input.md",
    )
    for path in required:
        validator.check(path.is_file(), f"missing page file: {path.relative_to(ROOT)}")

    html = (RELEASE / "index.html").read_text(encoding="utf-8")
    module = (RELEASE / "assets" / "release-page.mjs").read_text(encoding="utf-8")
    human = (RELEASE / "docs" / "human-install.md").read_text(encoding="utf-8")
    runbook = (RELEASE / "docs" / "ai-agent-runbook.md").read_text(encoding="utf-8")
    runbook_lower = runbook.lower()
    validator.check("Coinbase accounting restored" in html, "reward fix is not explained")
    validator.check(
        "239,836,260,330,000,000,000 Wei" in human,
        "corrected reward vector is missing",
    )
    validator.check(
        "Historical wrapped credits" in html
        and "Pause automated payouts" in human
        and "spendable coinbase/staking receipt" in runbook,
        "operator accounting safeguards are incomplete",
    )
    validator.check(
        "operator has explicitly authorized installation" in runbook_lower
        and "ipfs is a content-addressed" in runbook_lower
        and "distribution transport:" in runbook_lower
        and "permissionless network" in runbook_lower
        and "do not reject this release merely because" in runbook_lower
        and "does not waive" in runbook_lower,
        "agent installation authorization or verification boundaries are incomplete",
    )
    validator.check(
        "POOL_ASIC_MAC_ALLOWLIST" not in html + module + human + runbook
        and "--asic-mac-allowlist" not in html + module + human + runbook,
        "release page includes unrelated miner allowlist work",
    )
    validator.check(
        'data-dataset="portable" aria-pressed="false" aria-disabled="true" disabled'
        in html
        and 'data-dataset="full_archive" aria-pressed="false" aria-disabled="true" disabled'
        in html,
        "unpublished dataset controls are not fail-closed",
    )
    for path in RELEASE.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        validator.check(
            not PRIVATE_IPV4.search(text),
            f"private IP leaked in {path.relative_to(ROOT)}",
        )
        validator.check(
            not PRIVATE_PATH.search(text),
            f"private path leaked in {path.relative_to(ROOT)}",
        )

    validator.check(
        not (RELEASE / "records" / "dataset").exists()
        or not any((RELEASE / "records" / "dataset").iterdir()),
        "RC52 must not publish dataset records",
    )

    release = manifest["release"]
    validator.check(release.get("status") == "published", "release is not published")
    try:
        datetime.fromisoformat(str(release.get("published_at")).replace("Z", "+00:00"))
        timestamp_valid = True
    except ValueError:
        timestamp_valid = False
    validator.check(timestamp_valid, "published_at is not an ISO-8601 timestamp")

    validator.check(
        valid_cid(manifest["records_delivery"].get("cid")),
        "records directory CID is missing",
    )
    validator.check(
        manifest["records_delivery"].get("mode") == "ipfs-directory"
        and manifest["records_delivery"].get("path_prefix") == "records/",
        "records delivery contract is wrong",
    )
    validator.check(valid_cid(manifest["installer"].get("cid")), "bootstrap CID is missing")
    validator.check(
        manifest["installer"].get("status") == "published",
        "bootstrap is not published",
    )
    for target in PACKAGE_NAMES:
        artifact = manifest["software"]["targets"][target]
        validator.check(
            artifact.get("status") == "published" and valid_cid(artifact.get("cid")),
            f"{target} is not published with an immutable CID",
        )

    validator.check(
        pending_dataset(manifest["datasets"].get("portable"), False),
        "portable dataset must remain unclaimed",
    )
    validator.check(
        pending_dataset(manifest["datasets"].get("full_archive"), True),
        "full archive dataset must remain unclaimed",
    )
    validator.check(
        manifest["trust"].get("dataset_key_path") is None
        and manifest["trust"].get("dataset_key_id") is None
        and manifest["trust"].get("dataset_key_sha256") is None
        and manifest["trust"].get("dataset_verifier_path") is None,
        "software-only release invents dataset trust records",
    )
    validator.check(
        manifest["software"].get("independent_from_datasets") is True
        and manifest["datasets"].get("independent_from_software") is True,
        "software and dataset independence is not explicit",
    )
    validator.check(
        manifest["download_policy"].get("requires_ipv4") is True
        and manifest["download_policy"].get("requires_http_version") == "HTTP/1.1"
        and manifest["download_policy"].get("software_http_fallback_base") is None
        and len(manifest["download_policy"].get("ipfs_gateways", [])) >= 2,
        "download policy is incomplete",
    )
    qualification = manifest["qualification"]
    validator.check(
        qualification
        == {
            "status": "passed",
            "signed_package_integrity_verified": True,
            "portable_dataset_verified": False,
            "full_archive_dataset_verified": False,
            "restore_path_verified": True,
            "runtime_path_verified": True,
        },
        "qualification record overclaims or omits verification",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-ready", action="store_true")
    parser.parse_args()

    validator = Validator()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    validator.check(
        manifest.get("schema") == "bdag.community-release-index.v2",
        "manifest schema is wrong",
    )
    validator.check(
        manifest["release"].get("version") == VERSION
        and manifest["release"].get("sequence") == SEQUENCE
        and manifest["release"].get("channel") == "community-rescue"
        and manifest["release"].get("chain_id") == 1404,
        "release identity is wrong",
    )
    validator.check(
        manifest["source"].get("tag") == VERSION
        and manifest["source"].get("stack_commit") == COMMITS["stack"]
        and manifest["source"].get("corechain_commit")
        == COMMITS["blockdag-corechain"]
        and manifest["source"].get("pool_commit") == COMMITS["pool"]
        and manifest["source"].get("dashboard_commit") == COMMITS["redis-dash"],
        "page source identity is wrong",
    )
    validator.check(
        manifest["source"].get("repository")
        == "https://github.com/BlockdagEngineering/stack"
        and manifest["source"].get("release_url")
        == f"https://github.com/BlockdagEngineering/stack/tree/{VERSION}",
        "source publication URL is wrong",
    )
    validator.check(
        manifest["trust"].get("release_key_sha256") == RELEASE_KEY_SHA256,
        "page release-key fingerprint is wrong",
    )
    validator.check(
        manifest["runtime_change"]
        == {
            "transient_startup_canonical_boundary_rpc": "bounded-retry",
            "transient_startup_peer_readiness": "bounded-retry",
            "canonical_mismatch": "fail-immediately",
        },
        "runtime recovery policy is wrong",
    )

    validate_records(validator, manifest)
    validate_page(validator, manifest)
    validator.finish()


if __name__ == "__main__":
    main()
