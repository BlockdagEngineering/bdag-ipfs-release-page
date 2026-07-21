#!/usr/bin/env python3
"""Validate the signed, fail-closed RC44 release-page candidate."""

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
RELEASE = ROOT / "releases" / "2.0.0-community-rescue-rc.44"
MANIFEST_PATH = RELEASE / "release-manifest.json"
SOFTWARE = RELEASE / "records" / "software"
DATASET = RELEASE / "records" / "dataset"

VERSION = "2.0.0-community-rescue-rc.44"
SEQUENCE = 44
RELEASE_KEY_SHA256 = "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb"
SOURCE_LOCK_SHA256 = "6177262190a60ccf77671a87f4164ed5541e873efc4ddc36c7c9519e26a714f2"
COMMITS = {
    "stack": "bda8cf1e5c73a8e0316ce302650310feb0538939",
    "blockdag-corechain": "bb0f7a6fed918e56251aa602503c90f1e1f30cb8",
    "pool": "80774b865b60e695b6e91a817013d9aeffc03271",
    "redis-dash": "f00b654f79e50346bf6e866348cf07bdcb3b44ec",
}
PACKAGES = {
    "linux-amd64": {
        "filename": f"pool-stack-docker-{VERSION}-linux-amd64.zip",
        "sha256": "8713bf3035ecabe2867492a60214fcabfe16c257c9575d939da2b35984e445bd",
        "size_bytes": 638991557,
    },
    "linux-arm64": {
        "filename": f"pool-stack-docker-{VERSION}-linux-arm64.zip",
        "sha256": "f96fd9f4e35b83e2fe052914dbe5f85626c672d9caf7d8886aecb1458e39388c",
        "size_bytes": 460314761,
    },
}
BOOTSTRAP = {
    "filename": "bootstrap.sh",
    "sha256": "6b1c8175c91d75011851f971eadfa436ec11935bc4098dac58f0ccd01b93f7e4",
    "size_bytes": 5419,
}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHAIN_HASH = re.compile(r"^0x[0-9a-f]{64}$")
CID = re.compile(r"^b[a-z2-7]{20,}$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]*$")
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

    def finish(self, mode: str) -> None:
        if self.errors:
            print(f"RC44 {mode} validation failed:")
            for error in self.errors:
                print(f"- {error}")
            raise SystemExit(1)
        print(f"RC44 {mode} validation passed ({self.checks} checks).")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("ascii")


def safe_relative_path(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and not value.startswith("/")
        and "\\" not in value
        and SAFE_PATH.fullmatch(value)
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def valid_cid(value: object) -> bool:
    return isinstance(value, str) and bool(CID.fullmatch(value))


def valid_boundary(value: object, number_key: str) -> bool:
    if not isinstance(value, dict):
        return False
    expected = {number_key, "hash"} if number_key == "order" else {number_key, "hash", "state_root"}
    return bool(
        set(value) == expected
        and isinstance(value[number_key], int)
        and value[number_key] >= 0
        and CHAIN_HASH.fullmatch(str(value["hash"]))
        and (number_key == "order" or CHAIN_HASH.fullmatch(str(value["state_root"])))
    )


def run_checked(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def verify_release_key(validator: Validator) -> None:
    key = SOFTWARE / "release-key.pem"
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(key), "-outform", "DER"],
        check=True,
        stdout=subprocess.PIPE,
    )
    validator.check(
        hashlib.sha256(result.stdout).hexdigest() == RELEASE_KEY_SHA256,
        "release public-key fingerprint does not match the externally pinned value",
    )


def verify_release_lock(validator: Validator, lock: dict[str, Any]) -> None:
    signature = lock.get("signature", {})
    validator.check(lock.get("schema") == "bdag.release-lock.v3", "release-lock schema is invalid")
    validator.check(signature.get("algorithm") == "ed25519", "release-lock signature algorithm is invalid")
    validator.check(
        signature.get("public_key_sha256") == RELEASE_KEY_SHA256,
        "release-lock signature fingerprint is invalid",
    )
    try:
        decoded = base64.b64decode(signature.get("value", ""), validate=True)
    except (ValueError, TypeError):
        decoded = b""
    validator.check(len(decoded) == 64, "release-lock signature is not a 64-byte Ed25519 signature")
    if len(decoded) != 64:
        return
    with tempfile.TemporaryDirectory(prefix="rc44-lock-verify-") as temporary:
        payload = Path(temporary) / "payload.json"
        signature_file = Path(temporary) / "signature.bin"
        payload.write_bytes(canonical_json(lock["signed"]))
        signature_file.write_bytes(decoded)
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


