"""仓储层单测：建会话、作答、统计。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.data.database import connect, migrate
from app.data.repository import QuizRepository
from app.domain.models import Question


def make_question(qid: str, category: str = "基础", difficulty: int = 1) -> Question:
    return Question(id=qid, category=category, difficulty=difficulty, prompt="题干",
                    options=("A", "B", "C", "D"), answer=0, explanation="解析")


@pytest.fixture()
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    yield QuizRepository(conn)
    conn.close()


def test_migrate_is_idempotent(tmp_path) -> None:
    conn = connect(tmp_path / "test.db")
    assert migrate(conn) == 1
    assert migrate(conn) == 1
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    conn.close()


def test_create_session_persists_items(repo) -> None:
    session = repo.create_session("exam", [make_question("a"), make_question("b", "函数")],
                                  datetime.now(timezone.utc))
    assert session.id > 0
    assert session.total == 2
    loaded = repo.get(session.id)
    assert loaded is not None
    assert [item.question_id for item in loaded.items] == ["a", "b"]
    assert loaded.current_item is not None
    assert loaded.current_position == 1


def test_save_answer_and_finish(repo) -> None:
    started = datetime.now(timezone.utc)
    session = repo.create_session("practice", [make_question("a")], started)
    repo.save_answer(session.id, 1, 0, True, 10, 1234, started)
    loaded = repo.get(session.id)
    assert loaded.correct_count == 1
    assert loaded.score == 10
    assert loaded.current_item is None
    repo.finish(session.id, started, 5000)
    loaded = repo.get(session.id)
    assert loaded.status.value == "finished"
    assert loaded.duration_ms == 5000


def test_stats_and_history(repo) -> None:
    started = datetime.now(timezone.utc)
    session = repo.create_session("exam", [make_question("a"), make_question("b", "函数", 2)], started)
    repo.save_answer(session.id, 1, 0, True, 10, 800, started)
    repo.save_answer(session.id, 2, 1, False, 0, 1200, started)
    repo.finish(session.id, started, 2000)

    stats = repo.stats()
    assert stats["sessions"] == 1
    assert stats["answers"] == 2
    assert stats["correct"] == 1
    assert stats["accuracy"] == 0.5
    assert stats["best_score"] == 10

    history = repo.history()
    assert len(history) == 1
    assert history[0]["score"] == 10
    assert history[0]["correct"] == 1

    categories = {item["category"]: item for item in repo.category_stats()}
    assert categories["基础"]["accuracy"] == 1.0
    assert categories["函数"]["accuracy"] == 0.0


def test_missing_session_returns_none(repo) -> None:
    assert repo.get(999) is None
