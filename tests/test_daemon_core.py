from threading import Lock

from ghostty.daemon import handlers
from ghostty.daemon.handlers import extract_hints, handle_send, handle_session_history, handle_session_update
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
        lambda payload, **kwargs: {"ok": False, "error": "timeout_waiting_stable"},
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


def test_default_io_log_path_is_repo_local():
    state = SessionState()

    assert state.io_log_path.endswith("ghostty-io.log")
    assert not state.io_log_path.startswith("/tmp/")


def test_default_frame_log_path_is_repo_local():
    state = SessionState()

    assert state.frame_log_path is not None
    assert state.frame_log_path.endswith("ghostty-frame-history.jsonl")
    assert not state.frame_log_path.startswith("/tmp/")


def test_cli_connect_uses_simple_payload(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr("sys.argv", ["ghostty", "connect", "example.com"])

    cli_main_module.main()

    assert captured["payload"]["cmd"] == "connect"
    assert captured["payload"]["host"] == "example.com"
    assert "io_log_path" not in captured["payload"]
    assert "frame_log_path" not in captured["payload"]


def test_cli_session_update_passes_buffer_query_options(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ghostty",
            "session",
            "update",
            "--include-frames",
            "--frame-limit",
            "5",
            "--include-char-stream",
            "--char-limit",
            "1200",
        ],
    )

    cli_main_module.main()

    assert captured["payload"]["include_frames"] is True
    assert captured["payload"]["frame_limit"] == 5
    assert captured["payload"]["include_char_stream"] is True
    assert captured["payload"]["char_limit"] == 1200


def test_cli_session_history_passes_query_options(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ghostty",
            "session",
            "history",
            "--limit",
            "7",
            "--from-rev",
            "2",
            "--to-rev",
            "8",
            "--include-char-stream",
            "--char-limit",
            "999",
        ],
    )

    cli_main_module.main()

    assert captured["payload"]["cmd"] == "session_history"
    assert captured["payload"]["limit"] == 7
    assert captured["payload"]["from_rev"] == 2
    assert captured["payload"]["to_rev"] == 8
    assert captured["payload"]["include_char_stream"] is True
    assert captured["payload"]["char_limit"] == 999


def test_cli_screen_maps_to_session_update_latest(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr("sys.argv", ["ghostty", "screen"])

    cli_main_module.main()

    assert captured["payload"] == {"cmd": "session_update", "mode": "latest"}


def test_cli_key_maps_to_send_key(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr("sys.argv", ["ghostty", "key", "Enter"])

    cli_main_module.main()

    assert captured["payload"] == {"cmd": "send", "key": "Enter"}


def test_cli_type_maps_to_send_type_action(monkeypatch):
    import importlib

    cli_main_module = importlib.import_module("ghostty.cli.main")
    captured = {}

    def fake_daemon_request(payload, **kwargs):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli_main_module, "daemon_request", fake_daemon_request)
    monkeypatch.setattr("sys.argv", ["ghostty", "type", "hello"])

    cli_main_module.main()

    assert captured["payload"] == {"cmd": "send", "actions": [{"k": "type", "text": "hello"}]}


def test_handle_connect_uses_default_log_paths(monkeypatch):
    class DummySocket:
        def settimeout(self, _timeout):
            return None

        def close(self):
            return None

    class DummyThread:
        def __init__(self, target=None, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            return None

        def is_alive(self):
            return False

        def join(self, timeout=None):
            return None

    state = SessionState()
    monkeypatch.setattr(handlers, "STATE", state)
    monkeypatch.setattr(handlers, "teardown_connection", lambda _state: None)
    monkeypatch.setattr(handlers.socket, "create_connection", lambda *args, **kwargs: DummySocket())
    monkeypatch.setattr(handlers.threading, "Thread", DummyThread)

    payload = handlers.handle_connect({"host": "example.com"})

    assert payload["ok"] is True
    assert state.io_log_path.endswith("ghostty-io.log")
    assert state.frame_log_path is not None
    assert state.frame_log_path.endswith("ghostty-frame-history.jsonl")



def test_session_update_includes_diag_block(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(10, 3)
    state.io_log_path = "./logs/io.log"
    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "latest"})

    assert payload["ok"] is True
    assert payload["diag"]["io_log_path"] == "./logs/io.log"
    assert payload["diag"]["recv_error_count"] == 0
    assert isinstance(payload["diag"]["last_change_age_ms"], int)
    assert payload["diag"]["frame_buffer_size"] >= 1
    assert payload["diag"]["frame_buffer_limit"] == state.frame_buffer_limit
    assert payload["diag"]["last_frame_rev"] == state.frame_buffer[-1]["rev"]
    assert payload["diag"]["frame_log_path"] == state.frame_log_path
    assert payload["diag"]["frame_log_error_count"] == 0
    assert payload["diag"]["char_stream_limit"] == state.char_stream_limit
    assert payload["diag"]["char_stream_total_chars"] == 0



def test_frame_buffer_tracks_revisions():
    state = SessionState(frame_buffer_limit=3)
    state.configure_screen(10, 3)

    # Initial frame captured at rev 0.
    assert len(state.frame_buffer) == 1
    assert state.frame_buffer[-1]["rev"] == 0

    state.stream.feed("A")
    state.update_revision_if_needed()
    state.stream.feed("B")
    state.update_revision_if_needed()
    state.stream.feed("C")
    state.update_revision_if_needed()

    assert state.screen_rev == 3
    assert len(state.frame_buffer) == 3
    assert [frame["rev"] for frame in state.frame_buffer] == [1, 2, 3]



def test_session_update_uses_latest_frame_buffer_snapshot(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(8, 2)
    state.stream.feed("BUF")
    state.update_revision_if_needed()

    # Simulate divergent live render path; payload should still come from frame buffer.
    state.render_text = lambda: ["LIVE____", "________"]

    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "latest"})

    assert payload["ok"] is True
    assert payload["screen"]["text"] == state.frame_buffer[-1]["text"]
    assert payload["screen_rev"] == state.frame_buffer[-1]["rev"]


