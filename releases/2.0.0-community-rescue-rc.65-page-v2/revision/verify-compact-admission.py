#!/usr/bin/env python3
"""Verify the RC65 page revision and compact installer admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


EXPECTED = {
    "version": "2.0.0-community-rescue-rc.65",
    "sequence": 65,
    "tag": "jeremy-community-rescue-rc.65.6",
    "release_sha": "4f1c1962edb90dd99f4286d58507ed2216ea47f7bc83ccb055072269731b1335",
    "records_cid": "bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe",
    "predecessor_cid": "bafybeiet53pfpyf52mmbqwqg6qapxueblqhyqyit6f5zyfaotunpwtgweq",
    "outer_key": "9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66",
    "dataset_key": "f9f2f7df88d43c8d51df8bdc2a369601ff0b4b9de224e8ab9b609b423b203d24",
    "compact_name": "blockdag-chain1404-compact-data-2.0.0-community-rescue-rc.65-evm17884079.tar.zst",
    "compact_cid": "bafybeih55jggjwlwhdkapsb2h3cp4yx7lt3a43chiwyvuyazrh7eekm6y4",
    "compact_sha": "0939750a68afe7bec90774a48985f1ae5cdc734fc61364247296f32bd3a5eb92",
    "compact_bytes": 16191131162,
    "compact_unpacked": 32618071094,
    "release_lock_sha": "b5a0defbf297a8245793fbb10d1a9cdbac1e2bbff066ab279a9fb0d17b299e0e",
    "dataset_verifier_sha": "4b9ebdd22af3da564271f5749c7a66fd7360f12e470330fa6df0b639df91b99e",
}
CID_RE = re.compile(r"^b[a-z2-7]{20,}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise SystemExit(f"RC65 page-v2 admission failed: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def regular(path: Path) -> None:
    try:
        stat = path.lstat()
    except OSError as exc:
        fail(f"required file is unavailable: {path}: {exc}")
    if path.is_symlink() or not path.is_file() or stat.st_nlink != 1:
        fail(f"required path is not a regular single-link file: {path}")


def fingerprint(path: Path) -> str:
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(path), "-outform", "DER"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def verify_raw(public_key: Path, payload: Path, signature: Path) -> None:
    subprocess.run(
        [
            "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key),
            "-rawin", "-in", str(payload), "-sigfile", str(signature),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def nested(payload: dict, path: str):
    value = payload
    for segment in path.split("."):
        if not isinstance(value, dict) or segment not in value:
            fail(f"missing signed field: {path}")
        value = value[segment]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_root", type=Path)
    parser.add_argument("--ipfs-cid-check", action="store_true")
    args = parser.parse_args()
    root = args.release_root.expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        fail("release root is missing or unsafe")

    records = root / "records"
    revision = root / "revision"
    release_path = records / "release.json"
    outer_key = records / "release-public.pem"
    attestation_path = revision / "page-v2.json"
    attestation_sig = revision / "page-v2.json.sig"
    compact_path = revision / "compact-canonical-manifest.json"
    validation_path = revision / "compact-canonical-validation.json"
    verifier = records / "dataset/verify-canonical-manifest.py"
    dataset_key = records / "dataset/qualification-v2-20260711.pem"
    required = (
        release_path, outer_key, attestation_path, attestation_sig, compact_path,
        validation_path, verifier, dataset_key, root / "verify-load-v2.sh",
    )
    for path in required:
        regular(path)

    if fingerprint(outer_key) != EXPECTED["outer_key"]:
        fail("outer release key fingerprint mismatch")
    if fingerprint(dataset_key) != EXPECTED["dataset_key"]:
        fail("dataset key fingerprint mismatch")
    if sha256(release_path) != EXPECTED["release_sha"]:
        fail("original release record digest changed")
    verify_raw(outer_key, attestation_path, attestation_sig)

    subprocess.run(
        [
            sys.executable, str(verifier), "verify", "--envelope", str(compact_path),
            "--trusted-key-dir", str(records / "dataset"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    compact = json.loads(compact_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    expected_attestation = {
        "schema": "bdag.community-page-revision.v2",
        "status": "published",
        "release.version": EXPECTED["version"],
        "release.sequence": EXPECTED["sequence"],
        "release.softwareTag": EXPECTED["tag"],
        "presentation.revision": 2,
        "presentation.predecessorCid": EXPECTED["predecessor_cid"],
        "originalRecords.cid": EXPECTED["records_cid"],
        "originalRecords.releaseJsonSha256": EXPECTED["release_sha"],
        "trust.outerReleaseKeySha256": EXPECTED["outer_key"],
        "trust.datasetKeySha256": EXPECTED["dataset_key"],
        "compactAdmission.artifact.name": EXPECTED["compact_name"],
        "compactAdmission.artifact.cid": EXPECTED["compact_cid"],
        "compactAdmission.artifact.sha256": EXPECTED["compact_sha"],
        "compactAdmission.artifact.bytes": EXPECTED["compact_bytes"],
        "compactAdmission.artifact.unpackedBytes": EXPECTED["compact_unpacked"],
        "compactAdmission.manifestSha256": sha256(compact_path),
    }
    for path, expected in expected_attestation.items():
        actual = attestation.get(path) if "." not in path else nested(attestation, path)
        if actual != expected:
            fail(f"attestation field differs: {path}")
    for key in ("software", "compactDataset", "fullArchive", "originalRecords"):
        if nested(attestation, f"unchangedBytes.{key}") is not True:
            fail(f"unchanged-byte declaration is false: {key}")

    signed = compact.get("signed")
    signature = compact.get("signature")
    if compact.get("schema") != "bdag.canonical-data-manifest.v3" or not isinstance(signed, dict) or not isinstance(signature, dict):
        fail("canonical manifest envelope shape mismatch")
    expected_compact = {
        "network": "mainnet",
        "chain_id": 1404,
        "dataset_class": "verified-tip-state",
        "archive_node_equivalent": False,
        "artifact.name": EXPECTED["compact_name"],
        "artifact.sha256": EXPECTED["compact_sha"],
        "artifact.size_bytes": EXPECTED["compact_bytes"],
        "artifact.unpacked_size_bytes": EXPECTED["compact_unpacked"],
        "native.order": 18289992,
        "evm.number": 17884079,
        "fixed_checkpoint.number": 13863411,
        "provenance.build_tools.release_lock_sha256": EXPECTED["release_lock_sha"],
        "provenance.build_tools.dataset_verifier_sha256": EXPECTED["dataset_verifier_sha"],
    }
    for path, expected in expected_compact.items():
        actual = signed.get(path) if "." not in path else nested(signed, path)
        if actual != expected:
            fail(f"canonical manifest field differs: {path}")
    if signature.get("key_id") != "qualification-v2-20260711" or signature.get("public_key_sha256") != EXPECTED["dataset_key"]:
        fail("canonical manifest signer mismatch")
    if validation.get("schema") != "chain1404-compact-canonical-validation/v1" or nested(validation, "requirements.archiveNodeEquivalent") is not False:
        fail("compact validation specification mismatch")

    assets = nested(attestation, "presentation.assets")
    if not isinstance(assets, dict) or len(assets) < 5:
        fail("signed presentation asset inventory is incomplete")
    for relative, identity in assets.items():
        if not re.fullmatch(r"(?:assets|revision)/[A-Za-z0-9._/-]+|verify-load(?:-v2)?[.]sh", relative):
            fail(f"unsafe presentation asset path: {relative}")
        path = root / relative
        regular(path)
        if identity != {"bytes": path.stat().st_size, "sha256": sha256(path)}:
            fail(f"presentation asset differs: {relative}")

    if args.ipfs_cid_check:
        if subprocess.run(["ipfs", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            fail("IPFS CLI is unavailable for requested CID check")
        actual = subprocess.check_output(
            [
                "ipfs", "add", "--only-hash", "--cid-version=1", "--raw-leaves=true",
                "--chunker=size-262144", "--hash=sha2-256", "-Q", str(compact_path),
            ],
            text=True,
        ).strip()
        if actual != nested(attestation, "compactAdmission.manifestCid") or not CID_RE.fullmatch(actual):
            fail("compact canonical manifest CID mismatch")

    print("RC65 page-v2 signatures, immutable identities, assets, and compact admission passed")


if __name__ == "__main__":
    main()
