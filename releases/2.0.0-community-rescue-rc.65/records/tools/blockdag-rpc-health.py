#!/usr/bin/env python3
"""Fail-closed semantic readiness for a public BlockDAG archive RPC.

The health service normally certifies a local EVM commitment against fresh
authenticated native consensus. During a bounded native HTTP-503 "busy"
window, it may continue serving only when the EVM endpoint still exposes the
exact last certified committed head. A very short authenticated-native
transport-timeout transition is tolerated under the same exact-head rule so a
lock-heavy maintenance scan cannot erase the certificate immediately before
the native endpoint begins returning its explicit busy response. It never
treats an external public RPC as consensus authority.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping


# The signed release payload may be mounted read-only and is verified against
# an exact allowlist. Runtime imports must not create unsigned bytecode beside
# this source file.
sys.dont_write_bytecode = True

VERSION = "1.16"
MAX_ALIGNMENT_AGE_SECONDS = 900
MAX_NATIVE_BUSY_GRACE_SECONDS = 900
MAX_NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS = 30
MAX_TRANSIENT_EVM_GRACE_SECONDS = 120
HASH_RE = re.compile(r"^0x[0-9a-f]{64}$")
NATIVE_HTTP_STATUS_MARKER = "\n__BDAG_NATIVE_HTTP_STATUS__:"
EVM_HTTP_STATUS_MARKER = "\n__BDAG_EVM_HTTP_STATUS__:"

LOCAL_RPC_URL = os.environ.get("LOCAL_RPC_URL", "http://127.0.0.1:18545")
WITNESS_RPC_URL = os.environ.get("WITNESS_RPC_URL", "https://rpc.blockdag.works")
EXPECTED_CHAIN_ID = os.environ.get("EXPECTED_CHAIN_ID", "0x57c").lower()
ALIGNMENT_INTERVAL_SECONDS = max(
    1, int(os.environ.get("ALIGNMENT_INTERVAL_SECONDS", "300"))
)
ALIGNMENT_FAILURE_RETRY_SECONDS = min(
    ALIGNMENT_INTERVAL_SECONDS,
    max(1, int(os.environ.get("ALIGNMENT_FAILURE_RETRY_SECONDS", "15"))),
)
ALIGNMENT_MAX_AGE_SECONDS = min(
    MAX_ALIGNMENT_AGE_SECONDS,
    max(1, int(os.environ.get("ALIGNMENT_MAX_AGE_SECONDS", "900"))),
)
MAX_REMOTE_LAG_BLOCKS = max(
    0, int(os.environ.get("MAX_REMOTE_LAG_BLOCKS", "300"))
)
RPC_TIMEOUT_SECONDS = max(
    0.1, float(os.environ.get("RPC_TIMEOUT_SECONDS", "4"))
)
RPC_HEAD_RETRY_ATTEMPTS = max(
    1, int(os.environ.get("RPC_HEAD_RETRY_ATTEMPTS", "6"))
)
RPC_HEAD_RETRY_DELAY_SECONDS = max(
    0.0, float(os.environ.get("RPC_HEAD_RETRY_DELAY_SECONDS", "0.1"))
)
LOCAL_TRANSIENT_GRACE_SECONDS = min(
    MAX_TRANSIENT_EVM_GRACE_SECONDS,
    max(0, int(os.environ.get("LOCAL_TRANSIENT_GRACE_SECONDS", "30"))),
)
NATIVE_BUSY_GRACE_SECONDS = min(
    MAX_NATIVE_BUSY_GRACE_SECONDS,
    ALIGNMENT_MAX_AGE_SECONDS,
    max(0, int(os.environ.get("NATIVE_BUSY_GRACE_SECONDS", "900"))),
)
NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS = min(
    MAX_NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS,
    NATIVE_BUSY_GRACE_SECONDS,
    max(
        0,
        int(
            os.environ.get(
                "NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS",
                "30",
            )
        ),
    ),
)
HEALTH_BIND = os.environ.get("HEALTH_BIND", "0.0.0.0")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8080"))
ACTIVATION_HOLD_FILE = os.environ.get(
    "ACTIVATION_HOLD_FILE", "/etc/blockdag-rpc-activation-hold"
)
DATA_PATH = os.environ.get("DATA_PATH", "/data")
MIN_FREE_GIB = max(0.0, float(os.environ.get("MIN_FREE_GIB", "50")))
MIN_FREE_PERCENT = max(
    0.0, min(100.0, float(os.environ.get("MIN_FREE_PERCENT", "5")))
)
MIN_PEERS = max(0, int(os.environ.get("MIN_PEERS", "2")))
NATIVE_RPC_URL = os.environ.get("NATIVE_RPC_URL", "http://127.0.0.1:38131")
NATIVE_RPC_CURL_CONFIG = os.environ.get(
    "NATIVE_RPC_CURL_CONFIG", "/etc/blockdag-rpc-health-native.curl"
)
MIN_NATIVE_CONSENSUS_PEERS = max(
    0, int(os.environ.get("MIN_NATIVE_CONSENSUS_PEERS", "2"))
)
MAX_NEAR_TIP_PEER_LEAD_BLOCKS = min(
    64,
    max(0, int(os.environ.get("MAX_NEAR_TIP_PEER_LEAD_BLOCKS", "32"))),
)
ARCHIVE_PROBE_ADDRESS = os.environ.get(
    "ARCHIVE_PROBE_ADDRESS", "0x0000000000000000000000000000000000000000"
)
REQUIRE_HISTORICAL_STATE_TRIE = os.environ.get(
    "REQUIRE_HISTORICAL_STATE_TRIE", "true"
).strip().lower() in {"1", "true", "yes", "on"}
ARCHIVE_GENESIS_HEIGHT = int(os.environ.get("ARCHIVE_GENESIS_HEIGHT", "0"), 0)
ARCHIVE_GENESIS_HASH = os.environ.get(
    "ARCHIVE_GENESIS_HASH",
    "0x3fb19ea409ac7399ad7b988b88e0d436722c967137e51e834ccefd7611a592ef",
).lower()
ARCHIVE_GENESIS_ROOT = os.environ.get(
    "ARCHIVE_GENESIS_ROOT",
    "0x564aeb23c21b395f94839991240f0665fdf6b083cad3a41ac6412fa2180ac76a",
).lower()
ARCHIVE_CHECKPOINT_HEIGHT = int(
    os.environ.get("ARCHIVE_CHECKPOINT_HEIGHT", "13863411"), 0
)
ARCHIVE_CHECKPOINT_HASH = os.environ.get(
    "ARCHIVE_CHECKPOINT_HASH",
    "0xbf9a0ccd88fa03eb3d7cbc0052b258b9b21132ae4ba3f0276f6e482a9d601738",
).lower()
ARCHIVE_CHECKPOINT_ROOT = os.environ.get(
    "ARCHIVE_CHECKPOINT_ROOT",
    "0xad51cb1e1357172afc5ca5dcebc477ff818661b64b8b5b64cdf9cd54a8450c00",
).lower()
PRODUCER_CHECKPOINT_HEIGHT = int(
    os.environ.get("PRODUCER_CHECKPOINT_HEIGHT", "14600000"), 0
)
PRODUCER_CHECKPOINT_HASH = os.environ.get(
    "PRODUCER_CHECKPOINT_HASH",
    "0xf4a201ed8d9e2b8279223323825bc19b9c01f157d44104556828df2621ffa8f0",
).lower()
PRODUCER_CHECKPOINT_ROOT = os.environ.get(
    "PRODUCER_CHECKPOINT_ROOT",
    "0xb973e07c2a245d39d586e73ccb420eb97b491b4031bf02a4d1c1b5b7588feeb7",
).lower()

alignment_lock = threading.Lock()
alignment_state: dict[str, Any] = {
    "ok": False,
    "updated_at": None,
    "updated_at_epoch": 0,
    "error": "integrity alignment check has not run yet",
}
local_health_lock = threading.Lock()
local_health_state: dict[str, Any] = {
    "ok": False,
    "updated_at": None,
    "updated_at_epoch": 0,
}


class TransientEvmHeadUnavailable(RuntimeError):
    """The committed EVM gateway is temporarily at capacity or transitioning."""


class NativeRpcError(RuntimeError):
    """An authenticated native RPC request failed."""


class NativeRpcBusy(NativeRpcError):
    """The authenticated native RPC explicitly returned HTTP 503 busy."""

    def __init__(self, message: str, *, status: int = 503) -> None:
        super().__init__(message)
        self.status = status


class NativeRpcTimeout(NativeRpcError):
    """The authenticated native RPC transport exceeded its bounded timeout."""


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def bounded_error(value: object, limit: int = 512) -> str:
    text = str(value).strip()
    return text if len(text) <= limit else text[:limit] + "..."


def rpc_batch(
    url: str,
    calls: list[dict[str, Any]],
    timeout: float = RPC_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    data = json.dumps(calls, separators=(",", ":"))
    for attempt in range(1, RPC_HEAD_RETRY_ATTEMPTS + 1):
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/curl",
                    "--http1.1",
                    "-sS",
                    "--max-time",
                    str(timeout),
                    "-H",
                    "content-type: application/json",
                    "-H",
                    f"user-agent: blockdag-rpc-health/{VERSION}",
                    "--data",
                    data,
                    "--write-out",
                    EVM_HTTP_STATUS_MARKER + "%{http_code}",
                    url,
                ],
                text=True,
                capture_output=True,
                timeout=timeout + 2,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            if url == LOCAL_RPC_URL:
                raise TransientEvmHeadUnavailable(
                    "local EVM RPC transport temporarily timed out: "
                    f"{bounded_error(exc)}"
                ) from exc
            raise RuntimeError(
                f"EVM RPC transport failed: {bounded_error(exc)}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"EVM RPC transport failed: {bounded_error(exc)}"
            ) from exc
        if completed.returncode != 0:
            error = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"curl exited {completed.returncode}"
            )
            if url == LOCAL_RPC_URL and completed.returncode == 28:
                raise TransientEvmHeadUnavailable(
                    "local EVM RPC transport temporarily timed out: "
                    f"{bounded_error(error)}"
                )
            raise RuntimeError(f"EVM RPC transport failed: {bounded_error(error)}")
        body, marker, raw_status = completed.stdout.rpartition(
            EVM_HTTP_STATUS_MARKER
        )
        if not marker or not raw_status.isdigit():
            raise RuntimeError("EVM RPC response has no HTTP status")
        status = int(raw_status)
        if status < 200 or status >= 300:
            if url == LOCAL_RPC_URL and status in (429, 503):
                if attempt < RPC_HEAD_RETRY_ATTEMPTS:
                    time.sleep(RPC_HEAD_RETRY_DELAY_SECONDS * attempt)
                    continue
                raise TransientEvmHeadUnavailable(
                    "local EVM gateway capacity temporarily saturated: "
                    f"HTTP {status}: {bounded_error(body)}"
                )
            raise RuntimeError(
                f"EVM RPC returned HTTP {status}: {bounded_error(body)}"
            )
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("EVM RPC response is not valid JSON") from exc
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise RuntimeError("EVM RPC response is not a JSON array")
        errors = [
            item.get("error")
            for item in payload
            if isinstance(item, dict) and item.get("error")
        ]
        if errors:
            retryable_head = all(
                isinstance(error, dict)
                and error.get("code") == -32000
                and "EVM head unavailable" in str(error.get("message", ""))
                for error in errors
            )
            retryable_capacity = all(
                isinstance(error, dict)
                and error.get("code") == -32000
                and "server busy (too many concurrent requests)"
                in str(error.get("message", ""))
                for error in errors
            )
            retryable = retryable_head or retryable_capacity
            if retryable and attempt < RPC_HEAD_RETRY_ATTEMPTS:
                time.sleep(RPC_HEAD_RETRY_DELAY_SECONDS * attempt)
                continue
            if retryable:
                reason = (
                    "EVM head temporarily unavailable"
                    if retryable_head
                    else "normal EVM gateway capacity temporarily saturated"
                )
                raise TransientEvmHeadUnavailable(
                    f"{reason}: RPC error: {bounded_error(errors[0])}"
                )
            raise RuntimeError(f"EVM RPC error: {bounded_error(errors[0])}")
        return {
            str(item.get("id")): item.get("result")
            for item in payload
            if isinstance(item, dict)
        }
    raise RuntimeError("EVM head remained unavailable after bounded retries")


def _native_busy_response(status: int, body: str) -> bool:
    if status != 503:
        return False
    lowered = body.lower()
    return any(
        marker in lowered
        for marker in (
            "too busy",
            "server busy",
            "busy (too many",
            "temporarily busy",
        )
    )


def native_rpc(method: str) -> Any:
    data = json.dumps(
        {
            "jsonrpc": "1.0",
            "id": "native-health",
            "method": method,
            "params": [],
        },
        separators=(",", ":"),
    )
    try:
        completed = subprocess.run(
            [
                "/usr/bin/curl",
                "--config",
                NATIVE_RPC_CURL_CONFIG,
                "--http1.1",
                "-sS",
                "--max-time",
                str(RPC_TIMEOUT_SECONDS),
                "-H",
                "content-type: application/json",
                "-H",
                f"user-agent: blockdag-rpc-health/{VERSION}",
                "--data",
                data,
                "--write-out",
                NATIVE_HTTP_STATUS_MARKER + "%{http_code}",
                NATIVE_RPC_URL,
            ],
            text=True,
            capture_output=True,
            timeout=RPC_TIMEOUT_SECONDS + 2,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NativeRpcTimeout(
            f"native RPC transport timed out: {bounded_error(exc)}"
        ) from exc
    except OSError as exc:
        raise NativeRpcError(
            f"native RPC transport failed: {bounded_error(exc)}"
        ) from exc
    if completed.returncode != 0:
        error = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"curl exited {completed.returncode}"
        )
        if completed.returncode == 28:
            raise NativeRpcTimeout(
                f"native RPC transport timed out: {bounded_error(error)}"
            )
        raise NativeRpcError(
            f"native RPC transport failed: {bounded_error(error)}"
        )
    body, marker, raw_status = completed.stdout.rpartition(
        NATIVE_HTTP_STATUS_MARKER
    )
    if not marker or not raw_status.isdigit():
        raise NativeRpcError("native RPC response has no authenticated HTTP status")
    status = int(raw_status)
    if _native_busy_response(status, body):
        raise NativeRpcBusy(
            f"authenticated native RPC is busy (HTTP {status})",
            status=status,
        )
    if status < 200 or status >= 300:
        raise NativeRpcError(
            f"native RPC returned HTTP {status}: {bounded_error(body)}"
        )
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise NativeRpcError("native RPC response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise NativeRpcError("native RPC response is not a JSON object")
    if payload.get("error"):
        raise NativeRpcError(
            f"native RPC error: {bounded_error(payload['error'])}"
        )
    return payload.get("result")


def check_native_consensus() -> dict[str, Any]:
    result = native_rpc("getTemplateHealth")
    if not isinstance(result, dict):
        raise NativeRpcError("getTemplateHealth result is not an object")
    archive_mode = native_rpc("getArchiveStatus") is True
    consensus_peers = int(result.get("p2p_consensus_peer_count") or 0)
    fresh_peers = int(result.get("p2p_fresh_consensus_peer_count") or 0)
    chain_current = result.get("chain_current") is True
    p2p_current = result.get("p2p_current") is True
    p2p_mining_fresh = result.get("p2p_mining_fresh") is True
    best_peer_lead_blocks = int(result.get("p2p_best_peer_lead_blocks") or 0)
    near_tip_transition = (
        p2p_mining_fresh
        and result.get("sync_reason_code") == "ok"
        and abs(best_peer_lead_blocks) <= MAX_NEAR_TIP_PEER_LEAD_BLOCKS
    )
    shutdown = result.get("shutdown") is True
    ok = (
        chain_current
        and (p2p_current or near_tip_transition)
        and not shutdown
        and archive_mode
        and fresh_peers >= MIN_NATIVE_CONSENSUS_PEERS
    )
    return {
        "ok": ok,
        "chain_current": chain_current,
        "p2p_current": p2p_current,
        "p2p_mining_fresh": p2p_mining_fresh,
        "near_tip_transition_accepted": bool(
            not p2p_current and near_tip_transition
        ),
        "max_near_tip_peer_lead_blocks": MAX_NEAR_TIP_PEER_LEAD_BLOCKS,
        "shutdown": shutdown,
        "archive_mode": archive_mode,
        "archive_mode_verified": archive_mode,
        "consensus_peers": consensus_peers,
        "fresh_consensus_peers": fresh_peers,
        "minimum_fresh_consensus_peers": MIN_NATIVE_CONSENSUS_PEERS,
        "stale_consensus_peers": int(
            result.get("p2p_stale_consensus_peer_count") or 0
        ),
        "best_peer_lead_blocks": best_peer_lead_blocks,
        "best_peer_graph_state_age_ms": result.get(
            "p2p_best_peer_graph_state_age_ms"
        ),
        "main_order": result.get("main_order"),
        "best_peer_main_order": result.get("p2p_best_peer_main_order"),
        "sync_reason_code": result.get("sync_reason_code"),
    }


def parse_quantity(value: object) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise RuntimeError(f"invalid quantity: {value!r}")
    return int(value, 16)


def require_hash(value: object, label: str) -> str:
    normalized = str(value or "").lower()
    if not HASH_RE.fullmatch(normalized):
        raise RuntimeError(f"committed EVM head has invalid {label}")
    return normalized


def committed_head_from_block(block: object) -> dict[str, Any]:
    if not isinstance(block, dict):
        raise RuntimeError("committed EVM head block is unavailable")
    commitment: dict[str, Any] = {
        "height": parse_quantity(block.get("number")),
        "hash": require_hash(block.get("hash"), "block hash"),
        "parent_hash": require_hash(block.get("parentHash"), "parent hash"),
        "state_root": require_hash(block.get("stateRoot"), "state root"),
        "receipts_root": require_hash(
            block.get("receiptsRoot"), "receipts root"
        ),
        "transactions_root": require_hash(
            block.get("transactionsRoot"), "transactions root"
        ),
    }
    for field in (
        "nativeOrderCommitment",
        "nativeOrderHash",
        "nativeBlockOrderHash",
        "nativeBlockHash",
    ):
        if field in block and block.get(field) not in (None, ""):
            commitment[field] = require_hash(
                block.get(field), f"{field} commitment"
            )
    return commitment


def check_local_evm() -> dict[str, Any]:
    result = rpc_batch(
        LOCAL_RPC_URL,
        [
            {
                "jsonrpc": "2.0",
                "id": "chain",
                "method": "eth_chainId",
                "params": [],
            },
            {
                "jsonrpc": "2.0",
                "id": "head",
                "method": "eth_getBlockByNumber",
                "params": ["latest", False],
            },
            {
                "jsonrpc": "2.0",
                "id": "sync",
                "method": "eth_syncing",
                "params": [],
            },
            {
                "jsonrpc": "2.0",
                "id": "peers",
                "method": "net_peerCount",
                "params": [],
            },
        ],
    )
    chain_id = str(result.get("chain", "")).lower()
    committed_head = committed_head_from_block(result.get("head"))
    syncing = result.get("sync")
    evm_peers = parse_quantity(result.get("peers"))
    evm_ok = chain_id == EXPECTED_CHAIN_ID and syncing is False
    return {
        "evm_ok": evm_ok,
        "chain_id": chain_id,
        "head": committed_head["height"],
        "committed_head": committed_head,
        "syncing": syncing,
        "evm_peer_count": evm_peers,
        "evm_peer_count_role": "advisory-only",
        "minimum_evm_peers_advisory": MIN_PEERS,
        "expected_chain_id": EXPECTED_CHAIN_ID,
    }


def _invalidate_local_cache(reason: str) -> None:
    with local_health_lock:
        local_health_state.clear()
        local_health_state.update(
            {
                "ok": False,
                "updated_at": utc_now(),
                "updated_at_epoch": int(time.time()),
                "invalidated_reason": reason,
            }
        )


def _cached_local_state() -> dict[str, Any]:
    with local_health_lock:
        return copy.deepcopy(local_health_state)


def _cache_certified_local_state(state: Mapping[str, Any]) -> None:
    with local_health_lock:
        local_health_state.clear()
        local_health_state.update(copy.deepcopy(dict(state)))


def _normal_local_state(
    evm: Mapping[str, Any], native_consensus: Mapping[str, Any]
) -> dict[str, Any]:
    now_epoch = int(time.time())
    state = {
        **dict(evm),
        "ok": bool(evm.get("evm_ok") and native_consensus.get("ok")),
        "native_consensus": dict(native_consensus),
        "native_consensus_fresh": True,
        # This observer may report transition validity but never grants mining
        # authority. Mining has its own fail-closed readiness gate.
        "mining_ready": False,
        "consensus_transition_valid": bool(
            evm.get("evm_ok") and native_consensus.get("ok")
        ),
        "mining_authority": "not-granted-by-public-rpc-health",
        "readiness_mode": "fresh-native-and-committed-evm",
        "updated_at": utc_now(),
        "updated_at_epoch": now_epoch,
        "age_seconds": 0,
        "fresh": True,
        "transient_evm_grace_seconds": LOCAL_TRANSIENT_GRACE_SECONDS,
        "native_busy_grace_seconds": NATIVE_BUSY_GRACE_SECONDS,
        "native_timeout_transition_grace_seconds": (
            NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS
        ),
    }
    if state["ok"]:
        _cache_certified_local_state(state)
    else:
        _invalidate_local_cache("explicit local EVM/native readiness failure")
    return state


def _last_certified_head_during_native_unavailability(
    evm: Mapping[str, Any],
    error: NativeRpcError,
    *,
    grace_seconds: int,
    readiness_mode: str,
    unavailable_state: Mapping[str, Any],
    rejection_reason: str,
) -> dict[str, Any]:
    previous = _cached_local_state()
    age = int(time.time()) - int(previous.get("updated_at_epoch") or 0)
    previous_commitment = previous.get("committed_head")
    current_commitment = evm.get("committed_head")
    if (
        previous.get("ok") is not True
        or age < 0
        or age > grace_seconds
        or evm.get("evm_ok") is not True
        or not isinstance(previous_commitment, dict)
        or current_commitment != previous_commitment
    ):
        _invalidate_local_cache(
            f"{rejection_reason}: no fresh exact committed-head match"
        )
        raise NativeRpcError(
            "native RPC is unavailable and the exact last certified committed "
            "EVM head is unavailable, changed, or outside its bounded grace"
        ) from error
    state = {
        **dict(evm),
        "ok": True,
        "native_consensus": copy.deepcopy(
            previous.get("native_consensus", {})
        ),
        "native_consensus_fresh": False,
        "mining_ready": False,
        "consensus_transition_valid": False,
        "mining_authority": "not-granted-by-public-rpc-health",
        "readiness_mode": readiness_mode,
        "certified_at": previous.get("updated_at"),
        "certified_at_epoch": previous.get("updated_at_epoch"),
        "age_seconds": age,
        "fresh": True,
        "transient_evm_grace_seconds": LOCAL_TRANSIENT_GRACE_SECONDS,
        "native_busy_grace_seconds": NATIVE_BUSY_GRACE_SECONDS,
        "native_timeout_transition_grace_seconds": (
            NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS
        ),
    }
    state.update(copy.deepcopy(dict(unavailable_state)))
    return state


def _last_committed_head_during_native_busy(
    evm: Mapping[str, Any], error: NativeRpcBusy
) -> dict[str, Any]:
    return _last_certified_head_during_native_unavailability(
        evm,
        error,
        grace_seconds=NATIVE_BUSY_GRACE_SECONDS,
        readiness_mode="last-certified-committed-evm-head",
        unavailable_state={
            "native_rpc_busy": True,
            "native_rpc_busy_status": error.status,
            "native_rpc_busy_error": str(error),
        },
        rejection_reason="native busy grace rejected",
    )


def _last_committed_head_during_native_timeout(
    evm: Mapping[str, Any], error: NativeRpcTimeout
) -> dict[str, Any]:
    return _last_certified_head_during_native_unavailability(
        evm,
        error,
        grace_seconds=NATIVE_TIMEOUT_TRANSITION_GRACE_SECONDS,
        readiness_mode=(
            "last-certified-committed-evm-head-native-timeout-transition"
        ),
        unavailable_state={
            "native_rpc_timeout_transition": True,
            "native_rpc_timeout_error": str(error),
        },
        rejection_reason="native timeout transition grace rejected",
    )


def check_local_rpc() -> dict[str, Any]:
    evm = check_local_evm()
    native_consensus = check_native_consensus()
    return _normal_local_state(evm, native_consensus)


def check_local_rpc_with_transient_grace() -> dict[str, Any]:
    try:
        evm = check_local_evm()
    except TransientEvmHeadUnavailable as exc:
        previous = _cached_local_state()
        age = int(time.time()) - int(previous.get("updated_at_epoch") or 0)
        try:
            native_consensus = check_native_consensus()
        except Exception:
            _invalidate_local_cache(
                "native consensus unavailable during transient EVM failure"
            )
            raise
        if (
            previous.get("ok") is True
            and 0 <= age <= LOCAL_TRANSIENT_GRACE_SECONDS
            and native_consensus.get("ok") is True
        ):
            previous.update(
                {
                    "age_seconds": age,
                    "fresh": True,
                    "native_consensus": native_consensus,
                    "native_consensus_fresh": True,
                    "transient_evm_gateway_unavailable": True,
                    "transient_evm_gateway_error": str(exc),
                    "transient_evm_gateway_unavailable_at": utc_now(),
                    "readiness_mode": "bounded-transient-evm-gateway-grace",
                    "mining_ready": False,
                    "consensus_transition_valid": False,
                    "mining_authority": (
                        "not-granted-by-public-rpc-health"
                    ),
                }
            )
            return previous
        _invalidate_local_cache("transient EVM grace expired or uncertified")
        raise
    except Exception:
        _invalidate_local_cache("EVM committed-head probe failed")
        raise

    try:
        native_consensus = check_native_consensus()
    except NativeRpcBusy as exc:
        return _last_committed_head_during_native_busy(evm, exc)
    except NativeRpcTimeout as exc:
        return _last_committed_head_during_native_timeout(evm, exc)
    except Exception:
        _invalidate_local_cache("native RPC failed outside explicit busy grace")
        raise
    return _normal_local_state(evm, native_consensus)


def block_hash(url: str, height: int) -> str:
    result = rpc_batch(
        url,
        [
            {
                "jsonrpc": "2.0",
                "id": "block",
                "method": "eth_getBlockByNumber",
                "params": [hex(height), False],
            }
        ],
    ).get("block")
    if not isinstance(result, dict) or not result.get("hash"):
        raise RuntimeError(f"block {height} hash unavailable")
    return require_hash(result["hash"], f"block {height} hash")


def historical_state_pruned_error(error: Exception) -> bool:
    """Recognize the node's explicit pruned-state response, not generic RPC failure."""
    message = str(error).lower()
    return (
        "missing trie node" in message
        and "state" in message
        and ("not available" in message or "unavailable" in message)
    )


