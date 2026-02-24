from ghostty.daemon.handlers import extract_hints
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
