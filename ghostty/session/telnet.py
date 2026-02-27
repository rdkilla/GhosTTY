from __future__ import annotations

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240

OPT_ECHO = 1
OPT_SUPPRESS_GO_AHEAD = 3
OPT_TERMINAL_TYPE = 24
OPT_NAWS = 31


def _u16be(n: int) -> tuple[int, int]:
    return ((n >> 8) & 0xFF, n & 0xFF)


def parse_telnet_stream(
    chunk: bytes,
    pending: bytes,
    width: int,
    height: int,
) -> tuple[bytes, list[bytes], bytes]:
    data = pending + chunk
    out = bytearray()
    responses: list[bytes] = []
    i = 0

    while i < len(data):
        b = data[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue

        if i + 1 >= len(data):
            return bytes(out), responses, data[i:]

        cmd = data[i + 1]
        if cmd == IAC:
            out.append(IAC)
            i += 2
            continue

        if cmd in (DO, DONT, WILL, WONT):
            if i + 2 >= len(data):
                return bytes(out), responses, data[i:]
            opt = data[i + 2]

            if cmd == WILL:
                if opt in (OPT_ECHO, OPT_SUPPRESS_GO_AHEAD):
                    responses.append(bytes([IAC, DO, opt]))
                else:
                    responses.append(bytes([IAC, DONT, opt]))
            elif cmd == DO:
                if opt in (OPT_SUPPRESS_GO_AHEAD, OPT_NAWS, OPT_TERMINAL_TYPE):
                    responses.append(bytes([IAC, WILL, opt]))
                    if opt == OPT_NAWS:
                        w_hi, w_lo = _u16be(width)
                        h_hi, h_lo = _u16be(height)
                        responses.append(bytes([IAC, SB, OPT_NAWS, w_hi, w_lo, h_hi, h_lo, IAC, SE]))
                else:
                    responses.append(bytes([IAC, WONT, opt]))
            i += 3
            continue

        if cmd == SB:
            end = data.find(bytes([IAC, SE]), i + 2)
            if end < 0:
                return bytes(out), responses, data[i:]
            body = data[i + 2 : end]
            if len(body) >= 2 and body[0] == OPT_TERMINAL_TYPE and body[1] == 1:
                term = b"XTERM-256COLOR"
                responses.append(bytes([IAC, SB, OPT_TERMINAL_TYPE, 0]) + term + bytes([IAC, SE]))
            i = end + 2
            continue

        i += 2

    return bytes(out), responses, b""
