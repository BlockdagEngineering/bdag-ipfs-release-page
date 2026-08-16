#!/usr/bin/env python3
"""Validate the signed AMD64-only RC64 canonical recovery publication."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0-community-rescue-rc.64"
RELEASE = ROOT / "releases" / VERSION
RECORDS = RELEASE / "records"
PUBLIC_KEY = RECORDS / "release-public.pem"
HEX = "0123456789abcdef"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"RC64 validation failed: {message}")


def canonical(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    value = json.loads(data)
    expected = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")
    require(data == expected, f"{path.name} is not canonical JSON")
    return value


def digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in HEX for char in value)


def cid(value: object) -> bool:
    return isinstance(value, str) and value.startswith("b") and len(value) >= 20


def signature(payload: Path, detached: Path) -> None:
    require(detached.stat().st_size == 64, f"invalid signature size for {payload.name}")
    subprocess.run([
        "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(PUBLIC_KEY),
        "-rawin", "-in", str(payload), "-sigfile", str(detached),
    ], check=True, stdout=subprocess.DEVNULL)


def main() -> None:
    require(PUBLIC_KEY.is_file() and not PUBLIC_KEY.is_symlink(), "missing public key")
    with tempfile.TemporaryDirectory() as temporary:
        der = Path(temporary) / "release-public.der"
        subprocess.run(["openssl", "pkey", "-pubin", "-in", str(PUBLIC_KEY),
                        "-outform", "DER", "-out", str(der)], check=True)
        require(hashlib.sha256(der.read_bytes()).hexdigest() ==
                "9c78685439ff9841f14f1f7db386942a14a3d2dde1c75d9ea739a0da97149e66",
                "release key fingerprint drift")

    release_path = RECORDS / "release.json"
    release = canonical(release_path)
    signature(release_path, RECORDS / "release.json.sig")
    require(release.get("schema") == "bdag.community-canonical-recovery-release.v4", "wrong release schema")
    require(release.get("version") == VERSION and release.get("sequence") == 64, "wrong release identity")
    require(release.get("status") == "published", "release is not published")
    require(release.get("platforms") == ["linux/amd64"], "release is not AMD64-only")
    require(release.get("deferredPlatforms") == ["linux/arm64"], "ARM64 deferral missing")
    require(release.get("network") == {
        "chainId": 1404,
        "genesisHash": "0xd62590d28f5c32b6d46839075b3173c3d4c178482f8cd1b0e424bd3feeaed11c",
        "protocol": 46,
    }, "network identity drift")
    require(release.get("source") == {
        "releaseOperationsCommit": "bb439a40694a05b0086aacb4c62782048b62ee40",
        "poolStackCommit": "99579d1998a131ab7e7542ffda9608c058a1a43d",
        "nodeStackCommit": "ae1e8f1b4685d0e02888b127adbace5849c3a4f5",
        "coreCommit": "f07e084c06d758bc92377fc18cb5a0130fe6f89c",
        "poolCommit": "68d3f7471352cce2164cfab5550abafacf8dfae7",
    }, "source identity drift")

    node = release["images"]["node"]
    pool = release["images"]["pool"]
    require(node["qualifiedRuntimeManifest"] == "sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02", "node digest drift")
    require(node["configDigest"] == "sha256:7127ca53142c63e8061dc5cae218ccb84218f3130541ea58c344eabdfc55a38b", "node config drift")
    require(node["nodeBinarySha256"] == "3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19", "node binary drift")
    require(pool["qualifiedRuntimeManifest"] == "sha256:118bfca120162191449c6cca0e703815b365c2b0dbf4ad9732d69a3a151747ba", "pool digest drift")
    require(pool["configDigest"] == "sha256:eb4f110fab8b96be3225a172ff6bdfca50e1605270f66af8119eeb8bd7cc3646", "pool config drift")
    expected = {
        ("node", "dockerArchive"): ("06776981d38e75e4587c2ae17cd9963ee6a6ea47392d95d7db24f31481a98f56", 181312512),
        ("node", "ociArchive"): ("bc084724b0f358f21358073580f098034f101d5755c8ce8f3137c3b483f0121b", 181309952),
        ("pool", "dockerArchive"): ("c5378015d99472cbda7ba6e2b26dd119d3191695e730c90510ec3ec2dcd21f37", 48620544),
        ("pool", "ociArchive"): ("946bd6315b209b470ca420679c1a2b8493d9046aac36c26c7c417e08e802a785", 48618496),
    }
    for (role, carrier), (expected_sha, expected_bytes) in expected.items():
        artifact = release["images"][role][carrier]
        require(artifact["sha256"] == expected_sha and artifact["bytes"] == expected_bytes and
                cid(artifact["cid"]), f"{role} {carrier} drift")

    policy = release.get("runtimePolicy", {})
    for key in ("evmReferenceUrlsDefaultEmpty", "evmAdvisoryWhenGuardDisabled",
                "evmStrictWhenGuardEnabled", "nativeSafeMiningIgnoresLegacyV45Noise",
                "legacyCanonicalFeedContinues", "bootstrapPeersAreDiscoveryOnly",
                "publicLanAndExplicitVpnDialingAllowed"):
        require(policy.get(key) is True, f"runtime policy {key} missing")
    require(policy.get("automaticHeadscaleEnrollment") is False, "Headscale deferral missing")
    acceptance = release.get("acceptance", {})
    require(acceptance.get("minimumExactNodes", 0) >= 3 and
            acceptance.get("minimumExactMiningHosts", 0) >= 3, "minimum fleet gate missing")
    for key in ("ownerPayoutIdentityPreserved", "realDivergentAdoption",
                "sustainedIndependentConvergence", "recoveryBackupBacked",
                "publicRpcExactBlueGreen", "reachableAsicsReadyAndIncreasing"):
        require(acceptance.get(key) is True, f"acceptance {key} missing")
    require(acceptance.get("reverseContaminationObserved") is False, "reverse contamination asserted")

    bootstrap_path = RECORDS / "bootstrap-peers.txt"
    bootstrap_manifest_path = RECORDS / "bootstrap-peers.manifest.json"
    bootstrap_manifest = canonical(bootstrap_manifest_path)
    signature(bootstrap_path, RECORDS / "bootstrap-peers.txt.sig")
    signature(bootstrap_manifest_path, RECORDS / "bootstrap-peers.manifest.json.sig")
    require(hashlib.sha256(bootstrap_path.read_bytes()).hexdigest() ==
            bootstrap_manifest["file"]["sha256"], "bootstrap hash mismatch")
    require(bootstrap_manifest["trust"] == {
        "signatureRequired": True, "discoveryOnly": True,
        "consensusAuthority": False, "miningReadinessVoter": False,
    }, "bootstrap trust boundary drift")
    require(bootstrap_manifest["qualification"]["qualifiedDiscoveryPeerCount"] >= 3,
            "too few qualified discovery peers")

    data_path = RECORDS / "latest-data-manifest.json"
    data = canonical(data_path)
    signature(data_path, RECORDS / "latest-data-manifest.json.sig")
    require(data.get("schema") == "chain1404-latest-data-manifest/v1" and
            data.get("cleanShutdown") is True and data.get("platform") == "linux/amd64",
            "latest-data identity drift")
    require(cid(data["snapshot"]["cid"]) and digest(data["snapshot"]["sha256"]) and
            data["snapshot"]["bytes"] > 0, "invalid snapshot identity")
    require(all(data["sanitization"].get(key) is True for key in (
        "nodeIdentityExcluded", "peerstoreExcluded", "credentialsExcluded",
        "recoveryLatchesExcluded", "componentSourceExcluded")), "snapshot sanitization missing")

    fleet_path = RECORDS / "evidence" / "fleet-evidence.json"
    fleet = canonical(fleet_path)
    signature(fleet_path, RECORDS / "evidence" / "fleet-evidence.json.sig")
    require(fleet.get("schema") == "chain1404-fleet-public-evidence/v4" and
            fleet.get("status") == "passed", "fleet evidence did not pass")
    require(len(fleet.get("exactNodeHosts", [])) >= 3 and
            len(fleet.get("exactMiningHosts", [])) >= 3, "fleet minima absent")
    require(fleet.get("sourceFleetEvidenceSha256") ==
            release.get("acceptance", {}).get("fleetEvidenceSha256"),
            "public fleet summary is not bound to full evidence")
    require(hashlib.sha256(fleet_path.read_bytes()).hexdigest() ==
            release.get("acceptance", {}).get("publicFleetSummarySha256"),
            "public fleet summary hash mismatch")
    evidence_path = RECORDS / "evidence" / "release-evidence.json"
    evidence = canonical(evidence_path)
    signature(evidence_path, RECORDS / "evidence" / "release-evidence.json.sig")
    require(evidence.get("schema") == "chain1404-release-evidence/v4" and
            evidence.get("status") == "passed", "release evidence did not pass")
    require(evidence.get("releaseManifestSha256") == hashlib.sha256(release_path.read_bytes()).hexdigest(),
            "release evidence manifest hash mismatch")
    scan = canonical(RECORDS / "evidence" / "artifact-scan.json")
    require(scan.get("status") == "passed" and scan.get("amd64Only") is True and
            scan.get("componentSourceExcluded") is True and scan.get("findings") == [],
            "artifact scan did not pass")

    loader = (RELEASE / "verify-load-amd64.sh").read_text(encoding="utf-8")
    data_helper = (RELEASE / "install-or-reuse-data-amd64.sh").read_text(encoding="utf-8")
    guide = (RELEASE / "docs" / "install-amd64.md").read_text(encoding="utf-8")
    recovery_guide = (RELEASE / "docs" / "recover-divergent-node.md").read_text(encoding="utf-8")
    require("bootstrap-peers.txt.sig" in loader and "latest-data-manifest.json.sig" in loader and
            "docker load" in loader, "loader omits authenticated inputs")
    require("No snapshot request was made" in data_helper and "refusing to overwrite" not in data_helper,
            "existing-data no-download behavior missing")
    for marker in ("expected_extract_bytes=34359738368", "staging_overhead_bytes=2147483648",
                   "filesystem_bytes * 15 / 100", "minimum_reserve_bytes=21474836480",
                   "available_bytes < required_bytes", "after proving that no running service references"):
        require(marker in data_helper, f"storage-capacity gate missing: {marker}")
    require("larger of 20 GiB or 15%" in guide and "Never use a broad Docker prune" in guide,
            "storage lifecycle guidance omitted")
    require("repeated warm deltas" in recovery_guide and "zero-byte verification pass" in recovery_guide and
            "ordinary image upgrade" in recovery_guide,
            "downtime-bounded exceptional data relocation guidance omitted")
    require("guard disabled" in guide and "no external EVM request" in guide,
            "miner-friendly EVM policy omitted")

    for path in RELEASE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(RELEASE)
        lowered = str(relative).lower()
        require(not lowered.endswith((".go", ".ts", ".tsx", ".jsx", ".map")),
                f"component source path present: {relative}")
        data_bytes = path.read_bytes()
        require(b"PRIVATE KEY" not in data_bytes and b"/home/jeremy" not in data_bytes and
                b"192.168." not in data_bytes, f"private material in {relative}")
    print("RC64 signed AMD64 canonical recovery validation passed")


if __name__ == "__main__":
    main()
