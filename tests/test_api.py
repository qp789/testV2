"""API 单测：完整答题流程、参数校验与统计。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

QUESTIONS = Path(__file__).resolve().parent.parent / "data" / "questions.json"


@pytest.fixture()
def client(tmp_path):
    app = create_app(db_path=tmp_path / "api.db", questions_path=QUESTIONS)
    with TestClient(app) as test_client:
        yield test_client


def test_meta_reports_bank(client) -> None:
    response = client.get("/api/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["question_count"] == 15
    assert "函数" in meta["categories"]


def test_practice_session_end_to_end(client) -> None:
    created = client.post("/api/sessions", json={"mode": "practice", "count": 3})
    assert created.status_code == 201
    session = created.json()
    assert session["total"] == 3
    assert session["status"] == "active"

    for _ in range(3):
        question = session["question"]
        response = client.post(
            f"/api/sessions/{session['id']}/answers",
            json={"question_id": question["id"], "choice": 0, "elapsed_ms": 500},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["feedback"] is not None
        assert "explanation" in body["feedback"]
        session = body["session"]

    assert session["status"] == "finished"
    assert session["question"] is None

    summary = client.get(f"/api/sessions/{session['id']}/summary").json()
    assert summary["total"] == 3
    assert summary["correct"] == session["correct"]
    assert len(summary["wrong"]) == 3 - session["correct"]
    assert summary["duration_ms"] >= 0


def test_exam_mode_hides_feedback(client) -> None:
    session = client.post("/api/sessions", json={"count": 2, "mode": "exam"}).json()
    question = session["question"]
    body = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={"question_id": question["id"], "choice": None},
    ).json()
    assert body["feedback"] is None
    assert body["session"]["answered"] == 1


def test_conflicts_and_validation(client) -> None:
    session = client.post("/api/sessions", json={"count": 1}).json()
    question = session["question"]

    wrong_id = client.post(
        f"/api/sessions/{session['id']}/answers",
        json={"question_id": "not-current", "choice": 0},
    )
    assert wrong_id.status_code == 409

    assert client.post("/api/sessions", json={"count": 0}).status_code == 422
    assert client.post("/api/sessions", json={"count": 3, "categories": ["不存在"]}).status_code == 422
    assert client.get("/api/sessions/9999").status_code == 404

    client.post(f"/api/sessions/{session['id']}/answers",
                json={"question_id": question["id"], "choice": 0})
    again = client.post(f"/api/sessions/{session['id']}/answers",
                        json={"question_id": question["id"], "choice": 0})
    assert again.status_code == 409


def test_stats_and_history_after_session(client) -> None:
    session = client.post("/api/sessions", json={"count": 2}).json()
    for _ in range(2):
        question = session["question"]
        session = client.post(
            f"/api/sessions/{session['id']}/answers",
            json={"question_id": question["id"], "choice": 0},
        ).json()["session"]

    stats = client.get("/api/stats").json()
    assert stats["stats"]["sessions"] == 1
    assert stats["stats"]["answers"] == 2

    history = client.get("/api/history").json()["sessions"]
    assert len(history) == 1
    assert history[0]["id"] == session["id"]
