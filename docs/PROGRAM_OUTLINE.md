# GhosTTY Program Outline (v0.1)

## 1) Entry Points

- `ghostty` (CLI): user/agent command surface.
- `ghosttyd.py` (daemon): persistent session owner.

## 2) High-Level Flow

1. User invokes `ghostty ...`.
2. CLI sends JSON command to daemon over Unix socket.
3. Daemon executes command against single telnet session + screen state.
4. Daemon returns deterministic JSON payload.

## 3) Daemon Subsystems

- **Connection Manager**
  - Establishes telnet connection (`connect`).
  - Detects EOF/socket errors.
  - Marks disconnected state.

- **Screen Engine**
  - Receives incoming bytes from socket.
  - Feeds bytes into stream/screen emulator.
  - Produces fixed-grid text snapshots (`w`, `h`, `text`).

- **Revision & Stability Engine**
  - Computes screen signature from full text + cursor.
  - Increments `screen_rev` on meaningful changes.
  - Declares stability after idle period (`stable_ms`).

- **Action Executor**
  - Executes serialized action bundles (`key`, `type`).
  - Waits for stable state after send.

- **Hint Extractor**
  - Heuristics for `prompt`, `menu`, `pager`, `unknown`.

## 4) CLI Commands

- `connect`: open session.
- `session update --mode latest|stable`: fetch screen snapshot.
- `send --key ...` / `send --actions ...`: inject input and wait for response state.

## 5) Data Contracts

- Full grid screen output.
- Cursor coordinates (0-based).
- Disconnect payload: `connection_lost` + `disconnected` state.

## 6) Concurrency Model

- One global session state.
- Daemon recv thread ingests telnet bytes.
- Action lock serializes `send` requests.
- Shared state lock guards screen/session structures.

## 7) v0.1 Non-goals

- Multi-session support.
- SSH support.
- Auto-reconnect.
- Replay/recording.
- HTTP API and alternate CLIs in top-level run/test paths (kept in `experimental/`).