def test_session_update_can_include_frame_history(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(8, 2)
    state.stream.feed("A")
    state.update_revision_if_needed()
    state.stream.feed("B")
    state.update_revision_if_needed()
    state.stream.feed("C")
    state.update_revision_if_needed()

    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "latest", "include_frames": True, "frame_limit": 2})

    assert payload["ok"] is True
    assert [frame["rev"] for frame in payload["frames"]] == [2, 3]
    assert len(payload["frames"]) == 2


def test_session_update_can_include_char_stream_tail(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(8, 2)
    state.append_char_stream("HELLO")

    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_update({"mode": "latest", "include_char_stream": True, "char_limit": 3})

    assert payload["ok"] is True
    assert payload["char_stream"]["text"] == "LLO"
    assert payload["char_stream"]["returned_chars"] == 3
    assert payload["char_stream"]["buffered_chars"] == 5
    assert payload["char_stream"]["total_chars"] == 5
    assert payload["char_stream"]["truncated"] is True


def test_session_history_filters_revisions(monkeypatch):
    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.configure_screen(8, 2)
    state.stream.feed("A")
    state.update_revision_if_needed()
    state.stream.feed("B")
    state.update_revision_if_needed()
    state.stream.feed("C")
    state.update_revision_if_needed()

    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_history({"limit": 10, "from_rev": 2, "to_rev": 3})

    assert payload["ok"] is True
    assert payload["connected"] is True
    assert payload["frame_count"] == 2
    assert [frame["rev"] for frame in payload["frames"]] == [2, 3]


def test_session_history_works_when_disconnected(monkeypatch):
    state = SessionState(connected=False, lock=Lock(), action_lock=Lock())
    state.configure_screen(8, 2)

    monkeypatch.setattr(handlers, "STATE", state)

    payload = handle_session_history({"limit": 5})

    assert payload["ok"] is True
    assert payload["connected"] is False
    assert payload["frame_count"] == 1


def test_frame_snapshot_logging_writes_jsonl(tmp_path):
    log_path = tmp_path / "frames.jsonl"
    state = SessionState(frame_log_path=str(log_path))
    state.configure_screen(6, 2)
    state.stream.feed("X")
    state.update_revision_if_needed()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert '"rev": 1' in lines[-1]
    assert '"w": 6' in lines[-1]


def test_recv_loop_records_unexpected_exception(monkeypatch):
    class BoomSocket:
        def recv(self, _n):
            return b"x"

    state = SessionState(connected=True, lock=Lock(), action_lock=Lock())
    state.socket_obj = BoomSocket()
    state.connection_token = 1

    def boom_parse(**_kwargs):
        raise RuntimeError("parse failed")

    monkeypatch.setattr("ghostty.session.reader.parse_telnet_stream", boom_parse)

    recv_loop(state, connection_token=1)

    assert state.connected is False
    assert state.recv_error_count == 1
    assert state.last_recv_error == "parse failed"
