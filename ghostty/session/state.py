import hashlib
import os
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyte


def resolve_default_io_log_path() -> str:
    env_path = os.environ.get("GHOSTTY_IO_LOG")
    if env_path:
        return env_path

    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "ghostty-io.log")


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
    first_change_ts: float = 0.0
    socket_obj: socket.socket | None = None
    recv_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    connection_token: int = 0
    signature: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)
    action_lock: threading.Lock = field(default_factory=threading.Lock)
    io_log_path: str = field(default_factory=resolve_default_io_log_path)
    io_log_lock: threading.Lock = field(default_factory=threading.Lock)
    telnet_pending: bytes = b""
    io_log_error_count: int = 0
    last_io_log_error: str | None = None
    recv_error_count: int = 0
    last_recv_error: str | None = None
    frame_buffer_limit: int = 120
    frame_buffer: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=120))

    def configure_screen(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.screen = pyte.Screen(width, height)
        self.stream = pyte.Stream(self.screen)
        self.signature = self.compute_signature()
        self.telnet_pending = b""
        self.frame_buffer = deque(maxlen=self.frame_buffer_limit)
        self.append_frame_snapshot()

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
            now = time.time()
            if self.screen_rev == 0:
                self.first_change_ts = now
            self.signature = new_sig
            self.screen_rev += 1
            self.last_change_ts = now
            self.append_frame_snapshot()

    def append_frame_snapshot(self) -> None:
        self.frame_buffer.append(
            {
                "rev": self.screen_rev,
                "ts": time.time(),
                "text": self.render_text(),
            }
        )


    def latest_frame(self) -> dict[str, Any] | None:
        if not self.frame_buffer:
            return None
        return self.frame_buffer[-1]

    def screen_payload_from_frame(self, frame: dict[str, Any] | None) -> dict[str, Any]:
        text = self.render_text() if frame is None else frame["text"]
        return {
            "w": self.width,
            "h": self.height,
            "text": text,
        }

    def screen_payload(self) -> dict[str, Any]:
        return {
            "w": self.width,
            "h": self.height,
            "text": self.render_text(),
        }

    def log_io(self, direction: str, data: bytes) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        escaped = data.decode("utf-8", errors="backslashreplace")
        line = f"{timestamp}Z dir={direction} len={len(data)} hex={data.hex()} text={escaped!r}\n"
        with self.io_log_lock:
            Path(self.io_log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.io_log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def record_io_log_error(self, err: Exception) -> None:
        with self.io_log_lock:
            self.io_log_error_count += 1
            self.last_io_log_error = str(err)

    def record_recv_error(self, err: Exception) -> None:
        with self.io_log_lock:
            self.recv_error_count += 1
            self.last_recv_error = str(err)
