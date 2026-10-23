"""请求体模型（pydantic 负责类型与范围校验）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Choice = int | list[int] | None
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=120, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)

    model_config = {"extra": "forbid"}


class SessionCreate(BaseModel):
    mode: Literal["practice", "exam"] = "exam"
    count: int = Field(default=10, ge=1, le=50)
    categories: list[str] = Field(default_factory=list)
    difficulties: list[int] = Field(default_factory=list)
    seed: int | None = None

    model_config = {"extra": "forbid"}


class AnswerCreate(BaseModel):
    question_id: str = Field(min_length=1, max_length=32)
    choice: Choice = None
    elapsed_ms: int = Field(default=0, ge=0, le=3_600_000)

    model_config = {"extra": "forbid"}


class ReviewCreate(BaseModel):
    question_id: str = Field(min_length=1, max_length=32)
    choice: Choice = None
    elapsed_ms: int = Field(default=0, ge=0, le=3_600_000)

    model_config = {"extra": "forbid"}


class SyncEvent(BaseModel):
    client_id: str = Field(min_length=6, max_length=64)
    session_id: int | None = None
    question_id: str = Field(min_length=1, max_length=32)
    choice: Choice = None
    elapsed_ms: int = Field(default=0, ge=0, le=3_600_000)
    answered_at: datetime | None = None

    model_config = {"extra": "forbid"}


class SyncRequest(BaseModel):
    events: list[SyncEvent] = Field(default_factory=list, max_length=200)

    model_config = {"extra": "forbid"}
