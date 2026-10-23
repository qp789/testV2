"""仓储层：会话的读写与统计查询。"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ..domain.models import Question, QuizSession, SessionItem, SessionStatus


def _dt(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


class QuizRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------ 会话写入
    def create_session(self, mode: str, questions: list[Question], started_at: datetime) -> QuizSession:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO sessions (mode, status, started_at, total) VALUES (?, ?, ?, ?)",
                (mode, SessionStatus.ACTIVE.value, started_at.isoformat(timespec="seconds"), len(questions)),
            )
            session_id = int(cursor.lastrowid)
            self.conn.executemany(
                "INSERT INTO session_items (session_id, position, question_id, category, difficulty)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (session_id, index + 1, q.id, q.category, q.difficulty)
                    for index, q in enumerate(questions)
                ],
            )
        session = self.get(session_id)
        assert session is not None
        return session

    def save_answer(
        self,
        session_id: int,
        position: int,
        choice: int | None,
        correct: bool,
        points: int,
        elapsed_ms: int,
        answered_at: datetime,
    ) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE session_items SET choice = ?, correct = ?, points = ?, elapsed_ms = ?,"
                " answered_at = ? WHERE session_id = ? AND position = ?",
                (choice, int(correct), points, elapsed_ms,
                 answered_at.isoformat(timespec="seconds"), session_id, position),
            )

    def finish(self, session_id: int, finished_at: datetime, duration_ms: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET status = ?, finished_at = ?, duration_ms = ? WHERE id = ?",
                (SessionStatus.FINISHED.value, finished_at.isoformat(timespec="seconds"),
                 duration_ms, session_id),
            )

    # ------------------------------------------------------------ 会话读取
    def get(self, session_id: int) -> QuizSession | None:
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        items = [
            SessionItem(
                position=item["position"],
                question_id=item["question_id"],
                category=item["category"],
                difficulty=item["difficulty"],
                choice=item["choice"],
                correct=bool(item["correct"]) if item["correct"] is not None else None,
                points=item["points"],
                elapsed_ms=item["elapsed_ms"],
                answered_at=_dt(item["answered_at"]),
            )
            for item in self.conn.execute(
                "SELECT * FROM session_items WHERE session_id = ? ORDER BY position", (session_id,)
            )
        ]
        return QuizSession(
            id=row["id"],
            mode=row["mode"],
            status=SessionStatus(row["status"]),
            started_at=_dt(row["started_at"]),  # type: ignore[arg-type]
            items=items,
            finished_at=_dt(row["finished_at"]),
            duration_ms=row["duration_ms"],
        )

    # ---------------------------------------------------------------- 统计
    def history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.id, s.mode, s.status, s.started_at, s.finished_at, s.total, s.duration_ms,"
            " COALESCE(SUM(i.points), 0) AS score,"
            " COALESCE(SUM(i.correct), 0) AS correct"
            " FROM sessions s LEFT JOIN session_items i ON i.session_id = s.id"
            " GROUP BY s.id ORDER BY s.id DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM sessions) AS sessions,"
            " (SELECT COUNT(*) FROM session_items WHERE answered_at IS NOT NULL) AS answers,"
            " (SELECT COALESCE(SUM(correct), 0) FROM session_items WHERE answered_at IS NOT NULL) AS correct,"
            " (SELECT COALESCE(SUM(points), 0) FROM session_items WHERE answered_at IS NOT NULL) AS score,"
            " (SELECT MAX(started_at) FROM sessions) AS last_played"
        ).fetchone()
        best = self.conn.execute(
            "SELECT COALESCE(MAX(total_score), 0) FROM"
            " (SELECT SUM(points) AS total_score FROM session_items"
            "  WHERE answered_at IS NOT NULL GROUP BY session_id)"
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

    def category_stats(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT category, COUNT(*) AS total, COALESCE(SUM(correct), 0) AS correct"
            " FROM session_items WHERE answered_at IS NOT NULL"
            " GROUP BY category ORDER BY total DESC, category ASC"
        ).fetchall()
        return [
            {
                "category": row["category"],
                "total": int(row["total"]),
                "correct": int(row["correct"]),
                "accuracy": (row["correct"] / row["total"]) if row["total"] else 0.0,
            }
            for row in rows
        ]
