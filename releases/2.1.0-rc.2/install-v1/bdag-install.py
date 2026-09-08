#!/usr/bin/env python3
"""Small, owner-configured installer for the RC2 V2 release contract.

The command deliberately separates ``prepare`` (verify/plan/install/apply) from
``start`` (boot).  It never compiles source, migrates a ledger, or chooses an
operator payout/RPC authority.  The full runtime ZIP remains the immutable
Compose build context; the generated files are private target-local state.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import runpy
import secrets
import shutil
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable


VERSION = "2.1.0-rc.2"
RELEASE_RECORD_SHA256 = "468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2"
MODES = {"node", "pool", "redis-dash", "all-in-one"}
MODE_COMPONENTS = {
    "node": ("corechain", "stack"),
    "pool": ("pool", "stack"),
    "redis-dash": ("dashboard", "stack"),
    "all-in-one": ("corechain", "dashboard", "pool", "stack"),
}
MODE_SERVICES = {
    "node": ("node",),
    "pool": ("pool", "postgres"),
    "redis-dash": ("dashboard",),
    "all-in-one": ("node", "pool", "postgres", "dashboard"),
}
SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HEX_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


class InstallError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.write_bytes(canonical(value))
    os.chmod(path, mode)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise InstallError(f"{label} must be a regular file")
    return path


def directory(path: Path, label: str, *, must_exist: bool = True) -> Path:
    if not path.is_absolute() or path != path.resolve():
        raise InstallError(f"{label} must be an absolute canonical path")
    if path.is_symlink() or (must_exist and not path.is_dir()):
        raise InstallError(f"{label} must be a canonical directory")
    if not must_exist and path.exists():
        raise InstallError(f"{label} already exists")
    return path


def parse_env(path: Path) -> dict[str, str]:
    regular(path, "owner env")
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("export "):
            line = line.lstrip()[7:]
        if "=" not in line:
            raise InstallError(f"owner env line {number} is not KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not SAFE_NAME.fullmatch(key):
            raise InstallError(f"owner env line {number} has an invalid key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            if quote == "'":
                value = value[1:-1].replace("\\'", "'")
            else:
                try:
                    value = json.loads(value.replace("\\$", "$"))
                except json.JSONDecodeError as exc:
                    raise InstallError(f"owner env line {number} has invalid quoted escapes") from exc
        if "\x00" in value or "\n" in value or "\r" in value:
            raise InstallError(f"owner env line {number} contains an invalid value")
        result[key] = value
    return result


def parse_defaults(path: Path) -> dict[str, str]:
    # The shipped example is intentionally simple dotenv.  Ignore comments and
    # preserve values literally; no shell is ever evaluated.
    return parse_env(path)


def write_env(path: Path, values: dict[str, str]) -> None:
    lines = []
    for key in sorted(values):
        value = values[key]
        if "\n" in value or "\r" in value or "\x00" in value:
            raise InstallError(f"generated env value for {key} is not single-line")
        # Compose double quotes support escaped dollars and backslashes. This
        # also represents trailing backslashes, unlike single-quoted dotenv.
        encoded = json.dumps(value, ensure_ascii=False).replace("$", "\\$")
        lines.append(f"{key}={encoded}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def platform_name(value: str | None) -> str:
    if value:
        if value not in {"linux-amd64", "linux-arm64"}:
            raise InstallError("platform must be linux-amd64 or linux-arm64")
        return value
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "linux-amd64"
    if machine in {"aarch64", "arm64"}:
        return "linux-arm64"
    raise InstallError(f"unsupported host architecture: {machine}")


def safe_relative(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise InstallError(f"{label} has an unsafe path")
    return path


def load_release(record_path: Path) -> dict[str, Any]:
    regular(record_path, "release record")
    if digest(record_path) != RELEASE_RECORD_SHA256:
        raise InstallError("release record SHA-256 does not match the protected RC2 record")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError("release record is not valid JSON") from exc
    if record.get("schema") != "blockdag.develop-release/v1" or record.get("version") != VERSION:
        raise InstallError("release record is not the protected RC2 tuple")
    if record.get("status") != "published" or record.get("main_promoted") is not False:
        raise InstallError("release record status is not the protected prerelease")
    identity = record.get("dataset", {}).get("chain_identity")
    if not isinstance(identity, dict) or identity.get("evm_chain_id") != "1404":
        raise InstallError("release record lacks the pinned Chain 1404 identity")
    software = record.get("software", {})
    if software.get("cid") != "bafybeicem6wyor5s4xq7436nnhfr2uj7ydh357tfdh3nzbziw7lx5v2taq":
        raise InstallError("release record software CID is not the protected RC2 CID")
    return record


def software_artifacts(record: dict[str, Any], component: str, platform_id: str) -> dict[str, Any]:
    values = [a for a in record["software"]["artifacts"] if a.get("component") == component and a.get("platform") == platform_id]
    if len(values) != 1:
        raise InstallError(f"release record has no unique {component} {platform_id} artifact")
    artifact = values[0]
    safe_relative(artifact["path"], f"{component} artifact")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")):
        raise InstallError(f"{component} artifact hash is invalid")
    return artifact


def verify_artifact(record_root: Path, artifact: dict[str, Any]) -> Path:
    source = record_root / safe_relative(artifact["path"], "artifact")
    regular(source, f"{artifact['component']} artifact")
    if source.stat().st_size != artifact["bytes"] or digest(source) != artifact["sha256"]:
        raise InstallError(f"{artifact['component']} artifact bytes do not match the release record")
    return source


def verify_record_root(record_root: Path, record_path: Path, record: dict[str, Any], mode: str, platform_id: str) -> dict[str, Any]:
    directory(record_root, "record root")
    selected: dict[str, Any] = {}
    for component in MODE_COMPONENTS[mode]:
        artifact = software_artifacts(record, component, platform_id)
        verify_artifact(record_root, artifact)
        selected[component] = {**artifact, "artifact_id": platform_id}
    full = [a for a in record["software"]["artifacts"] if a.get("component") == "full stack" and a.get("platform") == platform_id]
    if len(full) != 1:
        raise InstallError("release record has no unique full runtime ZIP")
    verify_artifact(record_root, full[0])
    sums = record_root / "SHA256SUMS"
    if sums.is_file() and not sums.is_symlink():
        bound = record["software"].get("sha256sums_sha256")
        if bound and digest(sums) != bound:
            raise InstallError("SHA256SUMS does not match the release tuple")
    selected["full stack"] = {**full[0], "artifact_id": platform_id}
    return selected


def safe_extract_zip(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise InstallError("target must be a new directory")
    parent = target.parent
    if not parent.is_dir() or parent != parent.resolve():
        raise InstallError("target parent must be an existing canonical directory")
    temporary = parent / f".{target.name}.extract-{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        raise InstallError("temporary extraction path already exists")
    temporary.mkdir(mode=0o700)
    try:
        with zipfile.ZipFile(source) as bundle:
            members = bundle.infolist()
            roots = {Path(member.filename).parts[0] for member in members if member.filename}
            if len(roots) != 1:
                raise InstallError("runtime ZIP must contain one top-level directory")
            root = next(iter(roots))
            for member in members:
                name = member.filename
                if not name or name.endswith("/"):
                    continue
                path = Path(name)
                if path.is_absolute() or ".." in path.parts or path.parts[0] != root:
                    raise InstallError("runtime ZIP contains an unsafe path")
                mode = (member.external_attr >> 16) & 0o170000
                if mode and mode != stat.S_IFREG:
                    raise InstallError("runtime ZIP contains a non-regular member")
                relative = Path(*path.parts[1:])
                if not relative or relative in {Path("."), Path("..") }:
                    raise InstallError("runtime ZIP root is invalid")
                destination = temporary / relative
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    raise InstallError("runtime ZIP contains duplicate paths")
                with bundle.open(member) as src, destination.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                os.chmod(destination, 0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
        os.replace(temporary, target)
        for path in (target, *sorted(target.rglob("*"))):
            if path.is_dir() and not path.is_symlink():
                os.chmod(path, 0o755)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def nonzero_payout(env: dict[str, str]) -> str:
    value = env.get("POOL_COINBASE_ADDRESS") or env.get("MINING_POOL_ADDRESS") or ""
    if not HEX_ADDRESS.fullmatch(value) or int(value[2:], 16) == 0:
        raise InstallError("pool/all-in-one requires an owner-supplied non-zero payout address")
    return value


def require_values(env: dict[str, str], keys: Iterable[str], mode: str) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        raise InstallError(f"{mode} owner env is missing required values: {', '.join(missing)}")


def require_complete_pair(env: dict[str, str], user_key: str, pass_key: str, label: str) -> None:
    user_set = bool(env.get(user_key))
    pass_set = bool(env.get(pass_key))
    if user_set != pass_set:
        raise InstallError(f"{label} credentials must be provided as a complete pair")


def validate_credential_pairs(env: dict[str, str], mode: str) -> None:
    require_complete_pair(env, "NODE_RPC_USER", "NODE_RPC_PASS", "primary RPC")
    require_complete_pair(env, "NODE_RPC_LIMIT_USER", "NODE_RPC_LIMIT_PASS", "limited RPC")
    if mode in {"node", "all-in-one", "pool"}:
        require_values(env, ("NODE_RPC_USER", "NODE_RPC_PASS"), mode)
    if mode == "redis-dash":
        require_values(env, ("NODE_RPC_LIMIT_USER", "NODE_RPC_LIMIT_PASS"), mode)


def validate_owner_config(env: dict[str, str], mode: str) -> str | None:
    validate_credential_pairs(env, mode)
    if mode in {"pool", "all-in-one"}:
        require_values(env, ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"), mode)
        payout = nonzero_payout(env)
        env["MINING_POOL_ADDRESS"] = env.get("MINING_POOL_ADDRESS") or payout
        env["POOL_COINBASE_ADDRESS"] = env.get("POOL_COINBASE_ADDRESS") or payout
    else:
        # Node and observer modes do not acquire payout authority.
        env["MINING_POOL_ADDRESS"] = ""
        env["POOL_COINBASE_ADDRESS"] = ""
        for key in ("PG_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
            env.pop(key, None)
    if mode == "pool":
        endpoint = env.get("NODE_RPC_URL", "")
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise InstallError("pool requires an explicit credential-free NODE_RPC_URL")
        return endpoint
    if mode == "redis-dash":
        require_values(env, ("NODE_RPC_LIMIT_USER", "NODE_RPC_LIMIT_PASS", "BDAG_NODE_RPC_URL"), mode)
        parsed = urllib.parse.urlparse(env["BDAG_NODE_RPC_URL"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise InstallError("redis-dash observer URL must be an explicit credential-free HTTP URL")
        return None
    return "http://127.0.0.1:38131/"


def compose_environment(record_root: Path, target: Path, mode: str, owner_env: dict[str, str], platform_id: str) -> dict[str, str]:
    context = target / "compose-context"
    defaults = parse_defaults(context / ".env.example")
    merged = {**defaults, **owner_env}
    validate_credential_pairs(merged, mode)
    if mode != "redis-dash":
        # Compose parses every service while rendering, including the
        # dashboard's limited observer fields.  These are fresh target-local
        # observer credentials, never an admin fallback and never printed.
        merged["NODE_RPC_LIMIT_USER"] = merged.get("NODE_RPC_LIMIT_USER") or "bdag_rc2_observer"
        merged["NODE_RPC_LIMIT_PASS"] = merged.get("NODE_RPC_LIMIT_PASS") or secrets.token_urlsafe(24)
    endpoint = validate_owner_config(merged, mode)
    merged["BDAG_STACK_HOST_ROOT"] = str(target)
    merged["BDAG_RUNTIME_DIR"] = str(target / "ops" / "runtime")
    merged["NODE_DATA_DIR"] = str(Path(merged.get("NODE_DATA_DIR") or (target / "node-data")).expanduser())
    if not Path(merged["NODE_DATA_DIR"]).is_absolute():
        merged["NODE_DATA_DIR"] = str((target / merged["NODE_DATA_DIR"]).resolve())
    merged["SNAPSHOT_HOST_PATH"] = str(context / "docker" / "no-snapshot.marker")
    merged["DOCKER_PLATFORM"] = platform_id
    merged["BDAG_STACK_RELEASE_TAG"] = merged.get("BDAG_STACK_RELEASE_TAG") or "stack-dev-v2.1.0-rc.2"
    merged["BDAG_RELEASE_VERSION"] = VERSION
    # Compose's profile is removed from the rendered JSON, but setting this
    # makes the initial config command include pool services when needed.
    merged["COMPOSE_PROJECT_NAME"] = f"bdag-rc2-{hashlib.sha256(str(target).encode()).hexdigest()[:12]}"
    if mode == "pool":
        # Template loopback defaults must not silently redirect a remote pool.
        # An explicitly supplied owner list remains authoritative.
        for key in ("NODE_RPC_URLS", "POOL_SUBMIT_RPC_URLS"):
            if not owner_env.get(key):
                merged[key] = endpoint or ""
    if mode in {"node", "all-in-one"}:
        node_conf = context / "node.conf"
        source = context / "node.conf.example"
        if not source.is_file() or source.is_symlink():
            raise InstallError("runtime ZIP lacks node.conf.example")
        lines = source.read_text(encoding="utf-8").splitlines()
        replaced = {"rpcuser": False, "rpcpass": False, "rpclimituser": False, "rpclimitpass": False}
        result = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key == "rpcuser":
                result.append(f"rpcuser={merged['NODE_RPC_USER']}")
                replaced[key] = True
            elif key == "rpcpass":
                result.append(f"rpcpass={merged['NODE_RPC_PASS']}")
                replaced[key] = True
            elif key == "rpclimituser":
                result.append(f"rpclimituser={merged['NODE_RPC_LIMIT_USER']}")
                replaced[key] = True
            elif key == "rpclimitpass":
                result.append(f"rpclimitpass={merged['NODE_RPC_LIMIT_PASS']}")
                replaced[key] = True
            else:
                result.append(line)
        if not all(replaced.values()):
            raise InstallError("node.conf.example lacks RPC credential fields")
        node_conf.write_text("\n".join(result) + "\n", encoding="utf-8")
        os.chmod(node_conf, 0o600)
    (target / "ops" / "runtime").mkdir(mode=0o700, parents=True, exist_ok=True)
    write_env(target / ".env", merged)
    return merged


def render_compose(target: Path, mode: str, env_values: dict[str, str]) -> dict[str, Any]:
    context = target / "compose-context"
    source = context / "docker-compose.yml"
    if not source.is_file() or source.is_symlink():
        raise InstallError("runtime ZIP lacks docker-compose.yml")
    project = env_values["COMPOSE_PROJECT_NAME"]
    proc_env = os.environ.copy()
    for key in env_values:
        proc_env.pop(key, None)
    def config_document(compose_file: Path, *, profile: bool) -> dict[str, Any]:
        command = [
            "docker", "compose", "--project-directory", str(context),
            "--project-name", project, "--env-file", str(target / ".env"), "-f", str(compose_file),
        ]
        if profile and mode in {"pool", "all-in-one"}:
            command += ["--profile", "pool"]
        command += ["config", "--format", "json"]
        try:
            completed = subprocess.run(command, env=proc_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InstallError("docker compose config could not be executed") from exc
        if completed.returncode != 0:
            raise InstallError("docker compose config rejected the owner configuration")
        try:
            return json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InstallError("docker compose config did not return JSON") from exc

    document = config_document(source, profile=True)
    services = document.get("services")
    if not isinstance(services, dict):
        raise InstallError("docker compose config has no services object")
    selected_services = {"postgres": "pool-db"}
    wanted = {selected_services.get(name, name) for name in MODE_SERVICES[mode]}
    if not wanted.issubset(services):
        raise InstallError("docker compose config lacks a selected service")
    narrowed: dict[str, Any] = {}
    for name in wanted:
        service = dict(services[name])
        service.pop("container_name", None)
        service.pop("profiles", None)
        dependencies = service.get("depends_on")
        if isinstance(dependencies, dict):
            dependencies = {dep: value for dep, value in dependencies.items() if dep in wanted}
            if dependencies:
                service["depends_on"] = dependencies
            else:
                service.pop("depends_on", None)
        elif isinstance(dependencies, list):
            dependencies = [dep for dep in dependencies if dep in wanted]
            if dependencies:
                service["depends_on"] = dependencies
            else:
                service.pop("depends_on", None)
        narrowed[name] = service
    document["services"] = {name: narrowed[name] for name in sorted(narrowed)}
    volumes = document.get("volumes")
    if isinstance(volumes, dict):
        used = set()
        for service in narrowed.values():
            for mount in service.get("volumes", []) if isinstance(service.get("volumes"), list) else []:
                if isinstance(mount, dict) and isinstance(mount.get("source"), str) and mount["source"] in volumes:
                    used.add(mount["source"])
                elif isinstance(mount, str):
                    source_name = mount.split(":", 1)[0]
                    if source_name in volumes:
                        used.add(source_name)
        document["volumes"] = {name: values for name, values in volumes.items() if name in used}
        for name, values in document["volumes"].items():
            if isinstance(values, dict):
                values.pop("external", None)
                values["name"] = f"{project}_{name}"
    compose_path = target / "compose.json"
    write_json(compose_path, document, 0o600)
    # Re-read generated Compose JSON through the real parser. This catches
    # dotenv interpolation/quoting changes before the runner uses compose.json.
    reread = config_document(compose_path, profile=False)
    if not isinstance(reread.get("services"), dict) or not wanted.issubset(reread["services"]):
        raise InstallError("docker compose re-read lacks a selected service")
    write_json(compose_path, reread, 0o600)
    return reread


def invoke_stack(target: Path, operation: str, mode: str, record_root: Path, tuple_path: Path,
                 catalog_path: Path, identity_path: Path | None, endpoint: str | None,
                 selections: dict[str, Any], *, plan_path: Path | None = None) -> None:
    stack = target / "compose-context" / "scripts" / "bdag-stack"
    regular(stack, "shipped bdag-stack")
    if identity_path is not None:
        regular(identity_path, "Core identity")
    command = [sys.executable, str(stack), operation, "--root", str(record_root),
               "--catalog", str(catalog_path), "--tuple", str(tuple_path), "--mode", mode]
    if endpoint is not None:
        command += ["--core-endpoint", endpoint]
    if identity_path is not None:
        command += ["--core-identity", str(identity_path), "--expected-chain-identity", str(identity_path)]
    for component in MODE_COMPONENTS[mode]:
        command += ["--artifact", f"{component}={selections[component]['artifact_id']}" ]
    lock = target / "deployment-lock.json"
    if lock.exists() and not lock.is_symlink():
        command += ["--current-lock", str(lock)]
    if operation == "plan":
        assert plan_path is not None
        command += ["--output", str(plan_path)]
    elif operation == "install":
        command += ["--stage-root", str(target.with_name(target.name + ".v2-stage")), "--plan", str(plan_path)]
    elif operation == "apply":
        command += ["--stage-root", str(target.with_name(target.name + ".v2-stage")), "--target-root", str(target),
                    "--plan", str(plan_path), "--config", str(target / "target-local-config.v2"),
                    "--service-runner", str(target / "service-runner.py"), "--lock-output", str(lock)]
    elif operation == "boot":
        command += ["--target-root", str(target), "--config", str(target / "target-local-config.v2"),
                    "--service-runner", str(target / "service-runner.py"), "--lock-output", str(lock)]
    proc_env = os.environ.copy()
    proc_env["BDAG_INSTALL_RUNNER_PATH"] = str(target / "service-runner.py")
    proc_env["BDAG_INSTALL_PIN"] = str(target / "install-pin.json")
    for key in parse_env(target / ".env"):
        proc_env.pop(key, None)
    if operation == "boot" and endpoint is not None:
        # The frozen v2 validator has no credential CLI. Supply transport auth
        # to its exact identity request without modifying its source/checks.
        command = [sys.executable, str(Path(__file__).resolve()), "_authenticated-v2",
                   str(stack), str(target / ".env"), endpoint, *command[2:]]
    try:
        completed = subprocess.run(command, env=proc_env, cwd=str(target), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, check=False, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"shipped bdag-stack {operation} could not be executed") from exc
    diagnostic = target / f".v2-{operation}.log"
    descriptor = os.open(diagnostic, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as log:
        log.write(completed.stdout)
        log.write(completed.stderr)
    if completed.returncode != 0:
        raise InstallError(f"shipped bdag-stack {operation} failed; private diagnostic: {diagnostic}")


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    record_root = directory(Path(args.record_root), "record root")
    record_path = regular(Path(args.release_record), "release record")
    target = directory(Path(args.target), "target", must_exist=False)
    owner = parse_env(Path(args.owner_env))
    # Validate owner inputs BEFORE combining template defaults. Example payout
    # addresses and passwords must never satisfy an owner-authority requirement.
    validate_owner_config(owner, args.mode)
    record = load_release(record_path)
    mode = args.mode
    plat = platform_name(args.platform)
    selected = verify_record_root(record_root, record_path, record, mode, plat)
    full_source = verify_artifact(record_root, selected["full stack"])
    target.parent.mkdir(mode=0o755, exist_ok=True)
    target.mkdir(mode=0o700)
    safe_extract_zip(full_source, target / "compose-context")
    env_values = compose_environment(record_root, target, mode, owner, plat)
    render_compose(target, mode, env_values)
    shutil.copy2(target / "compose-context" / "scripts" / "bdag-stack", target / "bdag-stack")
    os.chmod(target / "bdag-stack", 0o700)
    identity = record["dataset"]["chain_identity"]
    identity_path = target / "core-identity.json"
    if mode != "redis-dash":
        write_json(identity_path, identity)
    endpoint = validate_owner_config(env_values, mode)
    config = {
        "schema": "bdag.target-local-config.v2", "mode": mode,
        "core_endpoint": endpoint,
        "components": {component: {"path": f"components/{component}/current", "artifact_sha256": selected[component]["sha256"]}
                        for component in MODE_COMPONENTS[mode]},
    }
    write_json(target / "target-local-config.v2", config)
    target.with_name(target.name + ".v2-stage").mkdir(mode=0o700)
    plan = target / "plan.json"
    catalog = record_root / "component-catalog.json"
    tuple_path = record_root / "release-tuple.json"
    regular(catalog, "component catalog")
    regular(tuple_path, "release tuple")
    invoke_stack(target, "verify", mode, record_root, tuple_path, catalog, identity_path if mode != "redis-dash" else None, endpoint, selected)
    invoke_stack(target, "plan", mode, record_root, tuple_path, catalog, identity_path if mode != "redis-dash" else None, endpoint, selected, plan_path=plan)
    invoke_stack(target, "install", mode, record_root, tuple_path, catalog, identity_path if mode != "redis-dash" else None, endpoint, selected, plan_path=plan)
    # The runner is copied only after the selected full ZIP has been checked.
    runner_source = Path(__file__).with_name("service-runner.py")
    regular(runner_source, "service runner source")
    runner_target = target / "service-runner.py"
    shutil.copyfile(runner_source, runner_target)
    os.chmod(runner_target, 0o700)
    runner_config = {
        "schema": "bdag.rc2-service-runner.v1", "target": str(target),
        "project": env_values["COMPOSE_PROJECT_NAME"], "compose": str(target / "compose.json"),
        "env_file": str(target / ".env"), "services": list(MODE_SERVICES[mode]),
    }
    write_json(target / "runner-config.json", runner_config)
    pin = {
        "schema": "bdag.rc2-install-pin.v1", "version": VERSION, "mode": mode,
        "platform": plat, "record_sha256": RELEASE_RECORD_SHA256,
        "release_tuple_sha256": digest(tuple_path), "target_local_config_sha256": digest(target / "target-local-config.v2"),
        "compose_sha256": digest(target / "compose.json"), "env_sha256": digest(target / ".env"),
        "runner_sha256": digest(runner_target), "runner_config_sha256": digest(target / "runner-config.json"),
        "full_runtime_zip_sha256": selected["full stack"]["sha256"],
        "components": {component: {"artifact_id": plat, "artifact_sha256": selected[component]["sha256"]}
                        for component in MODE_COMPONENTS[mode]},
    }
    # Apply's real V2 stop boundary uses the runner before apply commits its
    # deployment lock, so the runner pin must exist before that invocation.
    write_json(target / "install-pin.json", pin)
    # Apply is intentionally separate from boot, but it does call the real
    # runner's stop boundary as required by the shipped V2 transaction.
    invoke_stack(target, "apply", mode, record_root, tuple_path, catalog, identity_path if mode != "redis-dash" else None, endpoint, selected, plan_path=plan)
    # Apply must not mutate any pinned input; rewrite the same canonical pin as
    # a readback guard after the V2 lock has been committed.
    write_json(target / "install-pin.json", pin)
    return {"status": "prepared", "mode": mode, "platform": plat, "target": str(target), "booted": False,
            "record_sha256": RELEASE_RECORD_SHA256, "components": list(MODE_COMPONENTS[mode])}


def verify_pin(target: Path, *, require_runner: bool = True) -> dict[str, Any]:
    pin_path = regular(target / "install-pin.json", "install pin")
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    if (pin.get("schema") != "bdag.rc2-install-pin.v1" or pin.get("version") != VERSION
            or pin.get("record_sha256") != RELEASE_RECORD_SHA256 or pin.get("mode") not in MODES
            or pin.get("platform") not in {"linux-amd64", "linux-arm64"}):
        raise InstallError("install pin is not the protected RC2 pin")
    checks = [(target / "compose.json", "compose_sha256"), (target / ".env", "env_sha256"),
              (target / "target-local-config.v2", "target_local_config_sha256"),
              (target / "runner-config.json", "runner_config_sha256")]
    if require_runner:
        checks.append((target / "service-runner.py", "runner_sha256"))
    for path, key in checks:
        regular(path, key)
        if digest(path) != pin.get(key):
            raise InstallError(f"pinned {key} changed")
    return pin


def start(args: argparse.Namespace) -> dict[str, Any]:
    target = directory(Path(args.target), "target")
    pin = verify_pin(target)
    # Reuse the shipped bdag-stack boot path, which revalidates the target lock,
    # selected archives, target config and live Core identity where applicable.
    record_root = directory(Path(args.record_root), "record root")
    record_path = regular(Path(args.release_record), "release record")
    record = load_release(record_path)
    if digest(record_path) != pin["record_sha256"]:
        raise InstallError("release record changed after prepare")
    mode = pin["mode"]
    selected = verify_record_root(record_root, record_path, record, mode, pin["platform"])
    endpoint = None if mode == "redis-dash" else (parse_env(target / ".env").get("NODE_RPC_URL") if mode == "pool" else "http://127.0.0.1:38131/")
    identity_path = target / "core-identity.json" if mode != "redis-dash" else None
    invoke_stack(target, "boot", mode, record_root, record_root / "release-tuple.json", record_root / "component-catalog.json",
                 identity_path, endpoint, selected)
    return {"status": "booted", "mode": mode, "target": str(target), "booted": True,
            "services": list(MODE_SERVICES[mode]), "record_sha256": pin["record_sha256"]}


def stop(args: argparse.Namespace) -> dict[str, Any]:
    target = directory(Path(args.target), "target")
    pin = verify_pin(target, require_runner=False)
    runner = target / "service-runner.py"
    regular(runner, "service runner")
    try:
        completed = subprocess.run([sys.executable, str(runner), "stop"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, check=False, timeout=120,
                                   env={**os.environ, "BDAG_INSTALL_PIN": str(target / "install-pin.json")})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("service stop could not be executed") from exc
    if completed.returncode != 0:
        raise InstallError("service stop failed")
    return {"status": "stopped", "mode": pin["mode"], "target": str(target), "booted": False}


def status(args: argparse.Namespace) -> dict[str, Any]:
    target = directory(Path(args.target), "target")
    pin = verify_pin(target, require_runner=False)
    runner = target / "service-runner.py"
    try:
        completed = subprocess.run([sys.executable, str(runner), "status"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, check=False, timeout=120,
                                   env={**os.environ, "BDAG_INSTALL_PIN": str(target / "install-pin.json")})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("service status could not be executed") from exc
    if completed.returncode != 0:
        raise InstallError("service status failed")
    try:
        services = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallError("service runner returned invalid status JSON") from exc
    return {"status": "status", "mode": pin["mode"], "target": str(target), "services": services}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare and run a private BlockDAG RC2 V2 installation")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("prepare", "start"):
        q = sub.add_parser(command)
        q.add_argument("--record-root", required=True)
        q.add_argument("--release-record", required=True)
        q.add_argument("--target", required=True)
        if command == "prepare":
            q.add_argument("--mode", required=True, choices=sorted(MODES))
            q.add_argument("--owner-env", required=True)
            q.add_argument("--platform", choices=("linux-amd64", "linux-arm64"))
    for command in ("stop", "status"):
        q = sub.add_parser(command)
        q.add_argument("--target", required=True)
    return p


class IdentityAuth(urllib.request.BaseHandler):
    """Credentials apply only to the exact owner-selected identity request."""
    handler_order = 100

    def __init__(self, endpoint: str, user: str, password: str):
        self.endpoint = endpoint
        self.authorization = "Basic " + base64.b64encode((user + ":" + password).encode()).decode()

    def http_request(self, request):
        if request.full_url != self.endpoint or request.get_method() != "POST":
            raise InstallError("unexpected request in identity-only transport")
        if json.loads(request.data or b"null") != {"jsonrpc": "2.0", "id": 1, "method": "getChainIdentity", "params": []}:
            raise InstallError("unexpected method in identity-only transport")
        request.add_unredirected_header("Authorization", self.authorization)
        return request

    https_request = http_request


class NoIdentityRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise InstallError("Core identity redirects are not permitted")


def authenticated_v2(arguments: list[str]) -> int:
    script, env_path, endpoint, *stack_args = arguments
    values = parse_env(Path(env_path))
    require_values(values, ("NODE_RPC_USER", "NODE_RPC_PASS"), "Core identity")
    urllib.request.install_opener(urllib.request.build_opener(
        IdentityAuth(endpoint, values["NODE_RPC_USER"], values["NODE_RPC_PASS"]), NoIdentityRedirect()))
    sys.path.insert(0, str(Path(script).parent))
    sys.argv = [script, *stack_args]
    runpy.run_path(script, run_name="__main__")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        if (argv if argv is not None else sys.argv[1:])[:1] == ["_authenticated-v2"]:
            return authenticated_v2((argv if argv is not None else sys.argv[1:])[1:])
        args = parser().parse_args(argv)
        result = {"prepare": prepare, "start": start, "stop": stop, "status": status}[args.command](args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (InstallError, OSError, ValueError) as exc:
        print(f"bdag-install: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
