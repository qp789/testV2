"""API 单测：认证、答题、SRS 复习与离线同步。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

QUESTIONS = Path(__file__).resolve().parent.parent / "data" / "questions.json"


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        db_path=tmp_path / "api.db",
        questions_path=QUESTIONS,
        secret_path=tmp_path / "secret.key",
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth(client):
    response = client.post("/api/auth/register",
                           json={"email": "u@example.com", "password": "password123"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_meta_is_public(client) -> None:
    meta = client.get("/api/meta").json()
    assert meta["question_count"] == 18
    assert "multi" in meta["kinds"]


def test_endpoints_require_login(client) -> None:
    assert client.get("/api/stats").status_code == 401
    assert client.post("/api/sessions", json={"count": 1}).status_code == 401
    assert client.get("/api/stats", headers={"Authorization": "Bearer bad.token"}).status_code == 401


def test_register_and_login(client) -> None:
    assert client.post("/api/auth/register",
                       json={"email": "u@example.com", "password": "password123"}).status_code == 201
    assert client.post("/api/auth/register",
                       json={"email": "u@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login",
                       json={"email": "u@example.com", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/register",
                       json={"email": "bad", "password": "password123"}).status_code == 422

    login = client.post("/api/auth/login",
                        json={"email": "u@example.com", "password": "password123"})
    assert login.status_code == 200
    me = client.get("/api/auth/me",
                    headers={"Authorization": f"Bearer {login.json()['token']}"})
    assert me.json()["user"]["email"] == "u@example.com"


def test_practice_flow_with_feedback(client, auth) -> None:
    session = client.post("/api/sessions", json={"mode": "practice", "count": 4},
                          headers=auth).json()
    for _ in range(4):
        question = session["question"]
        body = client.post(f"/api/sessions/{session['id']}/answers",
                           json={"question_id": question["id"], "choice": [0]},
                           headers=auth).json()
        assert body["feedback"] is not None
        assert isinstance(body["feedback"]["answers"], list)
        session = body["session"]

    assert session["status"] == "finished"
    summary = client.get(f"/api/sessions/{session['id']}/summary", headers=auth).json()
    assert summary["total"] == 4
    assert len(summary["wrong"]) == 4 - session["correct"]


def test_exam_flow_hides_feedback(client, auth) -> None:
    session = client.post("/api/sessions", json={"count": 2}, headers=auth).json()
    body = client.post(f"/api/sessions/{session['id']}/answers",
                       json={"question_id": session["question"]["id"], "choice": 0},
                       headers=auth).json()
    assert body["feedback"] is None
    assert body["session"]["answered"] == 1


def test_study_due_and_review(client, auth) -> None:
    due = client.get("/api/study/due?limit=5", headers=auth).json()
    assert due["new"] >= 1 and due["questions"]
    question = due["questions"][0]

    review = client.post("/api/study/review",
                         json={"question_id": question["id"], "choice": [0]},
                         headers=auth).json()
    assert "interval_days" in review and review["interval_days"] >= 1

    again = client.get("/api/study/due?limit=50", headers=auth).json()
    assert all(item["id"] != question["id"] for item in again["questions"])


def test_sync_is_idempotent_and_detects_conflict(client, auth) -> None:
    session = client.post("/api/sessions", json={"count": 1}, headers=auth).json()
    question = session["question"]
    client.post(f"/api/sessions/{session['id']}/answers",
                json={"question_id": question["id"], "choice": 0}, headers=auth)

    conflict = client.post("/api/sync", headers=auth, json={"events": [{
        "client_id": "client-xyz", "session_id": session["id"],
        "question_id": question["id"], "choice": 1,
    }]}).json()
    assert conflict["results"][0]["status"] == "conflict"

    payload = {"events": [{"client_id": "event-1", "question_id": question["id"], "choice": 0}]}
    first = client.post("/api/sync", headers=auth, json=payload).json()
    second = client.post("/api/sync", headers=auth, json=payload).json()
    assert first["results"][0]["status"] == "accepted"
    assert second["results"][0]["status"] == "duplicate"


def test_history_and_stats_are_per_user(client, auth) -> None:
    session = client.post("/api/sessions", json={"count": 2}, headers=auth).json()
    for _ in range(2):
        question = session["question"]
        session = client.post(f"/api/sessions/{session['id']}/answers",
                              json={"question_id": question["id"], "choice": 0},
                              headers=auth).json()["session"]

    stats = client.get("/api/stats", headers=auth).json()
    assert stats["stats"]["sessions"] == 1
    history = client.get("/api/history", headers=auth).json()["sessions"]
    assert history and history[0]["id"] == session["id"]

    other = client.post("/api/auth/register",
                        json={"email": "other@example.com", "password": "password123"}).json()
    other_auth = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/api/stats", headers=other_auth).json()["stats"]["sessions"] == 0
