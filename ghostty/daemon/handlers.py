import socket
import threading
import time
from typing import Any

from ghostty.protocol.constants import DEFAULT_MAX_WAIT_MS, DEFAULT_STABLE_MS
from ghostty.protocol.schemas import disconnected_payload
from ghostty.session import SessionState, recv_loop, send_actions, wait_for_stable

STATE = SessionState()


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


def handle_connect(req: dict[str, Any]) -> dict[str, Any]:
    host = req["host"]
    port = int(req.get("port", 23))
    width = int(req.get("width", 80))
    height = int(req.get("height", 24))

    with STATE.lock:
        if STATE.connected and STATE.socket_obj:
            STATE.socket_obj.close()
        STATE.configure_screen(width, height)
        STATE.screen_rev = 0
        STATE.stable_rev = 0

    sock = socket.create_connection((host, port), timeout=10)
    sock.settimeout(None)
    with STATE.lock:
        STATE.socket_obj = sock
        STATE.connected = True
        STATE.host = host
        STATE.port = port
        STATE.stop_event.clear()
        STATE.last_change_ts = time.time()
        STATE.recv_thread = threading.Thread(target=recv_loop, args=(STATE,), daemon=True)
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

    with STATE.lock:
        if not STATE.connected:
            return disconnected_payload()

    ok = True
    if mode == "stable":
        ok = wait_for_stable(state=STATE, stable_ms=stable_ms, max_wait_ms=max_wait_ms)

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
        }


def handle_send(req: dict[str, Any]) -> dict[str, Any]:
    stable_ms = int(req.get("stable_ms", DEFAULT_STABLE_MS))
    max_wait_ms = int(req.get("max_wait_ms", DEFAULT_MAX_WAIT_MS))
    actions = req.get("actions")
    if not actions:
        key = req.get("key")
        if key:
            actions = [{"k": "key", "key": key}]
        else:
            actions = []

    with STATE.action_lock:
        with STATE.lock:
            if not STATE.connected:
                return disconnected_payload()
        send_actions(state=STATE, actions=actions)
        ok = wait_for_stable(state=STATE, stable_ms=stable_ms, max_wait_ms=max_wait_ms)
        if not ok:
            with STATE.lock:
                if not STATE.connected:
                    return disconnected_payload()
            return {"ok": False, "error": "timeout_waiting_stable"}
        return handle_session_update({"mode": "latest"})
