"""领域层单测：抽题、题型插件、SRS 与安全工具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.engine import build_items, finish_session
from app.domain.models import Question, QuizSession, SessionStatus
from app.domain.plugins import normalize_choice, registry
from app.domain.selection import QuizError, select_questions
from app.domain.srs import Card, review
from app.security import TokenSigner, hash_password, verify_password


def make_question(qid: str, kind: str = "single", answers: tuple[int, ...] = (0,),
                  difficulty: int = 1, category: str = "基础") -> Question:
    return Question(id=qid, kind=kind, category=category, difficulty=difficulty,
                    prompt="题干", options=("A", "B", "C", "D"),
                    answers=answers, explanation="解析")


def test_question_validation_and_points() -> None:
    assert make_question("q", difficulty=3).max_points == 18
    with pytest.raises(ValueError):
        make_question("bad", answers=(9,))
    with pytest.raises(ValueError):
        make_question("bad", kind="multi", answers=(0,))


def test_normalize_choice() -> None:
    assert normalize_choice(1) == [1]
    assert normalize_choice([2, 1, 2]) == [1, 2]
    assert normalize_choice(None) == []
    assert normalize_choice(True) == []


def test_single_multi_judge_scoring() -> None:
    single = make_question("s", "single", (2,), difficulty=2)
    assert registry.score(single, 2) == (True, 14)
    assert registry.score(single, [2]) == (True, 14)
    assert registry.score(single, 0) == (False, 0)

    multi = make_question("m", "multi", (0, 2), difficulty=3)
    assert registry.score(multi, [2, 0]) == (True, 18)
    assert registry.score(multi, [0]) == (False, 0)

    judge = make_question("j", "judge", (1,))
    assert registry.score(judge, 1) == (True, 10)


def test_selection_filters_and_seed() -> None:
    bank = [make_question("a", category="基础"), make_question("b", category="函数", difficulty=3)]
    assert [q.id for q in select_questions(bank, 5, categories=["函数"])] == ["b"]
    assert [q.id for q in select_questions(bank, 5, difficulties=[3])] == ["b"]
    first = [q.id for q in select_questions(bank, 2, seed=1)]
    assert first == [q.id for q in select_questions(bank, 2, seed=1)]
    with pytest.raises(QuizError):
        select_questions(bank, 1, categories=["不存在"])


def test_session_lifecycle() -> None:
    questions = [make_question("a"), make_question("b", difficulty=2)]
    started = datetime.now(timezone.utc)
    session = QuizSession(id=1, user_id=1, mode="exam",
                          status=SessionStatus.ACTIVE, started_at=started,
                          items=build_items(questions))
    assert session.current_position == 1 and session.current_item is not None
    session.items[0].answered_at = started
    session.items[0].correct = True
    session.items[0].points = 10
    assert session.current_position == 2
    finish_session(session, started + timedelta(seconds=30))
    assert session.duration_ms == 30_000
    assert session.score == 10 and session.max_score == 24


def test_srs_schedule_grows_then_resets() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    card = Card(question_id="q")
    review(card, True, now)
    assert card.interval_days == 1.0 and card.due_at == now + timedelta(days=1)
    review(card, True, now)
    assert card.interval_days == 3.0
    review(card, True, now)
    assert card.interval_days == 8.1  # 3 * 2.7
    review(card, False, now)
    assert card.interval_days == 0.0 and card.reps == 0 and card.lapses == 1
    assert card.ease >= 1.3


def test_password_hashing() -> None:
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong password", stored)
    assert hash_password("another-pass", salt=b"x" * 16) != stored
    with pytest.raises(ValueError):
        hash_password("short")


def test_token_signing_and_tampering() -> None:
    signer = TokenSigner(b"secret-key-for-tests", ttl_seconds=60)
    token = signer.issue(42)
    assert signer.verify(token) == 42
    assert signer.verify(token + "x") is None
    body, signature = token.split(".")
    assert signer.verify(f"{body}.{'A' * len(signature)}") is None

    expired = TokenSigner(b"secret-key-for-tests", ttl_seconds=-1).issue(7)
    assert TokenSigner(b"secret-key-for-tests").verify(expired) is None
