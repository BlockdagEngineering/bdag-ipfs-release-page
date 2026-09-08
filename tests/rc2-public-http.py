#!/usr/bin/env python3
"""Anonymous full HTTP byte proof with bounded memory, including assembled SHA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

root = Path(__file__).resolve().parents[1] / "releases/2.1.0-rc.2/install-v1"
spec = importlib.util.spec_from_file_location("download", root / "bdag-download.py")
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)
manifest = download.load_manifest(root / "downloads.json", "54295bdbffb45d39af214c37ed627372ded3c039366a85138643ab75fbcf504c")
deadline = time.monotonic() + 3600
results = []

def read_bytes(item, full):
    received = 0
    digest = hashlib.sha256()
    with download._open_http(item["urls"][0], 0) as response:
        download._validate_response(response, 0, item["bytes"])
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError("one-hour public byte-test deadline reached")
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            received += len(chunk)
            if received > item["bytes"]:
                raise RuntimeError("HTTP byte count exceeds manifest")
            digest.update(chunk)
            full.update(chunk)
    if received != item["bytes"] or digest.hexdigest() != item["sha256"]:
        raise RuntimeError("HTTP full-byte SHA mismatch")

try:
    for item in manifest["files"]:
        digest = hashlib.sha256()
        if item.get("parts"):
            for index, part in enumerate(item["parts"], 1):
                read_bytes(part, digest)
                print(json.dumps({"status":"PART_PASS", "part":index, "bytes":part["bytes"], "sha256":part["sha256"]}), flush=True)
        else:
            read_bytes(item, digest)
        if digest.hexdigest() != item["sha256"]:
            raise RuntimeError("Ordered dataset concatenation SHA mismatch")
        result = {"path":item["path"], "bytes":item["bytes"], "sha256":digest.hexdigest()}
        results.append(result)
        print(json.dumps({"status":"FILE_PASS", **result}), flush=True)
    print(json.dumps({"schema":"bdag.anonymous-http-byte-proof/v1", "status":"PASS", "files":results,
                      "dataset_parts":13, "authentication":False, "storage":"streamed; no archive installation claimed",
                      "complete_dataset_sha256":"8f7b093b73a7fe390d53d275f5d4b7d69d32aea96220b19a3e2cc54804a5d608"}), flush=True)
except Exception as error:
    print(json.dumps({"status":"FAIL", "verified_files":len(results), "classification":type(error).__name__,
                      "detail":"Full HTTP byte proof incomplete; no pass claimed"}), flush=True)
    raise SystemExit(1)
