import os

SOCKET_PATH = os.environ.get("GHOSTTY_SOCKET", "/tmp/ghosttyd.sock")
DEFAULT_STABLE_MS = 650
DEFAULT_MAX_WAIT_MS = 9000
DEFAULT_STABLE_WARMUP_MS = 2000

ERR_UNKNOWN_COMMAND = "unknown_command"
ERR_CONNECTION_LOST = "connection_lost"

KEY_MAP = {
    "Enter": "\r",
    "Esc": "\x1b",
    "Backspace": "\x08",
    "Tab": "\t",
    "Up": "\x1b[A",
    "Down": "\x1b[B",
    "Left": "\x1b[D",
    "Right": "\x1b[C",
}
