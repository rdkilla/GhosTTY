# GhosTTY v0.1 Implementation Plan

This plan converts the locked v0.1 product specification into an execution roadmap with milestones, deliverables, and acceptance checks.

## 1) Scope Baseline (Locked)

- **Single daemon-managed session** (one telnet connection, one screen buffer).
- **ANSI/VT100 emulation** through `pyte` (`Screen` + `Stream`).
- **Deterministic stable-screen engine** using signature + timing thresholds.
- **Agent-first JSON CLI** (`connect`, `session update`, `send`) with synchronous semantics.
- **No reconnect logic**, no multi-session, no SSH in v0.1.

## 2) Delivery Milestones

## Milestone M1 — Project Skeleton & Contracts

### Goals
- Establish package layout and strict JSON output contract for all CLI commands.
- Define canonical response/error schemas used by daemon and CLI.

### Deliverables
- Repository structure:
  - `ghostty/daemon/`
  - `ghostty/cli/`
  - `ghostty/protocol/` (JSON schema/types)
  - `ghostty/session/` (telnet + screen + stability)
- Shared constants/config module:
  - default `stable_ms=650`
  - default `max_wait_ms=9000`
  - default size `80x24`
- JSON response envelope conventions:
  - success: `{ "ok": true, ... }`
  - failure: `{ "ok": false, "error": "...", ... }`

### Acceptance checks
- CLI subcommands exist and return valid JSON stubs.
- Invalid invocation paths still return structured JSON errors.

---

## Milestone M2 — Telnet Session Core + Screen Model

### Goals
- Build daemon session state and telnet I/O loop.
- Pipe bytes into `pyte.Stream` and maintain full fixed-grid screen export.

### Deliverables
- `SessionState` implementation with at least:
  - `connected`, `host`, `port`
  - `screen`, `stream`
  - `screen_rev`, `stable_rev`
  - `last_change_ts`, `last_stable_ts`
  - `width`, `height`
- Telnet transport integration:
  - connect/disconnect handling
  - incoming byte reader task
  - outgoing write path for actions
- Screen snapshot serializer:
  - always full grid
  - always space padded
  - exact `w` x `h` rows/cols
  - separate cursor (`x`, `y` 0-based)

### Acceptance checks
- `connect` succeeds against a known host and initializes state.
- Snapshot output is deterministic and always fixed-size.
- Disconnect transitions state to `disconnected` and propagates errors.

---

## Milestone M3 — Deterministic Stability Engine

### Goals
- Implement revision tracking and stable detection exactly per spec.

### Deliverables
- Signature function over:
  - joined text grid
  - cursor `x/y`
- On signature change:
  - increment `screen_rev`
  - set `last_change_ts`
- Stability logic:
  - stable iff `(now - last_change_ts) >= stable_ms`
  - maintain `stable_rev` and `last_stable_ts`
- Wait helpers:
  - `wait_for_latest()` (non-blocking current snapshot)
  - `wait_for_stable(max_wait_ms)` (blocking with timeout)

### Acceptance checks
- Cursor-only changes increment revision.
- Stable window obeys configured timing.
- `wait_for_stable` exits by stable condition or timeout deterministically.

---

## Milestone M4 — Action Engine + `send` Semantics

### Goals
- Implement serialized action bundle execution and synchronous “one command → one reply”.

### Deliverables
- Action schema parser/validator:
  - `{k:"key", key:"Enter|Esc|Backspace|Tab|Up|Down|Left|Right", n?}`
  - `{k:"type", text:"..."}`
- Internal action queue (single session lock/serializer), while preserving “no control token” externally.
- `send` flow:
  1. validate actions
  2. execute actions to telnet
  3. wait for stable (or early terminal heuristic state if implemented)
  4. return JSON response with screen + cursor + revisions

### Acceptance checks
- Repeated key counts (`n`) work as expected.
- Concurrent human/agent inputs are serialized internally without data races.
- Each `send` returns exactly one deterministic JSON reply.

---

## Milestone M5 — CLI Command Completion

### Goals
- Finalize user-facing CLI semantics and daemon auto-start behavior.

