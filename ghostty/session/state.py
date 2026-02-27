import hashlib
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import pyte


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
            now = time.time()
            if self.screen_rev == 0:
                self.first_change_ts = now
            self.signature = new_sig
            self.screen_rev += 1
            self.last_change_ts = now

    def screen_payload(self) -> dict[str, Any]:
        return {
            "w": self.width,
            "h": self.height,
            "text": self.render_text(),
        }
