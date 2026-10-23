"""仓储层单测：用户、会话、卡片与同步幂等。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.data.database import connect, migrate
from app.data.repository import QuizRepository
from app.domain.models import Question
from app.domain.srs import review


def make_question(qid: str, category: str = "基础", difficulty: int = 1) -> Question:
    return Question(id=qid, kind="single", category=category, difficulty=difficulty,
                    prompt="题干", options=("A", "B", "C", "D"),
                    answers=(0,), explanation="解析")


@pytest.fixture()
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    assert migrate(conn) == 2
    yield QuizRepository(conn)
    conn.close()


@pytest.fixture()
def user(repo):
    return repo.create_user("a@example.com", "hash", datetime.now(timezone.utc))


def test_users(repo, user) -> None:
    assert repo.find_user("A@example.com")["id"] == user["id"]
    assert repo.get_user(user["id"])["email"] == "a@example.com"
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_user("a@example.com", "hash", datetime.now(timezone.utc))


def test_sessions_are_user_scoped(repo, user) -> None:
    session = repo.create_session("exam", [make_question("a"), make_question("b", "函数", 2)],
                                  datetime.now(timezone.utc), user["id"])
    assert repo.get(session.id, user["id"]) is not None
    assert repo.get(session.id, user["id"] + 1) is None

    started = datetime.now(timezone.utc)
    repo.save_answer(session.id, 1, 0, True, 10, 500, started)
    repo.save_answer(session.id, 2, [0], False, 0, 800, started)
    repo.finish(session.id, started, 1300)

    loaded = repo.get(session.id, user["id"])
    assert loaded.score == 10 and loaded.correct_count == 1
    assert loaded.items[0].choice == 0
    assert loaded.items[1].choice == [0]

    stats = repo.stats(user["id"])
    assert (stats["sessions"], stats["answers"], stats["correct"]) == (1, 2, 1)
    assert stats["best_score"] == 10
    assert repo.stats(user["id"] + 1)["sessions"] == 0
    assert len(repo.history(user["id"])) == 1


def test_cards_schedule_and_due(repo, user) -> None:
    now = datetime.now(timezone.utc)
    card = repo.get_card(user["id"], "q1")
    assert card.reps == 0
    review(card, True, now)
    repo.save_card(user["id"], card, now)

    again = repo.get_card(user["id"], "q1")
    assert again.reps == 1 and again.due_at is not None
    assert repo.due_question_ids(user["id"], now + timedelta(days=2), 10) == ["q1"]
    assert repo.due_question_ids(user["id"], now + timedelta(hours=1), 10) == []
    assert repo.card_ids(user["id"]) == {"q1"}


def test_sync_events_are_idempotent(repo, user) -> None:
    now = datetime.now(timezone.utc)
    assert repo.record_event(user["id"], "client-1", None, "q1", [0], now) is True
    assert repo.record_event(user["id"], "client-1", None, "q1", [0], now) is False
    assert repo.record_event(user["id"] + 1, "client-1", None, "q1", [0], now) is True
