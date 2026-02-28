# 👻 GhosTTY

GhosTTY is a lightweight **daemon + CLI** system for automating terminal-style telnet workflows through a deterministic JSON interface.

At runtime, you interact with a single command-line client (`ghostty.py` / `./ghostty`) that talks to a local Unix-socket daemon (`ghosttyd.py`). The daemon owns exactly one live telnet session and one terminal screen model.

---

## What this project provides

- A canonical CLI for machine/agent usage:
  - `connect`
  - `screen`
  - `key`
  - `type`
  - `session update`
  - `session history`
  - `send`
- A local daemon that:
  - maintains one telnet connection,
  - renders terminal output into a fixed-size text grid via `pyte`,
  - tracks revision/stability for deterministic reads,
  - serializes actions to avoid race conditions.
- JSON-first responses designed for automation.

---

## Current working command surface (repo rescan)

The authoritative CLI entrypoint is:

```bash
python3 ghostty.py --help
```

Current top-level commands:

- `connect`
- `session`
  - `update`
  - `history`
- `send`
- `screen`
- `key`
- `type`

### Quick help checklist

Use these any time to confirm command wiring in your local checkout:

```bash
python3 ghostty.py --help
python3 ghostty.py connect --help
python3 ghostty.py session --help
python3 ghostty.py session update --help
python3 ghostty.py session history --help
python3 ghostty.py send --help
python3 ghostty.py screen --help
python3 ghostty.py key --help
python3 ghostty.py type --help
```

### Runtime daemon command contract

The Unix-socket daemon accepts these JSON `cmd` values:

- `ping`
- `connect`
- `session_update`
- `session_history`
- `send`

The CLI wrappers map to daemon commands as follows:

- `connect` → `connect`
- `screen` → `session_update` with `mode=latest`
- `session update` → `session_update`
- `session history` → `session_history`
- `key` → `send` with a single key action
- `type` → `send` with a single type action
- `send` → `send`

---

## Core working functions by module

This section documents the current "working functions" that define the canonical behavior.

- `ghostty/cli/main.py`
  - `main()`: command parser + CLI → daemon payload mapping.
  - `print_json()`: stable JSON output formatting.
- `ghostty/cli/client.py`
  - `daemon_request()`: request + optional daemon autostart.
  - `start_daemon()`: background daemon launch + readiness ping.
- `ghostty/daemon/server.py`
  - `Handler.handle()`: receives JSON command and dispatches handlers.
  - `run_server()`: binds Unix socket and serves forever.
- `ghostty/daemon/handlers.py`
  - `handle_connect()`: establish/replace telnet session and recv thread.
  - `handle_session_update()`: latest/stable snapshot payload (+ optional frames/char stream).
  - `handle_session_history()`: filtered in-memory frame history.
  - `handle_send()`: validate/execute actions and wait for stability.
  - `extract_hints()`: prompt/menu/pager heuristics from rendered text.
- `ghostty/session/reader.py`
  - `recv_loop()`: telnet receive loop, telnet negotiation, pyte feed, revision updates.
  - `send_actions()`: emits key/type actions to telnet socket.
- `ghostty/session/stability.py`
  - `wait_for_stable()`: stable-state wait logic using revision timing windows.

---

## Repository layout

```text
.
├── ghostty/                  # Core Python package
│   ├── cli/                  # CLI parser + daemon client/autostart
│   ├── daemon/               # Unix socket server + command handlers
│   ├── session/              # Session state, recv loop, stability logic
│   └── protocol/             # Shared constants and payload helpers
├── tests/                    # Canonical daemon/CLI tests
├── experimental/             # Non-canonical experimental app and tests
├── ghostty.py                # CLI entrypoint script
├── ghosttyd.py               # Daemon entrypoint script
├── pyte.py                   # Local shim for pyte import compatibility
├── Makefile                  # run/lint/test/check helpers
└── README.md
```

---

## Runtime architecture

```text
ghostty CLI
    ↓ (JSON over Unix domain socket)
ghostty daemon
    ↓ (telnet socket)
remote host

Daemon internals:
  recv thread → pyte.Stream/Screen → fixed-grid screen payload
                          ↓
                   stability/revision engine
```

Key behavior:

- **Single session model**: one active connection in process-global state.
- **Fixed grid output**: responses include `screen.w`, `screen.h`, and space-padded `screen.text` lines.
- **Stability semantics**:
  - `latest` returns immediately.
  - `stable` waits until screen changes settle for `stable_ms`.
