import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import socketserver
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "releases/2.1.0-rc.2/install-v1/bdag-download.py"
CID = "bafybeiaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    payloads = {}
    ignored_ranges = set()
    corrupt = set()
    interrupted = set()
    truncated = set()
    overlong = set()
    counts = {}
    request_versions = {}

    def do_GET(self):  # noqa: N802
        FixtureHandler.counts[self.path] = FixtureHandler.counts.get(self.path, 0) + 1
        FixtureHandler.request_versions.setdefault(self.path, []).append(self.request_version)
        if self.path not in self.payloads:
            self.send_error(404)
            return
        body = self.payloads[self.path]
        range_header = self.headers.get("Range")
        start = 0
        if range_header and self.path not in self.ignored_ranges:
            start = int(range_header.removeprefix("bytes=" ).split("-", 1)[0])
        status = 206 if start else 200
        response = body[start:]
        if self.path in self.corrupt:
            response = bytes([response[0] ^ 1]) + response[1:] if response else response
        if self.path in self.truncated:
            response = response[: max(1, len(response) // 2)]
        if self.path in self.overlong:
            response = response + b"wrapper-overlong"
        self.send_response(status)
        self.send_header("Content-Length", str(len(response)))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(body)-1}/{len(body)}")
        self.end_headers()
        if self.path in self.interrupted and FixtureHandler.counts[self.path] == 1:
            self.wfile.write(response[: max(1, len(response) // 2)])
            self.wfile.flush()
            self.connection.shutdown(1)
            return
        try:
            self.wfile.write(response)
        except ConnectionResetError:
            # The client deliberately closes after rejecting an overlong body.
            pass

    def log_message(self, *_args):
        return


class Server:
    def __enter__(self):
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FixtureHandler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entry(path, group, body, url_path, *, parts=None):
    value = {
        "path": path,
        "group": group,
        "bytes": len(body),
        "sha256": digest(body),
        "ipfs": f"/ipfs/{CID}/{urlparse(url_path).path.lstrip('/') or path}",
        "urls": [url_path],
    }
    if parts is not None:
        value["parts"] = parts
    return value


def write_manifest(directory, files):
    manifest = {"schema": "blockdag.downloads/v1", "files": files}
    path = Path(directory) / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    return path, digest(path.read_bytes())


def run_cli(manifest, expected, output, *extra, env=None):
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(
        ["python3", str(SCRIPT), "--manifest", str(manifest), "--expect-manifest-sha256", expected,
         "--output-dir", str(output), *extra], capture_output=True, text=True, timeout=20,
        env=process_env,
    )


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        FixtureHandler.payloads = {}
        FixtureHandler.ignored_ranges = set()
        FixtureHandler.corrupt = set()
        FixtureHandler.interrupted = set()
        FixtureHandler.truncated = set()
        FixtureHandler.overlong = set()
        FixtureHandler.counts = {}
        FixtureHandler.request_versions = {}

    def test_http_resume_with_valid_content_range(self):
        body = b"software-body-" * 90000
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/software.tar.gz"; FixtureHandler.payloads[route] = body
            files = [entry("artifacts/software.tar.gz", "software", body, server.base + route)]
            manifest, expected = write_manifest(temporary, files)
            output = Path(temporary) / "out"; (output / "artifacts").mkdir(parents=True)
            partial = output / "artifacts/software.tar.gz.partial"; partial.write_bytes(body[:100000])
            result = run_cli(manifest, expected, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "artifacts/software.tar.gz").read_bytes(), body)
            self.assertGreaterEqual(FixtureHandler.counts[route], 1)

    def test_ignored_range_restarts_safely(self):
        body = b"ignored-range" * 80000
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/ignored.bin"; FixtureHandler.payloads[route] = body; FixtureHandler.ignored_ranges.add(route)
            files = [entry("ignored.bin", "software", body, server.base + route)]
            manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
            (output / "ignored.bin.partial").write_bytes(body[:40000])
            result = run_cli(manifest, expected, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "ignored.bin").read_bytes(), body)

    def test_interrupted_response_resumes(self):
        body = b"interrupted" * 70000
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/interrupted.bin"; FixtureHandler.payloads[route] = body; FixtureHandler.interrupted.add(route)
            files = [entry("interrupted.bin", "software", body, server.base + route)]
            manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
            result = run_cli(manifest, expected, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "interrupted.bin").read_bytes(), body)
            self.assertGreaterEqual(FixtureHandler.counts[route], 2)
            self.assertTrue(all(version == "HTTP/1.1" for version in FixtureHandler.request_versions[route]))

    def test_http_200_wrapper_truncated_and_overlong_bodies_fail_closed(self):
        body = b"valid-object" * 5000
        for mode in ("truncated", "overlong"):
            with self.subTest(mode=mode), Server() as server, tempfile.TemporaryDirectory() as temporary:
                route = f"/{mode}.bin"; FixtureHandler.payloads[route] = body
                getattr(FixtureHandler, mode).add(route)
                files = [entry(f"{mode}.bin", "software", body, server.base + route)]
                manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
                result = run_cli(manifest, expected, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((output / f"{mode}.bin").exists())

    def test_dataset_parts_assemble_and_retain_verified_pieces(self):
        first = b"first-part" * 50000; second = b"second-part" * 60000; body = first + second
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            r1 = "/dataset.001"; r2 = "/dataset.002"; FixtureHandler.payloads.update({r1: first, r2: second})
            parts = [
                {"name": "dataset.001", "bytes": len(first), "sha256": digest(first), "urls": [server.base + r1]},
                {"name": "dataset.002", "bytes": len(second), "sha256": digest(second), "urls": [server.base + r2]},
            ]
            files = [entry("dataset/snapshot.bdsnap", "dataset", body, server.base + "/dataset", parts=parts)]
            manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
            result = run_cli(manifest, expected, output, "--select", "dataset")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "dataset/snapshot.bdsnap").read_bytes(), body)
            self.assertTrue((output / "dataset/snapshot.bdsnap.parts/dataset.001").is_file())

    def test_corrupt_full_and_part_fail_without_final_output(self):
        body = b"corrupt-me" * 10000
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/bad.bin"; FixtureHandler.payloads[route] = body; FixtureHandler.corrupt.add(route)
            files = [entry("bad.bin", "software", body, server.base + route)]
            manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
            result = run_cli(manifest, expected, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / "bad.bin").exists())
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            first = b"part-one" * 20000; second = b"part-two" * 20000; body = first + second
            r1 = "/bad.001"; r2 = "/good.002"; FixtureHandler.payloads.update({r1: first, r2: second}); FixtureHandler.corrupt.add(r1)
            parts = [{"name": "bad.001", "bytes": len(first), "sha256": digest(first), "urls": [server.base + r1]},
                     {"name": "good.002", "bytes": len(second), "sha256": digest(second), "urls": [server.base + r2]}]
            files = [entry("dataset/bad.bdsnap", "dataset", body, server.base + "/dataset", parts=parts)]
            manifest, expected = write_manifest(temporary, files); output = Path(temporary) / "out"; output.mkdir()
            result = run_cli(manifest, expected, output, "--select", "dataset")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / "dataset/bad.bdsnap").exists())

    def test_invalid_manifest_hash_unsafe_path_and_symlink_rejected(self):
        body = b"safe"; with_server = None
        with tempfile.TemporaryDirectory() as temporary:
            manifest, expected = write_manifest(temporary, [entry("safe.bin", "software", body, "https://example.test/safe")])
            result = run_cli(manifest, "0" * 64, Path(temporary) / "out")
            self.assertNotEqual(result.returncode, 0)
            unsafe = {"schema": "blockdag.downloads/v1", "files": [dict(entry("../escape", "software", body, "https://example.test/x"))]}
            unsafe_path = Path(temporary) / "unsafe.json"; unsafe_path.write_text(json.dumps(unsafe)); unsafe_hash = digest(unsafe_path.read_bytes())
            self.assertNotEqual(run_cli(unsafe_path, unsafe_hash, Path(temporary) / "unsafe-out").returncode, 0)
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/safe"; FixtureHandler.payloads[route] = body
            manifest, expected = write_manifest(temporary, [entry("sub/safe.bin", "software", body, server.base + route)])
            output = Path(temporary) / "out"; output.mkdir(); outside = Path(temporary) / "outside"; outside.mkdir(); (output / "sub").symlink_to(outside, target_is_directory=True)
            self.assertNotEqual(run_cli(manifest, expected, output).returncode, 0)

    def test_https_redirect_validation_preserves_range_and_rejects_downgrade(self):
        spec = importlib.util.spec_from_file_location("bdag_download", SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

        class RequestFixture:
            full_url = "https://github.com/example/file"
            def header_items(self):
                return [("Host", "github.com"), ("Range", "bytes=12-"), ("User-agent", "test")]
            def get_method(self):
                return "GET"

        handler = module.SafeRedirect()
        redirected = handler.redirect_request(RequestFixture(), None, 302, "Found", {"Location": "https://release-assets.githubusercontent.com/file?sig=opaque"}, "https://release-assets.githubusercontent.com/file?sig=opaque")
        self.assertEqual(redirected.get_header("Range"), "bytes=12-")
        self.assertIsNone(redirected.get_header("Host"))
        with self.assertRaises(module.DownloadError):
            handler.redirect_request(RequestFixture(), None, 302, "Found", {"Location": "http://example.test/file"}, "http://example.test/file")

    def test_http11_connection_and_tls_policy_are_scoped(self):
        spec = importlib.util.spec_from_file_location("bdag_download_tls", SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.HTTP11Connection._http_vsn_str, "HTTP/1.1")
        self.assertEqual(module.HTTP11HTTPSConnection._http_vsn_str, "HTTP/1.1")
        with mock.patch.object(module.ssl.SSLContext, "set_alpn_protocols", autospec=True) as set_alpn:
            context = module._http11_tls_context()
        set_alpn.assert_called_once_with(context, ["http/1.1"])
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, module.ssl.CERT_REQUIRED)

    def test_flock_blocks_concurrent_download_without_stale_lock_deletion(self):
        body = b"locked"; lock_fd = None
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/locked"; FixtureHandler.payloads[route] = body
            manifest, expected = write_manifest(temporary, [entry("locked.bin", "software", body, server.base + route)])
            output = Path(temporary) / "out"; output.mkdir(); target = output / "locked.bin"; lock = Path(str(target) + ".lock")
            lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            result = run_cli(manifest, expected, output)
            self.assertNotEqual(result.returncode, 0)
            fcntl.flock(lock_fd, fcntl.LOCK_UN); os.close(lock_fd); lock_fd = None
            self.assertEqual(run_cli(manifest, expected, output).returncode, 0)
            self.assertTrue(lock.is_file())

    def test_skip_existing_correct_output_and_refuse_mismatch(self):
        body = b"already-correct"
        with Server() as server, tempfile.TemporaryDirectory() as temporary:
            route = "/existing"; FixtureHandler.payloads[route] = body
            manifest, expected = write_manifest(temporary, [entry("existing.bin", "software", body, server.base + route)])
            output = Path(temporary) / "out"; output.mkdir(); (output / "existing.bin").write_bytes(body)
            result = run_cli(manifest, expected, output); self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(FixtureHandler.counts.get(route, 0), 0)
            (output / "existing.bin").write_bytes(b"wrong")
            self.assertNotEqual(run_cli(manifest, expected, output).returncode, 0)

    def test_ipfs_cat_isolated_and_checksum_checked(self):
        body = b"ipfs-payload" * 800
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary); fake_bin = temporary / "bin"; fake_bin.mkdir()
            fake = fake_bin / "ipfs"
            fake.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(" + repr(body) + ")\n")
            fake.chmod(0o700)
            files = [entry("artifacts/ipfs.tar.gz", "software", body, "https://example.test/ipfs")]
            manifest, expected = write_manifest(temporary, files); output = temporary / "out"; output.mkdir()
            result = run_cli(manifest, expected, output, "--transport", "ipfs", env={"PATH": f"{fake_bin}:{os.environ['PATH']}"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "artifacts/ipfs.tar.gz").read_bytes(), body)


if __name__ == "__main__":
    unittest.main()
