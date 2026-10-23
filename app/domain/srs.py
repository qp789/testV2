"""SM-2 间隔重复调度（简化版）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Card:
    question_id: str
    ease: float = 2.5
    interval_days: float = 0.0
    reps: int = 0
    lapses: int = 0
    due_at: datetime | None = None

    def to_row(self) -> dict:
        return {
            "ease": self.ease,
            "interval_days": self.interval_days,
            "reps": self.reps,
            "lapses": self.lapses,
            "due_at": self.due_at.isoformat(timespec="seconds") if self.due_at else None,
        }


def review(card: Card, correct: bool, now: datetime) -> Card:
    """根据一次作答更新卡片：答对拉长间隔，答错重置。"""
    if correct:
        card.reps += 1
        if card.reps == 1:
            card.interval_days = 1.0
        elif card.reps == 2:
            card.interval_days = 3.0
        else:
            card.interval_days = round(card.interval_days * card.ease, 2)
        card.ease = min(3.0, round(card.ease + 0.1, 2))
    else:
        card.reps = 0
        card.lapses += 1
        card.interval_days = 0.0
        card.ease = max(1.3, round(card.ease - 0.2, 2))
    card.due_at = now + timedelta(days=card.interval_days)
    return card