- **Fatal disconnects**: if the socket drops, responses return `connection_lost`; no auto-reconnect.
- **I/O diagnostics log**: inbound and outbound telnet bytes are appended to `./ghostty-io.log` in the repo directory.
- **Frame history log**: each framebuffer revision is appended as JSONL to `./ghostty-frame-history.jsonl` in the repo directory.

---

### Logging and diagnostics

Daemon autostart from the CLI is quiet by default (stdout/stderr to `/dev/null`). To capture daemon output and exceptions:

```bash
python3 ghostty.py --verbose connect <host>
# or
GHOSTTY_DAEMON_VERBOSE=1 python3 ghostty.py connect <host>
# or (also enables logging)
GHOSTTY_DAEMON_LOG=/tmp/my-ghostty-daemon.log python3 ghostty.py connect <host>
```

Log locations:

- Daemon/server log: `/tmp/ghostty-daemon.log` (when enabled).
- Telnet I/O log: `./ghostty-io.log` (repo root).
- Frame history JSONL log: `./ghostty-frame-history.jsonl` (repo root).

## Installation

### Requirements

- Python 3.10+
- `pip`

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Quick start

### 1) Check CLI wiring

```bash
python3 ghostty.py --help
```

### 2) Connect to a telnet host

```bash
python3 ghostty.py connect connect.serionbbs.com
```

Optional terminal size:

```bash
python3 ghostty.py connect connect.serionbbs.com --width 100 --height 30
```

### 3) Fetch screen state

Immediate snapshot:

```bash
python3 ghostty.py screen
```

Wait for stable:

```bash
python3 ghostty.py session update --mode stable --stable-ms 650 --stable-warmup-ms 2000 --max-wait-ms 9000
```

### 4) Send input

Single key:

```bash
python3 ghostty.py key Enter
```

Type text:

```bash
python3 ghostty.py type "hello"
```

Action bundle:

```bash
python3 ghostty.py send --actions '[{"k":"key","key":"Down","n":2},{"k":"type","text":"hello"}]'
```

---

## CLI reference

The CLI currently exposes **simple agent commands**:

- `connect`
- `screen`
- `key`
- `type`

It also exposes **advanced/debug commands**:

- `session update`
- `session history`
- `send`

You can inspect these at any time with:

```bash
python3 ghostty.py --help
python3 ghostty.py connect --help
python3 ghostty.py screen --help
python3 ghostty.py key --help
python3 ghostty.py type --help
python3 ghostty.py session --help
python3 ghostty.py session update --help
python3 ghostty.py session history --help
python3 ghostty.py send --help
```

### `screen`

```bash
python3 ghostty.py screen
```

Returns the latest screen snapshot JSON. This is an alias for `session update --mode latest`.

### `key`

```bash
python3 ghostty.py key <Enter|Esc|Backspace|Tab|Up|Down|Left|Right>
```

Sends one keypress and returns the updated screen JSON.

### `type`

```bash
python3 ghostty.py type "<text>"
```

Types text bytes and returns the updated screen JSON.

### `connect`

```bash
python3 ghostty.py connect <host> [--port 23] [--width 80] [--height 24]
```

Creates (or replaces) the current daemon session and starts the background receive loop.

Options:

- `<host>`: telnet hostname or IP to connect to (required).
- `--port`: telnet port (default `23`).
- `--width`: terminal width passed to the screen model (default `80`).
- `--height`: terminal height passed to the screen model (default `24`).

Example:

```bash
python3 ghostty.py connect connect.serionbbs.com --port 23 --width 100 --height 30
```

### `session update`

```bash
python3 ghostty.py session update [--mode latest|stable] [--stable-ms 650] [--stable-warmup-ms 2000] [--max-wait-ms 9000] [--include-frames] [--frame-limit 20] [--include-char-stream] [--char-limit 8000]
```

Returns the current screen/cursor/revision/hints payload. Responses also include a `diag` block with I/O log path and runtime error counters to aid debugging stuck sessions. Optional query flags let agents retrieve recent frame-buffer history and a bounded tail of raw decoded application characters.

Options:

- `--mode latest|stable`:
  - `latest`: return immediately with current state.
  - `stable`: wait until no screen changes are observed for `stable-ms`.
- `--stable-ms`: quiet period required to consider the screen stable (default `650`).
- `--max-wait-ms`: upper bound on waiting for stability (default `9000`).
- `--include-frames`: include `frames` history from the in-memory frame buffer.
- `--frame-limit`: max number of recent frames returned when `--include-frames` is set (default `20`).
- `--include-char-stream`: include `char_stream` with recent raw app characters received from telnet (decoded as CP437, before display normalization).
- `--char-limit`: max number of recent characters returned in `char_stream.text` when `--include-char-stream` is set (default `8000`).

