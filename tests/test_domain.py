"""领域层单测：抽题、计分、会话状态。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.engine import build_items, evaluate, finish_session
from app.domain.models import Question, QuizSession, SessionStatus
from app.domain.selection import QuizError, select_questions


def make_question(qid: str, category: str = "基础", difficulty: int = 1, answer: int = 0) -> Question:
    return Question(
        id=qid, category=category, difficulty=difficulty,
        prompt="题干", options=("A", "B", "C", "D"), answer=answer, explanation="解析",
    )


BANK = [
    make_question("q1", "基础", 1, 0),
    make_question("q2", "基础", 2, 1),
    make_question("q3", "函数", 2, 2),
    make_question("q4", "函数", 3, 3),
]


def test_question_points_follow_difficulty() -> None:
    assert [q.max_points for q in BANK] == [10, 14, 14, 18]


def test_invalid_question_rejected() -> None:
    with pytest.raises(ValueError):
        make_question("bad", answer=9)


def test_select_filters_by_category_and_difficulty() -> None:
    picked = select_questions(BANK, count=10, categories=["函数"])
    assert {q.category for q in picked} == {"函数"}

    picked = select_questions(BANK, count=10, difficulties=[3])
    assert [q.id for q in picked] == ["q4"]


def test_select_is_reproducible_with_seed() -> None:
    first = [q.id for q in select_questions(BANK, count=3, seed=7)]
    second = [q.id for q in select_questions(BANK, count=3, seed=7)]
    assert first == second


def test_select_caps_count_and_validates() -> None:
    assert len(select_questions(BANK, count=99)) == len(BANK)
    with pytest.raises(QuizError):
        select_questions(BANK, count=0)
    with pytest.raises(QuizError):
        select_questions(BANK, count=2, categories=["不存在"])


def test_evaluate_scores_only_correct_answers() -> None:
    question = BANK[3]  # 答案 D，18 分
    assert evaluate(question, 3) == (True, 18)
    assert evaluate(question, 0) == (False, 0)
    assert evaluate(question, None) == (False, 0)
    with pytest.raises(ValueError):
        evaluate(question, 9)


def test_build_items_numbers_positions() -> None:
    items = build_items(BANK)
    assert [item.position for item in items] == [1, 2, 3, 4]
    assert [item.question_id for item in items] == ["q1", "q2", "q3", "q4"]
    assert all(not item.answered for item in items)


def test_finish_session_records_duration() -> None:
    started = datetime.now(timezone.utc)
    session = QuizSession(id=1, mode="exam", status=SessionStatus.ACTIVE, started_at=started,
                          items=build_items(BANK))
    finish_session(session, started + timedelta(seconds=42))
    assert session.status is SessionStatus.FINISHED
    assert session.duration_ms == 42_000
    assert session.finished_at is not None


def test_category_breakdown_only_counts_answered() -> None:
    session = QuizSession(id=1, mode="exam", status=SessionStatus.ACTIVE,
                          started_at=datetime.now(timezone.utc), items=build_items(BANK))
    session.items[0].answered_at = datetime.now(timezone.utc)
    session.items[0].correct = True
    breakdown = session.category_breakdown()
    assert breakdown == [{"category": "基础", "correct": 1, "total": 1}]
