import hashlib
import json
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyte


def resolve_default_io_log_path() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "ghostty-io.log")


def resolve_default_frame_log_path() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "ghostty-frame-history.jsonl")


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
    frame_log_path: str | None = field(default_factory=resolve_default_frame_log_path)
    frame_log_lock: threading.Lock = field(default_factory=threading.Lock)
    telnet_pending: bytes = b""
    io_log_error_count: int = 0
    last_io_log_error: str | None = None
    frame_log_error_count: int = 0
    last_frame_log_error: str | None = None
    recv_error_count: int = 0
    last_recv_error: str | None = None
    frame_buffer_limit: int = 120
    frame_buffer: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=120))
    char_stream_limit: int = 200_000
    char_stream_chunks: deque[str] = field(default_factory=deque)
    char_stream_chars: int = 0
    total_app_chars: int = 0

    def configure_screen(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.screen = pyte.Screen(width, height)
        self.stream = pyte.Stream(self.screen)
        self.signature = self.compute_signature()
        self.telnet_pending = b""
        self.frame_buffer = deque(maxlen=self.frame_buffer_limit)
        self.char_stream_chunks = deque()
        self.char_stream_chars = 0
        self.total_app_chars = 0
        self.append_frame_snapshot()

    def reset_log_paths(self) -> None:
        self.io_log_path = resolve_default_io_log_path()
        self.frame_log_path = resolve_default_frame_log_path()

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
        frame = {
            "rev": self.screen_rev,
            "ts": time.time(),
            "text": self.render_text(),
        }
        self.frame_buffer.append(frame)
        try:
            self.log_frame_snapshot(frame)
        except OSError as err:
            self.record_frame_log_error(err)

    def frames_tail(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        frames = list(self.frame_buffer)[-limit:]
        return [{"rev": frame["rev"], "ts": frame["ts"], "text": list(frame["text"])} for frame in frames]

    def frames_query(self, limit: int, from_rev: int | None = None, to_rev: int | None = None) -> list[dict[str, Any]]:
        if limit < 0:
            limit = 0

        frames = list(self.frame_buffer)
        if from_rev is not None:
            frames = [frame for frame in frames if int(frame["rev"]) >= from_rev]
        if to_rev is not None:
            frames = [frame for frame in frames if int(frame["rev"]) <= to_rev]
        if limit > 0:
            frames = frames[-limit:]
        elif limit == 0:
            frames = []

        return [{"rev": frame["rev"], "ts": frame["ts"], "text": list(frame["text"])} for frame in frames]

    def append_char_stream(self, text: str) -> None:
        if not text:
            return

        self.char_stream_chunks.append(text)
        chunk_len = len(text)
        self.char_stream_chars += chunk_len
        self.total_app_chars += chunk_len

        while self.char_stream_chars > self.char_stream_limit and self.char_stream_chunks:
            dropped = self.char_stream_chunks.popleft()
            self.char_stream_chars -= len(dropped)

    def char_stream_tail(self, max_chars: int) -> dict[str, Any]:
        if max_chars < 0:
            max_chars = 0

        combined = "".join(self.char_stream_chunks)
        if max_chars == 0:
            text = ""
        elif len(combined) <= max_chars:
            text = combined
        else:
            text = combined[-max_chars:]

        return {
            "text": text,
            "returned_chars": len(text),
            "buffered_chars": self.char_stream_chars,
            "total_chars": self.total_app_chars,
            "truncated": len(combined) > len(text),
        }

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

    def log_frame_snapshot(self, frame: dict[str, Any]) -> None:
        if not self.frame_log_path:
            return

        payload = {
            "ts": frame["ts"],
            "rev": frame["rev"],
            "w": self.width,
            "h": self.height,
            "cursor": {"x": self.screen.cursor.x, "y": self.screen.cursor.y},
            "text": frame["text"],
        }
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with self.frame_log_lock:
            Path(self.frame_log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.frame_log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def record_io_log_error(self, err: Exception) -> None:
        with self.io_log_lock:
            self.io_log_error_count += 1
            self.last_io_log_error = str(err)

    def record_frame_log_error(self, err: Exception) -> None:
        with self.frame_log_lock:
            self.frame_log_error_count += 1
            self.last_frame_log_error = str(err)

    def record_recv_error(self, err: Exception) -> None:
        with self.io_log_lock:
            self.recv_error_count += 1
            self.last_recv_error = str(err)
