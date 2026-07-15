"""Быстрая проверка API аналитики."""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001"


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())


def main() -> int:
    health = get("/health")
    print("health:", health.get("status"), "db:", health.get("database"))

    for doc_id in range(1, 50):
        try:
            data = get(f"/api/analytics/documents/{doc_id}/borrowings")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        print(
            f"doc #{doc_id}: {data.get('title')!r} "
            f"status={data.get('analytics_status')} "
            f"borrowings={data.get('borrowings_count')}"
        )
        return 0

    print("Документы не найдены — запустите seed_platform_demo.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
