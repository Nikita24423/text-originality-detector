"""Прямой тест API без subprocess."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings

settings = get_settings()
BASE = f"http://{settings.api_host}:{settings.api_port}"
TEXT = (
    "Искусственный интеллект меняет подход к анализу текстов. "
    "Современные системы проверяют оригинальность на нескольких уровнях."
)
CORPUS = (
    "Источник А\n"
    "Искусственный интеллект меняет подход к анализу текстов в образовании.\n"
    "---\n"
    "Источник Б\n"
    "Машинное обучение применяется в медицине."
)


def main() -> int:
    print("GET /health")
    h = requests.get(f"{BASE}/health", timeout=10).json()
    print(json.dumps(h, ensure_ascii=False, indent=2))
    if not h.get("database"):
        return 1

    print("\nPOST /api/tasks")
    r = requests.post(
        f"{BASE}/api/tasks",
        data={"mode": "corpus", "text": TEXT, "corpus": CORPUS},
        timeout=30,
    )
    print(r.status_code, r.text[:500])
    if r.status_code != 200:
        return 1
    task_id = r.json()["task_id"]
    print(f"task_id={task_id}")

    print("\nPolling...")
    for i in range(200):
        st = requests.get(f"{BASE}/api/tasks/{task_id}", timeout=15).json()
        status = st.get("status")
        progress = st.get("progress")
        if i % 5 == 0 or status in ("DONE", "FAILED"):
            print(f"  [{i}] {status} {progress}")
        if status == "DONE":
            res = st.get("result") or {}
            print("\n=== OK ===")
            print(f"originality: {res.get('originality_percent')}%")
            print(f"copy: {res.get('copy_percent')}%")
            print(f"deep: {res.get('deep_borrow_percent')}%")
            print(f"ai: {res.get('ai_percent')}%")
            return 0
        if status == "FAILED":
            print("FAILED:", st.get("error"))
            return 1
        time.sleep(3)

    print("TIMEOUT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
