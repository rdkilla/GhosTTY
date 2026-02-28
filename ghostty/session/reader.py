from typing import Any

from ghostty.protocol.constants import KEY_MAP

from .state import SessionState
from .telnet import parse_telnet_stream


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
            try:
                state.log_io("in", data)
            except OSError as err:
                state.record_io_log_error(err)

            with state.lock:
                if state.connection_token != connection_token:
                    return
                app_data, responses, pending = parse_telnet_stream(
                    chunk=data,
                    pending=state.telnet_pending,
                    width=state.width,
                    height=state.height,
                )
                state.telnet_pending = pending
                for payload in responses:
                    try:
                        state.log_io("out", payload)
                    except OSError as err:
                        state.record_io_log_error(err)
                    sock.sendall(payload)
                text = app_data.decode("utf-8", errors="ignore")
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
            state.log_io("out", payload)
            state.socket_obj.sendall(payload)
        elif kind == "type":
            text = action.get("text", "")
            payload = text.encode("utf-8")
            state.log_io("out", payload)
            state.socket_obj.sendall(payload)
        else:
            raise ValueError(f"unsupported action kind: {kind}")
