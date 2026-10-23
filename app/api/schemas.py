"""请求体模型（pydantic 负责类型与范围校验）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    mode: Literal["practice", "exam"] = "exam"
    count: int = Field(default=10, ge=1, le=50)
    categories: list[str] = Field(default_factory=list)
    difficulties: list[int] = Field(default_factory=list)
    seed: int | None = None

    model_config = {"extra": "forbid"}


class AnswerCreate(BaseModel):
    question_id: str = Field(min_length=1, max_length=32)
    choice: int | None = Field(default=None, ge=0, le=10)
    elapsed_ms: int = Field(default=0, ge=0, le=3_600_000)

    model_config = {"extra": "forbid"}
