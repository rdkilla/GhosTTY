from threading import Lock

from ghostty.daemon import handlers
from ghostty.daemon.handlers import extract_hints, handle_send, handle_session_update
from ghostty.session import recv_loop
from ghostty.session.state import SessionState


def test_fixed_grid_shape():
    state = SessionState()
    state.configure_screen(10, 3)
    state.stream.feed("hello")
    lines = state.render_text()
    assert len(lines) == 3
    assert all(len(line) == 10 for line in lines)
    assert lines[0].startswith("hello")


def test_signature_changes_with_cursor_move():
    state = SessionState()
    state.configure_screen(10, 3)
    sig1 = state.compute_signature()
    state.stream.feed("A")
    sig2 = state.compute_signature()
    assert sig1 != sig2


def test_hint_menu_detection():
    hints = extract_hints(["1) Messages", "2) Files"])
    assert hints["mode"] == "menu"
    assert hints["choices"][0]["key"] == "1"


def test_session_update_stable_timeout_returns_timeout_error(monkeypatch):
    monkeypatch.setattr(handlers, "wait_for_stable", lambda **kwargs: False)

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "stable", "stable_ms": 1, "max_wait_ms": 1})

    assert payload == {"ok": False, "error": "timeout_waiting_stable"}


def test_session_update_stable_disconnect_returns_connection_lost(monkeypatch):
    def fake_wait_for_stable(**kwargs):
        kwargs["state"].connected = False
        return False

    monkeypatch.setattr(handlers, "wait_for_stable", fake_wait_for_stable)

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "stable", "stable_ms": 1, "max_wait_ms": 1})

    assert payload["ok"] is False
    assert payload["error"] == "connection_lost"
    assert payload["state"] == "disconnected"


def test_send_timeout_returns_timeout_error(monkeypatch):
    monkeypatch.setattr(handlers, "send_actions", lambda **kwargs: None)
    monkeypatch.setattr(handlers, "wait_for_stable", lambda **kwargs: False)

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": [{"k": "key", "key": "Enter"}], "stable_ms": 1, "max_wait_ms": 1})

    assert payload == {"ok": False, "error": "timeout_waiting_stable"}


def test_send_disconnect_returns_connection_lost(monkeypatch):
    monkeypatch.setattr(handlers, "send_actions", lambda **kwargs: None)

    def fake_wait_for_stable(**kwargs):
        kwargs["state"].connected = False
        return False

    monkeypatch.setattr(handlers, "wait_for_stable", fake_wait_for_stable)

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": [{"k": "key", "key": "Enter"}], "stable_ms": 1, "max_wait_ms": 1})

    assert payload["ok"] is False
    assert payload["error"] == "connection_lost"
    assert payload["state"] == "disconnected"


def test_cli_prints_timeout_error_json_unchanged(capsys, monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")

    monkeypatch.setattr(
        cli_main_module,
        "daemon_request",
        lambda payload: {"ok": False, "error": "timeout_waiting_stable"},
    )
    monkeypatch.setattr("sys.argv", ["ghostty", "session", "update", "--mode", "stable"])

    cli_main_module.main()

    out = capsys.readouterr().out
    assert '"ok": false' in out
    assert '"error": "timeout_waiting_stable"' in out


def test_send_rejects_unsupported_key(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": [{"k": "key", "key": "NotARealKey"}]})

    assert payload == {"ok": False, "error": "invalid_action"}


def test_send_rejects_unknown_action_kind(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": [{"k": "noop"}]})

    assert payload == {"ok": False, "error": "invalid_action"}


def test_send_rejects_missing_required_fields(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload_key = handle_send({"actions": [{"k": "key"}]})
    payload_type = handle_send({"actions": [{"k": "type"}]})

    assert payload_key == {"ok": False, "error": "invalid_action"}
    assert payload_type == {"ok": False, "error": "invalid_action"}


def test_send_rejects_empty_actions_payload(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": []})

    assert payload == {"ok": False, "error": "invalid_action"}


def test_send_converts_send_actions_value_error(monkeypatch):
    def fake_send_actions(**kwargs):
        raise ValueError("unsupported action kind: nope")

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)
    monkeypatch.setattr(handlers, "send_actions", fake_send_actions)

    payload = handle_send({"actions": [{"k": "key", "key": "Enter"}]})

    assert payload == {"ok": False, "error": "invalid_action"}


def test_send_rejects_non_positive_repeat_count(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_send({"actions": [{"k": "key", "key": "Enter", "n": 0}]})

    assert payload == {"ok": False, "error": "invalid_action"}


def test_log_io_writes_hex_and_escaped_text(tmp_path):
    state = SessionState(io_log_path=str(tmp_path / "io.log"))

    state.log_io("in", b"\x01\x03A")

    content = (tmp_path / "io.log").read_text(encoding="utf-8")
    assert "dir=in" in content
    assert "len=3" in content
    assert "hex=010341" in content
    assert "'\\x01\\x03A'" in content


class _OneShotSocket:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._delivered = False

    def recv(self, size: int) -> bytes:
        if self._delivered:
            return b""
        self._delivered = True
        return self._payload

    def sendall(self, payload: bytes) -> None:
        return


def test_recv_loop_continues_when_inbound_log_io_fails(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(20, 3)
    state.connection_token = 7
    state.socket_obj = _OneShotSocket(b"hello")

    fed: list[str] = []

    def fake_feed(text: str) -> None:
        fed.append(text)
        state.stop_event.set()

    state.stream.feed = fake_feed

    def flaky_log(direction: str, data: bytes) -> None:
        if direction == "in":
            raise OSError("io log write failed")

    state.log_io = flaky_log

    recv_loop(state, connection_token=7)

    assert fed == ["hello"]
    assert state.connected is True
    assert state.io_log_error_count == 1
    assert state.last_io_log_error == "io log write failed"
