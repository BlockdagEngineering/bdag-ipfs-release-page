#!/usr/bin/env python3
"""Produce one exact-subject RC65 rich-page publication acceptance receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPO = Path("/home/jeremy/worktrees/bdag-rc64-release-page")
RELEASE = REPO / "releases/2.0.0-community-rescue-rc.65-page-v2"
PACKAGE = Path("/home/jeremy/.cache/bdag-francois-rc65.6/extracted/pool-stack-docker-jeremy-community-rescue-rc.65.6-linux-amd64")
PAGE_CID = "bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku"
RECORDS_CID = "bafybeihudga5veymvrnpdnzrz5juf6a277dgqudksaw6matcjc257judqe"
RELEASE_KEY_SHA = "26f0051185d9c1abada3b5adcd3d11c88f522e09b3850211a04773250c267ffb"
RELEASE_LOCK_SHA = "b5a0defbf297a8245793fbb10d1a9cdbac1e2bbff066ab279a9fb0d17b299e0e"
PROVIDER_PEER = "12D3KooWD3c6UAMwSBjuPbYinx4mJMTsEBK1kNjW9s5TtZL8L6Gi"
PROFILE = "257455992626"
REGION = "eu-central-1"
INSTANCE = "i-0003578e60e4abcb0"
SUBJECT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
sys.dont_write_bytecode = True


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str], *, cwd: Path = REPO, timeout: int = 300, capture: bool = False) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else None,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return completed.stdout.strip() if capture else ""


def accept_trust_ux() -> dict[str, object]:
    run([str(RELEASE / "verify-load-v2.sh"), str(RELEASE)])
    run([sys.executable, "tests/validate_rc65_release.py", "--publication-ready"])
    run([sys.executable, "tests/validate_rc65_page_v2.py", "--publication-ready"])
    run(["node", "--test", "tests/release-page-rc65-v2.test.mjs"], timeout=600)
    page_cid = run([
        "ipfs", "add", "-r", "--only-hash", "--hidden=true", "--empty-dirs=true",
        "--cid-version=1", "--raw-leaves=true", "--chunker=size-262144",
        "--hash=sha2-256", "--preserve-mode=false", "--preserve-mtime=false",
        "-Q", str(RELEASE),
    ], capture=True)
    records_cid = run([
        "ipfs", "add", "-r", "--only-hash", "--hidden=true", "--empty-dirs=true",
        "--cid-version=1", "--raw-leaves=true", "--chunker=size-262144",
        "--hash=sha2-256", "--preserve-mode=false", "--preserve-mtime=false",
        "-Q", str(RELEASE / "records"),
    ], capture=True)
    if page_cid != PAGE_CID or records_cid != RECORDS_CID:
        raise SystemExit("deterministic page or records CID mismatch")
    return {"pageCid": page_cid, "recordsCid": records_cid, "browserTests": "passed", "externalRuntimeDependencies": False}


def accept_installer() -> dict[str, object]:
    if sha256(PACKAGE / "release-lock.json") != RELEASE_LOCK_SHA:
        raise SystemExit("exact RC65.6 release lock is unavailable")
    run([sys.executable, str(RELEASE / "revision/verify-compact-admission.py"), str(RELEASE), "--ipfs-cid-check"])
    run([
        sys.executable, str(PACKAGE / "scripts/release_lock.py"), "verify",
        "--lock", str(PACKAGE / "release-lock.json"),
        "--trusted-key-dir", str(PACKAGE / "trust/release"),
        "--trusted-key-sha256", RELEASE_KEY_SHA,
        "--target", "linux-amd64", "--package-root", str(PACKAGE),
        "--expected-release-version", "jeremy-community-rescue-rc.65.6",
        "--expected-release-sequence", "65",
    ], timeout=900)

    sys.path.insert(0, str(PACKAGE / "ops"))
    sys.path.insert(0, str(PACKAGE / "scripts"))
    import canonical_data_manifest as canonical_manifest  # type: ignore
    import release_lock  # type: ignore

    trusted_release = release_lock.trusted_release_keys_by_fingerprint(PACKAGE / "trust/release", RELEASE_KEY_SHA)
    lock = release_lock.load_verified_release_lock(PACKAGE / "release-lock.json", trusted_release)
    policy = release_lock.dataset_policy_for_release(lock, PACKAGE / "release-lock.json")
    envelope = json.loads((RELEASE / "revision/compact-canonical-manifest.json").read_text(encoding="utf-8"))
    payload = envelope.get("signed")
    if not isinstance(payload, dict):
        raise SystemExit("compact canonical manifest payload is unavailable")
    errors = canonical_manifest.validate_manifest_install_mode(payload, policy, archive_mode=False)
    archive_errors = canonical_manifest.validate_manifest_install_mode(
        payload, policy, archive_mode=True, require_full_archive=True
    )
    if errors or not archive_errors:
        raise SystemExit(f"RC65.6 compact installer admission mismatch: {errors}; archive={archive_errors}")
    return {
        "releaseLockSha256": RELEASE_LOCK_SHA,
        "target": "linux-amd64",
        "compactMode": "admitted",
        "archiveMode": "rejected-for-compact-data",
    }


def api(port: int, endpoint: str, timeout: int = 60) -> dict[str, object]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/v0/{endpoint}", method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def accept_distribution() -> dict[str, object]:
    pins = json.loads((REPO / "publishing/free-pinning-cids.json").read_text(encoding="utf-8"))
    existing_names = {
        item["name"]: item["cid"] for item in pins["pins"]
        if item["name"] not in {"release-page-root", "release-records-root", "compact-canonical-admission-manifest"}
    }
    if len(existing_names) != 44:
        raise SystemExit("existing RC65 distribution inventory is incomplete")
    provider_required = {
        name: cid for name, cid in existing_names.items()
        if not name.startswith("full-archive-part-")
    }
    if len(provider_required) != 4:
        raise SystemExit("AWS current-payload inventory is incomplete")

    port = 15004
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise SystemExit(f"SSM preflight port is unavailable: {exc}")
    cache = Path("/home/jeremy/.cache/r65ssm-page-v2-preflight")
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    if cache.is_symlink():
        raise SystemExit("unsafe SSM preflight cache")
    process = subprocess.Popen(
        [
            "aws", "--profile", PROFILE, "--region", REGION, "ssm", "start-session",
            "--target", INSTANCE, "--document-name", "AWS-StartPortForwardingSession",
            "--parameters", json.dumps({"portNumber": ["5001"], "localPortNumber": [str(port)]}, separators=(",", ":")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "AWS_PAGER": "", "TMPDIR": str(cache), "TMP": str(cache), "TEMP": str(cache)},
    )
    try:
        deadline = time.monotonic() + 60
        identity: dict[str, object] = {}
        while time.monotonic() < deadline and process.poll() is None:
            try:
                identity = api(port, "id", timeout=5)
            except Exception:
                time.sleep(1)
                continue
            if identity.get("ID") == PROVIDER_PEER:
                break
        if identity.get("ID") != PROVIDER_PEER:
            raise SystemExit("AWS IPFS provider identity did not become ready")
        remote = api(port, "pin/ls?type=recursive", timeout=120).get("Keys", {})
        if not isinstance(remote, dict):
            raise SystemExit("AWS IPFS recursive pin inventory is invalid")
        missing = sorted(name for name, cid in provider_required.items() if cid not in remote)
        if missing:
            raise SystemExit("AWS IPFS provider is missing current RC65 roots: " + ", ".join(missing))
        repo_stat = api(port, "repo/stat?size-only=true", timeout=60)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def public_root(item: tuple[str, str]) -> tuple[str, int]:
        name, cid = item
        provider = subprocess.run(
            [
                "curl", "-4", "--http1.1", "-fsS", "--max-time", "45",
                "-H", "Accept: application/x-ndjson",
                "-H", "Cache-Control: no-cache",
                f"https://delegated-ipfs.dev/routing/v1/providers/{cid}",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if provider.returncode != 0:
            raise RuntimeError(f"delegated provider lookup failed for {name}: {provider.stderr.strip()}")
        providers = {
            json.loads(line).get("ID") for line in provider.stdout.splitlines() if line.strip()
        }
        providers.discard(None)
        if not providers:
            raise RuntimeError(f"no delegated provider for {name}")
        sampled = name in provider_required or name in {"full-archive-part-001", "full-archive-part-040"}
        if sampled:
            raw = subprocess.run(
                [
                    "curl", "-4", "--http1.1", "-fsS", "--max-time", "90",
                    "-H", "Accept: application/vnd.ipld.raw",
                    "-H", "Cache-Control: no-cache",
                    f"https://trustless-gateway.link/ipfs/{cid}?format=raw",
                    "-o", "/dev/null",
                ],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if raw.returncode != 0:
                raise RuntimeError(f"trustless root read failed for {name}: {raw.stderr.strip()}")
        return name, len(providers)

    provider_counts: dict[str, int] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="ipfs-proof") as executor:
        futures = {executor.submit(public_root, item): item[0] for item in existing_names.items()}
        for future in as_completed(futures):
            try:
                name, count = future.result()
                provider_counts[name] = count
            except Exception as exc:
                failures.append(f"{futures[future]}: {exc}")
    if failures or len(provider_counts) != len(existing_names):
        raise SystemExit("public RC65 root proof failed: " + "; ".join(sorted(failures)))

    rpc = run([
        "curl", "-fsS", "--max-time", "20", "-H", "content-type: application/json",
        "--data", '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}',
        "https://rpc.blockdag.engineering",
    ], capture=True)
    if json.loads(rpc).get("result") != "0x57c":
        raise SystemExit("production RPC chain identity is unavailable")
    return {
        "providerPeerId": PROVIDER_PEER,
        "awsCurrentRoots": len(provider_required),
        "publicExistingRoots": len(provider_counts),
        "trustlessSampledRoots": len(provider_required) + 2,
        "minimumDelegatedProviders": min(provider_counts.values()),
        "providerRepoSize": repo_stat.get("RepoSize"),
        "productionRpcChainId": "0x57c",
    }


def write_new(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise SystemExit(f"refusing unsafe or existing result: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value))
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("trust-ux", "installer-admission", "distribution"), required=True)
    parser.add_argument("--subject-sha256", required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not SUBJECT_RE.fullmatch(args.subject_sha256):
        raise SystemExit("invalid release subject SHA-256")
    details = {
        "trust-ux": accept_trust_ux,
        "installer-admission": accept_installer,
        "distribution": accept_distribution,
    }[args.role]()
    result = {
        "schema": "chain1404-rc65-page-v2-acceptance/v1",
        "status": "passed",
        "subject_sha256": args.subject_sha256,
        "role": args.role,
        "details": details,
    }
    write_new(args.result, result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
