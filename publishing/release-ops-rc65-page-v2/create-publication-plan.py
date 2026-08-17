#!/usr/bin/env python3
"""Bind the staged RC65 page-v2 tree into a release-ops publication plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path


REPO = Path("/home/jeremy/worktrees/bdag-rc64-release-page")
RELEASE = REPO / "releases/2.0.0-community-rescue-rc.65-page-v2"
ACCEPT = REPO / "publishing/release-ops-rc65-page-v2/accept-page-v2.py"
PUBLISH = REPO / "publishing/release-ops-rc65-page-v2/publish-page-v2.sh"
GATEWAY_VERIFY = REPO / "publishing/release-ops-rc65-page-v2/verify-gateway-page.py"
BRANCH = "jeremy/release/2026-08-17-rc65-rich-ipfs-page-v2"
BASE_COMMIT = "341a445531dd1337b55a49206c422b690f455309"
PAGE_CID = "bafybeiefg3ipbh6t57vccynamsn3msqevqaz3rlxgtidili4lnjyowm5ku"
GIT_OID = re.compile(r"^[0-9a-f]{40}$")


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def exact_file(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size < 1:
        raise SystemExit(f"unsafe subject file: {path}")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def write_new(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise SystemExit(f"refusing to replace output: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-subject", type=Path, required=True)
    parser.add_argument("--output-plan", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if workspace.is_symlink() or not workspace.is_dir():
        raise SystemExit("publication workspace is missing or unsafe")
    for path in (ACCEPT, PUBLISH, GATEWAY_VERIFY):
        exact_file(path)
    if git("branch", "--show-current") != BRANCH or git("rev-parse", "HEAD") != BASE_COMMIT:
        raise SystemExit("page-v2 branch or base commit differs")
    if git("diff", "--name-only"):
        raise SystemExit("unstaged tracked changes remain")
    if git("ls-files", "--others", "--exclude-standard"):
        raise SystemExit("untracked files remain outside the staged candidate")
    tree = git("write-tree")
    if not GIT_OID.fullmatch(tree):
        raise SystemExit("staged Git tree identity is invalid")

    release = json.loads((RELEASE / "records/release.json").read_text(encoding="utf-8"))
    revision = json.loads((RELEASE / "revision/page-v2.json").read_text(encoding="utf-8"))
    pin_manifest = json.loads((REPO / "publishing/free-pinning-cids.json").read_text(encoding="utf-8"))
    subject = {
        "schema": "chain1404-rc65-page-v2-subject/v1",
        "network": {"chainId": 1404, "protocol": 46},
        "git": {"repository": "BlockdagEngineering/bdag-ipfs-release-page", "branch": BRANCH, "baseCommit": BASE_COMMIT, "stagedTree": tree},
        "page": {
            "cid": PAGE_CID,
            "bytes": sum(path.stat().st_size for path in RELEASE.rglob("*") if path.is_file()),
            "attestationSha256": digest(RELEASE / "revision/page-v2.json"),
            "attestationSignatureSha256": digest(RELEASE / "revision/page-v2.json.sig"),
            "predecessorCid": revision["presentation"]["predecessorCid"],
        },
        "unchangedRelease": {
            "releaseJsonSha256": digest(RELEASE / "records/release.json"),
            "recordsCid": revision["originalRecords"]["cid"],
            "softwareTargets": release["software"]["targets"],
            "compactArtifact": release["datasets"]["compactMiningNode"]["artifact"],
            "fullArchiveSha256": release["datasets"]["fullArchive"]["sha256"],
            "fullArchivePartCount": len(release["datasets"]["fullArchive"]["delivery"]["parts"]),
        },
        "admission": {
            "manifestCid": revision["compactAdmission"]["manifestCid"],
            "manifestSha256": revision["compactAdmission"]["manifestSha256"],
            "releaseLockSha256": "b5a0defbf297a8245793fbb10d1a9cdbac1e2bbff066ab279a9fb0d17b299e0e",
        },
        "distribution": {
            "pinManifestSha256": digest(REPO / "publishing/free-pinning-cids.json"),
            "pinCount": len(pin_manifest["pins"]),
            "ipns": pin_manifest["ipns"],
        },
        "operations": {
            "acceptScriptSha256": digest(ACCEPT),
            "publishScriptSha256": digest(PUBLISH),
            "gatewayVerifierSha256": digest(GATEWAY_VERIFY),
        },
    }
    subject_bytes = canonical(subject)
    subject_sha = "sha256:" + hashlib.sha256(subject_bytes).hexdigest()
    evidence = workspace / "evidence-v7"

    def acceptance(job_id: str, role: str) -> dict[str, object]:
        result = evidence / f"{role}.json"
        return {
            "id": job_id, "stage": "qualification", "lane": "target", "kind": "command",
            "mechanism": "deterministic_script", "depends_on": [], "target_id": role,
            "host_id": "local-coordinator", "role": role, "qualifies_for_publication": True,
            "hard_stop": False,
            "argv": ["/usr/bin/python3", str(ACCEPT), "--role", role, "--subject-sha256", subject_sha, "--result", str(result)],
            "cwd": ".", "timeout_seconds": 1200, "max_output_bytes": 1048576,
            "result_json": str(result.relative_to(workspace)), "result_mode": "produced",
            "result_expect": {"status": "passed", "subject_sha256": subject_sha, "role": role},
        }

    publication_result = evidence / "publication.json"
    jobs = [
        acceptance("accept-trust-ux", "trust-ux"),
        acceptance("accept-installer", "installer-admission"),
        acceptance("accept-distribution", "distribution"),
        {
            "id": "approve-publication", "stage": "publication", "lane": "control",
            "kind": "coordinator_gate", "mechanism": "frontier_coordinator",
            "depends_on": ["accept-trust-ux", "accept-installer", "accept-distribution"],
        },
        {
            "id": "publish-page-v2", "stage": "publication", "lane": "control", "kind": "publication",
            "mechanism": "deterministic_script", "depends_on": ["approve-publication"],
            "target_id": "public-ipfs-and-pages", "host_id": "local-coordinator", "role": "publication",
            "repository_writer": True, "hard_stop": True,
            "argv": ["/usr/bin/bash", str(PUBLISH), str(args.output_subject.resolve()), subject_sha, str(publication_result)],
            "cwd": ".", "timeout_seconds": 2400, "max_output_bytes": 4194304,
            "result_json": str(publication_result.relative_to(workspace)), "result_mode": "produced",
            "result_expect": {"status": "passed", "subject_sha256": subject_sha, "pageCid": PAGE_CID},
        },
    ]
    plan = {
        "schema_version": "release-ops-plan/v1", "release_id": "chain1404-rc65-page-v2-7",
        "subject_sha256": subject_sha, "workspace_root": str(workspace),
        "concurrency": {"target": 3, "control": 1, "total": 4}, "environment": {},
        "inherit_env": ["HOME", "PATH", "SSH_AUTH_SOCK"],
        "publication_gate": {"job_id": "publish-page-v2", "minimum_targets": 3, "required_roles": ["trust-ux", "installer-admission", "distribution"]},
        "jobs": jobs,
    }
    write_new(args.output_subject.resolve(), subject_bytes)
    write_new(args.output_plan.resolve(), canonical(plan))
    print(json.dumps({"status": "prepared", "subject_sha256": subject_sha, "stagedTree": tree, "pageCid": PAGE_CID}, sort_keys=True))


if __name__ == "__main__":
    main()