### Deliverables
- `ghostty connect <host> [--port]`
  - ensures daemon availability
  - opens session and returns expected JSON payload
- `ghostty session update --mode latest|stable [--max-wait-ms]`
  - latest: immediate snapshot
  - stable: blocks until stable/timeout
- `ghostty send --key <Key>` and `ghostty send --actions '<json>'`
  - canonical action conversion for `--key`
  - full action bundle path for `--actions`

### Acceptance checks
- All commands output JSON only (machine-friendly by default).
- Command examples from spec execute with matching shape.

---

## Milestone M6 — Hint Extraction (Heuristic)

### Goals
- Provide optional hints in responses without affecting deterministic core behavior.

### Deliverables
- `hints` extractor returning:
  - `mode`: `prompt|menu|pager|unknown`
  - `prompt` token when detected
  - `choices` list from simple numbered/menu patterns
  - `pager` boolean
- Non-fatal extraction path (hint failures must never break screen response).

### Acceptance checks
- Known sample screens classify into expected modes.
- Hints included in `session update` and `send` responses.

---

## Milestone M7 — Reliability, Errors, and Packaging

### Goals
- Harden failure behavior and complete v0.1 readiness.

### Deliverables
- Error taxonomy (minimum):
  - `connection_lost`
  - `not_connected`
  - `invalid_action`
  - `timeout_waiting_stable`
  - `daemon_unavailable`
- Guaranteed disconnect behavior:
  - no auto-reconnect
  - immediate error response contract
- Logging strategy:
  - structured daemon logs (debug level configurable)
  - no noisy stdout contamination of CLI JSON
- Packaging + install docs + minimal operator runbook.

### Acceptance checks
- Forced disconnect test returns canonical error payload.
- Daemon restart does not silently restore dead sessions.

---

## 3) Cross-Cutting Technical Design

## Concurrency model
- Single writer path for outbound actions.
- Dedicated reader task for inbound telnet bytes.
- Shared session state protected via internal serialization primitive.
- Human UI (future) and agent commands both target same action pipe.

## Determinism guardrails
- Normalize line endings and padding before hashing/export.
- Keep one canonical screen serializer used by all commands.
- Explicit timeout behavior with machine-readable error fields.

## Config surface (v0.1 minimal)
- CLI flags for:
  - `--stable-ms`
  - `--max-wait-ms`
  - `--width`, `--height` (optional if exposed)
- Optional env overrides for daemon defaults.

## Observability
- Counters/metrics (even if only logs in v0.1):
  - bytes in/out
  - screen revisions
  - stable transitions
  - action queue depth
  - wait durations

## 4) Test Plan

## Unit tests
- Screen serializer fixed-grid behavior.
- Signature/revision logic (text changes and cursor changes).
- Stability timing logic with mocked clock.
- Action parser and key mapping.
- Hint extraction heuristics with fixture screens.

## Integration tests
- Connect to mock telnet server with scripted ANSI output.
- `session update latest` returns immediate snapshot.
- `session update stable` blocks then returns stable revision.
- `send --key` and `send --actions` drive expected remote state.
- Disconnect during wait yields `connection_lost`.

## End-to-end smoke
- Start daemon via CLI auto-start.
- Run scripted scenario: connect → send → update stable → disconnect.
- Validate all responses are valid JSON and schema-conformant.

## 5) Suggested Build Sequence (Practical)

1. Implement protocol/types + JSON error envelope.
2. Build daemon session state + telnet reader + screen export.
3. Add stability engine and wait APIs.
4. Add action execution and `send` command.
5. Finalize `session update` modes and connect behavior.
6. Layer hint extraction.
7. Add tests + docs + release checklist.

## 6) Definition of Done for v0.1

- All three core CLI commands implemented and JSON deterministic.
- Fixed-grid screen snapshots with cursor and revision fields.
- Stable detection semantics match spec defaults.
- `send` is synchronous and returns next stable screen.
- Disconnect behavior is fatal with no reconnect attempt.
- Integration suite passes against mock telnet target.
- Operator docs include known limitations and non-goals.