def check_archive_history() -> dict[str, Any]:
    anchors = (
        (
            "genesis",
            ARCHIVE_GENESIS_HEIGHT,
            ARCHIVE_GENESIS_HASH,
            ARCHIVE_GENESIS_ROOT,
        ),
        (
            "checkpoint",
            ARCHIVE_CHECKPOINT_HEIGHT,
            ARCHIVE_CHECKPOINT_HASH,
            ARCHIVE_CHECKPOINT_ROOT,
        ),
        (
            "producer_checkpoint",
            PRODUCER_CHECKPOINT_HEIGHT,
            PRODUCER_CHECKPOINT_HASH,
            PRODUCER_CHECKPOINT_ROOT,
        ),
    )
    calls: list[dict[str, Any]] = []
    for name, height, _expected_hash, _expected_root in anchors:
        calls.append(
            {
                "jsonrpc": "2.0",
                "id": f"{name}_block",
                "method": "eth_getBlockByNumber",
                "params": [hex(height), False],
            }
        )
    result = rpc_batch(
        LOCAL_RPC_URL, calls, timeout=max(RPC_TIMEOUT_SECONDS, 8)
    )
    details: dict[str, Any] = {}
    all_ok = True
    all_commitments_ok = True
    all_historical_state_reads_ok = True
    accepted_pruned_state = False
    for name, height, expected_hash, expected_root in anchors:
        block = result.get(f"{name}_block")
        actual_hash = (
            str(block.get("hash", "")).lower()
            if isinstance(block, dict)
            else ""
        )
        actual_root = (
            str(block.get("stateRoot", "")).lower()
            if isinstance(block, dict)
            else ""
        )
        commitment_ok = (
            actual_hash == expected_hash and actual_root == expected_root
        )
        balance = None
        balance_error = ""
        pruned_state = False
        try:
            balance = rpc_batch(
                LOCAL_RPC_URL,
                [
                    {
                        "jsonrpc": "2.0",
                        "id": f"{name}_balance",
                        "method": "eth_getBalance",
                        "params": [ARCHIVE_PROBE_ADDRESS, hex(height)],
                    }
                ],
                timeout=max(RPC_TIMEOUT_SECONDS, 8),
            ).get(f"{name}_balance")
        except Exception as exc:
            balance_error = bounded_error(exc)
            pruned_state = historical_state_pruned_error(exc)
        balance_ok = isinstance(balance, str) and bool(
            re.fullmatch(r"0x[0-9a-fA-F]+", balance)
        )
        pruned_state_accepted = bool(
            commitment_ok
            and pruned_state
            and not REQUIRE_HISTORICAL_STATE_TRIE
        )
        anchor_ok = commitment_ok and (balance_ok or pruned_state_accepted)
        details[name] = {
            "ok": anchor_ok,
            "height": height,
            "hash": actual_hash,
            "expected_hash": expected_hash,
            "state_root": actual_root,
            "expected_state_root": expected_root,
            "commitment_ok": commitment_ok,
            "historical_state_read_required": REQUIRE_HISTORICAL_STATE_TRIE,
            "historical_state_read_ok": balance_ok,
            "historical_state_read_error": balance_error or None,
            "pruned_historical_state_detected": pruned_state,
            "pruned_historical_state_accepted": pruned_state_accepted,
        }
        all_ok = all_ok and anchor_ok
        all_commitments_ok = all_commitments_ok and commitment_ok
        all_historical_state_reads_ok = (
            all_historical_state_reads_ok and balance_ok
        )
        accepted_pruned_state = accepted_pruned_state or pruned_state_accepted
    return {
        "ok": all_ok,
        "probe_address": ARCHIVE_PROBE_ADDRESS,
        "historical_state_read_required": REQUIRE_HISTORICAL_STATE_TRIE,
        "all_commitments_ok": all_commitments_ok,
        "all_historical_state_reads_ok": all_historical_state_reads_ok,
        "pruned_historical_state_accepted": accepted_pruned_state,
        "anchors": details,
    }


