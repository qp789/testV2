"""应用工厂：装配题库、数据库、路由与静态前端。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router
from .config import DB_PATH, QUESTIONS_PATH, WEB_DIR
from .data.database import connect, migrate
from .data.repository import QuizRepository
from .domain.models import Question


def load_questions(path: str | Path) -> list[Question]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = raw["questions"] if isinstance(raw, dict) else raw
    questions = [
        Question(
            id=item["id"],
            category=item["category"],
            difficulty=int(item["difficulty"]),
            prompt=item["prompt"],
            options=tuple(item["options"]),
            answer=int(item["answer"]),
            explanation=item["explanation"],
        )
        for item in entries
    ]
    if not questions:
        raise ValueError("题库为空")
    return questions


def create_app(db_path: str | Path | None = None, questions_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="qpquiz-web",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    questions = load_questions(questions_path or QUESTIONS_PATH)
    conn = connect(db_path or DB_PATH)
    migrate(conn)

    app.state.bank = {q.id: q for q in questions}
    app.state.repo = QuizRepository(conn)

    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


app = create_app()
