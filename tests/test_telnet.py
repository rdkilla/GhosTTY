from ghostty.session.telnet import IAC, DO, WILL, SB, SE, OPT_NAWS, OPT_TERMINAL_TYPE, parse_telnet_stream


def test_parse_telnet_negotiates_naws_and_filters_iac_from_screen_data():
    chunk = b"hello" + bytes([IAC, DO, OPT_NAWS]) + b"world"
    app, responses, pending = parse_telnet_stream(chunk=chunk, pending=b"", width=100, height=30)

    assert app == b"helloworld"
    assert pending == b""
    assert responses[0] == bytes([IAC, WILL, OPT_NAWS])
    assert responses[1] == bytes([IAC, SB, OPT_NAWS, 0, 100, 0, 30, IAC, SE])


def test_parse_telnet_handles_terminal_type_send_subnegotiation():
    chunk = bytes([IAC, SB, OPT_TERMINAL_TYPE, 1, IAC, SE])
    app, responses, pending = parse_telnet_stream(chunk=chunk, pending=b"", width=80, height=24)

    assert app == b""
    assert pending == b""
    assert responses == [bytes([IAC, SB, OPT_TERMINAL_TYPE, 0]) + b"XTERM-256COLOR" + bytes([IAC, SE])]


def test_parse_telnet_carries_incomplete_iac_sequence_between_chunks():
    app1, responses1, pending1 = parse_telnet_stream(
        chunk=bytes([IAC, DO]), pending=b"", width=80, height=24
    )
    assert app1 == b""
    assert responses1 == []
    assert pending1 == bytes([IAC, DO])

    app2, responses2, pending2 = parse_telnet_stream(
        chunk=bytes([OPT_NAWS]) + b"x", pending=pending1, width=80, height=24
    )
    assert app2 == b"x"
    assert pending2 == b""
    assert responses2[0] == bytes([IAC, WILL, OPT_NAWS])
