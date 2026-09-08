#!/usr/bin/env python3
"""Small, fail-closed downloader for the RC2 public manifest."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import stat
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


CHUNK = 1024 * 1024
MAX_PART = 1024 * 1024 * 1024
RETRIES = 4
HTTP_TIMEOUT = 20
IPFS_TOTAL_TIMEOUT = 14400
IPFS_INACTIVITY_TIMEOUT = 120
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CID = re.compile(r"^b[a-z2-7]{20,}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


class DownloadError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_reject(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DownloadError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def load_manifest(path: Path, expected_sha: str) -> dict:
    if not HEX64.fullmatch(expected_sha):
        raise DownloadError("--expect-manifest-sha256 must be a lowercase SHA-256")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise DownloadError(f"cannot read manifest: {exc}") from exc
    actual = sha256_bytes(raw)
    if actual != expected_sha:
        raise DownloadError(f"manifest SHA-256 mismatch: {actual}")
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=duplicate_reject)
    except (UnicodeDecodeError, json.JSONDecodeError, DownloadError) as exc:
        raise DownloadError(f"invalid manifest JSON: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def _validate_http_url(value: str) -> None:
    if not isinstance(value, str):
        raise DownloadError("URL must be a string")
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise DownloadError("unsafe download URL")
    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower().rstrip(".")
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise DownloadError("HTTP downgrade is allowed only for loopback fixtures")


def _validate_path(value: str, label: str = "path") -> None:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise DownloadError(f"unsafe {label}")
    raw_parts = value.split("/")
    if value.startswith("/") or value.endswith("/") or any(part in {"", ".", ".."} for part in raw_parts):
        raise DownloadError(f"unsafe {label}: noncanonical path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DownloadError(f"unsafe {label}: {value!r}")


def _validate_part(part: dict, index: int) -> None:
    if not isinstance(part, dict):
        raise DownloadError(f"part {index} is not an object")
    name = part.get("name")
    if not isinstance(name, str) or "/" in name or "\\" in name or not SAFE_NAME.fullmatch(name):
        raise DownloadError(f"unsafe part name: {name!r}")
    if not isinstance(part.get("bytes"), int) or part["bytes"] <= 0 or part["bytes"] > MAX_PART:
        raise DownloadError(f"invalid part size: {name}")
    if not isinstance(part.get("sha256"), str) or not HEX64.fullmatch(part["sha256"]):
        raise DownloadError(f"invalid part hash: {name}")
    urls = part.get("urls")
    if not isinstance(urls, list) or not urls:
        raise DownloadError(f"part has no URLs: {name}")
    for url in urls:
        _validate_http_url(url)


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema") != "blockdag.downloads/v1":
        raise DownloadError("unsupported download manifest schema")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise DownloadError("manifest files must be a non-empty list")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise DownloadError("manifest file entry is not an object")
        path = entry.get("path")
        _validate_path(path, "destination path")
        if path in seen:
            raise DownloadError(f"duplicate destination path: {path}")
        seen.add(path)
        if entry.get("group") not in {"software", "dataset"}:
            raise DownloadError(f"invalid file group: {path}")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
            raise DownloadError(f"invalid file size: {path}")
        if not isinstance(entry.get("sha256"), str) or not HEX64.fullmatch(entry["sha256"]):
            raise DownloadError(f"invalid file hash: {path}")
        ipfs = entry.get("ipfs")
        ipfs_match = re.fullmatch(r"/ipfs/(b[a-z2-7]{20,})/([A-Za-z0-9._+/-]+)", ipfs or "")
        if not ipfs_match:
            raise DownloadError(f"invalid IPFS path: {path}")
        _validate_path(ipfs_match.group(2), "IPFS path")
        parts = entry.get("parts")
        if parts is not None:
            if entry["group"] != "dataset" or not isinstance(parts, list) or not parts:
                raise DownloadError(f"invalid parts for: {path}")
            part_names = set()
            total = 0
            for index, part in enumerate(parts):
                _validate_part(part, index)
                if part["name"] in part_names:
                    raise DownloadError(f"duplicate part name: {part['name']}")
                part_names.add(part["name"])
                total += part["bytes"]
            if total != entry["bytes"]:
                raise DownloadError(f"part sizes do not equal file size: {path}")
        urls = entry.get("urls")
        if not isinstance(urls, list) or (not urls and parts is None):
            raise DownloadError(f"file has no URLs: {path}")
        for url in urls:
            _validate_http_url(url)


def _safe_output_root(path: Path) -> Path:
    path = path.absolute()
    if path.exists() and path.is_symlink():
        raise DownloadError("output directory must not be a symlink")
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise DownloadError("output directory is not a normal directory")
    return path


def _safe_destination(root: Path, relative: str) -> Path:
    _validate_path(relative, "destination path")
    destination = root.joinpath(*PurePosixPath(relative).parts)
    if os.path.commonpath((str(root), str(destination))) != str(root):
        raise DownloadError("destination escapes output directory")
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise DownloadError(f"unsafe destination parent: {relative}")
        current.mkdir(exist_ok=True)
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise DownloadError(f"unsafe destination: {relative}")
    return destination


def _already_verified(destination: Path, entry: dict) -> bool:
    return destination.exists() and destination.is_file() and not destination.is_symlink() and destination.stat().st_size == entry["bytes"] and sha256_file(destination) == entry["sha256"]


def _lock(path: Path):
    lock = Path(str(path) + ".lock")
    if lock.is_symlink():
        raise DownloadError(f"unsafe lock path: {path.name}")
    try:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock, flags, 0o600)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise DownloadError("lock is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, FileExistsError) as exc:
        if 'fd' in locals():
            os.close(fd)
        raise DownloadError(f"download already in progress: {path.name}") from exc
    except OSError as exc:
        raise DownloadError(f"cannot open lock: {path.name}") from exc
    return fd, lock


def _close_lock(fd: int, path: Path) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _response_headers(response):
    return {key.lower(): value for key, value in response.headers.items()}


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirects = 0

    def redirect_request(self, request, _fp, code, _message, headers, newurl):
        if self.redirects >= 5:
            raise DownloadError("too many HTTPS redirects")
        location = headers.get("Location") or newurl
        if not location:
            raise DownloadError("redirect has no Location")
        target = urlparse(urljoin(request.full_url, location))
        source = urlparse(request.full_url)
        if target.scheme not in {"https", "http"} or not target.netloc or target.username or target.password:
            raise DownloadError("unsafe redirect")
        if source.scheme == "https" and target.scheme != "https":
            raise DownloadError("HTTPS redirect downgrade")
        if target.scheme == "http" and (target.hostname or "").lower().rstrip(".") not in {"127.0.0.1", "localhost", "::1"}:
            raise DownloadError("redirect to non-loopback HTTP")
        self.redirects += 1
        headers = {key: value for key, value in request.header_items() if key.lower() not in {"host", "content-length", "authorization"}}
        return Request(target.geturl(), headers=headers, method=request.get_method())


def _open_http(url: str, offset: int):
    headers = {"User-Agent": "bdag-rc2-downloader/1", "Accept": "application/octet-stream"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    opener = build_opener(SafeRedirect())
    return opener.open(Request(url, headers=headers), timeout=HTTP_TIMEOUT)


def _validate_response(response, offset: int, expected: int) -> tuple[int, int]:
    status = getattr(response, "status", response.getcode())
    headers = _response_headers(response)
    if offset:
        if status == 200:
            return 0, expected
        if status != 206:
            raise DownloadError(f"resume HTTP status {status}")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", headers.get("content-range", ""))
        if not match or int(match.group(1)) != offset or match.group(3) == "*" or int(match.group(3)) != expected:
            raise DownloadError("invalid resume Content-Range")
        remaining = int(match.group(2)) - offset + 1
    else:
        if status not in {200, 206}:
            raise DownloadError(f"HTTP status {status}")
        remaining = expected
        if status == 206:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", headers.get("content-range", ""))
            if match and int(match.group(1)) != 0:
                raise DownloadError("invalid initial Content-Range")
    content_length = headers.get("content-length")
    if content_length is not None and int(content_length) != remaining:
        raise DownloadError("HTTP Content-Length does not match expected bytes")
    return (0 if status == 200 else offset), remaining


def _stream_http(urls: list[str], partial: Path, expected: int) -> None:
    restarted = False
    failures = 0
    while failures < RETRIES:
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == expected:
            return  # A completed interrupted transfer still needs the full SHA check.
        if offset > expected:
            partial.unlink()
            offset = 0
        url = urls[failures % len(urls)]
        try:
            with _open_http(url, offset) as response:
                write_offset, expected_body = _validate_response(response, offset, expected)
                if offset and write_offset == 0:
                    if restarted:
                        raise DownloadError("server repeatedly ignored Range")
                    partial.unlink(missing_ok=True)
                    restarted = True
                    continue
                mode = "ab" if write_offset else "wb"
                received = write_offset
                with partial.open(mode) as output:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > expected:
                            raise DownloadError("HTTP body exceeds manifest size")
                        output.write(chunk)
                if received != expected:
                    raise DownloadError(f"short HTTP body: {received}/{expected}")
                return
        except (DownloadError, HTTPError, URLError, OSError, TimeoutError, http.client.IncompleteRead) as exc:
            failures += 1
            if failures >= RETRIES:
                raise DownloadError(f"HTTP download failed after {RETRIES} attempts: {exc}") from exc
            time.sleep(0.05 * failures)


def _verify_and_replace(partial: Path, destination: Path, entry: dict) -> None:
    if partial.stat().st_size != entry["bytes"] or sha256_file(partial) != entry["sha256"]:
        partial.unlink(missing_ok=True)
        raise DownloadError(f"checksum mismatch: {entry['path']}")
    if destination.is_symlink() or destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise DownloadError(f"destination changed unsafely: {entry['path']}")
        if _already_verified(destination, entry):
            partial.unlink(missing_ok=True)
            return
        raise DownloadError(f"refusing to overwrite mismatched destination: {entry['path']}")
    os.replace(partial, destination)


def download_http_file(entry: dict, destination: Path) -> bool:
    if _already_verified(destination, entry):
        return False
    if destination.is_symlink() or destination.exists():
        raise DownloadError(f"refusing to overwrite mismatched destination: {entry['path']}")
    lock_fd, lock = _lock(destination)
    partial = Path(str(destination) + ".partial")
    try:
        if partial.is_symlink() or (partial.exists() and not partial.is_file()):
            raise DownloadError(f"unsafe partial path: {entry['path']}")
        _stream_http(entry["urls"], partial, entry["bytes"])
        _verify_and_replace(partial, destination, entry)
        return True
    finally:
        _close_lock(lock_fd, lock)


def download_ipfs_file(entry: dict, destination: Path) -> bool:
    if _already_verified(destination, entry):
        return False
    if destination.is_symlink() or destination.exists():
        raise DownloadError(f"refusing to overwrite mismatched destination: {entry['path']}")
    lock_fd, lock = _lock(destination)
    partial = Path(str(destination) + ".partial")
    try:
        if partial.is_symlink() or (partial.exists() and not partial.is_file()):
            raise DownloadError(f"unsafe partial path: {entry['path']}")
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > entry["bytes"]:
            partial.unlink()
            offset = 0
        if offset == entry["bytes"]:
            try:
                _verify_and_replace(partial, destination, entry)
                return True
            except DownloadError:
                partial.unlink(missing_ok=True)
                offset = 0
        mode = "ab" if offset else "wb"
        with partial.open(mode) as output:
            try:
                command = ["ipfs", "cat"] + (["--offset", str(offset)] if offset else []) + [entry["ipfs"]]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                selector = selectors.DefaultSelector()
                selector.register(process.stdout, selectors.EVENT_READ)
                received = offset
                deadline = time.monotonic() + IPFS_TOTAL_TIMEOUT
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        process.kill(); process.wait()
                        raise DownloadError("IPFS download exceeded total timeout")
                    events = selector.select(min(IPFS_INACTIVITY_TIMEOUT, remaining))
                    if not events:
                        if process.poll() is not None:
                            break
                        process.kill(); process.wait()
                        raise DownloadError("IPFS download exceeded inactivity timeout")
                    chunk = os.read(process.stdout.fileno(), CHUNK)
                    if not chunk:
                        selector.unregister(process.stdout)
                        break
                    received += len(chunk)
                    if received > entry["bytes"]:
                        process.kill(); process.wait()
                        raise DownloadError("IPFS body exceeds manifest size")
                    output.write(chunk)
                selector.close()
                process.wait(timeout=5)
                if process.returncode != 0:
                    raise DownloadError("IPFS cat failed")
            except OSError as exc:
                partial.unlink(missing_ok=True)
                raise DownloadError("IPFS download failed") from exc
            finally:
                if 'process' in locals() and process.poll() is None:
                    process.kill()
                    process.wait()
        _verify_and_replace(partial, destination, entry)
        return True
    finally:
        _close_lock(lock_fd, lock)


def download_dataset_parts(entry: dict, destination: Path) -> bool:
    if _already_verified(destination, entry):
        return False
    if destination.is_symlink() or destination.exists():
        raise DownloadError(f"refusing to overwrite mismatched destination: {entry['path']}")
    lock_fd, lock = _lock(destination)
    parts_root = Path(str(destination) + ".parts")
    try:
        if parts_root.is_symlink() or (parts_root.exists() and not parts_root.is_dir()):
            raise DownloadError(f"unsafe parts path: {entry['path']}")
        parts_root.mkdir(exist_ok=True)
        part_paths = []
        for part in entry["parts"]:
            part_path = parts_root / part["name"]
            part_entry = {"path": part["name"], "bytes": part["bytes"], "sha256": part["sha256"], "urls": part["urls"]}
            if not _already_verified(part_path, part_entry):
                if part_path.is_symlink() or part_path.exists():
                    raise DownloadError(f"refusing to overwrite mismatched part: {part['name']}")
                try:
                    download_http_file(part_entry, part_path)
                except DownloadError:
                    part_path.unlink(missing_ok=True)
                    raise
            part_paths.append(part_path)
        partial = Path(str(destination) + ".partial")
        if partial.is_symlink() or (partial.exists() and not partial.is_file()):
            raise DownloadError(f"unsafe partial path: {entry['path']}")
        with partial.open("wb") as output:
            for part_path in part_paths:
                with part_path.open("rb") as source:
                    shutil.copyfileobj(source, output, CHUNK)
        _verify_and_replace(partial, destination, entry)
        return True
    finally:
        _close_lock(lock_fd, lock)


def select_entries(manifest: dict, selection: str, requested: list[str]) -> list[dict]:
    if selection not in {"software", "dataset", "all"}:
        raise DownloadError("--select must be software, dataset or all")
    entries = [entry for entry in manifest["files"] if selection == "all" or entry["group"] == selection]
    by_path = {entry["path"]: entry for entry in entries}
    if requested:
        if len(set(requested)) != len(requested):
            raise DownloadError("duplicate --file")
        missing = [path for path in requested if path not in by_path]
        if missing:
            raise DownloadError(f"requested file is outside selection or manifest: {missing[0]}")
        entries = [by_path[path] for path in requested]
    return entries


def run(args) -> int:
    manifest = load_manifest(Path(args.manifest), args.expect_manifest_sha256)
    entries = select_entries(manifest, args.select, args.file)
    output = _safe_output_root(Path(args.output_dir))
    changed = 0
    for entry in entries:
        destination = _safe_destination(output, entry["path"])
        if args.transport == "http" and entry.get("parts") is not None:
            changed += int(download_dataset_parts(entry, destination))
        elif args.transport == "http":
            changed += int(download_http_file(entry, destination))
        else:
            changed += int(download_ipfs_file(entry, destination))
    print(json.dumps({"status": "PASS", "selected": len(entries), "downloaded": changed, "output_dir": str(output)}))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", required=True)
    result.add_argument("--expect-manifest-sha256", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--select", choices=("software", "dataset", "all"), default="software")
    result.add_argument("--file", action="append", default=[])
    result.add_argument("--transport", choices=("http", "ipfs"), default="http")
    return result


def main() -> int:
    try:
        return run(parser().parse_args())
    except DownloadError as exc:
        print(f"bdag-download: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
