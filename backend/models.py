from __future__ import annotations

from pydantic import BaseModel


class SayRequest(BaseModel):
    text: str


class SearchRequest(BaseModel):
    query: str


class ListenerFeedbackRequest(BaseModel):
    text: str
    source: str = "dashboard"


class ProgramUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    vibe: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    days_of_week: str | None = None
    host_name: str | None = None
    host_gender: str | None = None
    voice: str | None = None
    personality: str | None = None
    active: int | None = None


class PublicSessionRequest(BaseModel):
    session_id: str
