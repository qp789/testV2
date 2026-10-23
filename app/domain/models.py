"""领域模型：题目（支持多题型）、作答项与会话。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

OPTION_LABELS = ("A", "B", "C", "D", "E", "F")
KINDS = ("single", "multi", "judge")


def label_for(index: int) -> str:
    return OPTION_LABELS[index] if 0 <= index < len(OPTION_LABELS) else str(index + 1)


class SessionStatus(str, Enum):
    ACTIVE = "active"
    FINISHED = "finished"


@dataclass(frozen=True)
class Question:
    """一道题：kind 决定判分方式（单选 / 多选 / 判断）。"""

    id: str
    kind: str
    category: str
    difficulty: int
    prompt: str
    options: tuple[str, ...]
    answers: tuple[int, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.id or not self.category or not self.prompt:
            raise ValueError("题目缺少 id / category / prompt")
        if self.kind not in KINDS:
            raise ValueError(f"题目 {self.id} 的 kind 不支持：{self.kind}")
        if self.difficulty not in (1, 2, 3):
            raise ValueError(f"题目 {self.id} 的 difficulty 必须是 1/2/3")
        if len(self.options) < 2:
            raise ValueError(f"题目 {self.id} 至少需要两个选项")
        if not self.answers or any(not 0 <= index < len(self.options) for index in self.answers):
            raise ValueError(f"题目 {self.id} 的 answers 越界")
        if self.kind != "multi" and len(self.answers) != 1:
            raise ValueError(f"题目 {self.id} 的 {self.kind} 只能有一个答案")
        if self.kind == "multi" and len(self.answers) < 2:
            raise ValueError(f"题目 {self.id} 的多选题至少要有两个正确答案")
        if not self.explanation:
            raise ValueError(f"题目 {self.id} 缺少解析")

    @property
    def max_points(self) -> int:
        return 10 + 4 * (self.difficulty - 1)

    @property
    def answer_labels(self) -> list[str]:
        return [label_for(index) for index in self.answers]

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "category": self.category,
            "difficulty": self.difficulty,
            "points": self.max_points,
            "prompt": self.prompt,
            "options": list(self.options),
        }


@dataclass
class SessionItem:
    position: int
    question_id: str
    kind: str
    category: str
    difficulty: int
    choice: object | None = None
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
    user_id: int
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
