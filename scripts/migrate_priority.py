"""Добавляет колонку priority в tasks (миграция для существующих БД)."""
from __future__ import annotations

from database.pool import db_connection


def main() -> int:
    with db_connection() as conn:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority INT NOT NULL DEFAULT 1"
        )
        conn.execute("DROP INDEX IF EXISTS idx_tasks_status_pending")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_status_pending
            ON tasks (priority, created_at)
            WHERE status = 'PENDING'
            """
        )
        conn.commit()
    print("OK: колонка priority добавлена")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
