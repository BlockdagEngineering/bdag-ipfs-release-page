#!/usr/bin/env python3
"""Private real-Docker runner used by the shipped bdag-stack V2 lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import re


ALLOWED = {"node", "pool", "postgres", "dashboard"}
ALIASES = {"postgres": "pool-db"}
VERSION = "2.1.0-rc.2"
RECORD_SHA256 = "468b9390d209cda3c12453c81642daa6f2e4de1d2ec6e8e8295e23f8b588b0c2"
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class RunnerError(RuntimeError):
    pass


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RunnerError(f"{label} is not a regular file")


def env_keys(path: Path) -> set[str]:
    keys = set()
    regular(path, "environment file")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def load() -> tuple[Path, dict, dict]:
    script = Path(os.environ.get("BDAG_INSTALL_RUNNER_PATH", __file__)).resolve()
    regular(script, "runner")
    target = script.parent
    config_path = target / "runner-config.json"
    pin_path = Path(os.environ.get("BDAG_INSTALL_PIN", str(target / "install-pin.json")))
    regular(config_path, "runner configuration")
    regular(pin_path, "install pin")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    if (config.get("schema") != "bdag.rc2-service-runner.v1"
            or Path(config.get("target", "")).resolve() != target
            or not isinstance(config.get("project"), str)
            or not PROJECT_NAME.fullmatch(config["project"])):
        raise RunnerError("runner configuration target is invalid")
    if (pin.get("schema") != "bdag.rc2-install-pin.v1" or pin.get("version") != VERSION
            or pin.get("record_sha256") != RECORD_SHA256):
        raise RunnerError("install pin schema is invalid")
    if os.environ.get("BDAG_INSTALL_PIN") and Path(os.environ["BDAG_INSTALL_PIN"]).resolve() != pin_path.resolve():
        raise RunnerError("install pin path is not target-local")
    return target, config, pin


def verify_start_pin(target: Path, pin: dict, script: Path) -> None:
    checks = ((target / "compose.json", "compose_sha256"), (target / ".env", "env_sha256"),
              (target / "target-local-config.v2", "target_local_config_sha256"),
              (target / "runner-config.json", "runner_config_sha256"), (script, "runner_sha256"))
    for path, key in checks:
        regular(path, key)
        if file_sha(path) != pin.get(key):
            raise RunnerError(f"pinned {key} changed")


def verify_v2_context(target: Path, pin: dict) -> None:
    mode = os.environ.get("BDAG_MODE")
    if mode is None or any(key not in os.environ for key in ("BDAG_CORE_ENDPOINT", "BDAG_COMPONENT_SELECTION")):
        return
    if mode != pin["mode"]:
        raise RunnerError("V2 mode context differs from the pinned target")
    config = json.loads((target / "target-local-config.v2").read_text(encoding="utf-8"))
    endpoint = config.get("core_endpoint") or ""
    if os.environ.get("BDAG_CORE_ENDPOINT", "") != endpoint:
        raise RunnerError("V2 Core endpoint context differs from the target config")
    raw_selection = os.environ.get("BDAG_COMPONENT_SELECTION", "")
    try:
        selection = json.loads(raw_selection)
    except json.JSONDecodeError as exc:
        raise RunnerError("V2 component selection context is not JSON") from exc
    expected = pin.get("components", {})
    if set(selection) != set(expected):
        raise RunnerError("V2 component selection context differs from the pin")
    for component, value in expected.items():
        selected = selection.get(component, {})
        if selected.get("artifact_id") != value.get("artifact_id") or selected.get("artifact_sha256") != value.get("artifact_sha256"):
            raise RunnerError("V2 component selection context differs from the pin")


def compose_command(target: Path, config: dict) -> list[str]:
    compose = Path(config["compose"])
    env_file = Path(config["env_file"])
    context = target / "compose-context"
    if compose.resolve().parent != target or env_file.resolve().parent != target or not context.is_dir():
        raise RunnerError("runner paths are not target-local")
    regular(compose, "compose file")
    regular(env_file, "environment file")
    return ["docker", "compose", "--project-directory", str(context), "--project-name", config["project"],
            "--env-file", str(env_file), "-f", str(compose)]


def execute(action: str, services: list[str]) -> int:
    target, config, pin = load()
    script = Path(os.environ.get("BDAG_INSTALL_RUNNER_PATH", __file__)).resolve()
    verify_v2_context(target, pin)
    if action == "start":
        verify_start_pin(target, pin, script)
    if action not in {"start", "stop", "status"}:
        raise RunnerError("unsupported service action")
    configured = tuple(config.get("services", ()))
    if not configured or any(service not in ALLOWED for service in configured):
        raise RunnerError("runner service selection is invalid")
    selected = services or list(configured)
    if any(service not in configured for service in selected):
        raise RunnerError("requested service is outside the pinned mode")
    mapped = [ALIASES.get(service, service) for service in selected]
    command = compose_command(target, config)
    if action == "start":
        command += ["up", "-d", "--build", "--pull", "never", "--no-recreate", *mapped]
    elif action == "stop":
        command += ["stop", *mapped]
    else:
        command += ["ps", "--all", "--format", "json"]
    proc_env = os.environ.copy()
    for key in env_keys(target / ".env"):
        proc_env.pop(key, None)
    try:
        completed = subprocess.run(command, env=proc_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   check=False, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError("docker compose invocation failed") from exc
    if completed.returncode != 0:
        raise RunnerError("docker compose returned a failure")
    if action == "status":
        rows = []
        output = completed.stdout.decode("utf-8", "strict").strip()
        values = []
        if output:
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                values = [json.loads(raw) for raw in output.splitlines() if raw.strip()]
            else:
                values = parsed if isinstance(parsed, list) else [parsed]
        for value in values:
            if isinstance(value, dict):
                normalized = {str(key).lower(): item for key, item in value.items()}
                rows.append({key: normalized[key.lower()] for key in ("Name", "Service", "State", "Health")
                             if key.lower() in normalized})
        print(json.dumps(rows, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = list(argv if argv is not None else sys.argv[1:])
        if not args:
            raise RunnerError("action is required")
        return execute(args[0], args[1:])
    except (RunnerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"service-runner: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
