"""Проверка подключения к PostgreSQL и инициализация схемы."""
from __future__ import annotations

import sys

from config import get_settings
from database import check_db, init_schema, pgvector_available
from scripts.create_db import ensure_database_exists


def main() -> int:
    settings = get_settings()
    # Маскируем пароль в выводе
    url = settings.database_url
    if "@" in url:
        safe = url.split("@", 1)[1]
        print(f"DATABASE_URL: ...@{safe}")
    else:
        print(f"DATABASE_URL: {url}")

    print("\n1. Проверка подключения...")
    ok, msg = check_db()
    if not ok and ("не существует" in msg.lower() or "does not exist" in msg.lower()):
        print(f"   База не найдена, создаём...")
        created, cmsg = ensure_database_exists()
        print(f"   {cmsg}")
        if created:
            ok, msg = check_db()
    if not ok:
        print(f"   ОШИБКА: {msg}")
        print("\n   Убедитесь что:")
        print("   - PostgreSQL запущен на порту 5436")
        print("   - База nikita2 создана")
        print("   - Пароль в .env верный")
        return 1
    print(f"   OK: {msg}")

    print("\n2. Инициализация таблиц...")
    try:
        result = init_schema()
        print(f"   core: OK")
        if result["pgvector"]:
            print("   pgvector: установлен")
        else:
            print("   pgvector: не установлен (это нормально — очередь задач работает)")
    except Exception as exc:
        print(f"   ОШИБКА: {exc}")
        return 1

    print("\n3. Итог:")
    print(f"   pgvector_available = {pgvector_available()}")
    print("   Готово к запуску: python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
