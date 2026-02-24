# 👻 GhosTTY v0.1

GhosTTY v0.1 has one canonical product path:

- **`ghosttyd.py`**: single daemon that owns one telnet connection and one terminal screen model.
- **`./ghostty`**: JSON-first CLI that auto-starts the daemon and exposes the supported commands.

All docs and top-level scripts are aligned to this interface only:

- `connect`
- `session update`
- `send`

## Canonical command set

### `connect`

```bash
./ghostty connect connect.serionbbs.com
```

### `session update`

```bash
./ghostty session update --mode latest
./ghostty session update --mode stable
```

### `send`

```bash
./ghostty send --key Enter
./ghostty send --actions '[{"k":"key","key":"Down","n":2}]'
```

## Single source of truth: run + test

Use only the top-level Python workflow below for v0.1:

```bash
make run
make lint
make test
make check
```

Equivalent direct commands:

```bash
./ghostty --help
python3 -m py_compile ghostty ghosttyd.py pyte.py
python3 -m pytest -q tests
```

## Runtime model (v0.1)

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

Core behavior:

- Single daemon-managed session.
- Fixed-grid screen payload (`w`, `h`, padded `text`).
- `send` waits for stable state before returning.
- Disconnects are fatal (`connection_lost`), no auto-reconnect.

## Architecture Decision (v0.1 scope)

We intentionally exclude non-canonical surfaces from the mainline product to keep agent control deterministic and supportable:

- **FastAPI app** is moved to `experimental/app/` and not part of v0.1 run/test contracts.
- **Node CLI path** is removed from top-level build/test targets.

Why:

1. v0.1 requires one authoritative command surface for agents.
2. Parallel entrypoints (HTTP API + Node CLI + Python CLI) create divergence in behavior, docs, and tests.
3. A single daemon/CLI contract (`connect`, `session update`, `send`) keeps behavior auditable and reproducible.

Experimental work can continue under `experimental/` without changing the canonical v0.1 interface.
