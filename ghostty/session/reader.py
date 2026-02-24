from typing import Any

from ghostty.protocol.constants import KEY_MAP

from .state import SessionState


def recv_loop(state: SessionState, connection_token: int) -> None:
    while True:
        with state.lock:
            if state.connection_token != connection_token or state.stop_event.is_set() or not state.socket_obj:
                return
            sock = state.socket_obj

        try:
            data = sock.recv(4096)
            if not data:
                with state.lock:
                    if state.connection_token == connection_token:
                        state.connected = False
                return
            text = data.decode("utf-8", errors="ignore")
            with state.lock:
                if state.connection_token != connection_token:
                    return
                state.stream.feed(text)
                state.update_revision_if_needed()
        except OSError:
            with state.lock:
                if state.connection_token == connection_token:
                    state.connected = False
            return


def send_actions(state: SessionState, actions: list[dict[str, Any]]) -> None:
    if not state.socket_obj:
        return
    for action in actions:
        kind = action.get("k")
        if kind == "key":
            key = action.get("key")
            n = int(action.get("n", 1))
            if key not in KEY_MAP:
                raise ValueError(f"unsupported key: {key}")
            payload = KEY_MAP[key].encode("utf-8") * n
            state.socket_obj.sendall(payload)
        elif kind == "type":
            text = action.get("text", "")
            state.socket_obj.sendall(text.encode("utf-8"))
        else:
            raise ValueError(f"unsupported action kind: {kind}")
