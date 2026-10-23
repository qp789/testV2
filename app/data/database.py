"""SQLite 连接与 schema 迁移。

用 `PRAGMA user_version` 记录版本，后续加字段只需追加一条迁移。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mode        TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    finished_at TEXT,
    total       INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    question_id TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    difficulty  INTEGER NOT NULL,
    choice      INTEGER,
    correct     INTEGER,
    points      INTEGER NOT NULL DEFAULT 0,
    elapsed_ms  INTEGER NOT NULL DEFAULT 0,
    answered_at TEXT,
    UNIQUE (session_id, position)
);

CREATE INDEX IF NOT EXISTS idx_items_session ON session_items(session_id);
"""

MIGRATIONS: dict[int, str] = {1: SCHEMA_V1}


def connect(path: str | Path) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    for target in sorted(MIGRATIONS):
        if target <= version:
            continue
        conn.executescript(MIGRATIONS[target])
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()
        version = target
    return version
