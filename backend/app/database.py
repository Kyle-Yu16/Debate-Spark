import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .settings import settings
from .strategy_skill import DEFAULT_SKILL


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY, topic TEXT NOT NULL, stance TEXT NOT NULL,
              config TEXT NOT NULL, status TEXT NOT NULL, workspace TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS debates (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, mode TEXT NOT NULL,
              user_stance TEXT NOT NULL, difficulty TEXT NOT NULL,
              status TEXT NOT NULL, state TEXT NOT NULL, evaluation TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS turns (
              id TEXT PRIMARY KEY, debate_id TEXT NOT NULL, speaker TEXT NOT NULL,
              stance TEXT NOT NULL, stage TEXT NOT NULL, content TEXT NOT NULL,
              meta TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evolution_runs (
              id TEXT PRIMARY KEY, status TEXT NOT NULL, result TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_versions (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, label TEXT NOT NULL,
              workspace TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategies (
              id TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL,
              metrics TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS debate_trajectories (
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration INTEGER NOT NULL,
              topic TEXT NOT NULL, candidate_id TEXT NOT NULL, champion_id TEXT NOT NULL,
              candidate_stance TEXT NOT NULL, outcome TEXT NOT NULL,
              transcript TEXT NOT NULL, evaluation TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trajectories_created_at
              ON debate_trajectories(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trajectories_topic
              ON debate_trajectories(topic);
            """
        )
        db.execute(
            "INSERT OR IGNORE INTO strategies VALUES (?,?,?,?,?)",
            (
                "baseline-v1",
                "active",
                encode(DEFAULT_SKILL),
                encode({"source": "built-in", "status": "active"}),
                now_iso(),
            ),
        )
        baseline = db.execute(
            "SELECT config FROM strategies WHERE id='baseline-v1'"
        ).fetchone()
        baseline_config = decode(baseline["config"], {}) if baseline else {}
        if baseline and (
            "invariants" not in baseline_config
            or int(baseline_config.get("schema_version", 0))
            < int(DEFAULT_SKILL.get("schema_version", 1))
        ):
            db.execute(
                "UPDATE strategies SET config=?, metrics=? WHERE id='baseline-v1'",
                (
                    encode(DEFAULT_SKILL),
                    encode({"source": "built-in", "status": "active"}),
                ),
            )


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    return json.loads(value)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None
