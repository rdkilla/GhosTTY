#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import socket
import socketserver
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import pyte

SOCKET_PATH = os.environ.get("GHOSTTY_SOCKET", "/tmp/ghosttyd.sock")
DEFAULT_STABLE_MS = 650
DEFAULT_MAX_WAIT_MS = 9000

KEY_MAP = {
    "Enter": "\r",
    "Esc": "\x1b",
    "Backspace": "\x08",
    "Tab": "\t",
    "Up": "\x1b[A",
    "Down": "\x1b[B",
    "Left": "\x1b[D",
    "Right": "\x1b[C",
}


@dataclass
class SessionState:
    connected: bool = False
    host: str | None = None
    port: int | None = None
    width: int = 80
    height: int = 24
    screen: pyte.Screen = field(default_factory=lambda: pyte.Screen(80, 24))
    stream: pyte.Stream = field(default_factory=pyte.Stream)
    screen_rev: int = 0
    stable_rev: int = 0
    last_change_ts: float = field(default_factory=time.time)
    last_stable_ts: float = field(default_factory=time.time)
    socket_obj: socket.socket | None = None
    recv_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    signature: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)
    action_lock: threading.Lock = field(default_factory=threading.Lock)

    def configure_screen(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.screen = pyte.Screen(width, height)
        self.stream = pyte.Stream(self.screen)
        self.signature = self.compute_signature()

    def compute_signature(self) -> str:
        text = "\n".join(self.render_text())
        cursor = f"{self.screen.cursor.x}:{self.screen.cursor.y}"
        return hashlib.sha256(f"{text}\n{cursor}".encode("utf-8")).hexdigest()

    def render_text(self) -> list[str]:
        lines: list[str] = []
        display = self.screen.display
        for i in range(self.height):
            line = display[i] if i < len(display) else ""
            line = line[: self.width].ljust(self.width)
            lines.append(line)
        return lines

    def update_revision_if_needed(self) -> None:
        new_sig = self.compute_signature()
        if new_sig != self.signature:
            self.signature = new_sig
            self.screen_rev += 1
            self.last_change_ts = time.time()

    def screen_payload(self) -> dict[str, Any]:
        return {
            "w": self.width,
            "h": self.height,
            "text": self.render_text(),
        }


STATE = SessionState()


def _recv_loop() -> None:
    while not STATE.stop_event.is_set() and STATE.socket_obj:
        try:
            data = STATE.socket_obj.recv(4096)
            if not data:
                with STATE.lock:
                    STATE.connected = False
                return
            text = data.decode("utf-8", errors="ignore")
            with STATE.lock:
                STATE.stream.feed(text)
                STATE.update_revision_if_needed()
        except OSError:
            with STATE.lock:
                STATE.connected = False
            return


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


def wait_for_stable(stable_ms: int, max_wait_ms: int) -> bool:
    start = time.time()
    while True:
        with STATE.lock:
            if not STATE.connected:
                return False
            since_change = (time.time() - STATE.last_change_ts) * 1000
            if since_change >= stable_ms:
                STATE.stable_rev = STATE.screen_rev
                STATE.last_stable_ts = time.time()
                return True
        if (time.time() - start) * 1000 >= max_wait_ms:
            return False
        time.sleep(0.05)


def send_actions(actions: list[dict[str, Any]]) -> None:
    if not STATE.socket_obj:
        return
    for action in actions:
        kind = action.get("k")
        if kind == "key":
            key = action.get("key")
            n = int(action.get("n", 1))
            if key not in KEY_MAP:
                raise ValueError(f"unsupported key: {key}")
            payload = KEY_MAP[key].encode("utf-8") * n
            STATE.socket_obj.sendall(payload)
        elif kind == "type":
            text = action.get("text", "")
            STATE.socket_obj.sendall(text.encode("utf-8"))
        else:
            raise ValueError(f"unsupported action kind: {kind}")


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        data = self.rfile.readline().decode("utf-8").strip()
        if not data:
            return
        req = json.loads(data)
        cmd = req.get("cmd")

        try:
            if cmd == "ping":
                self.respond({"ok": True})
            elif cmd == "connect":
                self.respond(handle_connect(req))
            elif cmd == "session_update":
                self.respond(handle_session_update(req))
            elif cmd == "send":
                self.respond(handle_send(req))
            else:
                self.respond({"ok": False, "error": "unknown_command"})
        except Exception as exc:
            self.respond({"ok": False, "error": str(exc)})

    def respond(self, payload: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))


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
        STATE.recv_thread = threading.Thread(target=_recv_loop, daemon=True)
        STATE.recv_thread.start()

    return {
        "ok": True,
        "connected": True,
        "host": host,
        "screen_rev": STATE.screen_rev,
    }


def disconnected_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": "connection_lost",
        "state": "disconnected",
    }


def handle_session_update(req: dict[str, Any]) -> dict[str, Any]:
    mode = req.get("mode", "latest")
    stable_ms = int(req.get("stable_ms", DEFAULT_STABLE_MS))
    max_wait_ms = int(req.get("max_wait_ms", DEFAULT_MAX_WAIT_MS))

    with STATE.lock:
        if not STATE.connected:
            return disconnected_payload()

    if mode == "stable":
        wait_for_stable(stable_ms=stable_ms, max_wait_ms=max_wait_ms)

    with STATE.lock:
        if not STATE.connected:
            return disconnected_payload()
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
        send_actions(actions)
        wait_for_stable(stable_ms=stable_ms, max_wait_ms=max_wait_ms)
        return handle_session_update({"mode": "latest"})


def run_server() -> None:
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    class UnixServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    with UnixServer(SOCKET_PATH, Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("serve", nargs="?", default="serve")
    parser.parse_args()
    run_server()
