import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import socket

from ghostty.protocol.constants import SOCKET_PATH

DAEMON_CMD = [sys.executable, str(Path(__file__).resolve().parents[2] / "ghosttyd.py")]


def daemon_request(payload: dict[str, Any], autostart: bool = True, verbose: bool = False) -> dict[str, Any]:
    try:
        return _request(payload)
    except OSError:
        if not autostart:
            raise
        start_daemon(verbose=verbose)
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


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def start_daemon(verbose: bool = False) -> None:
    daemon_log = os.environ.get("GHOSTTY_DAEMON_LOG")
    daemon_verbose = verbose or _env_flag("GHOSTTY_DAEMON_VERBOSE") or bool(daemon_log)

    popen_kwargs: dict[str, Any] = {"start_new_session": True}
    daemon_log_file = None
    if daemon_verbose:
        log_path = daemon_log or "/tmp/ghostty-daemon.log"
        daemon_log_file = open(log_path, "a", encoding="utf-8")
        popen_kwargs["stdout"] = daemon_log_file
        popen_kwargs["stderr"] = daemon_log_file
    else:
        popen_kwargs["stdout"] = subprocess.DEVNULL
        popen_kwargs["stderr"] = subprocess.DEVNULL

    try:
        subprocess.Popen(DAEMON_CMD, **popen_kwargs)
    finally:
        if daemon_log_file is not None:
            daemon_log_file.close()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            _request({"cmd": "ping"})
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("failed to start daemon")
