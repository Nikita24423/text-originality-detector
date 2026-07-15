"""Список таблиц БД и число строк."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.pool import check_db, db_connection


def main() -> int:
    ok, msg = check_db()
    print("DB:", ok, msg)
    if not ok:
        return 1
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()
        print("TABLES:")
        for r in rows:
            name = r["table_name"]
            cnt = conn.execute(f'SELECT COUNT(*) AS c FROM "{name}"').fetchone()["c"]
            print(f"  {name}: {cnt} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
