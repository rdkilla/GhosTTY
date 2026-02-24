# GhosTTY

A lightweight Telnet-to-HTTP bridge for AI/game-agent control of BBS sessions (e.g., LORD, Exitilus).

## Features

- Persistent telnet sessions keyed by `session_id`
- Send commands/keystrokes over HTTP
- Poll latest screen snapshot
- Stream screen updates via Server-Sent Events (SSE)
- ANSI/control cleanup for easier agent parsing

## API

### `POST /session`
Create a telnet session.

Request body:

```json
{
  "host": "bbs.example.com",
  "port": 23,
  "username": null,
  "password": null,
  "name": "optional-friendly-name"
}
```

### `POST /session/{session_id}/command`
Send text/keys to telnet session.

```json
{
  "input": "A\\r",
  "wait_ms": 400
}
```

### `GET /session/{session_id}/screen`
Get the latest normalized screen.

### `GET /session/{session_id}/events`
SSE stream of screen updates.

### `DELETE /session/{session_id}`
Close and remove a session.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Notes

- This project intentionally keeps telnet option negotiation minimal for broad compatibility.
- Use raw session logs (`logs/`) for debugging parser mistakes and timing issues.
