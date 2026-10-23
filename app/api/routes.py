"""REST API：认证、答题会话、SRS 复习、离线同步与统计。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from .. import __version__
from ..domain.engine import finish_session
from ..domain.models import Question, QuizSession
from ..domain.plugins import normalize_choice, registry
from ..domain.selection import QuizError, select_questions
from ..domain.srs import review as srs_review
from ..security import hash_password, verify_password
from .schemas import AnswerCreate, Credentials, ReviewCreate, SessionCreate, SyncRequest

router = APIRouter()


# ------------------------------------------------------------------ 依赖
def get_repo(request: Request):
    return request.app.state.repo


def get_bank(request: Request) -> dict[str, Question]:
    return request.app.state.bank


def current_user(request: Request, authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要登录")
    user_id = request.app.state.signer.verify(authorization.split(" ", 1)[1].strip())
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效或已过期")
    user = get_repo(request).get_user(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def _now() -> datetime:
    return datetime.now().astimezone()


# ------------------------------------------------------------------ 序列化
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
                "answers": list(question.answers),
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


def _load_session(request: Request, session_id: int, user_id: int) -> QuizSession:
    session = get_repo(request).get(session_id, user_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return session


def _apply_srs(request: Request, user_id: int, question: Question, correct: bool) -> None:
    repo = get_repo(request)
    now = _now()
    card = repo.get_card(user_id, question.id)
    srs_review(card, correct, now)
    repo.save_card(user_id, card, now)


# ------------------------------------------------------------------ 认证
@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(request: Request, payload: Credentials) -> dict:
    repo = get_repo(request)
    if repo.find_user(payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    hashed = hash_password(payload.password)
    user = repo.create_user(payload.email, hashed, _now())
    return {"token": request.app.state.signer.issue(user["id"]), "user": user}


@router.post("/auth/login")
def login(request: Request, payload: Credentials) -> dict:
    repo = get_repo(request)
    record = repo.find_user(payload.email)
    if record is None or not verify_password(payload.password, record["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    return {
        "token": request.app.state.signer.issue(record["id"]),
        "user": {"id": record["id"], "email": record["email"]},
    }


@router.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": user, "kinds": registry.kinds()}


# ------------------------------------------------------------------ 题库
@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/meta")
def meta(request: Request) -> dict:
    bank = get_bank(request)
    return {
        "version": __version__,
        "question_count": len(bank),
        "categories": sorted({q.category for q in bank.values()}),
        "difficulties": [1, 2, 3],
        "kinds": registry.kinds(),
    }


@router.get("/questions")
def list_questions(request: Request, category: str | None = None) -> dict:
    bank = get_bank(request)
    return {
        "questions": [
            q.public() for q in bank.values() if category is None or q.category == category
        ]
    }


# ------------------------------------------------------------------ 会话
@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(request: Request, payload: SessionCreate,
                   user: dict = Depends(current_user)) -> dict:
    bank = get_bank(request)
    try:
        questions = select_questions(
            list(bank.values()), count=payload.count, categories=payload.categories,
            difficulties=payload.difficulties, seed=payload.seed,
        )
    except QuizError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session = get_repo(request).create_session(payload.mode, questions, _now(), user["id"])
    return session_state(session, bank)


@router.get("/sessions/{session_id}")
def get_session(request: Request, session_id: int, user: dict = Depends(current_user)) -> dict:
    return session_state(_load_session(request, session_id, user["id"]), get_bank(request))


@router.post("/sessions/{session_id}/answers")
def submit_answer(request: Request, session_id: int, payload: AnswerCreate,
                  user: dict = Depends(current_user)) -> dict:
    bank = get_bank(request)
    repo = get_repo(request)
    session = _load_session(request, session_id, user["id"])
    if session.status.value == "finished":
        raise HTTPException(status.HTTP_409_CONFLICT, "本轮已经结束")
    item = session.current_item
    if item is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "没有待作答的题目")
    if payload.question_id != item.question_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "题号与当前题目不一致")

    question = bank[item.question_id]
    correct, points = registry.score(question, payload.choice)
    now = _now()
    repo.save_answer(session_id, item.position, payload.choice, correct, points,
                     payload.elapsed_ms, now)
    _apply_srs(request, user["id"], question, correct)

    session = _load_session(request, session_id, user["id"])
    if session.current_item is None:
        finish_session(session, now)
        repo.finish(session_id, session.finished_at, session.duration_ms)  # type: ignore[arg-type]
        session = _load_session(request, session_id, user["id"])

    feedback = None
    if session.mode == "practice":
        feedback = {
            "correct": correct,
            "points": points,
            "answers": list(question.answers),
            "explanation": question.explanation,
        }
    return {"accepted": True, "feedback": feedback, "session": session_state(session, bank)}


@router.post("/sessions/{session_id}/finish")
def finish(request: Request, session_id: int, user: dict = Depends(current_user)) -> dict:
    repo = get_repo(request)
    session = _load_session(request, session_id, user["id"])
    if session.status.value != "finished":
        finish_session(session)
        repo.finish(session_id, session.finished_at, session.duration_ms)  # type: ignore[arg-type]
        session = _load_session(request, session_id, user["id"])
    return session_summary(session, get_bank(request))


@router.get("/sessions/{session_id}/summary")
def summary(request: Request, session_id: int, user: dict = Depends(current_user)) -> dict:
    return session_summary(_load_session(request, session_id, user["id"]), get_bank(request))


# ------------------------------------------------------------------ 复习
@router.get("/study/due")
def study_due(request: Request, limit: int = Query(default=10, ge=1, le=50),
              user: dict = Depends(current_user)) -> dict:
    repo = get_repo(request)
    bank = get_bank(request)
    now = _now()
    due_ids = repo.due_question_ids(user["id"], now, limit)
    known = repo.card_ids(user["id"])
    new_ids = [qid for qid in bank if qid not in known][: max(0, limit - len(due_ids))]
    ids = (due_ids + new_ids)[:limit]
    return {
        "due": len(due_ids),
        "new": len(new_ids),
        "questions": [bank[qid].public() for qid in ids if qid in bank],
    }


@router.post("/study/review")
def study_review(request: Request, payload: ReviewCreate,
                 user: dict = Depends(current_user)) -> dict:
    bank = get_bank(request)
    question = bank.get(payload.question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    correct, points = registry.score(question, payload.choice)
    _apply_srs(request, user["id"], question, correct)
    card = get_repo(request).get_card(user["id"], question.id)
    return {
        "correct": correct,
        "points": points,
        "answers": list(question.answers),
        "explanation": question.explanation,
        "interval_days": card.interval_days,
        "due_at": card.due_at.isoformat() if card.due_at else None,
    }


# ------------------------------------------------------------------ 同步
@router.post("/sync")
def sync_events(request: Request, payload: SyncRequest,
                user: dict = Depends(current_user)) -> dict:
    repo = get_repo(request)
    bank = get_bank(request)
    results = []
    for event in payload.events:
        server_choice = (repo.item_choice(event.session_id, event.question_id)
                         if event.session_id else None)
        if server_choice is not None and normalize_choice(server_choice) != normalize_choice(event.choice):
            results.append({"client_id": event.client_id, "status": "conflict",
                            "server_choice": server_choice})
            continue
        inserted = repo.record_event(
            user["id"], event.client_id, event.session_id, event.question_id,
            event.choice, event.answered_at or _now(),
        )
        if inserted and event.question_id in bank:
            correct, _ = registry.score(bank[event.question_id], event.choice)
            _apply_srs(request, user["id"], bank[event.question_id], correct)
        results.append({"client_id": event.client_id,
                        "status": "accepted" if inserted else "duplicate"})
    return {"results": results}


# ------------------------------------------------------------------ 统计
@router.get("/stats")
def stats(request: Request, user: dict = Depends(current_user)) -> dict:
    repo = get_repo(request)
    return {"stats": repo.stats(user["id"]), "categories": repo.category_stats(user["id"])}


@router.get("/history")
def history(request: Request, limit: int = Query(default=20, ge=1, le=100),
            user: dict = Depends(current_user)) -> dict:
    return {"sessions": get_repo(request).history(user["id"], limit)}
