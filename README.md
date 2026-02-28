# 👻 GhosTTY

GhosTTY is a lightweight **daemon + CLI** system for automating terminal-style telnet workflows through a deterministic JSON interface.

At runtime, you interact with a single command-line client (`ghostty.py` / `./ghostty`) that talks to a local Unix-socket daemon (`ghosttyd.py`). The daemon owns exactly one live telnet session and one terminal screen model.

---

## What this project provides

- A canonical CLI for machine/agent usage:
  - `connect`
  - `session update`
  - `send`
- A local daemon that:
  - maintains one telnet connection,
  - renders terminal output into a fixed-size text grid via `pyte`,
  - tracks revision/stability for deterministic reads,
  - serializes actions to avoid race conditions.
- JSON-first responses designed for automation.

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
- **I/O diagnostics log**: inbound and outbound telnet bytes are appended to `./ghostty-io.log` (repo root) by default. Set `GHOSTTY_IO_LOG` or pass `--io-log-path` on `connect` to override the path.

---

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
python3 ghostty.py session update --mode latest
```

Wait for stable:

```bash
python3 ghostty.py session update --mode stable --stable-ms 650 --stable-warmup-ms 2000 --max-wait-ms 9000
```

### 4) Send input

Single key:

```bash
python3 ghostty.py send --key Enter
```

Action bundle:

```bash
python3 ghostty.py send --actions '[{"k":"key","key":"Down","n":2},{"k":"type","text":"hello"}]'
```

---

## CLI reference

The CLI currently exposes **three user-facing commands**:

- `connect`
- `session update`
- `send`

You can inspect these at any time with:

```bash
python3 ghostty.py --help
python3 ghostty.py connect --help
python3 ghostty.py session --help
python3 ghostty.py session update --help
python3 ghostty.py send --help
```

### `connect`

```bash
python3 ghostty.py connect <host> [--port 23] [--width 80] [--height 24] [--io-log-path PATH]
```

Creates (or replaces) the current daemon session and starts the background receive loop.

Options:

- `<host>`: telnet hostname or IP to connect to (required).
- `--port`: telnet port (default `23`).
- `--width`: terminal width passed to the screen model (default `80`).
- `--height`: terminal height passed to the screen model (default `24`).
- `--io-log-path`: explicit path for the diagnostics log for this session.

Example:

```bash
python3 ghostty.py connect connect.serionbbs.com --port 23 --width 100 --height 30 --io-log-path ./logs/session-io.log
```

### `session update`

```bash
python3 ghostty.py session update [--mode latest|stable] [--stable-ms 650] [--stable-warmup-ms 2000] [--max-wait-ms 9000]
```

Returns the current screen/cursor/revision/hints payload.

Options:

- `--mode latest|stable`:
  - `latest`: return immediately with current state.
  - `stable`: wait until no screen changes are observed for `stable-ms`.
- `--stable-ms`: quiet period required to consider the screen stable (default `650`).
- `--max-wait-ms`: upper bound on waiting for stability (default `9000`).

Examples:

```bash
python3 ghostty.py session update --mode latest
python3 ghostty.py session update --mode stable --stable-ms 650 --max-wait-ms 9000
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
- `send`

Most users should prefer the CLI wrappers above.

---

## JSON response shape (typical)

Success example:

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
