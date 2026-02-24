# 👻 GhosTTY v0.1

GhosTTY is a **daemon-backed, screen-aware terminal operator** designed for LLM/agent control.

It provides a single shared telnet session, a deterministic terminal screen model, and a JSON-first CLI contract so both humans and agents can drive the same session safely and predictably.

---

## What GhosTTY is

GhosTTY splits into two pieces:

1. **`ghosttyd` daemon**
   - Owns one telnet connection.
   - Owns one terminal screen buffer.
   - Tracks revisions and stability.
   - Serializes incoming actions.

2. **`ghostty` CLI**
   - Agent-facing command interface.
   - Auto-starts daemon when needed.
   - Sends one command and receives one deterministic JSON reply.

This gives a stable control plane for automation:

```text
ghostty CLI
    ↓
local daemon (auto-start)
    ↓
Telnet socket
    ↓
pyte Stream → pyte Screen
    ↓
Screen Buffer + Stability Engine
```

---

## Core behavior (v0.1)

- **Single source of truth**
  - One daemon, one telnet connection, one screen buffer.
- **Agent-first JSON output**
  - All CLI replies are JSON.
- **Full fixed grid output**
  - Every screen snapshot returns full `w × h` lines, padded with spaces.
- **Synchronous step model**
  - `send` executes actions and waits for the next stable screen before returning.
- **Fatal disconnect semantics**
  - No auto-reconnect. Disconnect returns `connection_lost`.

---

## Program outline (implementation sketch)

### `ghosttyd.py` (daemon)

- **`SessionState`**
  - Holds connection metadata (`connected`, `host`, `port`).
  - Holds terminal model (`screen`, `stream`, `width`, `height`).
  - Holds revision/stability tracking (`screen_rev`, `stable_rev`, timestamps).
  - Holds synchronization primitives (`lock`, `action_lock`).

- **Input path**
  - Telnet bytes read in recv loop.
  - Bytes decoded and fed into stream/screen.
  - Screen signature (`text + cursor`) recomputed.
  - Revision increments on meaningful change.

- **Stability engine**
  - Stable when `(now - last_change_ts) >= stable_ms`.
  - Defaults:
    - `stable_ms = 650`
    - `max_wait_ms = 9000`

- **Action execution**
  - Supports action bundle schema:
    - `{ "k": "key", "key": "Enter" }`
    - `{ "k": "key", "key": "Down", "n": 3 }`
    - `{ "k": "type", "text": "hello" }`
  - Key support (v0.1): `Enter`, `Esc`, `Backspace`, `Tab`, arrows.

- **Control API handlers**
  - `connect`
  - `session_update` (`latest` or `stable`)
  - `send`

- **Hint extraction (heuristic)**
  - Returns `mode` (`prompt|menu|pager|unknown`) and optional prompt/choices flags.

### `ghostty` (CLI)

- Parses command line.
- Builds JSON payloads.
- Sends payload to daemon over Unix socket.
- Prints JSON response.
- Auto-starts daemon if socket is unavailable.

### `pyte.py` (local terminal model)

- Minimal in-repo `pyte`-compatible subset used by this prototype environment:
  - `Screen`
  - `Stream`
  - cursor movement + basic control handling.

---

## CLI commands

### Connect

```bash
./ghostty connect connect.serionbbs.com
```

Example response:

```json
{
  "ok": true,
  "connected": true,
  "host": "connect.serionbbs.com",
  "screen_rev": 0
}
```

### Session update

Non-blocking:

```bash
./ghostty session update --mode latest
```

Blocking until stable:

```bash
./ghostty session update --mode stable
```

### Send

Single key:

```bash
./ghostty send --key Enter
```

Action bundle:

```bash
./ghostty send --actions '[{"k":"key","key":"Down","n":2}]'
```

`send` is synchronous and returns the next stable (or timed-out latest) screen state.

---

## Screen payload contract

Each update returns full-grid screen data:

```json
{
  "w": 80,
  "h": 24,
  "text": [
    "exactly 80 chars per line",
    "... 24 lines total ..."
  ]
}
```

Also includes cursor coordinates:

```json
"cursor": { "x": 12, "y": 22 }
```

Coordinates are 0-based.

---

## Failure behavior

On connection loss:

```json
{
  "ok": false,
  "error": "connection_lost",
  "state": "disconnected"
}
```

No automatic reconnect is attempted.

---

## Run locally

```bash
python3 -m pytest -q
./ghostty session update --mode latest
```

> Note: This repository uses an in-repo `pyte.py` compatibility implementation so the prototype can run in restricted environments.
