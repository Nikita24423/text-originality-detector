"""Быстрая проверка API + очереди + анализа."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings

CHECK_TEXT = (
    "Искусственный интеллект меняет подход к анализу текстов. "
    "Современные системы проверяют оригинальность на нескольких уровнях. "
    "Лексический анализ выявляет прямое копирование фрагментов."
)
CORPUS_TEXT = (
    "Источник А\n"
    "Искусственный интеллект меняет подход к анализу текстов в образовании. "
    "Современные системы проверяют оригинальность работ студентов.\n"
    "---\n"
    "Источник Б\n"
    "Машинное обучение применяется в медицине и финансах для прогнозирования."
)


def http_json(method: str, url: str, data: dict | None = None, timeout: int = 30) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    settings = get_settings()
    base = f"http://{settings.api_host}:{settings.api_port}"
    print(f"Smoke test → {base}\n")

    # 1. Health
    print("1. GET /health")
    try:
        health = http_json("GET", f"{base}/health")
        print(f"   status={health.get('status')} database={health.get('database')} "
              f"pgvector={health.get('pgvector')} qdrant={health.get('qdrant')}")
        if not health.get("database"):
            print("   FAIL: нет подключения к БД")
            return 1
    except urllib.error.URLError as exc:
        print(f"   FAIL: сервер не запущен ({exc})")
        return 1

    # 2. Create task (multipart via simple form - use urllib for multipart is hard, use requests if available)
    print("2. POST /api/tasks")
    try:
        import requests

        resp = requests.post(
            f"{base}/api/tasks",
            data={
                "mode": "corpus",
                "text": CHECK_TEXT,
                "corpus": CORPUS_TEXT,
            },
            timeout=30,
        )
        created = resp.json()
        if resp.status_code != 200:
            print(f"   FAIL: {created}")
            return 1
        task_id = created["task_id"]
        print(f"   task_id={task_id} queue={created.get('queue_position')}")
    except ImportError:
        print("   SKIP: установите requests для полного теста")
        return 0
    except Exception as exc:
        print(f"   FAIL: {exc}")
        return 1

    # 3. Poll
    print("3. Ожидание результата (до 15 мин, первый раз — скачивание моделей)...")
    deadline = time.time() + 900
    last_progress = ""
    while time.time() < deadline:
        st = requests.get(f"{base}/api/tasks/{task_id}", timeout=15).json()
        status = st.get("status")
        progress = st.get("progress") or ""
        if progress != last_progress:
            print(f"   {status}: {progress}")
            last_progress = progress
        if status == "DONE":
            result = st.get("result") or {}
            print("\n=== РЕЗУЛЬТАТ ===")
            print(f"   Оригинальность: {result.get('originality_percent')}%")
            print(f"   Копирование:    {result.get('copy_percent')}%")
            print(f"   Глубокое:       {result.get('deep_borrow_percent')}%")
            print(f"   ИИ:             {result.get('ai_percent')}%")
            print("\nOK: программа работает")
            return 0
        if status == "FAILED":
            print(f"   FAIL: {st.get('error')}")
            return 1
        time.sleep(3)

    print("   TIMEOUT: задача не завершилась за 15 мин (workers загружают модели?)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
