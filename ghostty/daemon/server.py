import json
import logging
import os
import socketserver
from typing import Any

from ghostty.protocol.constants import ERR_UNKNOWN_COMMAND, SOCKET_PATH

from .handlers import handle_connect, handle_send, handle_session_update

LOGGER = logging.getLogger("ghostty.daemon")


def _configure_logging() -> None:
    if LOGGER.handlers:
        return

    log_path = os.environ.get("GHOSTTY_DAEMON_LOG", "/tmp/ghostty-daemon.log")
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s event=%(event)s cmd=%(cmd)s detail=%(detail)s"
    )
    handler.setFormatter(formatter)

    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        data = self.rfile.readline().decode("utf-8").strip()
        if not data:
            return

        req: dict[str, Any] | None = None
        cmd: str | None = None
        try:
            req = json.loads(data)
            cmd = req.get("cmd")

            if cmd == "ping":
                self.respond({"ok": True})
            elif cmd == "connect":
                self.respond(handle_connect(req))
            elif cmd == "session_update":
                self.respond(handle_session_update(req))
            elif cmd == "send":
                self.respond(handle_send(req))
            else:
                self.respond({"ok": False, "error": ERR_UNKNOWN_COMMAND})
        except Exception as exc:
            LOGGER.exception(
                "request handling failed",
                extra={"event": "request_error", "cmd": cmd or "unknown", "detail": str(exc)},
            )
            self.respond({"ok": False, "error": str(exc)})

    def respond(self, payload: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))


def run_server() -> None:
    _configure_logging()

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    class UnixServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    try:
        with UnixServer(SOCKET_PATH, Handler) as server:
            LOGGER.info(
                "daemon serving",
                extra={"event": "server_start", "cmd": "serve", "detail": SOCKET_PATH},
            )
            server.serve_forever()
    except Exception as exc:
        LOGGER.exception(
            "daemon server loop crashed",
            extra={"event": "server_error", "cmd": "serve", "detail": str(exc)},
        )
        raise