def check_storage() -> dict[str, Any]:
    stat = os.statvfs(DATA_PATH)
    total_bytes = stat.f_blocks * stat.f_frsize
    available_bytes = stat.f_bavail * stat.f_frsize
    free_percent = (
        available_bytes * 100.0 / total_bytes if total_bytes else 0.0
    )
    read_only = bool(stat.f_flag & getattr(os, "ST_RDONLY", 1))
    ok = (
        not read_only
        and available_bytes >= MIN_FREE_GIB * 1024**3
        and free_percent >= MIN_FREE_PERCENT
    )
    return {
        "ok": ok,
        "path": DATA_PATH,
        "read_only": read_only,
        "available_gib": round(available_bytes / 1024**3, 2),
        "total_gib": round(total_bytes / 1024**3, 2),
        "free_percent": round(free_percent, 2),
        "minimum_free_gib": MIN_FREE_GIB,
        "minimum_free_percent": MIN_FREE_PERCENT,
    }


def base_integrity_state(
    local: Mapping[str, Any], archive_history: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "ok": bool(local.get("ok") and archive_history.get("ok")),
        "updated_at": utc_now(),
        "updated_at_epoch": int(time.time()),
        "readiness_basis": (
            "certified-local-commitment-and-static-archive-anchors"
        ),
        "local_head": local.get("head"),
        "local_commitment": copy.deepcopy(local.get("committed_head")),
        "local_chain_id": local.get("chain_id"),
        "native_consensus": copy.deepcopy(local.get("native_consensus")),
        "native_consensus_fresh": local.get("native_consensus_fresh"),
        "local_readiness_mode": local.get("readiness_mode"),
        "archive_history": dict(archive_history),
        "external_reference_role": (
            "advisory-only-not-consensus-authority"
        ),
        "external_reference_url": WITNESS_RPC_URL,
    }


