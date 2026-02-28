from typing import Any

from ghostty.protocol.constants import KEY_MAP

from .state import SessionState
from .telnet import parse_telnet_stream


def _strip_synchronet_ctrl_a(text: str) -> str:
    """Strip Synchronet Ctrl-A attribute codes from display text.

    Synchronet commonly encodes color/style control as \x01 + <code>. These
    bytes should affect styling in a terminal, not appear as literal glyphs in
    the text grid. We strip the pair while preserving an escaped literal Ctrl-A
    represented as a doubled \x01\x01 sequence.
    """

    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch != "\x01":
            out.append(ch)
            i += 1
            continue

        if i + 1 >= len(text):
            break

        nxt = text[i + 1]
        if nxt == "\x01":
            out.append("\x01")
        i += 2

    return "".join(out)


def _decode_terminal_text(data: bytes) -> str:
    """Decode telnet application bytes for BBS-style terminals.

    - CP437 preserves common DOS/BBS glyphs that UTF-8+ignore drops.
    - NUL bytes are ignored for screen rendering.
    - Synchronet Ctrl-A attribute codes are stripped.
    """

    text = data.decode("cp437", errors="replace")
    text = text.replace("\x00", "")
    return _strip_synchronet_ctrl_a(text)


def _decode_raw_app_text(data: bytes) -> str:
    """Decode raw application bytes without display normalization."""

    return data.decode("cp437", errors="replace")


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
                state.append_char_stream(_decode_raw_app_text(app_data))
                text = _decode_terminal_text(app_data)
                state.stream.feed(text)
                state.update_revision_if_needed()
        except OSError as err:
            with state.lock:
                if state.connection_token == connection_token:
                    state.connected = False
                    state.record_recv_error(err)
            return
        except Exception as err:
            with state.lock:
                if state.connection_token == connection_token:
                    state.connected = False
                    state.record_recv_error(err)
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
