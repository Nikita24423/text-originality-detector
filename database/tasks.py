from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

import psycopg

from database.pool import db_connection, reset_pool

T = TypeVar("T")


def _db_retry(fn: Callable[[], T], attempts: int = 3) -> T:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except psycopg.OperationalError as exc:
            last_exc = exc
            reset_pool()
            if attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_task(
    mode: str,
    payload: dict[str, Any],
    filename: Optional[str] = None,
    priority: int = 1,
) -> int:
    with db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO tasks (mode, filename, payload, status, priority)
            VALUES (%s, %s, %s::jsonb, 'PENDING', %s)
            RETURNING id
            """,
            (mode, filename, json.dumps(payload, ensure_ascii=False), priority),
        ).fetchone()
        conn.commit()
        return int(row["id"])


def fetch_next_task() -> Optional[dict[str, Any]]:
    def _run() -> Optional[dict[str, Any]]:
        with db_connection() as conn:
            row = conn.execute(
                """
                UPDATE tasks
                SET status = 'PROCESSING',
                    started_at = COALESCE(started_at, now()),
                    progress = 'started'
                WHERE id = (
                    SELECT id FROM tasks
                    WHERE status = 'PENDING'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, mode, filename, payload, progress
                """
            ).fetchone()
            conn.commit()
            return dict(row) if row else None

    try:
        return _db_retry(_run)
    except Exception:
        # Пул/сеть БД временно недоступны — воркер подождёт idle_sleep
        reset_pool()
        return None


def update_task_progress(task_id: int, progress: str) -> None:
    def _run() -> None:
        with db_connection() as conn:
            conn.execute(
                "UPDATE tasks SET progress = %s WHERE id = %s",
                (progress, task_id),
            )
            conn.commit()

    _db_retry(_run)


def complete_task(task_id: int, result: dict[str, Any]) -> None:
    def _run() -> None:
        with db_connection() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    status = 'DONE',
                    progress = 'done',
                    plagiarism_pct = %s,
                    copy_pct = %s,
                    deep_borrow_pct = %s,
                    ai_pct = %s,
                    result_json = %s::jsonb,
                    finished_at = now()
                WHERE id = %s
                """,
                (
                    result.get("plagiarism_percent") or result.get("plagiarism_percent_ml"),
                    result.get("copy_percent") or result.get("copy_percent_ml"),
                    result.get("deep_borrow_percent") or result.get("deep_borrow_percent_ml"),
                    result.get("ai_percent") or result.get("ai_percent_ml"),
                    json.dumps(result, ensure_ascii=False),
                    task_id,
                ),
            )
            conn.commit()

    _db_retry(_run)


def fail_task(task_id: int, message: str) -> None:
    def _run() -> None:
        with db_connection() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    status = 'FAILED',
                    progress = 'failed',
                    error_message = %s,
                    finished_at = now()
                WHERE id = %s
                """,
                (message, task_id),
            )
            conn.commit()

    _db_retry(_run)


def get_task(task_id: int) -> Optional[dict[str, Any]]:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, status, mode, filename, progress, error_message,
                   plagiarism_pct, copy_pct, deep_borrow_pct, ai_pct,
                   result_json, created_at, started_at, finished_at
            FROM tasks WHERE id = %s
            """,
            (task_id,),
        ).fetchone()
        return dict(row) if row else None


def count_pending_tasks() -> int:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*)::int AS c FROM tasks WHERE status = 'PENDING'"
        ).fetchone()
        return int(row["c"])


def queue_position(task_id: int) -> int:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)::int AS pos
            FROM tasks
            WHERE status = 'PENDING'
              AND created_at <= (SELECT created_at FROM tasks WHERE id = %s)
            """,
            (task_id,),
        ).fetchone()
        return int(row["pos"])