def check_alignment() -> dict[str, Any]:
    local = check_local_rpc_with_transient_grace()
    archive_history = check_archive_history()
    state = base_integrity_state(local, archive_history)
    try:
        remote = rpc_batch(
            WITNESS_RPC_URL,
            [
                {
                    "jsonrpc": "2.0",
                    "id": "chain",
                    "method": "eth_chainId",
                    "params": [],
                },
                {
                    "jsonrpc": "2.0",
                    "id": "head",
                    "method": "eth_blockNumber",
                    "params": [],
                },
            ],
            timeout=max(RPC_TIMEOUT_SECONDS, 8),
        )
        remote_chain_id = str(remote.get("chain", "")).lower()
        remote_head = parse_quantity(remote.get("head"))
    except Exception as exc:
        state.update(
            {
                "external_reference_available": False,
                "external_reference_ok": None,
                "remote_reference_error": bounded_error(exc),
                "remote_reference_error_at": utc_now(),
            }
        )
        return state

    compare_height = min(int(local["head"]), remote_head)
    local_hash = block_hash(LOCAL_RPC_URL, compare_height)
    try:
        remote_hash = block_hash(WITNESS_RPC_URL, compare_height)
    except Exception as exc:
        state.update(
            {
                "external_reference_available": False,
                "external_reference_ok": None,
                "remote_head": remote_head,
                "remote_chain_id": remote_chain_id,
                "compare_height": compare_height,
                "local_hash": local_hash,
                "remote_reference_error": bounded_error(exc),
                "remote_reference_error_at": utc_now(),
            }
        )
        return state

    remote_lag_blocks = max(0, remote_head - int(local["head"]))
    remote_lag_ok = remote_lag_blocks <= MAX_REMOTE_LAG_BLOCKS
    hash_match = bool(local_hash) and local_hash == remote_hash
    reference_ok = (
        remote_chain_id == EXPECTED_CHAIN_ID
        and hash_match
        and remote_lag_ok
    )
    state.update(
        {
            "external_reference_available": True,
            "external_reference_ok": reference_ok,
            "remote_head": remote_head,
            "local_minus_remote": int(local["head"]) - remote_head,
            "remote_lag_blocks": remote_lag_blocks,
            "max_remote_lag_blocks": MAX_REMOTE_LAG_BLOCKS,
            "remote_lag_ok": remote_lag_ok,
            "compare_height": compare_height,
            "remote_chain_id": remote_chain_id,
            "local_hash": local_hash,
            "remote_hash": remote_hash,
            "hash_match": hash_match,
        }
    )
    if not reference_ok:
        state["external_reference_warning"] = (
            "public witness differs or is too far ahead; investigate against "
            "producer-majority native and EVM commitments"
        )
    return state


