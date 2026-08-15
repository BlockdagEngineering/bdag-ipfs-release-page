#!/usr/bin/env python3
"""Validate the signed AMD64-only canonical recovery RC63 publication."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0.0-community-rescue-rc.63"
RELEASE = ROOT / "releases" / VERSION
RECORD = RELEASE / "records" / "release.json"
SIGNATURE = RELEASE / "records" / "release.json.sig"
PUBLIC_KEY = RELEASE / "records" / "release-public.pem"
SHA256 = "0123456789abcdef"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"RC63 validation failed: {message}")


def digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in SHA256 for char in value)


def cid(value: object) -> bool:
    return isinstance(value, str) and value.startswith("b") and len(value) >= 20


def main() -> None:
    record_bytes = RECORD.read_bytes()
    record = json.loads(record_bytes)
    require(record_bytes == canonical(record), "release.json is not canonical JSON")
    require(record.get("schema") == "bdag.community-canonical-recovery-release.v3", "wrong schema")
    require(record.get("version") == VERSION and record.get("sequence") == 63, "wrong release identity")
    require(record.get("channel") == "community-rescue" and record.get("status") == "published", "wrong publication state")
    require(record.get("platforms") == ["linux/amd64"], "release is not AMD64-only")
    require(record.get("deferredPlatforms") == ["linux/arm64"], "ARM64 deferral is not explicit")
    require(record.get("network") == {"chainId": 1404, "genesisHash": "0xd62590d28f5c32b6d46839075b3173c3d4c178482f8cd1b0e424bd3feeaed11c"}, "network identity drift")
    require(record.get("source") == {
        "releaseOperationsCommit": "3b0a514f282b6385103190e2a949691a90332a8a",
        "nodeStackCommit": "ae1e8f1b4685d0e02888b127adbace5849c3a4f5",
        "coreCommit": "f07e084c06d758bc92377fc18cb5a0130fe6f89c",
        "poolStackCommit": "528a42bedeaaae9a2a4306fcd5a2a3c460f20b29",
        "poolCommit": "64c834a93bd7f5a2f91df7291c0328b39df12541",
    }, "source identity drift")

    images = record.get("images", {})
    node = images.get("node", {})
    pool = images.get("pool", {})
    require(node.get("qualifiedRuntimeManifest") == "sha256:893112e531ea43f8e9fb93b680f9355f6bac7e3c540a624030b0aaa35f101c02", "node manifest drift")
    require(node.get("configDigest") == "sha256:7127ca53142c63e8061dc5cae218ccb84218f3130541ea58c344eabdfc55a38b", "node config drift")
    require(node.get("nodeBinarySha256") == "3c88bb1b4750b8cc7237158b4a5fc682df0b71cc9b2c2edb9da95d29e4521a19", "node binary drift")
    require(pool.get("qualifiedRuntimeManifest") == "sha256:db0b7376d39e44dfbf35ced780fc2349e95f9bb197bc4ac8628de02e2c17c62c", "pool manifest drift")
    require(pool.get("configDigest") == "sha256:7aa238ff12706037f9064ecb22cedec8ae22dd42b216bd96efe88a53f0cc66fb", "pool config drift")
    expected_artifacts = {
        ("node", "dockerArchive"): ("06776981d38e75e4587c2ae17cd9963ee6a6ea47392d95d7db24f31481a98f56", 181312512),
        ("node", "ociArchive"): ("bc084724b0f358f21358073580f098034f101d5755c8ce8f3137c3b483f0121b", 181309952),
        ("pool", "dockerArchive"): ("a1dcabcdbef4a5c5c4187ec55213a4bfe98249c8afdaa5f4b361ab5acfd720e0", 51080704),
        ("pool", "ociArchive"): ("173aaae04670d003b9ee367728a05d9ff80feb57fcfa6f52eebc4a497f0039ad", 51078144),
    }
    for (role, carrier), (expected_sha, expected_bytes) in expected_artifacts.items():
        artifact = images[role][carrier]
        require(artifact.get("sha256") == expected_sha and artifact.get("bytes") == expected_bytes and cid(artifact.get("cid")), f"{role} {carrier} drift")

    tools = record.get("tools", {})
    require(tools.get("publicRpcHealth", {}).get("sha256") == "ac7789fa801a6d37eadaa05df03162eb0f922715d50e74ad44df420bddaa0241", "RPC health tool drift")
    require(tools.get("ownerSafePoolCutover", {}).get("sha256") == "a6ba9cd2c3781158402d149533a6f2eabce10307342a007c71796395d7334254", "pool cutover tool drift")
    for tool in tools.values():
        require(digest(tool.get("sha256")) and cid(tool.get("cid")), "invalid signed tool identity")

    anchors = record.get("anchors", {})
    require(anchors.get("native") == {"order": 17750631, "hash": "0x444121faebccaa1422ddc773487c10912abf135de2847be422d715ab7663889c", "stateRoot": "0xadbfc8f92b484e10476fc1718f223f561bf9c8032626cf4ed22c6077b89a622c"}, "native anchor drift")
    require(anchors.get("evm") == {"number": 17354990, "hash": "0xc935d81d9d3956cbeabe5d3874e9a008c604b6ed320c0ed20781e3e448930ed1", "stateRoot": "0x9aa4e9e9e5af5734cc94e87ae9384747e7b383886ae5683d4c419ee93a1a6c5e"}, "EVM anchor drift")
    acceptance = record.get("acceptance", {})
    for key in ("fleetComplete", "ownerPayoutIdentityPreserved", "realDivergentAdoption", "sustainedIndependentConvergence", "rollbackBacked", "publicRpcExactBlueGreen"):
        require(acceptance.get(key) is True, f"{key} is not asserted")
    require(acceptance.get("activeMiningHosts") == 5 and acceptance.get("reverseContaminationObserved") is False, "fleet acceptance drift")
    require(digest(acceptance.get("fleetEvidenceSha256")), "invalid fleet evidence digest")
    require(record.get("miningContinuity") == {
        "ownerAddressMustRemainExplicit": True,
        "sameStratumEndpoint": True,
        "sameAccountingDatabase": True,
        "implicitPoolFailover": False,
        "stageBeforeCutover": True,
        "backendHandoffOnlyAfterExactReadiness": True,
        "backendIdentityPinnedToFleetAcceptance": True,
        "ownerTemplateRequiredBeforeCutover": True,
        "acceptedShareGrowthRequiredAfterCutover": True,
        "localFallbackRetained": True,
        "boundedRestartAllowedWhenNoOwnerSafeShadowPath": True,
    }, "mining continuity drift")
    require(record.get("protocol45") == {"relayOnlyCannotInfluenceMiningReadiness": True, "ordinaryP2PRecoveryQualified": False, "successorInstallRequired": True}, "protocol-45 boundary drift")
    require(record.get("mirrors", {}).get("githubReleaseTag") == "jeremy-community-rescue-rc.63-amd64", "mirror tag drift")

    require(PUBLIC_KEY.stat().st_mode & 0o777 == 0o644, "public key mode is not 0644")
    require(SIGNATURE.stat().st_size == 64, "signature is not Ed25519-sized")
    with tempfile.TemporaryDirectory() as temporary:
        der = Path(temporary) / "release-public.der"
        subprocess.run(["openssl", "pkey", "-pubin", "-in", str(PUBLIC_KEY), "-outform", "DER", "-out", str(der)], check=True)
        require(hashlib.sha256(der.read_bytes()).hexdigest() == record.get("releaseKeySha256"), "release key fingerprint mismatch")
    subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(PUBLIC_KEY), "-rawin", "-in", str(RECORD), "-sigfile", str(SIGNATURE)], check=True)

    page = (RELEASE / "index.html").read_text(encoding="utf-8")
    guide = (RELEASE / "docs" / "install-amd64.md").read_text(encoding="utf-8")
    loader = (RELEASE / "verify-load-amd64.sh").read_text(encoding="utf-8")
    public_bundle = "bafybeic6lrevdxfv3tnv2tm6uktk7muleqg5iz3v3cigt3yq7qq2dzvrp4"
    require("jeremy-community-rescue-rc.63-amd64" in page and "dockerArchive" in page, "page omits release identity")
    require(public_bundle in page and public_bundle in guide, "public immutable bundle omitted")
    require("BDAG_RC63_BASE_URL=https://dweb.link/ipfs/" in guide, "public loader command omitted")
    require("cutover-pool-image-owner-safe.sh" in guide and "owner payout" in guide, "install guide omits owner-safe cutover")
    require("pkeyutl -verify" in loader and "docker load" in loader and "No running container" in loader, "loader omits authenticated staging boundary")
    for path in RELEASE.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            require(b"PRIVATE KEY" not in data, f"private key marker in {path.relative_to(ROOT)}")
            require(b"192.168." not in data and b"/home/jeremy" not in data, f"private fleet detail in {path.relative_to(ROOT)}")
    print("RC63 signed AMD64 canonical recovery validation passed")


if __name__ == "__main__":
    main()
