import socket
import threading
import time
from typing import Any

from ghostty.protocol.constants import (
    DEFAULT_MAX_WAIT_MS,
    DEFAULT_STABLE_MS,
    DEFAULT_STABLE_WARMUP_MS,
    KEY_MAP,
)
from ghostty.protocol.schemas import disconnected_payload
from ghostty.session import SessionState, recv_loop, send_actions, wait_for_stable

STATE = SessionState()


def _validate_actions(actions: Any) -> bool:
    if not isinstance(actions, list) or len(actions) == 0:
        return False

    for action in actions:
        if not isinstance(action, dict):
            return False

        kind = action.get("k")
        if kind not in {"key", "type"}:
            return False

        if "n" in action:
            try:
                n = int(action["n"])
            except (TypeError, ValueError):
                return False
            if n < 1:
                return False

        if kind == "key":
            key = action.get("key")
            if not isinstance(key, str) or key not in KEY_MAP:
                return False
        elif kind == "type":
            if not isinstance(action.get("text"), str):
                return False

    return True


def extract_hints(text_lines: list[str]) -> dict[str, Any]:
    raw = "\n".join(text_lines)
    stripped = [line.rstrip() for line in text_lines]
    mode = "unknown"
    prompt = None
    choices = []
    pager = False

    for line in stripped:
        if not line:
            continue
        if line.endswith((">", ":", "$", "#")):
            mode = "prompt"
            prompt = line[-1]
        if line.lower().startswith(("[more]", "--more--")):
            mode = "pager"
            pager = True
        if line[:1].isdigit() and ")" in line:
            mode = "menu"
            key = line.split(")", 1)[0]
            label = line.split(")", 1)[1].strip()
            choices.append({"key": key, "label": label})

    if "press any key" in raw.lower():
        pager = True
        mode = "pager"

    return {
        "mode": mode,
        "prompt": prompt,
        "choices": choices,
        "pager": pager,
    }


def teardown_connection(state: SessionState, join_timeout: float = 1.0) -> None:
    with state.lock:
        state.stop_event.set()
        old_socket = state.socket_obj
        old_thread = state.recv_thread
        state.socket_obj = None

    if old_socket:
        try:
            old_socket.close()
        except OSError:
            pass

    current = threading.current_thread()
    if old_thread and old_thread is not current and old_thread.is_alive():
        old_thread.join(timeout=join_timeout)


def handle_connect(req: dict[str, Any]) -> dict[str, Any]:
    host = req["host"]
    port = int(req.get("port", 23))
    width = int(req.get("width", 80))
    height = int(req.get("height", 24))
    io_log_path = req.get("io_log_path")

    teardown_connection(STATE)

    with STATE.lock:
        STATE.configure_screen(width, height)
        STATE.screen_rev = 0
        STATE.stable_rev = 0
        STATE.first_change_ts = 0.0
        STATE.io_log_error_count = 0
        STATE.last_io_log_error = None
        STATE.recv_error_count = 0
        STATE.last_recv_error = None
        if io_log_path:
            STATE.io_log_path = str(io_log_path)

    sock = socket.create_connection((host, port), timeout=10)
    sock.settimeout(None)

    with STATE.lock:
        STATE.connection_token += 1
        connection_token = STATE.connection_token
        STATE.socket_obj = sock
        STATE.connected = True
        STATE.host = host
        STATE.port = port
        STATE.stop_event = threading.Event()
        STATE.last_change_ts = time.time()
        STATE.recv_thread = threading.Thread(target=recv_loop, args=(STATE, connection_token), daemon=True)
        STATE.recv_thread.start()

    return {
        "ok": True,
        "connected": True,
        "host": host,
        "screen_rev": STATE.screen_rev,
    }


def handle_session_update(req: dict[str, Any]) -> dict[str, Any]:
    mode = req.get("mode", "latest")
    stable_ms = int(req.get("stable_ms", DEFAULT_STABLE_MS))
    max_wait_ms = int(req.get("max_wait_ms", DEFAULT_MAX_WAIT_MS))
    stable_warmup_ms = int(req.get("stable_warmup_ms", DEFAULT_STABLE_WARMUP_MS))

    with STATE.lock:
        if not STATE.connected:
            return disconnected_payload()

    ok = True
    if mode == "stable":
        ok = wait_for_stable(
            state=STATE,
            stable_ms=stable_ms,
            max_wait_ms=max_wait_ms,
            stable_warmup_ms=stable_warmup_ms,
        )

    with STATE.lock:
        if not STATE.connected:
            return disconnected_payload()
        if not ok:
            return {"ok": False, "error": "timeout_waiting_stable"}
        text = STATE.render_text()
        return {
            "ok": True,
            "stable": mode == "stable",
            "screen_rev": STATE.screen_rev,
            "cursor": {"x": STATE.screen.cursor.x, "y": STATE.screen.cursor.y},
            "screen": STATE.screen_payload(),
            "hints": extract_hints(text),
            "diag": {
                "io_log_path": STATE.io_log_path,
                "io_log_error_count": STATE.io_log_error_count,
                "last_io_log_error": STATE.last_io_log_error,
                "recv_error_count": STATE.recv_error_count,
                "last_recv_error": STATE.last_recv_error,
                "last_change_age_ms": int((time.time() - STATE.last_change_ts) * 1000),
            },
        }


def handle_send(req: dict[str, Any]) -> dict[str, Any]:
    stable_ms = int(req.get("stable_ms", DEFAULT_STABLE_MS))
    max_wait_ms = int(req.get("max_wait_ms", DEFAULT_MAX_WAIT_MS))
    stable_warmup_ms = int(req.get("stable_warmup_ms", DEFAULT_STABLE_WARMUP_MS))
    actions = req.get("actions")
    if not actions:
        key = req.get("key")
        if key:
            actions = [{"k": "key", "key": key}]
        else:
            actions = []

    if not _validate_actions(actions):
        return {"ok": False, "error": "invalid_action"}

    with STATE.action_lock:
        with STATE.lock:
            if not STATE.connected:
                return disconnected_payload()
        try:
            send_actions(state=STATE, actions=actions)
        except ValueError:
            return {"ok": False, "error": "invalid_action"}
        ok = wait_for_stable(
            state=STATE,
            stable_ms=stable_ms,
            max_wait_ms=max_wait_ms,
            stable_warmup_ms=stable_warmup_ms,
        )
        if not ok:
            with STATE.lock:
                if not STATE.connected:
                    return disconnected_payload()
            return {"ok": False, "error": "timeout_waiting_stable"}
        return handle_session_update({"mode": "latest"})
