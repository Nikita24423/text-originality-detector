"""Запуск API + ML workers."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser

from config import get_settings


def main() -> int:
    settings = get_settings()
    url = f"http://{settings.api_host}:{settings.api_port}"

    print("=" * 50)
    print("  Анализ оригинальности текста v2")
    print("  Приоритет анализа: глубокое -> копирование -> ИИ")
    print("  Модели: bge-m3 + reranker-v2-m3 + rugpt3small")
    print("=" * 50)
    print(f"  API:     {url}")
    print(f"  Analytics: {url}/api/analytics/documents/{{id}}/analyze")
    print(f"  Workers: {settings.ml_workers} ML-процессов")
    print("  Остановка: Ctrl+C")
    print("=" * 50)

    supervisor = subprocess.Popen(
        [sys.executable, "-m", "workers.supervisor"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent),
        env={**os.environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parent)},
    )

    def open_browser() -> None:
        time.sleep(2.0)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        import uvicorn

        uvicorn.run(
            "api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            workers=1,
            log_level="info",
        )
    finally:
        supervisor.terminate()
        supervisor.wait(timeout=15)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
