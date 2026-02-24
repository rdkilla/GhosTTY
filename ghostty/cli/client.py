import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import socket

from ghostty.protocol.constants import SOCKET_PATH

DAEMON_CMD = [sys.executable, str(Path(__file__).resolve().parents[2] / "ghosttyd.py")]


def daemon_request(payload: dict[str, Any], autostart: bool = True) -> dict[str, Any]:
    try:
        return _request(payload)
    except OSError:
        if not autostart:
            raise
        start_daemon()
        return _request(payload)


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(SOCKET_PATH)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            part = sock.recv(65536)
            if not part:
                break
            data += part
    return json.loads(data.decode("utf-8").strip())


def start_daemon() -> None:
    subprocess.Popen(DAEMON_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            _request({"cmd": "ping"})
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("failed to start daemon")
