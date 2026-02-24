import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .models import (
    CommandRequest,
    CommandResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ScreenSnapshot,
)
from .session import SessionManager

app = FastAPI(title="GhosTTY", version="0.1.0")
manager = SessionManager()


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/session", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    state = await manager.create(req.host, req.port)
    if req.username:
        await manager.send(state.session_id, req.username + "\r", 150)
    if req.password:
        await manager.send(state.session_id, req.password + "\r", 150)
    return CreateSessionResponse(
        session_id=state.session_id,
        connected=True,
        created_at=state.created_at,
    )


@app.post("/session/{session_id}/command", response_model=CommandResponse)
async def send_command(session_id: str, req: CommandRequest) -> CommandResponse:
    try:
        sent = await manager.send(session_id, req.input, req.wait_ms)
        snap = await manager.snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    return CommandResponse(session_id=session_id, seq=snap["seq"], sent_bytes=sent)


@app.get("/session/{session_id}/screen", response_model=ScreenSnapshot)
async def get_screen(session_id: str) -> ScreenSnapshot:
    try:
        snap = await manager.snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    return ScreenSnapshot(**snap)


@app.get("/session/{session_id}/events")
async def events(session_id: str) -> StreamingResponse:
    async def stream():
        try:
            async for evt in manager.subscribe(session_id):
                yield f"data: {json.dumps(evt, default=str)}\n\n"
        except KeyError:
            yield "event: error\ndata: session not found\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.delete("/session/{session_id}")
async def delete_session(session_id: str) -> dict:
    await manager.close(session_id)
    return {"closed": True, "session_id": session_id}