Examples:

```bash
python3 ghostty.py session update --mode latest
python3 ghostty.py session update --mode stable --stable-ms 650 --max-wait-ms 9000
python3 ghostty.py session update --mode latest --include-frames --frame-limit 10 --include-char-stream --char-limit 12000
```

### `session history`

```bash
python3 ghostty.py session history [--limit 50] [--from-rev N] [--to-rev N] [--include-char-stream] [--char-limit 8000]
```

Returns a filtered slice of in-memory frame-buffer history for agent reasoning and debugging.

Options:

- `--limit`: max number of frames returned (default `50`).
- `--from-rev`: optional inclusive lower revision bound.
- `--to-rev`: optional inclusive upper revision bound.
- `--include-char-stream`: include the same `char_stream` tail block as `session update`.
- `--char-limit`: max `char_stream.text` length when included (default `8000`).

Examples:

```bash
python3 ghostty.py session history --limit 20
python3 ghostty.py session history --from-rev 100 --to-rev 140 --include-char-stream --char-limit 16000
```

### `send`

```bash
python3 ghostty.py send [--key <Enter|Esc|Backspace|Tab|Up|Down|Left|Right>] [--actions '<json>'] [--stable-ms 650] [--stable-warmup-ms 2000] [--max-wait-ms 9000]
```

Sends input to the remote session, waits for stability, then returns updated state.

You can use either:

- `--key` for one keypress, or
- `--actions` for a full action list.

Supported keys:

- `Enter`
- `Esc`
- `Backspace`
- `Tab`
- `Up`
- `Down`
- `Left`
- `Right`

Valid action schema:

- `{"k":"key","key":"Enter","n":1}`
- `{"k":"type","text":"some text"}`

Optional action fields:

- `n` repeats a key action (`n >= 1`).

Examples:

```bash
python3 ghostty.py send --key Enter
python3 ghostty.py send --actions '[{"k":"key","key":"Down","n":2},{"k":"type","text":"hello"}]'
```

### Daemon command reference

The daemon has a minimal entrypoint:

```bash
python3 ghosttyd.py [serve]
```

- `serve` is optional and defaults to `serve` when omitted.
- In normal usage, the CLI autostarts the daemon as needed.

### Internal daemon JSON commands

For completeness, the daemon socket protocol accepts:

- `ping`
- `connect`
- `session_update`
- `session_history`
- `send`

Most users should prefer the CLI wrappers above.

---

## JSON response shape (typical)

Success example (`frames` and `char_stream` are optional, returned only when requested):

```json
{
  "ok": true,
  "stable": false,
  "screen_rev": 12,
  "cursor": { "x": 5, "y": 10 },
  "screen": {
    "w": 80,
    "h": 24,
    "text": ["... 24 padded lines ..."]
  },
  "hints": {
    "mode": "menu",
    "prompt": ">",
    "choices": [{"key":"1","label":"Messages"}],
    "pager": false
  },
  "frames": [
    {"rev": 10, "ts": 1739046200.123, "text": ["..."]},
    {"rev": 11, "ts": 1739046200.702, "text": ["..."]}
  ],
  "char_stream": {
    "text": "...tail of raw app chars...",
    "returned_chars": 8000,
    "buffered_chars": 12000,
    "total_chars": 25000,
    "truncated": true
  }
}
```

Common error payloads:

- `{"ok": false, "error": "connection_lost", "state": "disconnected"}`
- `{"ok": false, "error": "timeout_waiting_stable"}`
- `{"ok": false, "error": "invalid_action"}`
- `{"ok": false, "error": "unknown_command"}`

---

## Development workflow

Use the canonical targets:

```bash
make run
make lint
make test
make check
```

Direct equivalents:

```bash
python3 ghostty.py --help
python3 -m py_compile ghostty.py ghosttyd.py pyte.py
python3 -m pytest -q tests
```

---

## Current scope and non-goals

This repository is intentionally scoped to a deterministic v0.1 daemon/CLI flow.

Out of scope for canonical behavior:

- Multi-session orchestration
- SSH transport
- Auto-reconnect / resume
- HTTP API as top-level product interface

The `experimental/` tree contains alternate ideas that are not part of the canonical run/test contract.

---

## Notes

- Daemon socket path defaults to `/tmp/ghosttyd.sock` (override via `GHOSTTY_SOCKET`).
- CLI will autostart daemon if unavailable.
