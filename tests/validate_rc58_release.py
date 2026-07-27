#!/usr/bin/env python3
"""Validate the fail-closed RC58 draft or final signed software publication."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0-community-rescue-rc.58"
RELEASE_DIR = ROOT / "releases" / VERSION
MANIFEST_PATH = RELEASE_DIR / "release-manifest.json"
SOFTWARE_DIR = RELEASE_DIR / "records" / "software"
SEQUENCE = 58

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

# RC58_FINAL_METADATA_REQUIRED: replace every value below only from the final
# signed build and deterministic IPFS publication receipts. Deliberately invalid
# placeholders keep --publication-ready fail-closed while artifacts assemble.
FINAL_PLACEHOLDER_PREFIX = "__RC58_FINAL_"
FINAL_RELEASE_KEY_SHA256 = "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb"
FINAL_SOURCE_LOCK_SHA256 = "e7dadc8afac1592f9a22d2cbcd02bb7e0ce086577612b79e4af8bbb327f36f17"
FINAL_RECORDS_CID = "bafybeic5r7t5y6dpoprjbjps2yehjq2d4ovilsnv6ss4ixo45v3tu2zd6a"
FINAL_PAGE_CID = "bafybeibmkyhqwqz26t3lb6w7dp6sjqe2i4goyiopsn6ppfwnf4rrtryjwi"
FINAL_ARTIFACTS = {
    "installer": {
        "status": "published",
        "filename": "bootstrap.sh",
        "cid": "bafkreifjiyrt4tpjhgupyw2bw7ocudlc5fo3js62dvyepcpspan3kocncu",
        "sha256": "a946233e4de939a8fc5b41b7dc2a0d62e95db4cbda1d704789f2781bb5384d15",
        "size_bytes": 6223,
    },
    "linux-amd64": {
        "status": "published",
        "filename": f"pool-stack-docker-{VERSION}-linux-amd64.zip",
        "cid": "bafybeid3wexawynj3cnef7gy6jtewqo3fiaycs2bslz74tyd53rboqlbhm",
        "sha256": "8f0b544a3682e79e283be296a3f148d9121139236c4ffbcc2152f51fded25eb0",
        "size_bytes": 480461478,
    },
    "linux-arm64": {
        "status": "published",
        "filename": f"pool-stack-docker-{VERSION}-linux-arm64.zip",
        "cid": "bafybeifv2bjsgovh6ze2iupq2ykaf3soqtoen7pr5x5mq3b7qob3g5ebsq",
        "sha256": "2e40729208f90a24a9b3de9e853bfd6400d1e6c3682ee28f54d8c36c82aa57c4",
        "size_bytes": 455939492,
    },
}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
CID = re.compile(r"^b[a-z2-7]{20,}$")

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

    def finish(self, mode: str) -> None:
        if self.failures:
            print(f"RC58 {mode} validation failed:", file=sys.stderr)
            for failure in self.failures:
                print(f"- {failure}", file=sys.stderr)
            raise SystemExit(1)
        print(f"RC58 software-only {mode} validation passed")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {path.relative_to(ROOT)}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


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
    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def valid_cid(value: object) -> bool:
    return isinstance(value, str) and bool(CID.fullmatch(value))


def final_identity_configured(validator: Validator) -> bool:
    strings = {
        "release key SHA-256": FINAL_RELEASE_KEY_SHA256,
        "source-lock SHA-256": FINAL_SOURCE_LOCK_SHA256,
        "records CID": FINAL_RECORDS_CID,
        "page CID": FINAL_PAGE_CID,
    }
    for label, value in strings.items():
        validator.check(
            not value.startswith(FINAL_PLACEHOLDER_PREFIX),
            f"{label} still has an RC58_FINAL placeholder",
        )
    validator.check(
        bool(SHA256.fullmatch(FINAL_RELEASE_KEY_SHA256)),
        "release key SHA-256 is not a lowercase 64-character digest",
    )
    validator.check(
        bool(SHA256.fullmatch(FINAL_SOURCE_LOCK_SHA256)),
        "source-lock SHA-256 is not a lowercase 64-character digest",
    )
    validator.check(valid_cid(FINAL_RECORDS_CID), "records CID is invalid")
    validator.check(valid_cid(FINAL_PAGE_CID), "page CID is invalid")
    for label, artifact in FINAL_ARTIFACTS.items():
        for field in ("cid", "sha256"):
            value = artifact[field]
            validator.check(
                isinstance(value, str)
                and not value.startswith(FINAL_PLACEHOLDER_PREFIX),
                f"{label}.{field} still has an RC58_FINAL placeholder",
            )
        validator.check(
            isinstance(artifact["size_bytes"], int)
            and artifact["size_bytes"] > 0,
            f"{label}.size_bytes still has an RC58_FINAL placeholder",
        )
        validator.check(valid_cid(artifact["cid"]), f"{label}.cid is invalid")
        validator.check(
            bool(SHA256.fullmatch(str(artifact["sha256"]))),
            f"{label}.sha256 is not a lowercase 64-character digest",
        )
    return not any(
        isinstance(value, str) and value.startswith(FINAL_PLACEHOLDER_PREFIX)
        for value in (
            FINAL_RELEASE_KEY_SHA256,
            FINAL_SOURCE_LOCK_SHA256,
            FINAL_RECORDS_CID,
            FINAL_PAGE_CID,
            *(
                artifact[field]
                for artifact in FINAL_ARTIFACTS.values()
                for field in ("cid", "sha256")
            ),
        )
    ) and all(
        isinstance(artifact["size_bytes"], int) and artifact["size_bytes"] > 0
        for artifact in FINAL_ARTIFACTS.values()
    )


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


def verify_release_lock(
    validator: Validator,
    release_lock: dict[str, Any],
) -> None:
    try:
        signature = release_lock["signature"]
        signature_bytes = base64.b64decode(signature["value"], validate=True)
        validator.check(
            len(signature_bytes) == 64,
            "release-lock signature is not a 64-byte Ed25519 signature",
        )
        with tempfile.TemporaryDirectory(prefix="rc58-lock-verify-") as temporary:
            payload = Path(temporary) / "payload.json"
            signature_file = Path(temporary) / "signature.bin"
            payload.write_bytes(canonical_json(release_lock["signed"]))
            signature_file.write_bytes(signature_bytes)
            run_checked(
                [
                    "openssl",
                    "pkeyutl",
                    "-verify",
                    "-rawin",
                    "-pubin",
                    "-inkey",
                    str(SOFTWARE_DIR / "release-key.pem"),
                    "-in",
                    str(payload),
                    "-sigfile",
                    str(signature_file),
                ]
            )
    except (KeyError, TypeError, ValueError, subprocess.CalledProcessError):
        validator.check(False, "release-lock Ed25519 signature verification failed")


def validate_published_manifest(
    validator: Validator,
    manifest: dict[str, Any],
) -> None:
    validator.check(
        manifest.get("schema") == "bdag.community-release-index.v2",
        "manifest schema is wrong",
    )
    release = manifest.get("release", {})
    validator.check(
        {
            key: release.get(key)
            for key in ("version", "sequence", "channel", "status", "chain_id")
        }
        == {
            "version": VERSION,
            "sequence": SEQUENCE,
            "channel": "community-rescue",
            "status": "published",
            "chain_id": 1404,
        },
        "published release identity is wrong",
    )
    try:
        published_at = datetime.fromisoformat(
            str(release.get("published_at")).replace("Z", "+00:00")
        )
        timestamp_valid = published_at.tzinfo is not None
    except ValueError:
        timestamp_valid = False
    validator.check(timestamp_valid, "published_at is not a timezone-aware ISO-8601 timestamp")

    expected_source = {**SOURCE, "source_lock_sha256": FINAL_SOURCE_LOCK_SHA256}
    validator.check(
        manifest.get("source") == expected_source,
        "published source identity differs from the final signed source lock",
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
            "release_key_path": "records/software/release-key.pem",
            "release_key_sha256": FINAL_RELEASE_KEY_SHA256,
            "dataset_key_path": None,
            "dataset_key_id": None,
            "dataset_key_sha256": None,
            "dataset_verifier_path": None,
            "dataset_verifier_sha256": None,
        },
        "published trust record is wrong or invents dataset trust",
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
        == {
            "mode": "ipfs-directory",
            "cid": FINAL_RECORDS_CID,
            "path_prefix": "records/",
        },
        "signed-record delivery identity is wrong",
    )
    validator.check(
        manifest.get("installer") == FINAL_ARTIFACTS["installer"],
        "published installer identity is wrong",
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
                "linux-amd64": FINAL_ARTIFACTS["linux-amd64"],
                "linux-arm64": FINAL_ARTIFACTS["linux-arm64"],
            },
            "published architecture package identities are wrong",
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
            "software record paths are wrong",
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
            "status": "passed",
            "signed_package_integrity_verified": True,
            "portable_dataset_verified": False,
            "full_archive_dataset_verified": False,
            "restore_path_verified": True,
            "runtime_path_verified": True,
        },
        "publication qualification is incomplete or overclaims dataset verification",
    )


def validate_signed_records(
    validator: Validator,
    manifest: dict[str, Any],
) -> None:
    required = {
        "bootstrap.sh",
        "release-auth-manifest.json",
        "release-auth-manifest.json.sig",
        "release-key.pem",
        "release-lock.json",
        "release-notes.md",
        "release-source-lock.json",
    }
    if not SOFTWARE_DIR.is_dir() or SOFTWARE_DIR.is_symlink():
        validator.check(False, "signed software record directory is missing or unsafe")
        return
    actual = {path.name for path in SOFTWARE_DIR.iterdir() if path.is_file()}
    validator.check(actual == required, "signed software record inventory is not exact")
    if actual != required:
        return

    try:
        key_der = subprocess.run(
            [
                "openssl",
                "pkey",
                "-pubin",
                "-in",
                str(SOFTWARE_DIR / "release-key.pem"),
                "-outform",
                "DER",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
        key_fingerprint = hashlib.sha256(key_der).hexdigest()
        validator.check(
            key_fingerprint == FINAL_RELEASE_KEY_SHA256,
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
                str(SOFTWARE_DIR / "release-key.pem"),
                "-in",
                str(SOFTWARE_DIR / "release-auth-manifest.json"),
                "-sigfile",
                str(SOFTWARE_DIR / "release-auth-manifest.json.sig"),
            ]
        )
    except subprocess.CalledProcessError:
        validator.check(False, "release authorization signature verification failed")

    auth = load_json(SOFTWARE_DIR / "release-auth-manifest.json")
    source_lock = load_json(SOFTWARE_DIR / "release-source-lock.json")
    release_lock = load_json(SOFTWARE_DIR / "release-lock.json")
    verify_release_lock(validator, release_lock)

    validator.check(
        auth.get("schema") == "bdag.release-auth-manifest.v1",
        "release authorization schema is wrong",
    )
    validator.check(
        source_lock.get("schema") == "bdag.release-source-lock.v3",
        "release source-lock schema is wrong",
    )
    validator.check(
        release_lock.get("schema") == "bdag.release-lock.v3",
        "release-lock schema is wrong",
    )

    source_lock_sha256 = sha256_file(SOFTWARE_DIR / "release-source-lock.json")
    validator.check(
        source_lock_sha256 == FINAL_SOURCE_LOCK_SHA256,
        "source-lock bytes do not match the final pinned SHA-256",
    )
    validator.check(
        manifest["source"].get("source_lock_sha256") == source_lock_sha256,
        "page source-lock hash differs from the signed record bytes",
    )
    validator.check(
        release_lock.get("signed", {}).get("source_lock_sha256")
        == source_lock_sha256,
        "signed release-lock references the wrong source lock",
    )

    signature = release_lock.get("signature", {})
    validator.check(
        signature.get("algorithm") == "ed25519"
        and signature.get("public_key_sha256") == FINAL_RELEASE_KEY_SHA256,
        "release-lock trust record is wrong",
    )
    signed_release = release_lock.get("signed", {}).get("release", {})
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
        auth.get("release_key_sha256") == FINAL_RELEASE_KEY_SHA256,
        "release authorization key fingerprint is wrong",
    )

    repositories = {
        "stack": SOURCE["stack_commit"],
        "blockdag-corechain": SOURCE["corechain_commit"],
        "pool": SOURCE["pool_commit"],
        "redis-dash": SOURCE["dashboard_commit"],
    }
    validator.check(
        set(source_lock.get("repositories", {})) == set(repositories),
        "source-lock repository inventory is wrong",
    )
    validator.check(
        set(release_lock.get("signed", {}).get("repositories", {}))
        == set(repositories),
        "signed release-lock repository inventory is wrong",
    )
    for repository, commit in repositories.items():
        source_record = source_lock.get("repositories", {}).get(repository, {})
        signed_record = (
            release_lock.get("signed", {})
            .get("repositories", {})
            .get(repository, {})
        )
        validator.check(
            source_record.get("commit") == commit
            and source_record.get("dirty") is False,
            f"{repository} source-lock identity is wrong",
        )
        validator.check(
            signed_record.get("commit") == commit
            and signed_record.get("dirty") is False,
            f"{repository} signed release-lock identity is wrong",
        )

    targets = release_lock.get("signed", {}).get("targets", {})
    validator.check(
        set(targets) == {"linux-amd64", "linux-arm64"},
        "signed target inventory is wrong",
    )
    for target in ("linux-amd64", "linux-arm64"):
        target_record = targets.get(target, {})
        validator.check(
            target_record.get("target") == target
            and target_record.get("source_lock_sha256") == source_lock_sha256,
            f"{target} signed target does not bind the final source lock",
        )

    expected_assets = {
        artifact["filename"]: {
            "sha256": artifact["sha256"],
            "size_bytes": artifact["size_bytes"],
        }
        for artifact in FINAL_ARTIFACTS.values()
    }
    validator.check(
        auth.get("assets") == expected_assets,
        "release authorization asset inventory or identity is wrong",
    )
    validator.check(
        sha256_file(SOFTWARE_DIR / "bootstrap.sh")
        == FINAL_ARTIFACTS["installer"]["sha256"],
        "bootstrap bytes differ from the signed final identity",
    )
    validator.check(
        (SOFTWARE_DIR / "bootstrap.sh").stat().st_size
        == FINAL_ARTIFACTS["installer"]["size_bytes"],
        "bootstrap size differs from the signed final identity",
    )


def validate_published_copy(
    validator: Validator,
    manifest: dict[str, Any],
) -> None:
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
        validator.check(
            path.is_file() and not path.is_symlink(),
            f"missing {path.relative_to(ROOT)}",
        )
    validator.check(
        not (RELEASE_DIR / "records" / "dataset").exists(),
        "software-only RC58 must not contain dataset records",
    )

    combined = ""
    signature_path = SOFTWARE_DIR / "release-auth-manifest.json.sig"
    for path in RELEASE_DIR.rglob("*"):
        if path.is_symlink():
            validator.check(False, f"symlink found in {path.relative_to(ROOT)}")
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path == signature_path:
            validator.check(
                len(raw) == 64,
                "release authorization signature is not exactly 64 bytes",
            )
            text = raw.decode("latin-1")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                validator.check(
                    False,
                    f"unexpected binary file {path.relative_to(ROOT)}",
                )
                text = raw.decode("latin-1")
        combined += f"\n{text}"
        privacy_checks = (
            (PRIVATE_IPV4, "private IPv4 address"),
            (PRIVATE_IPV6, "private IPv6 address"),
            (PRIVATE_PATH, "private filesystem path"),
            (MAC_ADDRESS, "hardware address"),
            (PRIVATE_KEY, "private key material"),
            (SECRET_TOKEN, "credential-shaped token"),
        )
        for pattern, label in privacy_checks:
            validator.check(
                pattern.search(text) is None,
                f"{label} found in {path.relative_to(ROOT)}",
            )
        signed_machine_records = {
            "release-auth-manifest.json",
            "release-auth-manifest.json.sig",
            "release-key.pem",
            "release-lock.json",
            "release-source-lock.json",
        }
        if not (
            path.parent == SOFTWARE_DIR
            and path.name in signed_machine_records
        ):
            for pattern, label in (
                (MINER_ACCESS_MARKER, "out-of-scope miner-access content"),
                (OUT_OF_SCOPE_RECOVERY, "out-of-scope recovery change"),
            ):
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
        "most installed" not in combined.lower()
        and "installation count decides" not in combined.lower(),
        "distribution popularity is incorrectly described as canonical authority",
    )

    html = (RELEASE_DIR / "index.html").read_text(encoding="utf-8")
    validator.check(
        'class="draft-badge published" id="releaseBadge">Published</span>'
        in html
        and '<div class="release-alert published" id="draftNotice"' in html,
        "static page does not present RC58 as published",
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

    module = (RELEASE_DIR / "assets" / "release-page.mjs").read_text(
        encoding="utf-8"
    )
    validator.check(
        "publicationFinalized: true" in module
        and "publicationFinalized: false" not in module,
        "client publication lock is not finalized",
    )
    expected_module_values = {
        "sourceLockSha256": FINAL_SOURCE_LOCK_SHA256,
        "recordsCid": FINAL_RECORDS_CID,
        "releaseKeySha256": FINAL_RELEASE_KEY_SHA256,
    }
    for field, value in expected_module_values.items():
        validator.check(
            f'{field}: "{value}"' in module,
            f"client final identity is missing {field}",
        )
    for label, artifact in FINAL_ARTIFACTS.items():
        for value in (
            artifact["filename"],
            artifact["cid"],
            artifact["sha256"],
        ):
            validator.check(
                f'"{value}"' in module,
                f"client final identity is missing {label} value {value!r}",
            )
        validator.check(
            f"size_bytes: {artifact['size_bytes']}" in module,
            f"client final identity is missing {label} size",
        )
    validator.check(
        "datasetPending(datasets.portable, false)" in module
        and "fullArchivePending(datasets.full_archive)" in module,
        "publication gate does not require both datasets to remain absent",
    )


def validate_publication_pointers(validator: Validator) -> None:
    stable = (ROOT / "index.html").read_text(encoding="utf-8")
    validator.check(
        f"releases/{VERSION}/index.html" in stable
        and "2.0.0-community-rescue-rc.52/index.html" not in stable,
        "stable root does not select only RC58",
    )

    pins = load_json(ROOT / "publishing" / "free-pinning-cids.json")
    validator.check(
        pins.get("schema") == "bdag.community-ipfs-pins.v1"
        and pins.get("release") == VERSION,
        "published pin manifest release identity is wrong",
    )
    validator.check(
        pins.get("pins")
        == [
            {
                "name": "release-page-root",
                "cid": FINAL_PAGE_CID,
                "recursive": True,
            },
            {
                "name": "release-records-root",
                "cid": FINAL_RECORDS_CID,
                "recursive": True,
            },
            {
                "name": "verified-installer",
                "cid": FINAL_ARTIFACTS["installer"]["cid"],
                "recursive": False,
            },
            {
                "name": "linux-amd64-software",
                "cid": FINAL_ARTIFACTS["linux-amd64"]["cid"],
                "recursive": True,
            },
            {
                "name": "linux-arm64-software",
                "cid": FINAL_ARTIFACTS["linux-arm64"]["cid"],
                "recursive": True,
            },
        ],
        "published pin inventory is not the exact software-only RC58 set",
    )

    publishing = (ROOT / "publishing" / "README.md").read_text(encoding="utf-8")
    validator.check(
        VERSION in publishing
        and FINAL_PAGE_CID in publishing
        and FINAL_RECORDS_CID in publishing
        and "tests/validate_rc58_release.py --publication-ready" in publishing,
        "publishing guide does not reproduce the final RC58 identities and gate",
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    validator.check(
        f"Current release: `{VERSION}`" in readme
        and f"`releases/{VERSION}/`" in readme,
        "repository README does not identify RC58 as current",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publication-ready",
        action="store_true",
        help="Require the exact final signed software-only publication",
    )
    args = parser.parse_args()

    validator = Validator()
    validator.check(RELEASE_DIR.is_dir(), f"missing releases/{VERSION}")
    validator.check(MANIFEST_PATH.is_file(), "missing RC58 release manifest")
    if not MANIFEST_PATH.is_file():
        validator.finish("publication" if args.publication_ready else "draft")
        return

    manifest = load_json(MANIFEST_PATH)
    if args.publication_ready:
        final_identity_configured(validator)
        validate_published_manifest(validator, manifest)
        validate_signed_records(validator, manifest)
        validate_published_copy(validator, manifest)
        validate_publication_pointers(validator)
        validator.finish("publication")
        return

    validate_manifest(validator, manifest)
    validate_public_copy(validator)
    validate_stable_publication_is_unchanged(validator)
    validator.finish("draft")


if __name__ == "__main__":
    main()
