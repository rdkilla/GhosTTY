from datetime import datetime
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    host: str
    port: int = 23
    username: str | None = None
    password: str | None = None
    name: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    connected: bool
    created_at: datetime


class CommandRequest(BaseModel):
    input: str = Field(..., description="Text/keys to send (e.g. 'A\\r')")
    wait_ms: int = Field(default=400, ge=0, le=5000)


class CommandResponse(BaseModel):
    session_id: str
    seq: int
    sent_bytes: int


class ScreenSnapshot(BaseModel):
    session_id: str
    seq: int
    timestamp: datetime
    raw_text: str
    lines: list[str]
    prompt_detected: bool
    screen_hash: str
