import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from .parser import normalize_screen

IAC = 255
DO = 253
DONT = 254
WILL = 251
WONT = 252
SB = 250
SE = 240


@dataclass
class SessionState:
    session_id: str
    host: str
    port: int
    created_at: datetime
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    buffer: bytearray = field(default_factory=bytearray)
    seq: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    read_task: asyncio.Task | None = None


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(self, host: str, port: int) -> SessionState:
        reader, writer = await asyncio.open_connection(host, port)
        session_id = str(uuid.uuid4())
        state = SessionState(
            session_id=session_id,
            host=host,
            port=port,
            created_at=datetime.now(timezone.utc),
            reader=reader,
            writer=writer,
        )
        state.read_task = asyncio.create_task(self._reader_loop(state), name=f"read-{session_id}")
        async with self._lock:
            self._sessions[session_id] = state
        return state

    async def get(self, session_id: str) -> SessionState:
        async with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
            return self._sessions[session_id]

    async def close(self, session_id: str) -> None:
        async with self._lock:
            state = self._sessions.pop(session_id, None)
        if state is None:
            return
        if state.read_task:
            state.read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.read_task
        state.writer.close()
        with contextlib.suppress(Exception):
            await state.writer.wait_closed()

    async def send(self, session_id: str, payload: str, wait_ms: int) -> int:
        state = await self.get(session_id)
        async with state.lock:
            data = payload.encode("utf-8", errors="ignore")
            state.writer.write(data)
            await state.writer.drain()
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000)
            return len(data)

    async def snapshot(self, session_id: str) -> dict:
        state = await self.get(session_id)
        raw = state.buffer.decode("utf-8", errors="ignore")
        raw_text, lines, prompt_detected, screen_hash = normalize_screen(raw)
        return {
            "session_id": session_id,
            "seq": state.seq,
            "timestamp": state.timestamp,
            "raw_text": raw_text,
            "lines": lines,
            "prompt_detected": prompt_detected,
            "screen_hash": screen_hash,
        }

    async def subscribe(self, session_id: str) -> AsyncGenerator[dict, None]:
        state = await self.get(session_id)
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        state.subscribers.append(queue)
        try:
            # initial snapshot
            yield await self.snapshot(session_id)
            while True:
                item = await queue.get()
                yield item
        finally:
            with contextlib.suppress(ValueError):
                state.subscribers.remove(queue)

    async def _reader_loop(self, state: SessionState) -> None:
        while True:
            chunk = await state.reader.read(1024)
            if not chunk:
                return
            cooked = self._strip_telnet_iac(state.writer, chunk)
            if cooked:
                state.buffer.extend(cooked)
                if len(state.buffer) > 200_000:
                    del state.buffer[:-120_000]
                state.seq += 1
                state.timestamp = datetime.now(timezone.utc)
                snap = {
                    "session_id": state.session_id,
                    "seq": state.seq,
                    "timestamp": state.timestamp,
                    "raw_text": normalize_screen(state.buffer.decode("utf-8", errors="ignore"))[0],
                    "lines": normalize_screen(state.buffer.decode("utf-8", errors="ignore"))[1],
                    "prompt_detected": normalize_screen(state.buffer.decode("utf-8", errors="ignore"))[2],
                    "screen_hash": normalize_screen(state.buffer.decode("utf-8", errors="ignore"))[3],
                }
                for q in list(state.subscribers):
                    if q.full():
                        with contextlib.suppress(asyncio.QueueEmpty):
                            q.get_nowait()
                    with contextlib.suppress(asyncio.QueueFull):
                        q.put_nowait(snap)

    def _strip_telnet_iac(self, writer: asyncio.StreamWriter, data: bytes) -> bytes:
        out = bytearray()
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b != IAC:
                out.append(b)
                i += 1
                continue
            if i + 1 >= n:
                break
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= n:
                    break
                opt = data[i + 2]
                if cmd in (DO, DONT):
                    writer.write(bytes([IAC, WONT, opt]))
                else:
                    writer.write(bytes([IAC, DONT, opt]))
                i += 3
            elif cmd == SB:
                i += 2
                while i + 1 < n and not (data[i] == IAC and data[i + 1] == SE):
                    i += 1
                i += 2
            else:
                i += 2
        return bytes(out)
