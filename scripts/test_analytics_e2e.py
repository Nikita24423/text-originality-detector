"""End-to-end тест модуля аналитики (без HTTP, напрямую через сервис)."""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.platform import get_borrowings
from database.pool import init_schema
from scripts.seed_platform_demo import seed_demo_documents
from services.analytics_service import analyze_document


def main() -> int:
    print("1. Инициализация схемы...")
    init_schema()

    print("2. Демо-документы...")
    id_a, id_b = seed_demo_documents()

    print(f"3. Анализ document #{id_a} (может занять несколько минут — загрузка моделей)...")
    result = analyze_document(id_a)
    print(f"   status: {result.get('analytics_status')}")
    print(f"   originality: {result.get('originality_percent')}%")
    print(f"   borrowings: {result.get('borrowings_count')}")

    print("4. Чтение borrowings из БД...")
    data = get_borrowings(id_a)
    assert data is not None
    print(f"   borrowings_count: {data['borrowings_count']}")
    for b in data["borrowings"]:
        print(
            f"   -> doc #{b['target_document_id']} "
            f"({b.get('target_title')}): {b['similarity_percent']}%"
        )

    if data["borrowings_count"] == 0 and id_b:
        print("   WARN: заимствований не найдено — проверьте тексты demo")
        return 1

    print("\nOK: модуль аналитики работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
