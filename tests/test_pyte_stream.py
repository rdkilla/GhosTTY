from pyte import Screen, Stream


def test_csi_sequence_does_not_stall_stream():
    screen = Screen(20, 5)
    stream = Stream(screen)

    stream.feed("HELLO")
    stream.feed("\x1b[2J")
    stream.feed("WORLD")

    assert screen.display[0].startswith("WORLD")


def test_unsupported_csi_sequence_is_ignored_and_text_continues():
    screen = Screen(20, 5)
    stream = Stream(screen)

    stream.feed("A\x1b[?25lB")

    assert screen.display[0].startswith("AB")


def test_newline_at_bottom_scrolls_screen():
    screen = Screen(6, 2)
    stream = Stream(screen)

    stream.feed("A\r\nB\r\nC")

    assert screen.display == ["B     ", "C     "]
