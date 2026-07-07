from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class PublicChannelSnapshot(StrictModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    host_model: str | None = None
    status: str | None = None
    cover_path: str | None = None


class PublicPlaybackSnapshot(StrictModel):
    type: str | None = None
    title: str | None = None
    artist: str | None = None
    started_at: str | None = None


class PublicProgramSnapshot(StrictModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    vibe: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    days_of_week: str | None = None
    cover_path: str | None = None
    active: int | None = None


class PublicSongSnapshot(StrictModel):
    id: int | None = None
    title: str | None = None
    artist: str | None = None
    plays: int | None = None


class PublicGenreSnapshot(StrictModel):
    genre: str | None = None
    plays: int | None = None


class PublicBreakdownSnapshot(StrictModel):
    label: str | None = None
    percent: int | None = None


class PublicActivitySnapshot(StrictModel):
    kind: str | None = None
    actor: str | None = None
    content: str | None = None
    created_at: str | None = None


class PublicStreamSnapshot(StrictModel):
    url: str | None = None
    status: str | None = None


class PublicMetricsSnapshot(StrictModel):
    current_listeners: int | None = None
    popularity: int | None = None
    average_session: str | None = None


class PublicSnapshotRequest(StrictModel):
    schema_version: int | None = None
    generated_at: str | None = None
    expires_at: str | None = None
    channel: PublicChannelSnapshot | None = None
    now_playing: PublicPlaybackSnapshot | None = None
    current_program: PublicProgramSnapshot | None = None
    current_minutes_left: int | None = None
    next_program: PublicProgramSnapshot | None = None
    next_programs: list[PublicProgramSnapshot] = Field(default_factory=list)
    programs: list[PublicProgramSnapshot] = Field(default_factory=list)
    top_songs: list[PublicSongSnapshot] = Field(default_factory=list)
    top_genres: list[PublicGenreSnapshot] = Field(default_factory=list)
    content_breakdown: list[PublicBreakdownSnapshot] = Field(default_factory=list)
    activity: list[PublicActivitySnapshot] = Field(default_factory=list)
    stream: PublicStreamSnapshot | None = None
    metrics: PublicMetricsSnapshot | None = None
