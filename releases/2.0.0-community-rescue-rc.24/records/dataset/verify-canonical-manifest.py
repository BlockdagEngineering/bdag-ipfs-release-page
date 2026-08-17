#!/usr/bin/env python3
"""Create and verify signed BlockDAG data and release envelopes."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping


LEGACY_DATA_MANIFEST_SCHEMA = "bdag.canonical-data-manifest.v2"
DATA_MANIFEST_SCHEMA = "bdag.canonical-data-manifest.v3"
LEGACY_RELEASE_LOCK_SCHEMA = "bdag.release-lock.v1"
PREVIOUS_RELEASE_LOCK_SCHEMA = "bdag.release-lock.v2"
RELEASE_LOCK_SCHEMA = "bdag.release-lock.v3"
SIGNATURE_ALGORITHM = "ed25519"
EXPECTED_NETWORK = "mainnet"
EXPECTED_CHAIN_ID = 1404
EXPECTED_GENESIS_HASH = "0x3fb19ea409ac7399ad7b988b88e0d436722c967137e51e834ccefd7611a592ef"
EXPECTED_GENESIS_STATE_ROOT = "0x564aeb23c21b395f94839991240f0665fdf6b083cad3a41ac6412fa2180ac76a"
DATASET_PATHS = ("mainnet/BdagChain", "mainnet/bdageth/chaindata")
VERIFIED_TIP_DATASET_CLASS = "verified-tip-state"
PRODUCER_PRUNED_DATASET_CLASS = "producer-pruned-state"
PRODUCER_PRUNED_DERIVATION_SCHEMA = "bdag.producer-pruned-derivation.v1"
DERIVATION_EVIDENCE_DIRECTORY = "DERIVATION-EVIDENCE"
DERIVATION_EVIDENCE_ROLES = (
    "parent_manifest",
    "pre_prune_state_traversal_log",
    "prune_log",
    "post_prune_state_traversal_log",
    "cold_portable_validation_log",
)
# Candidate A tip bound to native order 14,239,720. This is the stateful
# checkpoint shipped by the community rescue dataset, not an archive-state
# promise for older blocks.
GOVERNED_CHECKPOINT_NUMBER = 13_863_411
GOVERNED_CHECKPOINT_HASH = "0xbf9a0ccd88fa03eb3d7cbc0052b258b9b21132ae4ba3f0276f6e482a9d601738"
GOVERNED_CHECKPOINT_STATE_ROOT = "0xad51cb1e1357172afc5ca5dcebc477ff818661b64b8b5b64cdf9cd54a8450c00"
# The core checks this earlier point as a lineage guard. It intentionally does
# not need to be the dataset's restorable state checkpoint above.
CANONICAL_EVM_CHECKPOINT_NUMBER = 13_700_000
CANONICAL_EVM_CHECKPOINT_HASH = "0xf001ca3751618d87d92e21b65d60cd2cc243ceb6d1e4f152bed92016947e994b"
CANONICAL_EVM_CHECKPOINT_STATE_ROOT = "0x9ba2c71154656c151fdeb048c0ef3eed1aba91f6dde495f983e8367a6a7478f3"
GOVERNED_PARENT_DATASET_VERSION = "v24"
GOVERNED_PARENT_ARTIFACT_SHA256 = "5c48007675f47c21e3c8e67884da19087b0eb075f9e1676a1a863d30a10801c7"
GOVERNED_PARENT_ARTIFACT_SIZE_BYTES = 160_903_731_459
GOVERNED_PARENT_UNPACKED_SIZE_BYTES = 250_559_217_446
GOVERNED_PARENT_BASE_MANIFEST_SHA256 = "669e2b23c11cc73052d7b0f8aa3fa69b1e9740e08f3ef4343d183a39c7c8731b"
GOVERNED_PARENT_RELEASE_VERSION = "stack-v2.0.0-rc.5"
GOVERNED_PARENT_RELEASE_SEQUENCE = 5
GOVERNED_PARENT_RELEASE_LOCK_SHA256 = "3e427f1339e7902b115979cfbc84c7b8ad31730248072b4519068d4cbc8ff344"
GOVERNED_PARENT_CORE_SOURCE_REVISION = "4ece7b67f65933ced259d8e09e859d88d3e4e560"
GOVERNED_PARENT_STACK_SOURCE_REVISION = "dca031d16bc54f634f1ba628336814336c0a1508"
GOVERNED_PARENT_RECOVERY_BINARY_SHA256 = (
    "44d288b019ba22ee3bd7fae78505ef3e88efc7e2f48967d07bf9ab0b0369895c",
    "68e1c5df199637104b730494f2319695dd9a93bee2cbe58602ebd7e444840622",
)
GOVERNED_PARENT_DATASET_BUILDER_SHA256 = "9266f324a6f2ccb54c66495103352276b1f83324b428ce1f1d14c6f6d44ac5a9"
REVIEWED_BOOTSTRAP_PEERS = (
    "/ip4/52.8.54.60/tcp/8150/p2p/16Uiu2HAkzUWr4YUM7mAhLdCVZgFoV9He6aQzKTyWWrJ7SWQKRTN7",
    "/ip4/13.57.132.47/tcp/8150/p2p/16Uiu2HAmDynYpWjWmgVGf9qVWvDdLnJ3ybVgDmFexizR4zMereus",
    "/ip4/54.151.18.92/tcp/8150/p2p/16Uiu2HAmVm91o1JXS2C7P6uTVuVX5empgnRtzuK4UaC8fHmePbKP",
)
KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
VERSION_RE = re.compile(r"^v[1-9][0-9]*$")
HASH_RE = re.compile(r"^0x[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
EVIDENCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")


class ManifestError(RuntimeError):
    """Raised when a signed envelope is malformed or cannot be authenticated."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Mapping[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(mode)
    os.replace(temporary, path)
    try:
        descriptor = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _run_openssl(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["openssl", *args],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ManifestError(f"openssl is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ManifestError(f"openssl {' '.join(args[:2])} failed: {detail or 'unknown error'}")
    return result.stdout


def public_key_der(path: Path, *, private: bool = False) -> bytes:
    args = ["pkey", "-in", str(path)]
    if not private:
        args.append("-pubin")
    args.extend(("-pubout", "-outform", "DER"))
    return _run_openssl(args)


def public_key_sha256(path: Path, *, private: bool = False) -> str:
    return hashlib.sha256(public_key_der(path, private=private)).hexdigest()


def _sign_bytes(data: bytes, private_key: Path) -> bytes:
    with tempfile.NamedTemporaryFile(prefix="bdag-signed-", delete=False) as payload_file:
        payload_file.write(data)
        payload_path = Path(payload_file.name)
    try:
        return _run_openssl(
            ["pkeyutl", "-sign", "-rawin", "-inkey", str(private_key), "-in", str(payload_path)]
        )
    finally:
        payload_path.unlink(missing_ok=True)


def _verify_bytes(data: bytes, signature: bytes, public_key: Path) -> None:
    with tempfile.NamedTemporaryFile(prefix="bdag-signed-", delete=False) as payload_file:
        payload_file.write(data)
        payload_path = Path(payload_file.name)
    with tempfile.NamedTemporaryFile(prefix="bdag-signature-", delete=False) as signature_file:
        signature_file.write(signature)
        signature_path = Path(signature_file.name)
    try:
        _run_openssl(
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


def sign_envelope(payload: Mapping[str, Any], private_key: Path, key_id: str, *, schema: str) -> dict[str, Any]:
    if not KEY_ID_RE.fullmatch(key_id):
        raise ManifestError("signing key ID is invalid")
    if not private_key.is_file():
        raise ManifestError(f"signing private key is unavailable: {private_key}")
    signed = dict(payload)
    signature = _sign_bytes(canonical_json(signed), private_key)
    return {
        "schema": schema,
        "signed": signed,
        "signature": {
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id": key_id,
            "public_key_sha256": public_key_sha256(private_key, private=True),
            "value": base64.b64encode(signature).decode("ascii"),
        },
    }


def trusted_key_map(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise ManifestError(f"trusted key directory is unavailable: {directory}")
    keys: dict[str, Path] = {}
    for candidate in sorted(directory.iterdir()):
        if not candidate.is_file() or candidate.suffix.lower() not in {".pem", ".pub"}:
            continue
        key_id = candidate.stem
        if not KEY_ID_RE.fullmatch(key_id):
            raise ManifestError(f"trusted key filename has an invalid key ID: {candidate.name}")
        keys[key_id] = candidate
    if not keys:
        raise ManifestError(f"trusted key directory contains no PEM public keys: {directory}")
    return keys


def verify_envelope(
    envelope: Any,
    trusted_keys: Mapping[str, Path],
    *,
    expected_schema: str,
    validator: Callable[[Any], list[str]] | None = None,
) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise ManifestError("signed envelope is not an object")
    if envelope.get("schema") != expected_schema:
        raise ManifestError(f"signed envelope schema must be {expected_schema}")
    signed = envelope.get("signed")
    signature = envelope.get("signature")
    if not isinstance(signed, dict) or not isinstance(signature, dict):
        raise ManifestError("signed envelope must contain signed and signature objects")
    algorithm = str(signature.get("algorithm") or "").lower()
    key_id = str(signature.get("key_id") or "")
    if algorithm != SIGNATURE_ALGORITHM:
        raise ManifestError(f"signature algorithm must be {SIGNATURE_ALGORITHM}")
    if not KEY_ID_RE.fullmatch(key_id):
        raise ManifestError("signature key ID is invalid")
    public_key = trusted_keys.get(key_id)
    if public_key is None:
        raise ManifestError(f"signature key ID is not trusted: {key_id}")
    expected_fingerprint = str(signature.get("public_key_sha256") or "").lower()
    actual_fingerprint = public_key_sha256(public_key)
    if expected_fingerprint != actual_fingerprint:
        raise ManifestError("signature public-key fingerprint does not match the trusted key")
    try:
        decoded_signature = base64.b64decode(str(signature.get("value") or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ManifestError("signature value is not valid base64") from exc
    if not decoded_signature:
        raise ManifestError("signature value is empty")
    _verify_bytes(canonical_json(signed), decoded_signature, public_key)
    if validator is not None:
        errors = validator(signed)
        if errors:
            raise ManifestError("manifest validation failed: " + "; ".join(errors))
    return dict(signed)


def load_and_verify(
    path: Path,
    trusted_keys: Mapping[str, Path],
    *,
    expected_schema: str,
    validator: Callable[[Any], list[str]] | None = None,
) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"signed envelope is unreadable: {path}: {exc}") from exc
    return verify_envelope(envelope, trusted_keys, expected_schema=expected_schema, validator=validator)


def _valid_boundary(value: Any, *, prefix: str, number_key: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    number = value.get(number_key)
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        errors.append(f"{prefix}.{number_key} must be a positive integer")
    for key in ("hash", "state_root"):
        if not HASH_RE.fullmatch(str(value.get(key) or "").lower()):
            errors.append(f"{prefix}.{key} must be a 32-byte 0x hash")
    return errors


def _valid_nonnegative_boundary(value: Any, *, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    if set(value) != {"number", "hash", "state_root"}:
        errors.append(f"{prefix} has an invalid field set")
    number = value.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 0:
        errors.append(f"{prefix}.number must be a non-negative integer")
    for key in ("hash", "state_root"):
        if not HASH_RE.fullmatch(str(value.get(key) or "").lower()):
            errors.append(f"{prefix}.{key} must be a 32-byte 0x hash")
    return errors


def _valid_evidence_file(value: Any, *, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    if set(value) != {"name", "sha256", "size_bytes"}:
        errors.append(f"{prefix} has an invalid field set")
    name = str(value.get("name") or "")
    if not EVIDENCE_NAME_RE.fullmatch(name) or Path(name).name != name:
        errors.append(f"{prefix}.name must be a safe basename")
    if not SHA256_RE.fullmatch(str(value.get("sha256") or "").lower()):
        errors.append(f"{prefix}.sha256 must be a SHA-256 digest")
    size = value.get("size_bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        errors.append(f"{prefix}.size_bytes must be a positive integer")
    return errors


def validate_producer_pruned_derivation(payload: Mapping[str, Any]) -> list[str]:
    derivation = payload.get("derivation")
    if not isinstance(derivation, dict):
        return ["derivation must be an object for producer-pruned-state"]
    errors: list[str] = []
    required_fields = {
        "schema",
        "parent",
        "retained_state_roots",
        "sizes",
        "pruning_tool",
        "evidence_files",
    }
    if set(derivation) != required_fields:
        errors.append("derivation has an invalid field set")
    if derivation.get("schema") != PRODUCER_PRUNED_DERIVATION_SCHEMA:
        errors.append(f"derivation.schema must be {PRODUCER_PRUNED_DERIVATION_SCHEMA}")

    parent = derivation.get("parent")
    if not isinstance(parent, dict):
        errors.append("derivation.parent must be an object")
    else:
        if set(parent) != {
            "version",
            "artifact_sha256",
            "artifact_size_bytes",
            "manifest_schema",
            "manifest_sha256",
            "release_version",
            "release_sequence",
            "release_lock_sha256",
        }:
            errors.append("derivation.parent has an invalid field set")
        if not VERSION_RE.fullmatch(str(parent.get("version") or "")):
            errors.append("derivation.parent.version must match vN")
        parent_version = str(parent.get("version") or "")
        child_version = str(payload.get("version") or "")
        if VERSION_RE.fullmatch(parent_version) and VERSION_RE.fullmatch(child_version):
            if int(child_version[1:]) <= int(parent_version[1:]):
                errors.append("producer-pruned manifest version must be newer than its parent")
        for key in ("artifact_sha256", "manifest_sha256", "release_lock_sha256"):
            if not SHA256_RE.fullmatch(str(parent.get(key) or "").lower()):
                errors.append(f"derivation.parent.{key} must be a SHA-256 digest")
        if str(parent.get("manifest_sha256") or "").lower() == GOVERNED_PARENT_BASE_MANIFEST_SHA256:
            errors.append("derivation parent must be the RC5-bound manifest, not the base manifest")
        if parent.get("manifest_schema") != LEGACY_DATA_MANIFEST_SCHEMA:
            errors.append(f"derivation.parent.manifest_schema must be {LEGACY_DATA_MANIFEST_SCHEMA}")
        if not str(parent.get("release_version") or ""):
            errors.append("derivation.parent.release_version is required")
        release_sequence = parent.get("release_sequence")
        if isinstance(release_sequence, bool) or not isinstance(release_sequence, int) or release_sequence <= 0:
            errors.append("derivation.parent.release_sequence must be a positive integer")
        parent_size = parent.get("artifact_size_bytes")
        if isinstance(parent_size, bool) or not isinstance(parent_size, int) or parent_size <= 0:
            errors.append("derivation.parent.artifact_size_bytes must be a positive integer")

    retained = derivation.get("retained_state_roots")
    if not isinstance(retained, dict) or set(retained) != {"genesis", "checkpoint", "head"}:
        errors.append("derivation.retained_state_roots must contain exactly genesis, checkpoint, and head")
    else:
        for role in ("genesis", "checkpoint", "head"):
            errors.extend(
                _valid_nonnegative_boundary(
                    retained.get(role),
                    prefix=f"derivation.retained_state_roots.{role}",
                )
            )
        expected_roots = {
            "genesis": {
                "number": 0,
                "hash": payload.get("genesis_hash"),
                "state_root": payload.get("genesis_state_root"),
            },
            "checkpoint": payload.get("fixed_checkpoint"),
            "head": payload.get("evm"),
        }
        for role, expected in expected_roots.items():
            if retained.get(role) != expected:
                errors.append(f"derivation retained {role} root differs from the canonical manifest boundary")

    sizes = derivation.get("sizes")
    if not isinstance(sizes, dict):
        errors.append("derivation.sizes must be an object")
    else:
        if set(sizes) != {"before_data_bytes", "after_data_bytes", "evidence_bytes"}:
            errors.append("derivation.sizes has an invalid field set")
        for key in ("before_data_bytes", "after_data_bytes", "evidence_bytes"):
            value = sizes.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                errors.append(f"derivation.sizes.{key} must be a positive integer")
        before = sizes.get("before_data_bytes")
        after = sizes.get("after_data_bytes")
        evidence = sizes.get("evidence_bytes")
        if (
            isinstance(before, int)
            and not isinstance(before, bool)
            and isinstance(after, int)
            and not isinstance(after, bool)
        ):
            if after >= before:
                errors.append("derivation after_data_bytes must be smaller than before_data_bytes")
        artifact = payload.get("artifact")
        unpacked = artifact.get("unpacked_size_bytes") if isinstance(artifact, dict) else None
        if all(isinstance(value, int) and not isinstance(value, bool) for value in (after, evidence, unpacked)):
            if after + evidence != unpacked:
                errors.append(
                    "artifact.unpacked_size_bytes must equal derivation after_data_bytes plus evidence_bytes"
                )

    tool = derivation.get("pruning_tool")
    if not isinstance(tool, dict):
        errors.append("derivation.pruning_tool must be an object")
    else:
        if set(tool) != {"name", "command", "retention_mode", "binary_sha256", "core_source_revision"}:
            errors.append("derivation.pruning_tool has an invalid field set")
        if tool.get("name") != "blockdag-node":
            errors.append("derivation.pruning_tool.name must be blockdag-node")
        if tool.get("command") != "snapshot prune-state":
            errors.append("derivation.pruning_tool.command must be snapshot prune-state")
        if tool.get("retention_mode") != "genesis-checkpoint-head":
            errors.append(
                "derivation.pruning_tool.retention_mode must be genesis-checkpoint-head"
            )
        if not SHA256_RE.fullmatch(str(tool.get("binary_sha256") or "").lower()):
            errors.append("derivation.pruning_tool.binary_sha256 must be a SHA-256 digest")
        if not HEX40_RE.fullmatch(str(tool.get("core_source_revision") or "").lower()):
            errors.append("derivation.pruning_tool.core_source_revision must be a full Git revision")

    evidence_files = derivation.get("evidence_files")
    if not isinstance(evidence_files, dict) or set(evidence_files) != set(DERIVATION_EVIDENCE_ROLES):
        errors.append(
            "derivation.evidence_files must contain exactly " + ", ".join(DERIVATION_EVIDENCE_ROLES)
        )
    else:
        names: list[str] = []
        evidence_size = 0
        for role in DERIVATION_EVIDENCE_ROLES:
            record = evidence_files.get(role)
            errors.extend(_valid_evidence_file(record, prefix=f"derivation.evidence_files.{role}"))
            if isinstance(record, dict):
                names.append(str(record.get("name") or ""))
                size = record.get("size_bytes")
                if isinstance(size, int) and not isinstance(size, bool):
                    evidence_size += size
        if len(set(names)) != len(names):
            errors.append("derivation evidence filenames must be unique")
        if isinstance(parent, dict):
            parent_record = evidence_files.get("parent_manifest")
            if isinstance(parent_record, dict) and str(parent_record.get("sha256") or "").lower() != str(
                parent.get("manifest_sha256") or ""
            ).lower():
                errors.append("derivation parent manifest digest differs from its evidence file")
        if isinstance(sizes, dict) and sizes.get("evidence_bytes") != evidence_size:
            errors.append("derivation.sizes.evidence_bytes differs from the evidence file sizes")
    return errors


def validate_data_manifest(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["signed manifest is not an object"]
    errors: list[str] = []
    if not VERSION_RE.fullmatch(str(payload.get("version") or "")):
        errors.append("version must match vN")
    if payload.get("network") != EXPECTED_NETWORK:
        errors.append(f"network must be {EXPECTED_NETWORK}")
    if payload.get("chain_id") != EXPECTED_CHAIN_ID:
        errors.append(f"chain_id must be {EXPECTED_CHAIN_ID}")
    if str(payload.get("genesis_hash") or "").lower() != EXPECTED_GENESIS_HASH:
        errors.append("genesis_hash does not match mainnet")
    if str(payload.get("genesis_state_root") or "").lower() != EXPECTED_GENESIS_STATE_ROOT:
        errors.append("genesis_state_root does not match mainnet")
    dataset_class = payload.get("dataset_class")
    if dataset_class not in {VERIFIED_TIP_DATASET_CLASS, PRODUCER_PRUNED_DATASET_CLASS}:
        errors.append(
            f"dataset_class must be {VERIFIED_TIP_DATASET_CLASS} or {PRODUCER_PRUNED_DATASET_CLASS}"
        )
    if payload.get("archive_node_equivalent") is not False:
        errors.append("archive_node_equivalent must be false")
    paths = payload.get("paths")
    if paths != list(DATASET_PATHS):
        errors.append(f"paths must be exactly {list(DATASET_PATHS)}")
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        errors.append("artifact must be an object")
    else:
        if not SHA256_RE.fullmatch(str(artifact.get("sha256") or "").lower()):
            errors.append("artifact.sha256 must be a SHA-256 digest")
        for key in ("size_bytes", "unpacked_size_bytes"):
            value = artifact.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                errors.append(f"artifact.{key} must be a positive integer")
        if artifact.get("format") not in {"tar", "tar.gz", "tar.zst"}:
            errors.append("artifact.format is unsupported")
        name = str(artifact.get("name") or "")
        if not name or Path(name).name != name:
            errors.append("artifact.name must be a basename")
    errors.extend(_valid_boundary(payload.get("native"), prefix="native", number_key="order"))
    errors.extend(_valid_boundary(payload.get("evm"), prefix="evm", number_key="number"))
    replay_anchor = payload.get("replay_anchor")
    if replay_anchor is not None:
        errors.extend(_valid_boundary(replay_anchor, prefix="replay_anchor", number_key="number"))
    fixed_checkpoint = payload.get("fixed_checkpoint")
    if fixed_checkpoint is None:
        errors.append("fixed_checkpoint is required")
    else:
        errors.extend(_valid_boundary(fixed_checkpoint, prefix="fixed_checkpoint", number_key="number"))
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        build_tools = provenance.get("build_tools")
        if not isinstance(build_tools, dict):
            errors.append("provenance.build_tools must be an object")
        else:
            if not str(build_tools.get("recovery_binary") or ""):
                errors.append("provenance.build_tools.recovery_binary is required")
            for key in (
                "recovery_binary_sha256",
                "dataset_builder_sha256",
                "validation_spec_sha256",
                "release_lock_sha256",
            ):
                if not SHA256_RE.fullmatch(str(build_tools.get(key) or "").lower()):
                    errors.append(f"provenance.build_tools.{key} must be a SHA-256 digest")
            for key in ("core_source_revision", "stack_source_revision"):
                if not HEX40_RE.fullmatch(str(build_tools.get(key) or "").lower()):
                    errors.append(f"provenance.build_tools.{key} must be a full Git revision")
    if dataset_class == PRODUCER_PRUNED_DATASET_CLASS:
        errors.extend(validate_producer_pruned_derivation(payload))
    elif "derivation" in payload:
        errors.append("derivation is only valid for producer-pruned-state")
    return errors


def validate_legacy_data_manifest(payload: Any) -> list[str]:
    errors = validate_data_manifest(payload)
    if isinstance(payload, dict):
        if payload.get("dataset_class") != VERIFIED_TIP_DATASET_CLASS:
            errors.append(f"legacy manifest dataset_class must be {VERIFIED_TIP_DATASET_CLASS}")
        if "derivation" in payload:
            errors.append("legacy manifest cannot contain derivation evidence")
    return errors


def legacy_governed_dataset_policy() -> dict[str, Any]:
    return {
        "network": EXPECTED_NETWORK,
        "chain_id": EXPECTED_CHAIN_ID,
        "genesis_hash": EXPECTED_GENESIS_HASH,
        "genesis_state_root": EXPECTED_GENESIS_STATE_ROOT,
        "required_checkpoint": {
            "number": GOVERNED_CHECKPOINT_NUMBER,
            "hash": GOVERNED_CHECKPOINT_HASH,
            "state_root": GOVERNED_CHECKPOINT_STATE_ROOT,
            "require_state": True,
            "require_receipts": True,
        },
        "canonical_evm_checkpoint": {
            "number": CANONICAL_EVM_CHECKPOINT_NUMBER,
            "hash": CANONICAL_EVM_CHECKPOINT_HASH,
            "state_root": CANONICAL_EVM_CHECKPOINT_STATE_ROOT,
        },
        "provenance_policy": {
            "release_match_required": False,
        },
        "bootstrap_peers": list(REVIEWED_BOOTSTRAP_PEERS),
        "producer_activation": {
            "minimum_fresh_consensus_peers": 2,
            "maximum_peer_lead_blocks": 0,
            "maximum_remaining_blocks": 0,
            "require_chain_current": True,
            "require_p2p_current": True,
            "require_p2p_mining_fresh": True,
        },
    }


def require_parent_bound_manifest_sha256(value: str) -> str:
    digest = value.strip().lower()
    if not SHA256_RE.fullmatch(digest):
        raise ManifestError("RC5-bound parent manifest SHA-256 is required for producer-pruned policy")
    if digest == GOVERNED_PARENT_BASE_MANIFEST_SHA256:
        raise ManifestError("the base v24 manifest SHA-256 cannot authorize producer-pruned policy")
    return digest


def producer_pruned_class_policy(parent_bound_manifest_sha256: str) -> dict[str, Any]:
    parent_manifest_sha256 = require_parent_bound_manifest_sha256(parent_bound_manifest_sha256)
    return {
        "derivation_required": True,
        "archive_mode_allowed": False,
        "derivation_schema": PRODUCER_PRUNED_DERIVATION_SCHEMA,
        "parent_version": GOVERNED_PARENT_DATASET_VERSION,
        "parent_artifact_sha256": GOVERNED_PARENT_ARTIFACT_SHA256,
        "parent_artifact_size_bytes": GOVERNED_PARENT_ARTIFACT_SIZE_BYTES,
        "parent_unpacked_size_bytes": GOVERNED_PARENT_UNPACKED_SIZE_BYTES,
        "parent_manifest_schema": LEGACY_DATA_MANIFEST_SCHEMA,
        "parent_manifest_sha256": parent_manifest_sha256,
        "parent_base_manifest_sha256": GOVERNED_PARENT_BASE_MANIFEST_SHA256,
        "parent_release": {
            "version": GOVERNED_PARENT_RELEASE_VERSION,
            "sequence": GOVERNED_PARENT_RELEASE_SEQUENCE,
            "release_lock_sha256": GOVERNED_PARENT_RELEASE_LOCK_SHA256,
            "core_source_revision": GOVERNED_PARENT_CORE_SOURCE_REVISION,
            "stack_source_revision": GOVERNED_PARENT_STACK_SOURCE_REVISION,
            "recovery_binary_sha256": list(GOVERNED_PARENT_RECOVERY_BINARY_SHA256),
            "dataset_builder_sha256": GOVERNED_PARENT_DATASET_BUILDER_SHA256,
        },
        "retained_state_roots": ["genesis", "checkpoint", "head"],
    }


def governed_dataset_policy(parent_bound_manifest_sha256: str | None = None) -> dict[str, Any]:
    if parent_bound_manifest_sha256 is None:
        return legacy_governed_dataset_policy()
    policy = legacy_governed_dataset_policy()
    policy["dataset_class_policy"] = {
        VERIFIED_TIP_DATASET_CLASS: {
            "derivation_required": False,
            "archive_mode_allowed": True,
        },
        PRODUCER_PRUNED_DATASET_CLASS: producer_pruned_class_policy(
            parent_bound_manifest_sha256
        ),
    }
    return policy


def previous_legacy_governed_dataset_policy() -> dict[str, Any]:
    policy = legacy_governed_dataset_policy()
    del policy["canonical_evm_checkpoint"]
    del policy["provenance_policy"]
    return policy


def previous_governed_dataset_policy(
    parent_bound_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    policy = governed_dataset_policy(parent_bound_manifest_sha256)
    del policy["canonical_evm_checkpoint"]
    del policy["provenance_policy"]
    return policy


def v1_release_governed_dataset_policy() -> dict[str, Any]:
    policy = previous_legacy_governed_dataset_policy()
    policy["required_checkpoint"] = {
        "number": CANONICAL_EVM_CHECKPOINT_NUMBER,
        "hash": CANONICAL_EVM_CHECKPOINT_HASH,
        "state_root": CANONICAL_EVM_CHECKPOINT_STATE_ROOT,
        "require_state": True,
        "require_receipts": True,
    }
    return policy


def validate_v1_release_governed_dataset_policy(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["dataset policy differs from the v1 governed mainnet checkpoint policy"]
    unsigned = {key: value for key, value in policy.items() if key != "release_binding"}
    if unsigned != v1_release_governed_dataset_policy():
        return ["dataset policy differs from the v1 governed mainnet checkpoint policy"]
    migrated = dict(policy)
    migrated["required_checkpoint"] = legacy_governed_dataset_policy()["required_checkpoint"]
    migrated["canonical_evm_checkpoint"] = {
        "number": CANONICAL_EVM_CHECKPOINT_NUMBER,
        "hash": CANONICAL_EVM_CHECKPOINT_HASH,
        "state_root": CANONICAL_EVM_CHECKPOINT_STATE_ROOT,
    }
    migrated["provenance_policy"] = {
        "release_match_required": False,
    }
    return validate_governed_dataset_policy(migrated)


def policy_supports_producer_pruned(policy: Mapping[str, Any]) -> bool:
    if not isinstance(policy, Mapping):
        return False
    unsigned = {key: value for key, value in policy.items() if key != "release_binding"}
    class_policy = unsigned.get("dataset_class_policy")
    if not isinstance(class_policy, dict):
        return False
    producer_policy = class_policy.get(PRODUCER_PRUNED_DATASET_CLASS)
    if not isinstance(producer_policy, dict):
        return False
    parent_manifest_sha256 = str(producer_policy.get("parent_manifest_sha256") or "")
    try:
        expected = governed_dataset_policy(parent_manifest_sha256)
    except ManifestError:
        return False
    return unsigned == expected


def previous_policy_supports_producer_pruned(policy: Mapping[str, Any]) -> bool:
    if not isinstance(policy, Mapping):
        return False
    unsigned = {key: value for key, value in policy.items() if key != "release_binding"}
    class_policy = unsigned.get("dataset_class_policy")
    if not isinstance(class_policy, dict):
        return False
    producer_policy = class_policy.get(PRODUCER_PRUNED_DATASET_CLASS)
    if not isinstance(producer_policy, dict):
        return False
    parent_manifest_sha256 = str(producer_policy.get("parent_manifest_sha256") or "")
    try:
        expected = previous_governed_dataset_policy(parent_manifest_sha256)
    except ManifestError:
        return False
    return unsigned == expected


def validate_previous_governed_dataset_policy(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["dataset policy differs from the previous governed mainnet checkpoint policy"]
    unsigned = {key: value for key, value in policy.items() if key != "release_binding"}
    if (
        unsigned != previous_legacy_governed_dataset_policy()
        and not previous_policy_supports_producer_pruned(unsigned)
    ):
        return ["dataset policy differs from the previous governed mainnet checkpoint policy"]
    migrated = dict(policy)
    migrated["canonical_evm_checkpoint"] = {
        "number": CANONICAL_EVM_CHECKPOINT_NUMBER,
        "hash": CANONICAL_EVM_CHECKPOINT_HASH,
        "state_root": CANONICAL_EVM_CHECKPOINT_STATE_ROOT,
    }
    migrated["provenance_policy"] = {
        "release_match_required": False,
    }
    return validate_governed_dataset_policy(migrated)


def validate_governed_dataset_policy(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["dataset policy differs from the governed mainnet checkpoint policy"]
    unsigned = {key: value for key, value in policy.items() if key != "release_binding"}
    legacy = legacy_governed_dataset_policy()
    is_governed = policy_supports_producer_pruned(unsigned)
    if unsigned != legacy and not is_governed:
        return ["dataset policy differs from the governed mainnet checkpoint policy"]
    binding = policy.get("release_binding")
    if binding is not None:
        if not isinstance(binding, dict):
            return ["dataset release binding must be an object"]
        required = {
            "release_version",
            "release_lock_sha256",
            "core_source_revision",
            "stack_source_revision",
            "recovery_binary_sha256",
            "dataset_builder_sha256",
        }
        if is_governed:
            required.add("producer_dataset_builder_sha256")
        if set(binding) != required:
            return ["dataset release binding has an invalid field set"]
        if not str(binding.get("release_version") or ""):
            return ["dataset release binding version is required"]
        digest_keys = ["release_lock_sha256", "dataset_builder_sha256"]
        if is_governed:
            digest_keys.append("producer_dataset_builder_sha256")
        for key in digest_keys:
            if not SHA256_RE.fullmatch(str(binding.get(key) or "").lower()):
                return [f"dataset release binding {key} is invalid"]
        for key in ("core_source_revision", "stack_source_revision"):
            if not HEX40_RE.fullmatch(str(binding.get(key) or "").lower()):
                return [f"dataset release binding {key} is invalid"]
        recovery_digests = binding.get("recovery_binary_sha256")
        if (
            not isinstance(recovery_digests, list)
            or not recovery_digests
            or any(not SHA256_RE.fullmatch(str(item).lower()) for item in recovery_digests)
        ):
            return ["dataset release binding recovery binary digests are invalid"]
    return []


def validate_manifest_against_policy(payload: Mapping[str, Any], policy: Mapping[str, Any]) -> list[str]:
    errors = validate_governed_dataset_policy(policy)
    if errors:
        return errors
    for key in ("network", "chain_id", "genesis_hash", "genesis_state_root"):
        if payload.get(key) != policy.get(key):
            errors.append(f"manifest {key} differs from signed release policy")
    fixed = payload.get("fixed_checkpoint")
    required = policy.get("required_checkpoint")
    if not isinstance(fixed, dict) or not isinstance(required, dict):
        errors.append("manifest or release policy checkpoint is missing")
    else:
        for key in ("number", "hash", "state_root"):
            if fixed.get(key) != required.get(key):
                errors.append(f"manifest fixed_checkpoint.{key} differs from signed release policy")
    dataset_class = payload.get("dataset_class")
    class_policy = policy.get("dataset_class_policy")
    if class_policy is None:
        if dataset_class != VERIFIED_TIP_DATASET_CLASS:
            errors.append("manifest dataset_class is not authorized by the signed release policy")
        selected_class_policy: Mapping[str, Any] = {
            "derivation_required": False,
            "archive_mode_allowed": True,
        }
    elif isinstance(class_policy, dict) and isinstance(class_policy.get(dataset_class), dict):
        selected_class_policy = class_policy[dataset_class]
    else:
        selected_class_policy = {}
        errors.append("manifest dataset_class is not authorized by the signed release policy")
    derivation = payload.get("derivation")
    if selected_class_policy.get("derivation_required") is True and not isinstance(derivation, dict):
        errors.append("manifest derivation evidence is required by the signed release policy")
    if selected_class_policy.get("derivation_required") is False and "derivation" in payload:
        errors.append("manifest derivation evidence is forbidden by the signed release policy")
    if dataset_class == PRODUCER_PRUNED_DATASET_CLASS and isinstance(derivation, dict):
        parent = derivation.get("parent") if isinstance(derivation.get("parent"), dict) else {}
        sizes = derivation.get("sizes") if isinstance(derivation.get("sizes"), dict) else {}
        retained = (
            derivation.get("retained_state_roots")
            if isinstance(derivation.get("retained_state_roots"), dict)
            else {}
        )
        expected_parent = {
            "version": selected_class_policy.get("parent_version"),
            "artifact_sha256": selected_class_policy.get("parent_artifact_sha256"),
            "artifact_size_bytes": selected_class_policy.get("parent_artifact_size_bytes"),
            "manifest_schema": selected_class_policy.get("parent_manifest_schema"),
            "manifest_sha256": selected_class_policy.get("parent_manifest_sha256"),
        }
        parent_release = selected_class_policy.get("parent_release")
        if isinstance(parent_release, dict):
            expected_parent.update(
                {
                    "release_version": parent_release.get("version"),
                    "release_sequence": parent_release.get("sequence"),
                    "release_lock_sha256": parent_release.get("release_lock_sha256"),
                }
            )
        for key, expected in expected_parent.items():
            if parent.get(key) != expected:
                errors.append(f"manifest derivation parent {key} differs from signed release policy")
        if derivation.get("schema") != selected_class_policy.get("derivation_schema"):
            errors.append("manifest derivation schema differs from signed release policy")
        if sizes.get("before_data_bytes") != selected_class_policy.get("parent_unpacked_size_bytes"):
            errors.append("manifest derivation before_data_bytes differs from signed release policy")
        if sorted(retained) != sorted(selected_class_policy.get("retained_state_roots") or []):
            errors.append("manifest derivation retained roots differ from signed release policy")
    provenance = payload.get("provenance")
    build_tools = provenance.get("build_tools") if isinstance(provenance, dict) else None
    if dataset_class == PRODUCER_PRUNED_DATASET_CLASS and isinstance(derivation, dict):
        pruning_tool = (
            derivation.get("pruning_tool")
            if isinstance(derivation.get("pruning_tool"), dict)
            else {}
        )
        if not isinstance(build_tools, dict):
            errors.append("manifest build-tool provenance is missing")
        else:
            if str(pruning_tool.get("binary_sha256") or "").lower() != str(
                build_tools.get("recovery_binary_sha256") or ""
            ).lower():
                errors.append("manifest pruning binary differs from build-tool provenance")
            if str(pruning_tool.get("core_source_revision") or "").lower() != str(
                build_tools.get("core_source_revision") or ""
            ).lower():
                errors.append("manifest pruning core revision differs from build-tool provenance")
    return errors


def validate_manifest_install_mode(
    payload: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    archive_mode: bool,
) -> list[str]:
    errors = validate_manifest_against_policy(payload, policy)
    if errors:
        return errors
    dataset_class = payload.get("dataset_class")
    class_policy = policy.get("dataset_class_policy")
    archive_allowed = True
    if isinstance(class_policy, dict):
        selected = class_policy.get(dataset_class)
        archive_allowed = isinstance(selected, dict) and selected.get("archive_mode_allowed") is True
    elif dataset_class != VERIFIED_TIP_DATASET_CLASS:
        archive_allowed = False
    if archive_mode and not archive_allowed:
        errors.append(f"archive mode is forbidden for dataset_class {dataset_class}")
    return errors


def validate_parent_manifest_against_policy(
    payload: Mapping[str, Any],
    *,
    envelope_schema: str,
    manifest_sha256: str,
    class_policy: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("dataset_class") != VERIFIED_TIP_DATASET_CLASS:
        errors.append("parent dataset_class must be verified-tip-state")
    if envelope_schema != class_policy.get("parent_manifest_schema"):
        errors.append("parent manifest schema differs from signed policy")
    if manifest_sha256.lower() != str(class_policy.get("parent_manifest_sha256") or "").lower():
        errors.append("parent manifest digest differs from signed policy")
    if payload.get("version") != class_policy.get("parent_version"):
        errors.append("parent version differs from signed policy")
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    artifact_expected = {
        "sha256": class_policy.get("parent_artifact_sha256"),
        "size_bytes": class_policy.get("parent_artifact_size_bytes"),
        "unpacked_size_bytes": class_policy.get("parent_unpacked_size_bytes"),
    }
    for key, expected in artifact_expected.items():
        if artifact.get(key) != expected:
            errors.append(f"parent artifact.{key} differs from signed policy")

    parent_release = class_policy.get("parent_release")
    parent_release = parent_release if isinstance(parent_release, dict) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
    tools = provenance.get("build_tools") if isinstance(provenance.get("build_tools"), dict) else {}
    expected_tools = {
        "release_lock_sha256": parent_release.get("release_lock_sha256"),
        "core_source_revision": parent_release.get("core_source_revision"),
        "stack_source_revision": parent_release.get("stack_source_revision"),
        "dataset_builder_sha256": parent_release.get("dataset_builder_sha256"),
    }
    for key, expected in expected_tools.items():
        if tools.get(key) != expected:
            errors.append(f"parent build_tools.{key} differs from signed policy")
    if tools.get("recovery_binary_sha256") not in parent_release.get("recovery_binary_sha256", []):
        errors.append("parent recovery binary is not authorized by its RC5 release")

    dataset_build = provenance.get("dataset_build")
    dataset_build = dataset_build if isinstance(dataset_build, dict) else {}
    if set(dataset_build) != {"parent_manifest_sha256", "build_tools"}:
        errors.append("parent dataset_build provenance has an invalid field set")
    if dataset_build.get("parent_manifest_sha256") != class_policy.get(
        "parent_base_manifest_sha256"
    ):
        errors.append("parent dataset_build provenance does not bind the pinned base manifest")

    qualification = provenance.get("release_qualification")
    qualification = qualification if isinstance(qualification, dict) else {}
    qualification_fields = {
        "schema",
        "release_version",
        "release_lock_sha256",
        "core_source_revision",
        "core_binary_sha256",
        "cold_validation_report_sha256",
        "restore_journal_sha256",
        "prepared_stage_integrity_sha256",
        "target_shutdown_marker",
        "target_shutdown_marker_absent",
    }
    if set(qualification) != qualification_fields:
        errors.append("parent release_qualification provenance has an invalid field set")
    qualification_expected = {
        "schema": "bdag.dataset-release-qualification.v1",
        "release_version": parent_release.get("version"),
        "release_lock_sha256": parent_release.get("release_lock_sha256"),
        "core_source_revision": parent_release.get("core_source_revision"),
        "target_shutdown_marker": "mainnet/shutdown.lock",
        "target_shutdown_marker_absent": True,
    }
    for key, expected in qualification_expected.items():
        if qualification.get(key) != expected:
            errors.append(f"parent release_qualification.{key} differs from signed policy")
    if qualification.get("core_binary_sha256") not in parent_release.get(
        "recovery_binary_sha256", []
    ):
        errors.append("parent qualification binary is not authorized by its RC5 release")
    for key in (
        "cold_validation_report_sha256",
        "restore_journal_sha256",
        "prepared_stage_integrity_sha256",
    ):
        if not SHA256_RE.fullmatch(str(qualification.get(key) or "").lower()):
            errors.append(f"parent release_qualification.{key} is invalid")
    return errors


def verify_data_manifest(path: Path, trusted_keys: Mapping[str, Path]) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"signed envelope is unreadable: {path}: {exc}") from exc
    schema = envelope.get("schema") if isinstance(envelope, dict) else None
    if schema == DATA_MANIFEST_SCHEMA:
        validator = validate_data_manifest
    elif schema == LEGACY_DATA_MANIFEST_SCHEMA:
        validator = validate_legacy_data_manifest
    else:
        raise ManifestError(
            "signed envelope schema must be "
            f"{DATA_MANIFEST_SCHEMA} or compatibility-only {LEGACY_DATA_MANIFEST_SCHEMA}"
        )
    return verify_envelope(
        envelope,
        trusted_keys,
        expected_schema=schema,
        validator=validator,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign = subparsers.add_parser("sign")
    sign.add_argument(
        "--schema",
        required=True,
        choices=(LEGACY_DATA_MANIFEST_SCHEMA, DATA_MANIFEST_SCHEMA, RELEASE_LOCK_SCHEMA),
    )
    sign.add_argument("--payload", required=True, type=Path)
    sign.add_argument("--private-key", required=True, type=Path)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--output", required=True, type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument(
        "--schema",
        required=True,
        choices=(LEGACY_DATA_MANIFEST_SCHEMA, DATA_MANIFEST_SCHEMA, RELEASE_LOCK_SCHEMA),
    )
    verify.add_argument("--envelope", required=True, type=Path)
    verify.add_argument("--trusted-key-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "sign":
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ManifestError("payload must be a JSON object")
            if args.schema in {LEGACY_DATA_MANIFEST_SCHEMA, DATA_MANIFEST_SCHEMA}:
                validator = (
                    validate_legacy_data_manifest
                    if args.schema == LEGACY_DATA_MANIFEST_SCHEMA
                    else validate_data_manifest
                )
                errors = validator(payload)
                if errors:
                    raise ManifestError("manifest validation failed: " + "; ".join(errors))
            envelope = sign_envelope(payload, args.private_key, args.key_id, schema=args.schema)
            atomic_write_json(args.output, envelope)
            print(args.output)
            return 0
        keys = trusted_key_map(args.trusted_key_dir)
        validators = {
            LEGACY_DATA_MANIFEST_SCHEMA: validate_legacy_data_manifest,
            DATA_MANIFEST_SCHEMA: validate_data_manifest,
        }
        validator = validators.get(args.schema)
        verified = load_and_verify(
            args.envelope,
            keys,
            expected_schema=args.schema,
            validator=validator,
        )
        print(json.dumps(verified, indent=2, sort_keys=True))
        return 0
    except (ManifestError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
