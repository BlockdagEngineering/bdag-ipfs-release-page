#!/usr/bin/env python3
"""Fast unit coverage for the private RC2 installer boundary."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "releases/2.1.0-rc.2/install-v1/bdag-install.py"
SPEC = importlib.util.spec_from_file_location("bdag_install_rc2", SCRIPT)
assert SPEC and SPEC.loader
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)
RUNNER_SCRIPT = SCRIPT.with_name("service-runner.py")
RUNNER_SPEC = importlib.util.spec_from_file_location("bdag_service_runner_rc2", RUNNER_SCRIPT)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


class InstallerTests(unittest.TestCase):
    def test_mode_contracts_are_independent(self):
        self.assertEqual(INSTALL.MODE_COMPONENTS["node"], ("corechain", "stack"))
        self.assertEqual(INSTALL.MODE_COMPONENTS["pool"], ("pool", "stack"))
        self.assertEqual(INSTALL.MODE_COMPONENTS["redis-dash"], ("dashboard", "stack"))
        self.assertEqual(INSTALL.MODE_SERVICES["all-in-one"], ("node", "pool", "postgres", "dashboard"))
        self.assertNotIn("node", INSTALL.MODE_SERVICES["redis-dash"])

    def test_owner_values_are_required_and_payout_is_not_in_node(self):
        node = {"NODE_RPC_USER": "u", "NODE_RPC_PASS": "p"}
        self.assertEqual(INSTALL.validate_owner_config(node, "node"), "http://127.0.0.1:38131/")
        self.assertEqual(node["MINING_POOL_ADDRESS"], "")
        self.assertEqual(node["POOL_COINBASE_ADDRESS"], "")
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.validate_owner_config({"NODE_RPC_USER": "u", "NODE_RPC_PASS": "p"}, "pool")

    def test_pool_and_observer_authority_are_explicit(self):
        pool = {
            "NODE_RPC_USER": "u", "NODE_RPC_PASS": "p", "NODE_RPC_URL": "http://core.example:38131/",
            "POSTGRES_USER": "db", "POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "pool",
            "MINING_POOL_ADDRESS": "0x1111111111111111111111111111111111111111",
        }
        self.assertEqual(INSTALL.validate_owner_config(pool, "pool"), pool["NODE_RPC_URL"])
        observer = {"NODE_RPC_LIMIT_USER": "u", "NODE_RPC_LIMIT_PASS": "p", "BDAG_NODE_RPC_URL": "http://observer:38131/"}
        self.assertIsNone(INSTALL.validate_owner_config(observer, "redis-dash"))
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.validate_owner_config({**observer, "BDAG_NODE_RPC_URL": "http://u:p@observer/"}, "redis-dash")

    def test_safe_extract_rejects_existing_target_and_traversal(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "runtime.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("payload/docker-compose.yml", "services: {}")
            target = root / "target"
            INSTALL.safe_extract_zip(archive, target)
            self.assertEqual((target / "docker-compose.yml").read_text(), "services: {}")
            with self.assertRaises(INSTALL.InstallError):
                INSTALL.safe_extract_zip(archive, target)
            bad = root / "bad.zip"
            with zipfile.ZipFile(bad, "w") as zf:
                zf.writestr("payload/../../escape", "x")
            with self.assertRaises(INSTALL.InstallError):
                INSTALL.safe_extract_zip(bad, root / "bad-target")

    def test_render_compose_narrows_services_dependencies_and_names(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            context = target / "compose-context"
            context.mkdir()
            (context / "docker-compose.yml").write_text("services: {}")
            (target / ".env").write_text("POSTGRES_PASSWORD=secret\n")
            document = {
                "services": {
                    "node": {"container_name": "node", "profiles": ["x"], "volumes": []},
                    "pool": {"container_name": "pool", "depends_on": {"pool-db": {"condition": "service_healthy"}}, "volumes": []},
                    "pool-db": {"container_name": "postgres", "profiles": ["pool"], "volumes": [{"type": "volume", "source": "postgres-data", "target": "/var/lib/postgresql/data"}]},
                    "dashboard": {"container_name": "dashboard", "depends_on": {"node": {"condition": "service_started"}, "pool": {"required": False}}, "volumes": []},
                },
                "volumes": {"postgres-data": {"name": "postgres-data"}, "unused": {"name": "unused"}},
            }
            fake = mock.Mock(returncode=0, stdout=json.dumps(document).encode(), stderr=b"")
            with mock.patch.object(INSTALL.subprocess, "run", return_value=fake):
                rendered = INSTALL.render_compose(target, "pool", {"COMPOSE_PROJECT_NAME": "bdag-test"})
            self.assertEqual(set(rendered["services"]), {"pool", "pool-db"})
            self.assertNotIn("container_name", rendered["services"]["pool-db"])
            self.assertNotIn("profiles", rendered["services"]["pool-db"])
            self.assertEqual(set(rendered["services"]["pool"]["depends_on"]), {"pool-db"})
            self.assertEqual(set(rendered["volumes"]), {"postgres-data"})
            self.assertEqual(rendered["volumes"]["postgres-data"]["name"], "bdag-test_postgres-data")

    def test_render_dashboard_removes_excluded_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "compose-context").mkdir()
            (target / "compose-context/docker-compose.yml").write_text("services: {}")
            (target / ".env").write_text("NODE_RPC_LIMIT_USER=u\n")
            document = {"services": {"dashboard": {"depends_on": {"node": {"condition": "service_started"}, "pool": {"required": False}}, "volumes": []}, "node": {"volumes": []}}}
            fake = mock.Mock(returncode=0, stdout=json.dumps(document).encode(), stderr=b"")
            with mock.patch.object(INSTALL.subprocess, "run", return_value=fake):
                rendered = INSTALL.render_compose(target, "redis-dash", {"COMPOSE_PROJECT_NAME": "bdag-test"})
            self.assertEqual(set(rendered["services"]), {"dashboard"})
            self.assertNotIn("depends_on", rendered["services"]["dashboard"])

    def test_service_runner_maps_postgres_without_shell_hooks(self):
        source = RUNNER_SCRIPT.read_text()
        self.assertIn('ALIASES = {"postgres": "pool-db"}', source)
        self.assertIn('"--build", "--pull", "never", "--no-recreate"', source)
        self.assertNotIn("shell=True", source)

    def test_node_start_waits_for_delayed_pinned_identity_with_owner_auth(self):
        expected = {"schema": "bdag.chain-identity.v1", "network": "mainnet", "native_network_magic": "0xb4c3dce8",
                    "native_genesis_hash": "0xnative", "evm_chain_id": "1404", "evm_genesis_hash": "0xevm"}

        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return json.dumps({"jsonrpc": "2.0", "id": 1, "result": expected}).encode()

        requests = []
        calls = {"count": 0}

        def delayed(request, timeout):
            requests.append(request)
            calls["count"] += 1
            if calls["count"] < 3:
                raise urllib.error.URLError("not ready")
            return Response()

        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "core-identity.json").write_bytes(INSTALL.canonical(expected))
            (target / ".env").write_text("NODE_RPC_USER=owner\nNODE_RPC_PASS=local-test-only\n")
            with mock.patch.object(RUNNER.urllib.request, "urlopen", side_effect=delayed), \
                 mock.patch.object(RUNNER.time, "sleep", return_value=None):
                RUNNER.wait_for_core_identity(target, "http://127.0.0.1:38131/", timeout_seconds=1)
            self.assertEqual(calls["count"], 3)
            self.assertTrue(requests[-1].get_header("Authorization").startswith("Basic "))
            self.assertIn("ready after 3", (target / ".core-readiness.log").read_text())

    def test_wrong_identity_fails_closed_and_writes_private_diagnostic(self):
        expected = {"schema": "bdag.chain-identity.v1", "network": "mainnet"}
        wrong = {"schema": "bdag.chain-identity.v1", "network": "other"}

        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return json.dumps({"jsonrpc": "2.0", "id": 1, "result": wrong}).encode()

        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "core-identity.json").write_bytes(INSTALL.canonical(expected))
            (target / ".env").write_text("NODE_RPC_USER=owner\nNODE_RPC_PASS=local-test-only\n")
            with mock.patch.object(RUNNER.urllib.request, "urlopen", return_value=Response()):
                with self.assertRaises(RUNNER.RunnerError):
                    RUNNER.wait_for_core_identity(target, "http://127.0.0.1:38131/", timeout_seconds=1)
            diagnostic = target / ".core-readiness.log"
            self.assertEqual(diagnostic.stat().st_mode & 0o777, 0o600)
            self.assertIn("mismatch", diagnostic.read_text())

    def test_canonical_metadata_includes_required_lf(self):
        self.assertEqual(INSTALL.canonical({"b": 2, "a": 1}), b'{"a":1,"b":2}\n')

    def test_auth_transport_is_exact_endpoint_and_method_only(self):
        handler = INSTALL.IdentityAuth("http://127.0.0.1:38131/", "owner", "test-only")
        body = INSTALL.canonical({"jsonrpc":"2.0","id":1,"method":"getChainIdentity","params":[]})
        request = INSTALL.urllib.request.Request(handler.endpoint, data=body)
        self.assertTrue(handler.http_request(request).get_header("Authorization").startswith("Basic "))
        self.assertNotIn("Authorization", request.headers)  # Not forwarded by ordinary redirects.
        with self.assertRaises(INSTALL.InstallError):
            handler.http_request(INSTALL.urllib.request.Request("https://unrelated.invalid/", data=body))
        with self.assertRaises(INSTALL.InstallError):
            handler.http_request(INSTALL.urllib.request.Request(handler.endpoint, data=body.replace(b'getChainIdentity', b'submitBlock')))


if __name__ == "__main__":
    unittest.main()
