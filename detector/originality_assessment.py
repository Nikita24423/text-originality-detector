"""
Модуль 2: Оценка оригинальности текста.

Получает список SegmentMatch от BorrowingRecognizer
и вычисляет итоговый процент оригинальности (0–100%).
"""
from typing import List

from .scorer import AnalysisResult, SegmentMatch, compute_originality


class OriginalityAssessor:
    """Оценка оригинальности на основе найденных заимствований."""

    def __init__(
        self,
        tfidf_weight: float = 0.60,
        bm25_weight: float = 0.40,
        threshold: float = 0.55,
        matching_mode: str = "TF-IDF + BM25",
    ):
        self.tfidf_weight = tfidf_weight
        self.bm25_weight = bm25_weight
        self.threshold = threshold
        self.matching_mode = matching_mode

    def assess(self, matches: List[SegmentMatch]) -> AnalysisResult:
        """
        Вычисляет оригинальность текста по списку сопоставлений фрагментов.

        Args:
            matches: результат BorrowingRecognizer.recognize()

        Returns:
            AnalysisResult с originality_percent, borrowing_percent, risk_level.
        """
        return compute_originality(
            matches,
            self.tfidf_weight,
            self.bm25_weight,
            self.threshold,
            self.matching_mode,
        )
