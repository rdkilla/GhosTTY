from ghostty.session.reader import _decode_terminal_text, _strip_synchronet_ctrl_a


def test_strip_synchronet_ctrl_a_sequences():
    text = "Welcome\x01n to \x01hBBS\x01w!"

    assert _strip_synchronet_ctrl_a(text) == "Welcome to BBS!"


def test_strip_synchronet_ctrl_a_preserves_escaped_literal_ctrl_a():
    text = "A\x01\x01B"

    assert _strip_synchronet_ctrl_a(text) == "A\x01B"


def test_decode_terminal_text_uses_cp437_and_strips_nuls_and_ctrl_a():
    data = b"\xb3\x00\x01nX"

    assert _decode_terminal_text(data) == "\u2502X"
