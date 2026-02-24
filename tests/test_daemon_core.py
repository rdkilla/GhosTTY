from threading import Lock

from ghostty.daemon import handlers
from ghostty.daemon.handlers import extract_hints, handle_send, handle_session_update
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
