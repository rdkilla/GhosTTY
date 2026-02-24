import json
import os
import socketserver
from typing import Any

from ghostty.protocol.constants import ERR_UNKNOWN_COMMAND, SOCKET_PATH

from .handlers import handle_connect, handle_send, handle_session_update


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
                self.respond({"ok": False, "error": ERR_UNKNOWN_COMMAND})
        except Exception as exc:
            self.respond({"ok": False, "error": str(exc)})

    def respond(self, payload: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))


def run_server() -> None:
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    class UnixServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    with UnixServer(SOCKET_PATH, Handler) as server:
        server.serve_forever()
