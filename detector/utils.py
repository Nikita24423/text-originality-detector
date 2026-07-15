"""
Вспомогательные функции: сегментация текста, токенизация, нормализация score.
"""
import re
from typing import List


def split_into_segments(text: str, min_length: int = 20) -> List[str]:
    """
    Разбивает текст на фрагменты для попарного сравнения.

    Сначала пробует разбить по абзацам (пустая строка между блоками).
    Если абзац один — разбивает по предложениям (. ! ? …).
    Фрагменты короче min_length символов отбрасываются.
    """
    text = text.strip()
    if not text:
        return []

    # Абзацы — предпочтительная единица сравнения
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) > 1:
        return [p for p in paragraphs if len(p) >= min_length]

    # Иначе — предложения
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    segments = [s.strip() for s in sentences if len(s.strip()) >= min_length]
    return segments if segments else [text]


def tokenize(text: str) -> List[str]:
    """Разбивает текст на слова (для TF-IDF и BM25)."""
    return re.findall(r"\b\w+\b", text.lower(), flags=re.UNICODE)


def normalize_score(value: float) -> float:
    """Ограничивает значение сходства диапазоном [0, 1]."""
    return max(0.0, min(1.0, float(value)))
