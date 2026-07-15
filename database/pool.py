from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import get_settings
from database.sql_runner import run_sql_file

_pool: Optional[ConnectionPool] = None
_pgvector_available: bool = False


def pgvector_available() -> bool:
    return _pgvector_available


def _configure_connection(conn: psycopg.Connection) -> None:
    if not _pgvector_available:
        return
    try:
        from pgvector.psycopg import register_vector

        register_vector(conn)
    except Exception:
        pass


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=6,
            max_idle=120,
            timeout=10,
            kwargs={"row_factory": dict_row},
            configure=_configure_connection,
            open=True,
            check=ConnectionPool.check_connection,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def reset_pool() -> None:
    """Сброс пула после обрыва соединения (долгие ML-задачи)."""
    close_pool()


@contextmanager
def db_connection() -> Generator[psycopg.Connection, None, None]:
    with get_pool().connection() as conn:
        yield conn


def check_db() -> tuple[bool, str]:
    try:
        settings = get_settings()
        with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT current_database() AS db"
            ).fetchone()
            db_name = row[0] if row else "?"
            return True, f"Подключено к базе «{db_name}»"
    except Exception as exc:
        return False, str(exc)


def _table_exists(conn: psycopg.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS ok",
        (f"public.{name}",),
    ).fetchone()
    if not row:
        return False
    if isinstance(row, dict):
        return bool(row.get("ok"))
    return bool(row[0])


def init_schema() -> dict[str, bool]:
    """Создаёт таблицы. pgvector — опционально."""
    global _pgvector_available

    root = Path(__file__).resolve().parent.parent
    core_sql = (root / "sql" / "init_core.sql").read_text(encoding="utf-8")
    pg_sql = (root / "sql" / "init_pgvector.sql").read_text(encoding="utf-8")

    with db_connection() as conn:
        run_sql_file(conn, core_sql)
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
        print("[DB] init_core: tasks, corpus_sources, corpus_chunks — OK")

        if not _table_exists(conn, "corpus_chunks"):
            raise RuntimeError("Таблица corpus_chunks не создана после init_core.sql")

        try:
            run_sql_file(conn, pg_sql)
            conn.commit()
            _pgvector_available = True
            print("[DB] pgvector: включён")
        except Exception as exc:
            conn.rollback()
            _pgvector_available = False
            print(f"[DB] pgvector: недоступен ({exc})")

        platform_sql = (root / "sql" / "init_platform.sql").read_text(encoding="utf-8")
        platform_analytics_sql = (
            root / "sql" / "init_platform_analytics.sql"
        ).read_text(encoding="utf-8")
        try:
            run_sql_file(conn, platform_sql)
            conn.commit()
            print("[DB] platform: institutions, documents, plagiarism_matches — OK")
            if _pgvector_available:
                run_sql_file(conn, platform_analytics_sql)
                conn.commit()
                # document_chunks больше не создаём (не использовалась в коде)
                print("[DB] platform analytics SQL — OK")
        except Exception as exc:
            conn.rollback()
            print(f"[DB] platform: {exc}")

    return {"core": True, "pgvector": _pgvector_available}
