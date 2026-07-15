"""Создать базу из DATABASE_URL если её нет."""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import psycopg

from config import get_settings


def ensure_database_exists() -> tuple[bool, str]:
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        return False, "В DATABASE_URL не указано имя базы"

    admin_path = "/postgres"
    admin_url = urlunparse(parsed._replace(path=admin_path))

    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
            ).fetchone()
            if row:
                return True, f"База «{db_name}» существует"
            conn.execute(f'CREATE DATABASE "{db_name}"')
            return True, f"База «{db_name}» создана"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    ok, msg = ensure_database_exists()
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
