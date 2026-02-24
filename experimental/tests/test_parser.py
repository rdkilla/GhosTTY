from experimental.app.parser import normalize_screen


def test_normalize_screen_strips_ansi_and_ctrl():
    raw = "\x1b[31mHELLO\x1b[0m\r\nWOR\x08LD> "
    text, lines, prompt, h = normalize_screen(raw)
    assert "\x1b" not in text
    assert "HELLO" in text
    assert lines[-1].endswith(">")
    assert prompt is True
    assert h.startswith("sha256:")