def _failed_alignment(error: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "updated_at": utc_now(),
        "updated_at_epoch": int(time.time()),
        "error": bounded_error(error),
    }


def set_alignment_state(state: Mapping[str, Any]) -> None:
    with alignment_lock:
        alignment_state.clear()
        alignment_state.update(copy.deepcopy(dict(state)))


def alignment_worker() -> None:
    while True:
        try:
            state = check_alignment()
        except Exception as exc:
            # Static archive, local transport, canonical commitment, native
            # shutdown, and consensus failures withdraw readiness immediately.
            # The external public witness is handled as advisory in
            # check_alignment and never reaches this branch.
            state = _failed_alignment(exc)
        set_alignment_state(state)
        delay = (
            ALIGNMENT_INTERVAL_SECONDS
            if state.get("ok") is True
            else ALIGNMENT_FAILURE_RETRY_SECONDS
        )
        time.sleep(delay)


def current_alignment() -> dict[str, Any]:
    with alignment_lock:
        state = copy.deepcopy(alignment_state)
    age = int(time.time()) - int(state.get("updated_at_epoch") or 0)
    state["age_seconds"] = age
    archive_history = state.get("archive_history")
    archive_ok = (
        isinstance(archive_history, dict)
        and archive_history.get("ok") is True
    )
    state["fresh"] = (
        state.get("ok") is True
        and archive_ok
        and 0 <= age <= ALIGNMENT_MAX_AGE_SECONDS
    )
    state["max_age_seconds"] = ALIGNMENT_MAX_AGE_SECONDS
    return state


