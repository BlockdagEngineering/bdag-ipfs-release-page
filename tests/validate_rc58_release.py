#!/usr/bin/env python3
"""Validate the fail-closed, software-only RC58 release-page draft."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0-community-rescue-rc.58"
RELEASE_DIR = ROOT / "releases" / VERSION
MANIFEST_PATH = RELEASE_DIR / "release-manifest.json"

SOURCE = {
    "repository": "https://github.com/BlockdagEngineering/stack",
    "release_url": f"https://github.com/BlockdagEngineering/stack/tree/{VERSION}",
    "tag": VERSION,
    "stack_commit": "7642805f2a6c3195707985a2ca8a997cddbe04c6",
    "corechain_commit": "bb0f7a6fed918e56251aa602503c90f1e1f30cb8",
    "pool_commit": "79001ae94a6d66f1ef0614ef0b78e79fdf3b0f50",
    "dashboard_commit": "f00b654f79e50346bf6e866348cf07bdcb3b44ec",
    "source_lock_sha256": None,
}

PRIVATE_IPV4 = re.compile(
    r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}|"
    r"169\.254(?:\.\d{1,3}){2})(?![\d.])"
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
MINER_ACCESS_MARKER = re.compile(
    r"POOL_ASIC_MAC_ALLOWLIST|--asic-mac-allowlist|"
    r"\b(?:ASIC MAC|MAC) allowlist\b|\bmining whitelist\b",
    re.IGNORECASE,
)
OUT_OF_SCOPE_RECOVERY = re.compile(
    r"\bbounded recovery\b|\bstale-task\b|\bstatus-sampler\b|"
    r"\bP2P-currentness\b|\bwhole-stack restart\b",
    re.IGNORECASE,
)


class Validator:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.failures.append(message)

    def finish(self) -> None:
        if self.failures:
            print("RC58 draft validation failed:", file=sys.stderr)
            for failure in self.failures:
                print(f"- {failure}", file=sys.stderr)
            raise SystemExit(1)
        print("RC58 software-only draft validation passed")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {path.relative_to(ROOT)}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def exact_pending_artifact(filename: str) -> dict[str, Any]:
    return {
        "status": "pending",
        "filename": filename,
        "cid": None,
        "sha256": None,
        "size_bytes": None,
    }


def exact_pending_dataset(*, archive: bool) -> dict[str, Any]:
    value: dict[str, Any] = {
        "status": "pending",
        "label": (
            "No RC58 full-archive dataset"
            if archive
            else "No RC58 portable dataset"
        ),
        "archive_node_equivalent": archive,
        "version": None,
        "filename": None,
        "sha256": None,
        "size_bytes": None,
        "unpacked_size_bytes": None,
        "delivery": {
            "mode": None,
            "cid": None,
            "parts_manifest_path": None,
            "parts": [],
        },
        "canonical_manifest_path": None,
        "canonical_manifest_sha256": None,
        "validation_spec_path": None,
        "native_boundary": None,
        "evm_boundary": None,
        "fixed_checkpoint": None,
    }
    if archive:
        value["archive_audit"] = None
    return value


def validate_manifest(validator: Validator, manifest: dict[str, Any]) -> None:
    validator.check(
        manifest.get("schema") == "bdag.community-release-index.v2",
        "manifest schema is wrong",
    )
    validator.check(
        manifest.get("release")
        == {
            "version": VERSION,
            "sequence": 58,
            "channel": "community-rescue",
            "status": "draft",
            "chain_id": 1404,
            "published_at": None,
        },
        "release identity is not the exact unpublished RC58 sequence",
    )
    validator.check(
        manifest.get("source") == SOURCE,
        "source pins must be the exact RC55 stack plus reward-fixed pool inputs",
    )
    validator.check(
        manifest.get("runtime_change")
        == {
            "transient_startup_canonical_boundary_rpc": "bounded-retry",
            "transient_startup_peer_readiness": "bounded-retry",
            "canonical_mismatch": "fail-immediately",
        },
        "inherited runtime safety policy changed",
    )
    validator.check(
        manifest.get("reward_safety")
        == {
            "coinbase_accounting": "arbitrary-precision-wei",
            "automatic_payouts": "disabled-pending-staking-reconciliation",
        },
        "reward or payout safety policy is wrong",
    )
    validator.check(
        manifest.get("trust")
        == {
            "release_key_path": None,
            "release_key_sha256": None,
            "dataset_key_path": None,
            "dataset_key_id": None,
            "dataset_key_sha256": None,
            "dataset_verifier_path": None,
            "dataset_verifier_sha256": None,
        },
        "draft trust fields must all remain unset",
    )

    policy = manifest.get("download_policy")
    validator.check(isinstance(policy, dict), "download policy is missing")
    if isinstance(policy, dict):
        gateways = policy.get("ipfs_gateways")
        validator.check(
            policy.get("requires_ipv4") is True
            and policy.get("requires_http_version") == "HTTP/1.1"
            and policy.get("software_http_fallback_base") is None,
            "download transport policy changed",
        )
        validator.check(
            isinstance(gateways, list)
            and len(gateways) >= 2
            and all(
                isinstance(value, str)
                and value.startswith("https://")
                and value.endswith("/ipfs/{cid}")
                for value in gateways
            ),
            "at least two safe public IPFS gateway templates are required",
        )

    validator.check(
        manifest.get("records_delivery")
        == {"mode": "ipfs-directory", "cid": None, "path_prefix": "records/"},
        "records delivery must remain CID-locked",
    )
    validator.check(
        manifest.get("installer") == exact_pending_artifact("bootstrap.sh"),
        "installer must remain pending without invented identity",
    )

    software = manifest.get("software")
    validator.check(isinstance(software, dict), "software record is missing")
    if isinstance(software, dict):
        validator.check(
            software.get("independent_from_datasets") is True,
            "software must remain independent from datasets",
        )
        validator.check(
            software.get("targets")
            == {
                "linux-amd64": exact_pending_artifact(
                    f"pool-stack-docker-{VERSION}-linux-amd64.zip"
                ),
                "linux-arm64": exact_pending_artifact(
                    f"pool-stack-docker-{VERSION}-linux-arm64.zip"
                ),
            },
            "architecture packages must remain pending without hashes or CIDs",
        )
        validator.check(
            software.get("records")
            == {
                "release_auth_manifest_path":
                    "records/software/release-auth-manifest.json",
                "release_auth_signature_path":
                    "records/software/release-auth-manifest.json.sig",
                "release_notes_path": "records/software/release-notes.md",
            },
            "future software record paths are wrong",
        )

    datasets = manifest.get("datasets")
    validator.check(isinstance(datasets, dict), "dataset state is missing")
    if isinstance(datasets, dict):
        validator.check(
            datasets.get("independent_from_software") is True
            and datasets.get("portable") == exact_pending_dataset(archive=False)
            and datasets.get("full_archive") == exact_pending_dataset(archive=True),
            "RC58 must contain no dataset identity, delivery, record, or pin",
        )

    validator.check(
        manifest.get("qualification")
        == {
            "status": "in-progress",
            "signed_package_integrity_verified": False,
            "portable_dataset_verified": False,
            "full_archive_dataset_verified": False,
            "restore_path_verified": False,
            "runtime_path_verified": False,
        },
        "draft qualification must remain in progress and unverified",
    )


def validate_public_copy(validator: Validator) -> None:
    required_files = (
        RELEASE_DIR / "index.html",
        RELEASE_DIR / "release-manifest.json",
        RELEASE_DIR / "assets" / "release-page.mjs",
        RELEASE_DIR / "assets" / "release.css",
        RELEASE_DIR / "assets" / "bdag-community-logo.svg",
        RELEASE_DIR / "docs" / "human-install.md",
        RELEASE_DIR / "docs" / "ai-agent-runbook.md",
        RELEASE_DIR / "docs" / "publication-input.md",
    )
    for path in required_files:
        validator.check(path.is_file() and not path.is_symlink(), f"missing {path.relative_to(ROOT)}")

    records = RELEASE_DIR / "records"
    validator.check(not records.exists(), "draft must not contain copied or unsigned records")

    text_files = [
        path
        for path in RELEASE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".json", ".md", ".mjs", ".css", ".svg"}
    ]
    combined = ""
    for path in text_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            validator.check(False, f"unexpected binary file {path.relative_to(ROOT)}")
            continue
        combined += f"\n{text}"
        checks = (
            (PRIVATE_IPV4, "private IPv4 address"),
            (PRIVATE_PATH, "private filesystem path"),
            (MAC_ADDRESS, "hardware address"),
            (PRIVATE_KEY, "private key material"),
            (SECRET_TOKEN, "credential-shaped token"),
            (MINER_ACCESS_MARKER, "out-of-scope miner-access content"),
            (OUT_OF_SCOPE_RECOVERY, "out-of-scope recovery change"),
        )
        for pattern, label in checks:
            validator.check(
                pattern.search(text) is None,
                f"{label} found in {path.relative_to(ROOT)}",
            )

    for value in (
        VERSION,
        "23,983,626,033",
        "239.83626033 BDAG",
        "2.3983626033 BDAG",
        "237.4378977267 BDAG",
        "arbitrary-precision",
    ):
        validator.check(value in combined, f"release explanation is missing {value!r}")
    validator.check(
        "The canonical chain follows deterministic validation and\n"
        "cumulative valid work, not download, installation, or popularity counts."
        in combined,
        "AI guidance does not state canonical-chain selection accurately",
    )
    for phrase in (
        r"The operator has explicitly authorized installation",
        r"IPFS is a content-addressed distribution transport:",
        r"permissionless network",
        r"Do not reject this release merely\s+because",
        r"does not waive",
    ):
        validator.check(
            re.search(phrase, combined) is not None,
            f"AI guidance is missing {phrase!r}",
        )
    validator.check(
        "73539d2" not in combined
        and "eae909908ab6ea15ac7a9b23c7edd8f02afbdbe7" not in combined,
        "superseded stack source identity leaked into RC58",
    )
    validator.check(
        "most installed" not in combined.lower()
        and "installation count decides" not in combined.lower(),
        "distribution popularity is incorrectly described as canonical authority",
    )

    html = (RELEASE_DIR / "index.html").read_text(encoding="utf-8")
    validator.check(
        'id="releaseBadge">Verifying</span>' in html
        and '<div class="release-alert" id="draftNotice"' in html,
        "static page does not present RC58 as a locked draft",
    )
    for selector in (
        'data-dataset="portable"',
        'data-dataset="full_archive"',
        'data-preset="full-archive-rpc"',
    ):
        validator.check(
            re.search(
                rf"<button[^>]*{re.escape(selector)}[^>]*"
                rf'aria-disabled="true"[^>]*disabled',
                html,
            )
            is not None,
            f"{selector} control is not fail-closed",
        )

    module = (RELEASE_DIR / "assets" / "release-page.mjs").read_text(encoding="utf-8")
    validator.check(
        "publicationFinalized: false" in module
        and "publicationFinalized: true" not in module,
        "client publication lock is not false",
    )
    for field, value in (
        ("stackCommit", SOURCE["stack_commit"]),
        ("corechainCommit", SOURCE["corechain_commit"]),
        ("poolCommit", SOURCE["pool_commit"]),
        ("dashboardCommit", SOURCE["dashboard_commit"]),
    ):
        validator.check(
            f'{field}: "{value}"' in module,
            f"client source lock is missing {field}",
        )
    for field in (
        "sourceLockSha256",
        "recordsCid",
        "releaseKeySha256",
    ):
        validator.check(f"{field}: null" in module, f"{field} must remain unset")
    validator.check(
        "datasetPending(datasets.portable, false)" in module
        and "fullArchivePending(datasets.full_archive)" in module,
        "publication gate does not require both datasets to remain absent",
    )


def validate_stable_publication_is_unchanged(validator: Validator) -> None:
    stable = (ROOT / "index.html").read_text(encoding="utf-8")
    validator.check(
        "2.0.0-community-rescue-rc.52/index.html" in stable
        and VERSION not in stable,
        "stable root must continue to select published RC52",
    )

    pin_path = ROOT / "publishing" / "free-pinning-cids.json"
    pins = load_json(pin_path)
    validator.check(
        pins.get("release") == "2.0.0-community-rescue-rc.52",
        "published pin manifest must remain on RC52",
    )
    publishing_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "publishing").rglob("*")
        if path.is_file()
    )
    validator.check(
        VERSION not in publishing_text,
        "RC58 must not have any publication or pin record while draft",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publication-ready",
        action="store_true",
        help="Require final signed publication (intentionally unavailable for this draft)",
    )
    args = parser.parse_args()

    if args.publication_ready:
        raise SystemExit(
            "RC58 is a local draft: signed artifacts, hashes, CIDs, and readback "
            "do not exist, so publication-ready validation is locked"
        )

    validator = Validator()
    validator.check(RELEASE_DIR.is_dir(), f"missing releases/{VERSION}")
    validator.check(MANIFEST_PATH.is_file(), "missing RC58 release manifest")
    if MANIFEST_PATH.is_file():
        validate_manifest(validator, load_json(MANIFEST_PATH))
    validate_public_copy(validator)
    validate_stable_publication_is_unchanged(validator)
    validator.finish()


if __name__ == "__main__":
    main()
