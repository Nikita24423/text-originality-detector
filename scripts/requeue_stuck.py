"""Сброс зависших задач PROCESSING → PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg
from config import get_settings


def main() -> int:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            """
            UPDATE tasks
            SET status = 'PENDING', progress = 'requeued', started_at = NULL
            WHERE status = 'PROCESSING'
            RETURNING id
            """
        ).fetchall()
        conn.commit()
    ids = [r[0] for r in rows]
    print(f"Перезапущено задач: {ids if ids else 'нет'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
