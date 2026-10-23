"""领域模型：题目、作答项与答题会话。

这一层不依赖 FastAPI、SQLite，任何地方都可以直接构造和断言。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Sequence

OPTION_LABELS = ("A", "B", "C", "D", "E", "F")


def label_for(index: int) -> str:
    if 0 <= index < len(OPTION_LABELS):
        return OPTION_LABELS[index]
    return str(index + 1)


class SessionStatus(str, Enum):
    ACTIVE = "active"
    FINISHED = "finished"


@dataclass(frozen=True)
class Question:
    """单选题。answer 是正确选项下标（从 0 开始）。"""

    id: str
    category: str
    difficulty: int
    prompt: str
    options: tuple[str, ...]
    answer: int
    explanation: str

    def __post_init__(self) -> None:
        if not self.id or not self.category or not self.prompt:
            raise ValueError("题目缺少 id / category / prompt")
        if self.difficulty not in (1, 2, 3):
            raise ValueError(f"题目 {self.id} 的 difficulty 必须是 1/2/3")
        if len(self.options) < 2:
            raise ValueError(f"题目 {self.id} 至少需要两个选项")
        if not 0 <= self.answer < len(self.options):
            raise ValueError(f"题目 {self.id} 的 answer 越界")
        if not self.explanation:
            raise ValueError(f"题目 {self.id} 缺少解析")

    @property
    def max_points(self) -> int:
        return 10 + 4 * (self.difficulty - 1)

    @property
    def answer_label(self) -> str:
        return label_for(self.answer)

    def public(self) -> dict:
        """给前端看的字段，不含答案与解析。"""
        return {
            "id": self.id,
            "category": self.category,
            "difficulty": self.difficulty,
            "points": self.max_points,
            "prompt": self.prompt,
            "options": list(self.options),
        }


@dataclass
class SessionItem:
    """会话中的一道题及其作答状态。"""

    position: int
    question_id: str
    category: str
    difficulty: int
    choice: int | None = None
    correct: bool | None = None
    points: int = 0
    elapsed_ms: int = 0
    answered_at: datetime | None = None

    @property
    def answered(self) -> bool:
        return self.answered_at is not None

    @property
    def max_points(self) -> int:
        return 10 + 4 * (self.difficulty - 1)


@dataclass
class QuizSession:
    id: int
    mode: str
    status: SessionStatus
    started_at: datetime
    items: list[SessionItem] = field(default_factory=list)
    finished_at: datetime | None = None
    duration_ms: int = 0

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def answered_count(self) -> int:
        return sum(1 for item in self.items if item.answered)

    @property
    def correct_count(self) -> int:
        return sum(1 for item in self.items if item.correct)

    @property
    def score(self) -> int:
        return sum(item.points for item in self.items)

    @property
    def max_score(self) -> int:
        return sum(item.max_points for item in self.items)

    @property
    def accuracy(self) -> float:
        return self.correct_count / self.total if self.total else 0.0

    @property
    def current_item(self) -> SessionItem | None:
        for item in self.items:
            if not item.answered:
                return item
        return None

    @property
    def current_position(self) -> int:
        item = self.current_item
        return item.position if item else self.total

    def category_breakdown(self) -> list[dict]:
        buckets: dict[str, list[int]] = {}
        for item in self.items:
            if not item.answered:
                continue
            stat = buckets.setdefault(item.category, [0, 0])
            stat[0] += 1 if item.correct else 0
            stat[1] += 1
        return [
            {"category": name, "correct": ok, "total": total}
            for name, (ok, total) in sorted(buckets.items(), key=lambda kv: (-kv[1][1], kv[0]))
        ]
