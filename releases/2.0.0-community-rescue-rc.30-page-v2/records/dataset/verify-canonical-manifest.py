#!/usr/bin/env python3
"""Verify a signed BlockDAG canonical-data manifest with an Ed25519 key."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "bdag.canonical-data-manifest.v3"
SIGNATURE_ALGORITHM = "ed25519"
NETWORK = "mainnet"
CHAIN_ID = 1404
KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHAIN_HASH = re.compile(r"^0x[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    """Raised when a manifest is malformed or cannot be authenticated."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read manifest: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError("manifest must be a JSON object")
    return value


def run_openssl(arguments: list[str], input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["openssl", *arguments],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise VerificationError(f"openssl is unavailable: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(detail or "openssl verification failed")
    return result.stdout


def public_key_fingerprint(path: Path) -> str:
    der = run_openssl(["pkey", "-pubin", "-in", str(path), "-pubout", "-outform", "DER"])
    return hashlib.sha256(der).hexdigest()


def trusted_key(directory: Path, key_id: str) -> Path:
    if not KEY_ID.fullmatch(key_id):
        raise VerificationError("manifest key ID is invalid")
    if not directory.is_dir():
        raise VerificationError("trusted-key directory is unavailable")
    matches = [candidate for suffix in (".pem", ".pub") if (candidate := directory / f"{key_id}{suffix}").is_file()]
    if len(matches) != 1:
        raise VerificationError("trusted-key directory must contain exactly one key for the manifest key ID")
    return matches[0]


def verify_signature(payload: dict[str, Any], signature: bytes, public_key: Path) -> None:
    with tempfile.NamedTemporaryFile(prefix="bdag-manifest-", delete=False) as payload_file:
        payload_file.write(canonical_json(payload))
        payload_path = Path(payload_file.name)
    with tempfile.NamedTemporaryFile(prefix="bdag-signature-", delete=False) as signature_file:
        signature_file.write(signature)
        signature_path = Path(signature_file.name)
    try:
        run_openssl(
            [
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(public_key),
                "-in",
                str(payload_path),
                "-sigfile",
                str(signature_path),
            ]
        )
    finally:
        payload_path.unlink(missing_ok=True)
        signature_path.unlink(missing_ok=True)


def require_hash(value: object, label: str) -> None:
    if not isinstance(value, str) or not CHAIN_HASH.fullmatch(value):
        raise VerificationError(f"{label} is not a canonical chain hash")


def validate_boundary(value: object, label: str, number_key: str, require_state: bool) -> None:
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is missing")
    number = value.get(number_key)
    if not isinstance(number, int) or number < 0:
        raise VerificationError(f"{label}.{number_key} is invalid")
    require_hash(value.get("hash"), f"{label}.hash")
    if require_state:
        require_hash(value.get("state_root"), f"{label}.state_root")


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("network") != NETWORK or payload.get("chain_id") != CHAIN_ID:
        raise VerificationError("manifest does not identify BlockDAG mainnet chain ID 1404")
    if not isinstance(payload.get("archive_node_equivalent"), bool):
        raise VerificationError("archive-node equivalence declaration is missing")

    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        raise VerificationError("artifact record is missing")
    if not isinstance(artifact.get("name"), str) or not artifact["name"]:
        raise VerificationError("artifact filename is missing")
    if not isinstance(artifact.get("sha256"), str) or not SHA256.fullmatch(artifact["sha256"]):
        raise VerificationError("artifact SHA-256 is invalid")
    for key in ("size_bytes", "unpacked_size_bytes"):
        if not isinstance(artifact.get(key), int) or artifact[key] <= 0:
            raise VerificationError(f"artifact {key} is invalid")

    validate_boundary(payload.get("native"), "native", "order", require_state=True)
    validate_boundary(payload.get("evm"), "evm", "number", require_state=True)
    validate_boundary(payload.get("fixed_checkpoint"), "fixed_checkpoint", "number", require_state=True)


def verify(envelope_path: Path, trusted_key_directory: Path, expected_schema: str) -> dict[str, Any]:
    envelope = load_json(envelope_path)
    if envelope.get("schema") != expected_schema:
        raise VerificationError("manifest schema is not accepted")
    payload = envelope.get("signed")
    signature_record = envelope.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature_record, dict):
        raise VerificationError("signed payload or signature record is missing")
    if signature_record.get("algorithm") != SIGNATURE_ALGORITHM:
        raise VerificationError("signature algorithm is not accepted")

    key_id = signature_record.get("key_id")
    fingerprint = signature_record.get("public_key_sha256")
    if not isinstance(key_id, str) or not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint):
        raise VerificationError("signature key identity is invalid")
    key_path = trusted_key(trusted_key_directory, key_id)
    if public_key_fingerprint(key_path) != fingerprint:
        raise VerificationError("trusted public-key fingerprint does not match the signed record")

    encoded_signature = signature_record.get("value")
    if not isinstance(encoded_signature, str):
        raise VerificationError("signature value is missing")
    try:
        signature = base64.b64decode(encoded_signature, validate=True)
    except (ValueError, binascii.Error) as error:
        raise VerificationError("signature value is not valid base64") from error
    if len(signature) != 64:
        raise VerificationError("Ed25519 signature has an invalid length")

    verify_signature(payload, signature, key_path)
    validate_payload(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--schema", default=SCHEMA)
    verify_parser.add_argument("--envelope", type=Path, required=True)
    verify_parser.add_argument("--trusted-key-dir", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = verify(args.envelope, args.trusted_key_dir, args.schema)
    except VerificationError as error:
        print(f"manifest verification failed: {error}", file=sys.stderr)
        return 1
    artifact = payload["artifact"]
    print(
        "manifest verified: "
        f"chain_id={payload['chain_id']} version={payload.get('version')} "
        f"archive_node_equivalent={str(payload['archive_node_equivalent']).lower()} "
        f"artifact={artifact['name']} sha256={artifact['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
