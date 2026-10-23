"""计分与状态流转。"""

from __future__ import annotations

from datetime import datetime

from .models import Question, QuizSession, SessionItem, SessionStatus


def evaluate(question: Question, choice) -> tuple[bool, int]:
    """返回 (是否答对, 得分)；判分逻辑委托给题型插件。"""
    from .plugins import registry

    return registry.score(question, choice)


def build_items(questions: list[Question]) -> list[SessionItem]:
    return [
        SessionItem(position=index + 1, question_id=q.id, kind=q.kind,
                    category=q.category, difficulty=q.difficulty)
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