def validate_signed_records(validator: Validator, manifest: dict[str, Any]) -> None:
    source_lock_path = SOFTWARE / "release-source-lock.json"
    release_lock_path = SOFTWARE / "release-lock.json"
    auth_path = SOFTWARE / "release-auth-manifest.json"
    required = (
        source_lock_path,
        release_lock_path,
        auth_path,
        SOFTWARE / "release-auth-manifest.json.sig",
        SOFTWARE / "release-key.pem",
        SOFTWARE / "bootstrap.sh",
        SOFTWARE / "release-notes.md",
    )
    for path in required:
        validator.check(path.is_file(), f"missing signed software record: {path.relative_to(ROOT)}")
    if not all(path.is_file() for path in required):
        return

    verify_release_key(validator)
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
            str(auth_path),
            "-sigfile",
            str(SOFTWARE / "release-auth-manifest.json.sig"),
        ]
    )
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    release_lock = json.loads(release_lock_path.read_text(encoding="utf-8"))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    verify_release_lock(validator, release_lock)

    validator.check(sha256_file(source_lock_path) == SOURCE_LOCK_SHA256, "source-lock file hash is wrong")
    validator.check(manifest["source"]["source_lock_sha256"] == SOURCE_LOCK_SHA256, "page source-lock hash is wrong")
    validator.check(release_lock["signed"]["source_lock_sha256"] == SOURCE_LOCK_SHA256, "signed release-lock references the wrong source lock")
    for repository, commit in COMMITS.items():
        validator.check(source_lock["repositories"][repository]["commit"] == commit, f"{repository} source-lock commit is wrong")
        validator.check(release_lock["signed"]["repositories"][repository]["commit"] == commit, f"{repository} signed commit is wrong")
        validator.check(source_lock["repositories"][repository]["dirty"] is False, f"{repository} source lock is dirty")

    validator.check(auth["release"] == {"sequence": SEQUENCE, "version": VERSION}, "release authorization identity is wrong")
    validator.check(auth["release_key_sha256"] == RELEASE_KEY_SHA256, "release authorization key fingerprint is wrong")
    validator.check(
        auth["assets"]["bootstrap.sh"]
        == {"sha256": BOOTSTRAP["sha256"], "size_bytes": BOOTSTRAP["size_bytes"]},
        "bootstrap authorization is wrong",
    )
    validator.check(
        sha256_file(SOFTWARE / "bootstrap.sh") == BOOTSTRAP["sha256"],
        "recorded bootstrap bytes are wrong",
    )
    installer = manifest["installer"]
    validator.check(
        {key: installer.get(key) for key in BOOTSTRAP} == BOOTSTRAP,
        "page bootstrap identity is wrong",
    )
    for target, expected in PACKAGES.items():
        validator.check(auth["assets"].get(expected["filename"]) == {"sha256": expected["sha256"], "size_bytes": expected["size_bytes"]}, f"{target} authorization is wrong")
        artifact = manifest["software"]["targets"][target]
        validator.check(
            {key: artifact.get(key) for key in expected} == expected,
            f"{target} page identity is wrong",
        )


def validate_full_archive_pending(validator: Validator, archive: dict[str, Any]) -> None:
    validator.check(archive.get("status") == "pending", "full archive must remain pending")
    validator.check(archive.get("archive_node_equivalent") is True, "full archive type is wrong")
    for key in (
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
        "archive_audit",
    ):
        validator.check(archive.get(key) is None, f"pending full archive must not claim {key}")
    validator.check(
        archive.get("delivery") == {
            "mode": None,
            "cid": None,
            "parts_manifest_path": None,
            "parts": [],
        },
        "pending full archive delivery fields must remain empty",
    )


