"""Прямой тест пайплайна без веб-сервера."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEXT = (
    "Искусственный интеллект меняет подход к анализу текстов. "
    "Современные системы проверяют оригинальность на нескольких уровнях."
)
CORPUS = [
    "Искусственный интеллект меняет подход к анализу текстов в образовании.",
    "Машинное обучение применяется в медицине и финансах.",
]
LABELS = ["Источник А", "Источник Б"]


def main() -> int:
    print("Загрузка моделей и анализ (первый раз — скачивание с HuggingFace)...")
    from detector.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline()

    def progress(step: str) -> None:
        print(f"  → {step}")

    result = pipeline.analyze_corpus(
        TEXT,
        CORPUS,
        LABELS,
        filename="test.txt",
        on_progress=progress,
    )
    print("\n=== РЕЗУЛЬТАТ ===")
    print(f"Оригинальность: {result.get('originality_percent')}%")
    print(f"Копирование:    {result.get('copy_percent')}%")
    print(f"Глубокое:       {result.get('deep_borrow_percent')}%")
    print(f"ИИ:             {result.get('ai_percent')}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
