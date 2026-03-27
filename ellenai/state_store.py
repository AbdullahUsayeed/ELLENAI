from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id TEXT PRIMARY KEY,
                    session_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            session_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            if "version" not in session_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    attachments_count INTEGER NOT NULL,
                    attachment_types_json TEXT NOT NULL,
                    attachment_urls_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON message_history(user_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incoming_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_status ON incoming_events(status)")

    def save_session(self, user_id: str, session: dict[str, Any]) -> bool:
        session_payload = {k: v for k, v in session.items() if k != "_version"}
        payload = json.dumps(session_payload, ensure_ascii=True)
        expected_version = int(session.get("_version", 0) or 0)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE sessions
                SET session_json = ?, updated_at = ?, version = version + 1
                WHERE user_id = ? AND version = ?
                """,
                (payload, self._utc_now_iso(), user_id, expected_version),
            )
            if cursor.rowcount == 1:
                session["_version"] = expected_version + 1
                return True

            existing = conn.execute("SELECT version FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO sessions(user_id, session_json, updated_at, version)
                    VALUES (?, ?, ?, 0)
                    """,
                    (user_id, payload, self._utc_now_iso()),
                )
                session["_version"] = 0
                return True

        return False

    def get_session(self, user_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT session_json, version FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row[0]))
        if not isinstance(payload, dict):
            return None
        payload["_version"] = int(row[1] or 0)
        return payload

    def insert_incoming_event(self, event: dict[str, Any]) -> int:
        user_id = str(event.get("user_id", "")).strip()
        payload = json.dumps(event, ensure_ascii=True)
        now_iso = self._utc_now_iso()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO incoming_events(user_id, payload_json, status, attempts, last_error, created_at, updated_at)
                VALUES (?, ?, 'pending', 0, NULL, ?, ?)
                """,
                (user_id, payload, now_iso, now_iso),
            )
            return int(cursor.lastrowid)

    def get_incoming_event(self, event_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json, status, attempts FROM incoming_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row[0]))
        if not isinstance(payload, dict):
            return None
        payload["_db_status"] = str(row[1])
        payload["_db_attempts"] = int(row[2] or 0)
        return payload

    def mark_incoming_event(
        self,
        event_id: int,
        status: str,
        error: str | None = None,
        increment_attempt: bool = False,
    ) -> None:
        safe_error = (error or "")[:2000] if error else None
        with sqlite3.connect(self.db_path) as conn:
            if increment_attempt:
                conn.execute(
                    """
                    UPDATE incoming_events
                    SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, safe_error, self._utc_now_iso(), event_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE incoming_events
                    SET status = ?, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, safe_error, self._utc_now_iso(), event_id),
                )

    def fetch_pending_event_ids(self, limit: int = 200) -> list[int]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM incoming_events
                WHERE status IN ('pending', 'retry')
                ORDER BY id ASC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [int(r[0]) for r in rows]

    def append_history(
        self,
        user_id: str,
        message: str,
        attachments_count: int,
        attachment_types: list[str],
        attachment_urls: list[str],
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO message_history(
                    user_id, text, attachments_count, attachment_types_json, attachment_urls_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    message,
                    max(0, attachments_count),
                    json.dumps(attachment_types, ensure_ascii=True),
                    json.dumps(attachment_urls, ensure_ascii=True),
                    self._utc_now_iso(),
                ),
            )

    def recent_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT text, attachments_count, attachment_types_json, attachment_urls_json, created_at
                FROM message_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, max(1, limit)),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for text, cnt, types_json, urls_json, created_at in reversed(rows):
            try:
                types = json.loads(str(types_json))
            except json.JSONDecodeError:
                types = []
            try:
                urls = json.loads(str(urls_json))
            except json.JSONDecodeError:
                urls = []
            result.append(
                {
                    "text": str(text),
                    "attachments_count": int(cnt or 0),
                    "attachment_types": types if isinstance(types, list) else [],
                    "attachment_urls": urls if isinstance(urls, list) else [],
                    "created_at": str(created_at),
                }
            )
        return result