def readiness_snapshot() -> tuple[int, dict[str, Any]]:
    activation_hold = os.path.exists(ACTIVATION_HOLD_FILE)
    status: dict[str, Any] = {
        "ok": False,
        "checked_at": utc_now(),
        "activation_hold": {
            "active": activation_hold,
            "file": ACTIVATION_HOLD_FILE,
        },
    }
    code = 503
    try:
        local = check_local_rpc_with_transient_grace()
        storage = check_storage()
        alignment = current_alignment()
        ok = bool(
            local.get("ok")
            and storage.get("ok")
            and alignment.get("fresh")
            and not activation_hold
        )
        code = 200 if ok else 503
        status.update(
            {
                "ok": ok,
                "local_rpc": local,
                "storage": storage,
                "canonical_witness_alignment": alignment,
                "mining_ready": bool(
                    ok and local.get("mining_ready") is True
                ),
            }
        )
    except Exception as exc:
        status.update(
            {
                "ok": False,
                "error": bounded_error(exc),
                "canonical_witness_alignment": current_alignment(),
                "mining_ready": False,
            }
        )
    return code, status


class HealthHandler(BaseHTTPRequestHandler):
    server_version = f"blockdag-rpc-health/{VERSION}"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in ("/health", "/ready", "/"):
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        code, status = readiness_snapshot()
        self.send_json(code, status)

    def send_json(self, code: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def check_once() -> int:
    try:
        set_alignment_state(check_alignment())
    except Exception as exc:
        set_alignment_state(_failed_alignment(exc))
    code, status = readiness_snapshot()
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if code == 200 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-once",
        action="store_true",
        help="run a complete synchronous readiness check and exit",
    )
    parser.add_argument(
        "--version", action="store_true", help="print the health version and exit"
    )
    args = parser.parse_args(argv)
    if args.version:
        print(VERSION)
        return 0
    if args.check_once:
        return check_once()
    thread = threading.Thread(target=alignment_worker, daemon=True)
    thread.start()
    server = ThreadingHTTPServer((HEALTH_BIND, HEALTH_PORT), HealthHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
