"""计分与状态流转。"""

from __future__ import annotations

from datetime import datetime

from .models import Question, QuizSession, SessionItem, SessionStatus


def evaluate(question: Question, choice: int | None) -> tuple[bool, int]:
    """返回 (是否答对, 得分)；跳过（choice=None）按答错处理。"""
    if choice is not None and not 0 <= choice < len(question.options):
        raise ValueError(f"选项下标越界：{choice}")
    correct = choice is not None and choice == question.answer
    return correct, (question.max_points if correct else 0)


def build_items(questions: list[Question]) -> list[SessionItem]:
    return [
        SessionItem(position=index + 1, question_id=q.id, category=q.category, difficulty=q.difficulty)
        for index, q in enumerate(questions)
    ]


def finish_session(session: QuizSession, now: datetime | None = None) -> QuizSession:
    if session.status is SessionStatus.FINISHED:
        return session
    moment = now or datetime.now().astimezone()
    session.status = SessionStatus.FINISHED
    session.finished_at = moment
    session.duration_ms = max(0, int((moment - session.started_at).total_seconds() * 1000))
    return session