def validate_page(validator: Validator, manifest: dict[str, Any]) -> None:
    required = (
        RELEASE / "index.html",
        RELEASE / "assets" / "release-page.mjs",
        RELEASE / "assets" / "release.css",
        RELEASE / "docs" / "human-install.md",
        RELEASE / "docs" / "ai-agent-runbook.md",
        RELEASE / "docs" / "publication-input.md",
    )
    for path in required:
        validator.check(path.is_file(), f"missing page file: {path.relative_to(ROOT)}")
    html = (RELEASE / "index.html").read_text(encoding="utf-8")
    module = (RELEASE / "assets" / "release-page.mjs").read_text(encoding="utf-8")
    validator.check('data-preset="full-archive-rpc"' in html, "full archive RPC preset is missing")
    validator.check('aria-disabled="true" disabled' in html, "pending full archive preset is not disabled")
    validator.check('preset: "full-archive-rpc"' in module, "full archive preset resolver is missing")
    validator.check('profile: "public-rpc"' in module, "full archive preset does not select public-rpc")
    validator.check('dataset: "full_archive"' in module, "full archive preset does not select full archive data")
    validator.check('retention: "archive"' in module, "full archive preset does not select archive retention")
    validator.check('"--full-archive"' in module, "full archive preset does not invoke --full-archive")
    validator.check("TLS edge proxy" in html and "per-client abuse controls" in module, "public RPC edge guidance is incomplete")
    for path in RELEASE.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        validator.check(not PRIVATE_IPV4.search(text), f"private IP leaked in {path.relative_to(ROOT)}")
        validator.check(not PRIVATE_PATH.search(text), f"private path leaked in {path.relative_to(ROOT)}")

    validator.check(manifest["runtime_change"]["canonical_mismatch"] == "fail-immediately", "canonical mismatch policy is not fail-closed")
    validator.check(manifest["runtime_change"]["transient_startup_canonical_boundary_rpc"] == "bounded-retry", "EVM readiness policy is not bounded")
    validator.check(manifest["runtime_change"]["transient_startup_peer_readiness"] == "bounded-retry", "peer readiness policy is not bounded")


