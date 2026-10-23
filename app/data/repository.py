"""仓储层：用户、会话、SRS 卡片与同步事件。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..domain.models import Question, QuizSession, SessionItem, SessionStatus
from ..domain.srs import Card


def _dt(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def _loads(raw):
    """choice 列可能被 SQLite 的 INTEGER 亲和性存成数字，需要兼容。"""
    if raw is None or isinstance(raw, (int, list)):
        return raw
    return json.loads(raw)


class QuizRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ 用户
    def create_user(self, email: str, password_hash: str, created_at: datetime) -> dict:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email.lower(), password_hash, created_at.isoformat(timespec="seconds")),
            )
        return {"id": int(cursor.lastrowid), "email": email.lower()}

    def find_user(self, email: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ 会话
    def create_session(self, mode: str, questions: list[Question], started_at: datetime,
                       user_id: int) -> QuizSession:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO sessions (mode, status, started_at, total, user_id) VALUES (?, ?, ?, ?, ?)",
                (mode, SessionStatus.ACTIVE.value, started_at.isoformat(timespec="seconds"),
                 len(questions), user_id),
            )
            session_id = int(cursor.lastrowid)
            self.conn.executemany(
                "INSERT INTO session_items (session_id, position, question_id, kind, category, difficulty)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(session_id, index + 1, q.id, q.kind, q.category, q.difficulty)
                 for index, q in enumerate(questions)],
            )
        session = self.get(session_id, user_id)
        assert session is not None
        return session

    def save_answer(self, session_id: int, position: int, choice, correct: bool, points: int,
                    elapsed_ms: int, answered_at: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE session_items SET choice = ?, correct = ?, points = ?, elapsed_ms = ?,"
                " answered_at = ? WHERE session_id = ? AND position = ?",
                (json.dumps(choice), int(correct), points, elapsed_ms,
                 answered_at.isoformat(timespec="seconds"), session_id, position),
            )

    def finish(self, session_id: int, finished_at: datetime, duration_ms: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET status = ?, finished_at = ?, duration_ms = ? WHERE id = ?",
                (SessionStatus.FINISHED.value, finished_at.isoformat(timespec="seconds"),
                 duration_ms, session_id),
            )

    def get(self, session_id: int, user_id: int | None = None) -> QuizSession | None:
        query = "SELECT * FROM sessions WHERE id = ?"
        params: list = [session_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        row = self.conn.execute(query, params).fetchone()
        if row is None:
            return None
        items = [
            SessionItem(
                position=item["position"],
                question_id=item["question_id"],
                kind=item["kind"],
                category=item["category"],
                difficulty=item["difficulty"],
                choice=_loads(item["choice"]),
                correct=bool(item["correct"]) if item["correct"] is not None else None,
                points=item["points"],
                elapsed_ms=item["elapsed_ms"],
                answered_at=_dt(item["answered_at"]),
            )
            for item in self.conn.execute(
                "SELECT * FROM session_items WHERE session_id = ? ORDER BY position", (session_id,))
        ]
        return QuizSession(
            id=row["id"], user_id=row["user_id"] or 0, mode=row["mode"],
            status=SessionStatus(row["status"]), started_at=_dt(row["started_at"]),  # type: ignore[arg-type]
            items=items, finished_at=_dt(row["finished_at"]), duration_ms=row["duration_ms"],
        )

    # ------------------------------------------------------------------ 统计
    def history(self, user_id: int, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.id, s.mode, s.status, s.started_at, s.finished_at, s.total, s.duration_ms,"
            " COALESCE(SUM(i.points), 0) AS score, COALESCE(SUM(i.correct), 0) AS correct"
            " FROM sessions s LEFT JOIN session_items i ON i.session_id = s.id"
            " WHERE s.user_id = ? GROUP BY s.id ORDER BY s.id DESC LIMIT ?",
            (user_id, max(1, limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self, user_id: int) -> dict:
        row = self.conn.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM sessions WHERE user_id = ?) AS sessions,"
            " (SELECT COUNT(*) FROM session_items i JOIN sessions s ON s.id = i.session_id"
            "   WHERE s.user_id = ? AND i.answered_at IS NOT NULL) AS answers,"
            " (SELECT COALESCE(SUM(i.correct), 0) FROM session_items i"
            "   JOIN sessions s ON s.id = i.session_id"
            "   WHERE s.user_id = ? AND i.answered_at IS NOT NULL) AS correct,"
            " (SELECT COALESCE(SUM(i.points), 0) FROM session_items i"
            "   JOIN sessions s ON s.id = i.session_id"
            "   WHERE s.user_id = ? AND i.answered_at IS NOT NULL) AS score,"
            " (SELECT MAX(started_at) FROM sessions WHERE user_id = ?) AS last_played",
            (user_id,) * 5,
        ).fetchone()
        best = self.conn.execute(
            "SELECT COALESCE(MAX(total_score), 0) FROM ("
            " SELECT SUM(i.points) AS total_score FROM session_items i"
            " JOIN sessions s ON s.id = i.session_id"
            " WHERE s.user_id = ? AND i.answered_at IS NOT NULL GROUP BY i.session_id)",
            (user_id,),
        ).fetchone()[0]
        answers = int(row["answers"])
        sessions = int(row["sessions"])
        return {
            "sessions": sessions,
            "answers": answers,
            "correct": int(row["correct"]),
            "accuracy": (row["correct"] / answers) if answers else 0.0,
            "best_score": int(best),
            "average_score": (row["score"] / sessions) if sessions else 0.0,
            "last_played": row["last_played"],
        }

    def category_stats(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT i.category, COUNT(*) AS total, COALESCE(SUM(i.correct), 0) AS correct"
            " FROM session_items i JOIN sessions s ON s.id = i.session_id"
            " WHERE s.user_id = ? AND i.answered_at IS NOT NULL"
            " GROUP BY i.category ORDER BY total DESC, i.category ASC",
            (user_id,),
        ).fetchall()
        return [{"category": row["category"], "total": int(row["total"]),
                 "correct": int(row["correct"]),
                 "accuracy": (row["correct"] / row["total"]) if row["total"] else 0.0}
                for row in rows]

    # ---------------------------------------------------------------- SRS 卡片
    def get_card(self, user_id: int, question_id: str) -> Card:
        row = self.conn.execute(
            "SELECT * FROM cards WHERE user_id = ? AND question_id = ?", (user_id, question_id)
        ).fetchone()
        if row is None:
            return Card(question_id=question_id)
        return Card(question_id=question_id, ease=row["ease"], interval_days=row["interval_days"],
                    reps=row["reps"], lapses=row["lapses"], due_at=_dt(row["due_at"]))

    def save_card(self, user_id: int, card: Card, now: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO cards (user_id, question_id, ease, interval_days, reps, lapses, due_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(user_id, question_id) DO UPDATE SET"
                " ease = excluded.ease, interval_days = excluded.interval_days,"
                " reps = excluded.reps, lapses = excluded.lapses,"
                " due_at = excluded.due_at, updated_at = excluded.updated_at",
                (user_id, card.question_id, card.ease, card.interval_days, card.reps, card.lapses,
                 card.due_at.isoformat(timespec="seconds") if card.due_at else None,
                 now.isoformat(timespec="seconds")),
            )

    def card_ids(self, user_id: int) -> set[str]:
        rows = self.conn.execute("SELECT question_id FROM cards WHERE user_id = ?", (user_id,))
        return {row["question_id"] for row in rows}

    def due_question_ids(self, user_id: int, now: datetime, limit: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT question_id FROM cards WHERE user_id = ? AND (due_at IS NULL OR due_at <= ?)"
            " ORDER BY due_at IS NULL, due_at ASC LIMIT ?",
            (user_id, now.isoformat(timespec="seconds"), limit),
        ).fetchall()
        return [row["question_id"] for row in rows]

    # ---------------------------------------------------------------- 同步
    def record_event(self, user_id: int, client_id: str, session_id: int | None,
                     question_id: str, choice, created_at: datetime) -> bool:
        """幂等写入：同一 (user, client_id) 只接受一次。"""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO sync_events (user_id, client_id, session_id, question_id, choice, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, client_id, session_id, question_id, json.dumps(choice),
                     created_at.isoformat(timespec="seconds")),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def item_choice(self, session_id: int, question_id: str):
        row = self.conn.execute(
            "SELECT choice, answered_at FROM session_items WHERE session_id = ? AND question_id = ?",
            (session_id, question_id),
        ).fetchone()
        if row is None or row["answered_at"] is None:
            return None
        return _loads(row["choice"])
