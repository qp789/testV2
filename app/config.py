"""运行配置：路径与监听参数都可以用环境变量覆盖。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"


def _path(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name)
    return Path(raw).expanduser() if raw else default


QUESTIONS_PATH = _path("QPQUIZ_QUESTIONS", DATA_DIR / "questions.json")
DB_PATH = _path("QPQUIZ_DB", DATA_DIR / "qpquiz.db")
HOST = os.environ.get("QPQUIZ_HOST", "0.0.0.0")
PORT = int(os.environ.get("QPQUIZ_PORT", "8765"))


def server_hint(host: str, port: int) -> str:
    """给终端打印的可访问地址提示。"""
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{shown}:{port}"