def validate_publication_ready(validator: Validator, manifest: dict[str, Any]) -> None:
    release = manifest["release"]
    validator.check(release.get("status") == "published", "release is not published")
    try:
        datetime.fromisoformat(str(release.get("published_at")).replace("Z", "+00:00"))
        valid_timestamp = True
    except ValueError:
        valid_timestamp = False
    validator.check(valid_timestamp, "published_at is not an ISO-8601 timestamp")
    validator.check(valid_cid(manifest["records_delivery"].get("cid")), "records directory CID is missing")
    validator.check(valid_cid(manifest["installer"].get("cid")), "bootstrap CID is missing")
    for target in PACKAGES:
        artifact = manifest["software"]["targets"][target]
        validator.check(artifact.get("status") == "published", f"{target} is not published")
        validator.check(valid_cid(artifact.get("cid")), f"{target} CID is missing")

    archive = manifest["datasets"]["full_archive"]
    archive_available = archive.get("status") == "published"
    if archive_available:
        validator.check(archive.get("archive_node_equivalent") is True, "full archive equivalence proof is missing")
        validator.check(isinstance(archive.get("version"), str) and bool(archive["version"]), "full archive version is missing")
        validator.check(isinstance(archive.get("sha256"), str) and bool(SHA256.fullmatch(archive["sha256"])), "full archive SHA-256 is missing")
        validator.check(isinstance(archive.get("size_bytes"), int) and archive["size_bytes"] > 0, "full archive size is missing")
        validator.check(isinstance(archive.get("unpacked_size_bytes"), int) and archive["unpacked_size_bytes"] > 0, "full archive unpacked size is missing")
        validator.check(valid_boundary(archive.get("native_boundary"), "order"), "full archive native boundary is invalid")
        validator.check(valid_boundary(archive.get("evm_boundary"), "number"), "full archive EVM boundary is invalid")
        validator.check(valid_boundary(archive.get("fixed_checkpoint"), "number"), "full archive checkpoint is invalid")
        archive_audit = archive.get("archive_audit")
        validator.check(
            isinstance(archive_audit, dict) and archive_audit.get("status") == "passed",
            "full archive audit has not passed",
        )
        validator.check(safe_relative_path(archive.get("canonical_manifest_path")), "full archive signed manifest path is missing")
        validator.check(safe_relative_path(archive.get("validation_spec_path")), "full archive validation spec path is missing")
        delivery = archive.get("delivery")
        if not isinstance(delivery, dict):
            delivery = {}
        direct = delivery.get("mode") == "direct" and valid_cid(delivery.get("cid"))
        multipart = (
            delivery.get("mode") == "multipart"
            and safe_relative_path(delivery.get("parts_manifest_path"))
            and isinstance(delivery.get("parts"), list)
            and len(delivery["parts"]) > 1
            and all(isinstance(part, dict) and valid_cid(part.get("cid")) for part in delivery["parts"])
        )
        validator.check(direct or multipart, "full archive delivery is not immutable")
    else:
        validate_full_archive_pending(validator, archive)
    qualification = manifest["qualification"]
    validator.check(qualification.get("status") == "passed", "qualification is incomplete")
    for key in (
        "signed_package_integrity_verified",
        "portable_dataset_verified",
        "restore_path_verified",
        "runtime_path_verified",
    ):
        validator.check(qualification.get(key) is True, f"qualification.{key} has not passed")
    validator.check(
        qualification.get("full_archive_dataset_verified") is archive_available,
        "qualification.full_archive_dataset_verified does not match availability",
    )
    html = (RELEASE / "index.html").read_text(encoding="utf-8")
    validator.check("noindex,nofollow" not in html, "published page must be indexable")
    root_index = (ROOT / "index.html").read_text(encoding="utf-8")
    validator.check(
        "releases/2.0.0-community-rescue-rc.44/index.html" in root_index,
        "root redirect does not select published RC44",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-ready", action="store_true")
    args = parser.parse_args()

    validator = Validator()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    validator.check(manifest.get("schema") == "bdag.community-release-index.v2", "manifest schema is wrong")
    validator.check(manifest["release"].get("version") == VERSION, "release version is wrong")
    validator.check(manifest["release"].get("sequence") == SEQUENCE, "release sequence is wrong")
    validator.check(manifest["release"].get("chain_id") == 1404, "chain ID is wrong")
    validator.check(manifest["source"].get("tag") == VERSION, "source tag is wrong")
    validator.check(manifest["source"].get("stack_commit") == COMMITS["stack"], "page stack commit is wrong")
    validator.check(manifest["source"].get("corechain_commit") == COMMITS["blockdag-corechain"], "page core commit is wrong")
    validator.check(manifest["source"].get("pool_commit") == COMMITS["pool"], "page pool commit is wrong")
    validator.check(manifest["source"].get("dashboard_commit") == COMMITS["redis-dash"], "page dashboard commit is wrong")
    validator.check(manifest["trust"].get("release_key_sha256") == RELEASE_KEY_SHA256, "page release-key fingerprint is wrong")

    validate_signed_records(validator, manifest)
    validate_page(validator, manifest)
    run_checked(
        [
            "python3",
            str(DATASET / "verify-canonical-manifest.py"),
            "verify",
            "--envelope",
            str(DATASET / "portable-v27-canonical-manifest.json"),
            "--trusted-key-dir",
            str(DATASET),
        ]
    )

    if args.publication_ready or manifest["release"].get("status") == "published":
        validate_publication_ready(validator, manifest)
        mode = "publication-ready"
    else:
        validator.check(manifest["release"].get("status") == "draft", "draft status is missing")
        validator.check(manifest["release"].get("published_at") is None, "draft must not claim a publication time")
        validator.check(manifest["records_delivery"].get("cid") is None, "draft must not invent a records CID")
        validator.check(manifest["installer"].get("status") == "signed-pending-cid", "signed bootstrap identity is not recorded")
        validator.check(manifest["installer"].get("cid") is None, "draft must not invent a bootstrap CID")
        validator.check(manifest["qualification"].get("status") == "in-progress", "draft qualification status is wrong")
        validator.check(manifest["qualification"].get("runtime_path_verified") is True, "runtime qualification is not recorded")
        validator.check(manifest["qualification"].get("restore_path_verified") is False, "draft overclaims restore qualification")
        validate_full_archive_pending(validator, manifest["datasets"]["full_archive"])
        validator.check("noindex,nofollow" in (RELEASE / "index.html").read_text(encoding="utf-8"), "draft page must remain noindex")
        mode = "draft"
    validator.finish(mode)


if __name__ == "__main__":
    main()
