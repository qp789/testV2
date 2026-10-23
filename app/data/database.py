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

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE session_items ADD COLUMN kind TEXT NOT NULL DEFAULT 'single';

CREATE TABLE IF NOT EXISTS cards (
    user_id       INTEGER NOT NULL,
    question_id   TEXT    NOT NULL,
    ease          REAL    NOT NULL DEFAULT 2.5,
    interval_days REAL    NOT NULL DEFAULT 0,
    reps          INTEGER NOT NULL DEFAULT 0,
    lapses        INTEGER NOT NULL DEFAULT 0,
    due_at        TEXT,
    updated_at    TEXT    NOT NULL,
    PRIMARY KEY (user_id, question_id)
);

CREATE TABLE IF NOT EXISTS sync_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_id   TEXT    NOT NULL,
    session_id  INTEGER,
    question_id TEXT    NOT NULL,
    choice      TEXT,
    created_at  TEXT    NOT NULL,
    UNIQUE (user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(user_id, due_at);
"""

MIGRATIONS: dict[int, str] = {1: SCHEMA_V1, 2: SCHEMA_V2}


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
