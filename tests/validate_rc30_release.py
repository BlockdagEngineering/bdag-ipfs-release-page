#!/usr/bin/env python3
"""Validate the fail-closed RC30 page and its publication input contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "releases" / "2.0.0-community-rescue-rc.30"
MANIFEST_PATH = RELEASE / "release-manifest.json"
RC24 = "releases/2.0.0-community-rescue-rc.24/"

SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHAIN_HASH = re.compile(r"^0x[0-9a-f]{64}$")
CID = re.compile(r"^b[a-z2-7]{20,}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
PRIVATE_IPV4 = re.compile(
    r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}|"
    r"127(?:\.\d{1,3}){3})(?![\d.])"
)
EMAIL_OR_USER_HOST = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PRIVATE_PATH = re.compile(r"(?:/home/|/Users/|/run/media/|[A-Za-z]:\\Users\\)")
PLACEHOLDER_VALUE = re.compile(r"(?:<[^>]+>|\bTODO\b|\bTBD\b|\$\{[^}]+\})")


class ReleaseHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.inline_style_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"] or "")
        if tag == "style":
            self.inline_style_count += 1
        for attribute in ("href", "src"):
            value = attributes.get(attribute)
            if value:
                self.references.append((attribute, value))


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checks = 0

    def check(self, condition: object, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def finish(self, mode: str) -> None:
        if self.errors:
            print(f"RC30 {mode} validation failed:", file=sys.stderr)
            for error in self.errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print(f"RC30 {mode} validation passed ({self.checks} checks).")


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    return all(part not in (".", "..") and bool(SAFE_FILENAME.fullmatch(part)) for part in value.split("/"))


def valid_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.username is None and parsed.password is None


def valid_gateway(value: object) -> bool:
    if not isinstance(value, str) or value.count("{cid}") != 1:
        return False
    if re.search(r"[\\`\"$\r\n]", value):
        return False
    return valid_https(value.replace("{cid}", "cid-placeholder"))


def valid_artifact(artifact: object) -> bool:
    return bool(
        isinstance(artifact, dict)
        and artifact.get("status") == "published"
        and isinstance(artifact.get("filename"), str)
        and SAFE_FILENAME.fullmatch(artifact["filename"])
        and isinstance(artifact.get("cid"), str)
        and CID.fullmatch(artifact["cid"])
        and isinstance(artifact.get("sha256"), str)
        and SHA256.fullmatch(artifact["sha256"])
        and isinstance(artifact.get("size_bytes"), int)
        and artifact["size_bytes"] > 0
    )


def valid_part(part: object) -> bool:
    return bool(
        isinstance(part, dict)
        and isinstance(part.get("filename"), str)
        and SAFE_FILENAME.fullmatch(part["filename"])
        and isinstance(part.get("cid"), str)
        and CID.fullmatch(part["cid"])
        and isinstance(part.get("sha256"), str)
        and SHA256.fullmatch(part["sha256"])
        and isinstance(part.get("size_bytes"), int)
        and part["size_bytes"] > 0
    )


def valid_boundary(value: object, native: bool) -> bool:
    if not isinstance(value, dict):
        return False
    number_key = "order" if native else "number"
    required = {number_key, "hash"} if native else {number_key, "hash", "state_root"}
    if set(value) != required:
        return False
    if not isinstance(value[number_key], int) or value[number_key] < 0:
        return False
    return all(isinstance(value[key], str) and CHAIN_HASH.fullmatch(value[key]) for key in required - {number_key})


def valid_dataset(dataset: object, archive_expected: bool) -> bool:
    if not isinstance(dataset, dict):
        return False
    required_scalars = (
        isinstance(dataset.get("version"), str) and bool(dataset["version"]),
        isinstance(dataset.get("filename"), str) and bool(SAFE_FILENAME.fullmatch(dataset["filename"])),
        isinstance(dataset.get("sha256"), str) and bool(SHA256.fullmatch(dataset["sha256"])),
        isinstance(dataset.get("size_bytes"), int) and dataset["size_bytes"] > 0,
        isinstance(dataset.get("unpacked_size_bytes"), int) and dataset["unpacked_size_bytes"] > 0,
        safe_relative_path(dataset.get("canonical_manifest_path")),
        isinstance(dataset.get("canonical_manifest_sha256"), str)
        and bool(SHA256.fullmatch(dataset["canonical_manifest_sha256"])),
        safe_relative_path(dataset.get("validation_spec_path")),
    )
    if dataset.get("status") != "published" or dataset.get("archive_node_equivalent") is not archive_expected:
        return False
    if not all(required_scalars):
        return False
    if not valid_boundary(dataset.get("native_boundary"), native=True):
        return False
    if not valid_boundary(dataset.get("evm_boundary"), native=False):
        return False
    if not valid_boundary(dataset.get("fixed_checkpoint"), native=False):
        return False

    delivery = dataset.get("delivery")
    if not isinstance(delivery, dict):
        return False
    if delivery.get("mode") == "direct":
        if not isinstance(delivery.get("cid"), str) or not CID.fullmatch(delivery["cid"]):
            return False
        if delivery.get("parts_manifest_path") is not None or delivery.get("parts") != []:
            return False
    elif delivery.get("mode") == "multipart":
        parts = delivery.get("parts")
        if delivery.get("cid") is not None or not safe_relative_path(delivery.get("parts_manifest_path")):
            return False
        if not isinstance(parts, list) or len(parts) < 2 or not all(valid_part(part) for part in parts):
            return False
        if len({part["filename"] for part in parts}) != len(parts):
            return False
        if len({part["cid"] for part in parts}) != len(parts):
            return False
        if sum(part["size_bytes"] for part in parts) != dataset["size_bytes"]:
            return False
    else:
        return False

    if archive_expected:
        audit = dataset.get("archive_audit")
        if not isinstance(audit, dict) or audit.get("status") != "passed":
            return False
    return True


def dataset_pending(dataset: object, archive_expected: bool) -> bool:
    if not isinstance(dataset, dict):
        return False
    nullable = (
        "version", "filename", "sha256", "size_bytes", "unpacked_size_bytes",
        "canonical_manifest_path", "canonical_manifest_sha256", "validation_spec_path",
        "native_boundary", "evm_boundary", "fixed_checkpoint",
    )
    if archive_expected:
        nullable += ("archive_audit",)
    return bool(
        dataset.get("status") == "pending"
        and dataset.get("archive_node_equivalent") is archive_expected
        and all(dataset.get(key) is None for key in nullable)
        and dataset.get("delivery") == {
            "mode": None,
            "cid": None,
            "parts_manifest_path": None,
            "parts": [],
        }
    )


def walk_values(value: object):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)
    else:
        yield value


def validate_common(validator: Validator, manifest: dict) -> None:
    validator.check(manifest.get("schema") == "bdag.community-release-index.v2", "unexpected manifest schema")
    release = manifest.get("release", {})
    validator.check(release.get("version") == "2.0.0-community-rescue-rc.30", "unexpected release version")
    validator.check(release.get("sequence") == 30, "unexpected release sequence")
    validator.check(release.get("channel") == "community-rescue", "unexpected release channel")
    validator.check(release.get("chain_id") == 1404, "unexpected chain ID")
    validator.check(manifest.get("software", {}).get("independent_from_datasets") is True, "software must be independent from datasets")
    validator.check(manifest.get("datasets", {}).get("independent_from_software") is True, "datasets must be independent from software")
    validator.check(manifest.get("datasets", {}).get("portable", {}).get("archive_node_equivalent") is False, "portable dataset cannot be archive equivalent")
    validator.check(manifest.get("datasets", {}).get("full_archive", {}).get("archive_node_equivalent") is True, "full archive dataset must be archive equivalent")
    runtime_change = manifest.get("runtime_change", {})
    validator.check(runtime_change.get("transient_startup_canonical_boundary_rpc") == "bounded-retry", "startup boundary availability must use bounded retry")
    validator.check(runtime_change.get("transient_startup_peer_readiness") == "bounded-retry", "startup peer readiness must use bounded retry")
    validator.check(runtime_change.get("canonical_mismatch") == "fail-immediately", "canonical mismatch must fail immediately")

    policy = manifest.get("download_policy", {})
    gateways = policy.get("ipfs_gateways")
    validator.check(policy.get("requires_ipv4") is True, "IPv4 download policy is required")
    validator.check(policy.get("requires_http_version") == "HTTP/1.1", "HTTP/1.1 download policy is required")
    validator.check(isinstance(gateways, list) and len(gateways) >= 2, "at least two IPFS gateway templates are required")
    if isinstance(gateways, list):
        validator.check(all(valid_gateway(gateway) for gateway in gateways), "gateway templates must be safe HTTPS URLs with one {cid}")


def validate_draft(validator: Validator, manifest: dict) -> None:
    release = manifest["release"]
    validator.check(release.get("status") == "draft", "draft release status must remain draft")
    validator.check(release.get("published_at") is None, "draft publication time must be null")

    source = manifest["source"]
    validator.check(source.get("stack_commit") == "a0fb1ef7b979e5977728d6c6cb38f56d215fd719", "draft stack revision is incorrect")
    for key in ("release_url", "tag", "corechain_commit", "pool_commit", "dashboard_commit", "source_lock_sha256"):
        validator.check(source.get(key) is None, f"draft source.{key} must be null")

    for key, value in manifest["trust"].items():
        if key == "dataset_verifier_path":
            validator.check(value == "records/dataset/verify-canonical-manifest.py", "draft dataset verifier path is incorrect")
        else:
            validator.check(value is None, f"draft trust.{key} must be null")

    for label, artifact in (
        ("installer", manifest["installer"]),
        ("linux-amd64", manifest["software"]["targets"]["linux-amd64"]),
        ("linux-arm64", manifest["software"]["targets"]["linux-arm64"]),
    ):
        validator.check(artifact.get("status") == "pending", f"draft {label} status must be pending")
        for key in ("filename", "cid", "sha256", "size_bytes"):
            validator.check(artifact.get(key) is None, f"draft {label}.{key} must be null")

    for key, value in manifest["software"]["records"].items():
        validator.check(value is None, f"draft software.records.{key} must be null")

    for name in ("portable", "full_archive"):
        dataset = manifest["datasets"][name]
        validator.check(dataset.get("status") == "pending", f"draft {name} status must be pending")
        for key in (
            "version", "filename", "sha256", "size_bytes", "unpacked_size_bytes",
            "canonical_manifest_path", "canonical_manifest_sha256", "validation_spec_path", "native_boundary",
            "evm_boundary", "fixed_checkpoint",
        ):
            validator.check(dataset.get(key) is None, f"draft {name}.{key} must be null")
        validator.check(dataset["delivery"] == {"mode": None, "cid": None, "parts_manifest_path": None, "parts": []}, f"draft {name} delivery must be empty")
    validator.check(manifest["datasets"]["full_archive"].get("archive_audit") is None, "draft archive audit must be null")

    qualification = manifest["qualification"]
    validator.check(qualification.get("status") == "pending", "draft qualification status must be pending")
    for key, value in qualification.items():
        if key != "status":
            validator.check(value is False, f"draft qualification.{key} must be false")

    validator.check(manifest["download_policy"].get("software_http_fallback_base") is None, "draft software fallback must be null")


def validate_publication(validator: Validator, manifest: dict, html: str, human_guide: str) -> None:
    release = manifest["release"]
    validator.check(release.get("status") == "published", "publication release status must be published")
    validator.check(isinstance(release.get("published_at"), str) and "T" in release["published_at"], "publication time is required")
    validator.check(valid_https(manifest["source"].get("release_url")), "public release URL must use HTTPS")
    validator.check(manifest["source"].get("tag") == release["version"], "release tag must match version")
    for key in ("stack_commit", "corechain_commit", "pool_commit", "dashboard_commit"):
        value = manifest["source"].get(key)
        validator.check(isinstance(value, str) and bool(COMMIT.fullmatch(value)), f"source.{key} must be a full commit SHA")
    validator.check(manifest["source"].get("stack_commit") == "a0fb1ef7b979e5977728d6c6cb38f56d215fd719", "published stack revision is incorrect")
    source_lock_sha256 = manifest["source"].get("source_lock_sha256")
    validator.check(isinstance(source_lock_sha256, str) and bool(SHA256.fullmatch(source_lock_sha256)), "source-lock SHA-256 is required")

    trust = manifest["trust"]
    for key in ("release_key_path", "dataset_verifier_path"):
        validator.check(safe_relative_path(trust.get(key)), f"trust.{key} must be a safe relative path")
    release_key_sha256 = trust.get("release_key_sha256")
    validator.check(isinstance(release_key_sha256, str) and bool(SHA256.fullmatch(release_key_sha256)), "release-key fingerprint must be SHA-256")

    validator.check(valid_artifact(manifest["installer"]), "published installer metadata is invalid")
    for target in ("linux-amd64", "linux-arm64"):
        validator.check(valid_artifact(manifest["software"]["targets"][target]), f"published {target} metadata is invalid")
    for key, value in manifest["software"]["records"].items():
        validator.check(safe_relative_path(value), f"software.records.{key} must be a safe relative path")

    portable_valid = valid_dataset(manifest["datasets"]["portable"], archive_expected=False)
    archive_valid = valid_dataset(manifest["datasets"]["full_archive"], archive_expected=True)
    validator.check(portable_valid or dataset_pending(manifest["datasets"]["portable"], archive_expected=False), "portable dataset must be valid or explicitly pending")
    validator.check(archive_valid or dataset_pending(manifest["datasets"]["full_archive"], archive_expected=True), "full archive dataset must be valid or explicitly pending")
    if portable_valid or archive_valid:
        validator.check(safe_relative_path(trust.get("dataset_key_path")), "dataset key path must be a safe relative path")
        dataset_key_sha256 = trust.get("dataset_key_sha256")
        validator.check(isinstance(dataset_key_sha256, str) and bool(SHA256.fullmatch(dataset_key_sha256)), "dataset-key fingerprint must be SHA-256")
        validator.check(isinstance(trust.get("dataset_key_id"), str) and bool(SAFE_FILENAME.fullmatch(trust["dataset_key_id"])), "dataset key ID is invalid")
    else:
        for key in ("dataset_key_path", "dataset_key_id", "dataset_key_sha256"):
            validator.check(trust.get(key) is None, f"unused trust.{key} must remain null")
    validator.check(manifest["download_policy"].get("software_http_fallback_base") is None, "public software install must not depend on a restricted HTTP fallback")

    qualification = manifest["qualification"]
    validator.check(qualification.get("status") == "passed", "qualification status must be passed")
    validator.check(qualification.get("signed_package_integrity_verified") is True, "signed package qualification must pass")
    validator.check(qualification.get("portable_dataset_verified") is portable_valid, "portable qualification must match availability")
    validator.check(qualification.get("full_archive_dataset_verified") is archive_valid, "archive qualification must match availability")
    validator.check(qualification.get("restore_path_verified") is True, "restore-path qualification must pass")
    validator.check(qualification.get("runtime_path_verified") is True, "runtime qualification must pass")

    placeholder_values = [value for value in walk_values(manifest) if isinstance(value, str) and PLACEHOLDER_VALUE.search(value)]
    validator.check(not placeholder_values, "published manifest contains placeholder strings")
    validator.check("noindex,nofollow" not in html, "remove noindex directive before publication")
    validator.check("> **Draft:**" not in human_guide, "remove draft warning from human guide before publication")


def validate_page_files(validator: Validator) -> tuple[str, str]:
    required = (
        RELEASE / "index.html",
        RELEASE / "release-manifest.json",
        RELEASE / "assets" / "release.css",
        RELEASE / "assets" / "release-page.mjs",
        RELEASE / "docs" / "human-install.md",
        RELEASE / "docs" / "ai-agent-runbook.md",
        RELEASE / "docs" / "publication-input.md",
        RELEASE / "records" / "dataset" / "verify-canonical-manifest.py",
    )
    for path in required:
        validator.check(path.is_file(), f"missing required file: {path.relative_to(ROOT)}")

    html = (RELEASE / "index.html").read_text(encoding="utf-8")
    human_guide = (RELEASE / "docs" / "human-install.md").read_text(encoding="utf-8")
    ai_guide = (RELEASE / "docs" / "ai-agent-runbook.md").read_text(encoding="utf-8")
    publication_contract = (RELEASE / "docs" / "publication-input.md").read_text(encoding="utf-8")
    script = (RELEASE / "assets" / "release-page.mjs").read_text(encoding="utf-8")

    parser = ReleaseHTMLParser()
    parser.feed(html)
    validator.check(len(parser.ids) == len(set(parser.ids)), "HTML contains duplicate IDs")
    validator.check(parser.inline_style_count == 0, "page must use the external stylesheet")
    validator.check('type="module" src="assets/release-page.mjs"' in html, "page does not load the release module")
    validator.check("release-manifest.json" in html and "release-manifest.json" in script, "page is not manifest-driven")
    validator.check("Portable dataset" in html and "Full archive dataset" in html, "both dataset options must be visible")
    validator.check("ASIC MAC addresses" in html and "Public payout wallet" in html, "mining prerequisites are incomplete")
    validator.check("peer-readiness" in html and "canonical checkpoint or boundary mismatch" in html, "page omits RC30 startup policy")

    for _, reference in parser.references:
        if reference.startswith(("https://", "http://", "#")):
            continue
        target = (RELEASE / reference).resolve()
        exists = target.is_file() or (target.is_dir() and (target / "index.html").is_file())
        validator.check(exists and (ROOT == target or ROOT in target.parents), f"broken local page reference: {reference}")

    for label, text in (("human guide", human_guide), ("AI runbook", ai_guide), ("page module", script)):
        validator.check("curl -4 --http1.1" in text, f"{label} does not force IPv4 and HTTP/1.1")
    for label, text in (("human guide", human_guide), ("AI runbook", ai_guide), ("publication contract", publication_contract)):
        validator.check("peer-readiness" in text, f"{label} omits bounded peer-readiness handling")
        validator.check("canonical checkpoint" in text and "boundary mismatch" in text, f"{label} omits immediate canonical mismatch handling")
    validator.check("gateway" in human_guide.lower() and "resume" in human_guide.lower(), "human guide lacks gateway fallback guidance")
    validator.check("independent" in human_guide.lower(), "human guide does not explain independent software and data")

    public_files = [path for path in RELEASE.rglob("*") if path.is_file()]
    for path in public_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT)
        validator.check(not PRIVATE_IPV4.search(text), f"public file contains a private IP address: {relative}")
        validator.check(not EMAIL_OR_USER_HOST.search(text), f"public file contains an email or user-host identity: {relative}")
        validator.check(not PRIVATE_PATH.search(text), f"public file contains a private filesystem path: {relative}")

    root_index = (ROOT / "index.html").read_text(encoding="utf-8")
    validator.check(RC24 in root_index or "releases/2.0.0-community-rescue-rc.30/" in root_index, "root redirect must name a published release")
    return html, human_guide


def validate_git_scope(validator: Validator) -> None:
    if not (ROOT / ".git").exists():
        return
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "releases/2.0.0-community-rescue-rc.24"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    validator.check(result.returncode == 0 and not result.stdout.strip(), "immutable RC24 content contains working-tree changes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-ready", action="store_true", help="require complete final publication metadata")
    args = parser.parse_args()

    validator = Validator()
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"cannot load RC30 manifest: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    validate_common(validator, manifest)
    html, human_guide = validate_page_files(validator)
    validate_git_scope(validator)
    if args.publication_ready:
        validate_publication(validator, manifest, html, human_guide)
        mode = "publication-ready"
    else:
        validate_draft(validator, manifest)
        mode = "draft"
    validator.finish(mode)


if __name__ == "__main__":
    main()
