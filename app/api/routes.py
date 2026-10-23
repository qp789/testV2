"""REST API：题库、答题会话、统计与历史。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status

from .. import __version__
from ..domain.engine import evaluate, finish_session
from ..domain.models import Question, QuizSession
from ..domain.selection import QuizError, select_questions
from .schemas import AnswerCreate, SessionCreate

router = APIRouter()


def _bank(request: Request) -> dict[str, Question]:
    return request.app.state.bank


def _repo(request: Request):
    return request.app.state.repo


def _now() -> datetime:
    return datetime.now().astimezone()


def session_state(session: QuizSession, bank: dict[str, Question]) -> dict:
    item = session.current_item
    question = bank.get(item.question_id) if item else None
    return {
        "id": session.id,
        "mode": session.mode,
        "status": session.status.value,
        "total": session.total,
        "answered": session.answered_count,
        "score": session.score,
        "correct": session.correct_count,
        "position": session.current_position,
        "started_at": session.started_at.isoformat(),
        "question": {**question.public(), "position": item.position} if question else None,
    }


def session_summary(session: QuizSession, bank: dict[str, Question]) -> dict:
    wrong = []
    for item in session.items:
        if item.answered and not item.correct:
            question = bank[item.question_id]
            wrong.append({
                "question": question.public(),
                "choice": item.choice,
                "answer_index": question.answer,
                "explanation": question.explanation,
            })
    return {
        "id": session.id,
        "mode": session.mode,
        "status": session.status.value,
        "score": session.score,
        "max_score": session.max_score,
        "correct": session.correct_count,
        "total": session.total,
        "accuracy": session.accuracy,
        "duration_ms": session.duration_ms,
        "started_at": session.started_at.isoformat(),
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "categories": session.category_breakdown(),
        "wrong": wrong,
    }


def _load_or_404(request: Request, session_id: int) -> QuizSession:
    session = _repo(request).get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return session


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/meta")
def meta(request: Request) -> dict:
    bank = _bank(request)
    return {
        "version": __version__,
        "question_count": len(bank),
        "categories": sorted({q.category for q in bank.values()}),
        "difficulties": [1, 2, 3],
    }


@router.get("/questions")
def list_questions(request: Request, category: str | None = None) -> dict:
    bank = _bank(request)
    items = [q for q in bank.values() if category is None or q.category == category]
    return {"questions": [q.public() for q in items]}


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(request: Request, payload: SessionCreate) -> dict:
    bank = _bank(request)
    try:
        questions = select_questions(
            list(bank.values()),
            count=payload.count,
            categories=payload.categories,
            difficulties=payload.difficulties,
            seed=payload.seed,
        )
    except QuizError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session = _repo(request).create_session(payload.mode, questions, _now())
    return session_state(session, bank)


@router.get("/sessions/{session_id}")
def get_session(request: Request, session_id: int) -> dict:
    return session_state(_load_or_404(request, session_id), _bank(request))


@router.post("/sessions/{session_id}/answers")
def submit_answer(request: Request, session_id: int, payload: AnswerCreate) -> dict:
    bank = _bank(request)
    session = _load_or_404(request, session_id)
    if session.status.value == "finished":
        raise HTTPException(status.HTTP_409_CONFLICT, "本轮已经结束")
    item = session.current_item
    if item is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "没有待作答的题目")
    if payload.question_id != item.question_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "题号与当前题目不一致")
    question = bank[item.question_id]

    try:
        correct, points = evaluate(question, payload.choice)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    now = _now()
    _repo(request).save_answer(
        session_id, item.position, payload.choice, correct, points, payload.elapsed_ms, now
    )
    session = _load_or_404(request, session_id)

    if session.current_item is None:
        finish_session(session, now)
        _repo(request).finish(session_id, session.finished_at, session.duration_ms)  # type: ignore[arg-type]
        session = _load_or_404(request, session_id)

    feedback = None
    if session.mode == "practice":
        feedback = {
            "correct": correct,
            "points": points,
            "answer_index": question.answer,
            "explanation": question.explanation,
        }
    return {"accepted": True, "feedback": feedback, "session": session_state(session, bank)}


@router.post("/sessions/{session_id}/finish")
def finish(request: Request, session_id: int) -> dict:
    session = _load_or_404(request, session_id)
    if session.status.value != "finished":
        finish_session(session, _now())
        _repo(request).finish(session_id, session.finished_at, session.duration_ms)  # type: ignore[arg-type]
        session = _load_or_404(request, session_id)
    return session_summary(session, _bank(request))


@router.get("/sessions/{session_id}/summary")
def summary(request: Request, session_id: int) -> dict:
    return session_summary(_load_or_404(request, session_id), _bank(request))


@router.get("/stats")
def stats(request: Request) -> dict:
    repo = _repo(request)
    return {"stats": repo.stats(), "categories": repo.category_stats()}


@router.get("/history")
def history(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"sessions": _repo(request).history(limit)}
