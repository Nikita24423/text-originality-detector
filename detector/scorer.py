"""
Структуры данных и формулы оценки оригинальности.

SegmentMatch  — результат сравнения одного фрагмента с корпусом
AnalysisResult — итоговая оценка всего текста
"""
from dataclasses import dataclass
from typing import Any, List, Optional

from .utils import normalize_score


@dataclass
class SegmentMatch:
    """Сопоставление одного фрагмента проверяемого текста с источником."""

    segment_index: int
    segment_text: str
    source_index: int
    source_text: str
    tfidf_score: float
    bm25_score: float
    combined_score: float
    is_borrowing: bool
    risk_level: str


@dataclass
class AnalysisResult:
    """Итог анализа оригинальности всего текста."""

    originality_percent: float
    borrowing_percent: float
    risk_level: str
    total_segments: int
    borrowed_segments: int
    matches: List[SegmentMatch]
    summary: str
    method_weights: dict
    matching_mode: str = "TF-IDF + BM25"
    ai_analysis: Optional[Any] = None


def classify_risk(score: float) -> str:
    """Уровень риска для одного фрагмента по combined_score."""
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    if score >= 0.35:
        return "low"
    return "none"


def risk_label(level: str) -> str:
    """Человекочитаемая подпись уровня риска."""
    labels = {
        "high": "Высокий риск заимствования",
        "medium": "Средний риск заимствования",
        "low": "Низкий риск заимствования",
        "none": "Оригинальный фрагмент",
    }
    return labels.get(level, "Не определено")


def compute_originality(
    matches: List[SegmentMatch],
    tfidf_weight: float = 0.60,
    bm25_weight: float = 0.40,
    threshold: float = 0.55,
    matching_mode: str = "TF-IDF + BM25",
) -> AnalysisResult:
    """
    Модуль 2: агрегирует фрагменты в итоговую оценку.

    Формула:
      borrowing_ratio    = число заимствований / всего фрагментов
      weighted_borrowing = сумма combined_score заимствованных / всего
      borrowing%         = 50% · ratio + 50% · weighted
      originality%       = 100 − borrowing%
    """
    if not matches:
        return AnalysisResult(
            originality_percent=100.0,
            borrowing_percent=0.0,
            risk_level="none",
            total_segments=0,
            borrowed_segments=0,
            matches=[],
            summary="Текст пуст или слишком короткий для анализа.",
            method_weights={
                "tfidf": tfidf_weight,
                "bm25": bm25_weight,
                "threshold": threshold,
            },
            matching_mode=matching_mode,
        )

    borrowed = [m for m in matches if m.is_borrowing]

    borrowing_ratio = len(borrowed) / len(matches)
    weighted_borrowing = sum(m.combined_score for m in borrowed) / len(matches)

    borrowing_percent = normalize_score(
        0.5 * borrowing_ratio + 0.5 * weighted_borrowing
    ) * 100
    originality_percent = max(0.0, 100.0 - borrowing_percent)

    if borrowing_percent >= 60:
        overall_risk = "high"
    elif borrowing_percent >= 35:
        overall_risk = "medium"
    elif borrowing_percent >= 15:
        overall_risk = "low"
    else:
        overall_risk = "none"

    summary = _build_summary(
        originality_percent, borrowed, len(matches), overall_risk
    )

    return AnalysisResult(
        originality_percent=round(originality_percent, 1),
        borrowing_percent=round(borrowing_percent, 1),
        risk_level=overall_risk,
        total_segments=len(matches),
        borrowed_segments=len(borrowed),
        matches=matches,
        summary=summary,
        method_weights={
            "tfidf": tfidf_weight,
            "bm25": bm25_weight,
            "threshold": threshold,
        },
        matching_mode=matching_mode,
    )


def _build_summary(
    originality: float,
    borrowed: List[SegmentMatch],
    total: int,
    risk: str,
) -> str:
    """Формирует текстовое резюме для веб-интерфейса."""
    if total == 0:
        return "Нет данных для анализа."

    parts = [
        f"Оригинальность текста: {originality:.1f}%.",
        f"Проанализировано фрагментов: {total}.",
        f"Обнаружено потенциальных заимствований: {len(borrowed)}.",
    ]

    if borrowed:
        top = max(borrowed, key=lambda m: m.combined_score)
        parts.append(
            f"Наиболее похожий фрагмент (совпадение {top.combined_score * 100:.0f}%): "
            f"«{top.segment_text[:80]}…»"
        )

    parts.append(f"Общая оценка: {risk_label(risk)}.")
    return " ".join(parts)
