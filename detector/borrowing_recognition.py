"""
Модуль копирования (приоритет 2 в пайплайне): TF-IDF + BM25.

Выполняется после семантического анализа глубокого заимствования (bge-m3 + reranker).
"""
from typing import List, Optional, Tuple

import numpy as np

from .front_matter import strip_academic_front_matter
from .lexical import LexicalMatcher
from .scorer import SegmentMatch, classify_risk
from .utils import split_into_segments


class BorrowingRecognizer:
    """Распознавание заимствований в тексте (TF-IDF + BM25)."""

    DEFAULT_TFIDF_WEIGHT = 0.60
    DEFAULT_BM25_WEIGHT = 0.40
    DEFAULT_THRESHOLD = 0.55
    MATCHING_MODE = "TF-IDF + BM25"

    def __init__(
        self,
        tfidf_weight: float = DEFAULT_TFIDF_WEIGHT,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
        threshold: float = DEFAULT_THRESHOLD,
        strip_front_matter: bool = True,
    ):
        self.tfidf_weight = tfidf_weight
        self.bm25_weight = bm25_weight
        self.threshold = threshold
        self.strip_front_matter = strip_front_matter
        self._lexical = LexicalMatcher(tfidf_weight, bm25_weight)
        self.last_strip_stats = None

    def _prepare_text(self, text: str) -> str:
        if not self.strip_front_matter:
            self.last_strip_stats = None
            return text
        cleaned, stats = strip_academic_front_matter(text)
        self.last_strip_stats = stats
        return cleaned

    @property
    def matching_mode(self) -> str:
        return self.MATCHING_MODE

    def _prepare_corpus(
        self,
        reference_corpus: List[str],
        reference_labels: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """Разбивает каждый источник корпуса на фрагменты."""
        corpus_segments: List[str] = []
        corpus_labels: List[str] = []

        for i, ref in enumerate(reference_corpus):
            label = (
                reference_labels[i]
                if reference_labels and i < len(reference_labels)
                else f"Источник {i + 1}"
            )
            for segment in split_into_segments(self._prepare_text(ref)):
                corpus_segments.append(segment)
                corpus_labels.append(label)

        return corpus_segments, corpus_labels

    def _combined_matrix(
        self,
        tfidf_sim: np.ndarray,
        bm25_sim: np.ndarray,
    ) -> np.ndarray:
        """Гибридная матрица: tfidf_weight·TF-IDF + bm25_weight·BM25."""
        return np.clip(
            self.tfidf_weight * tfidf_sim + self.bm25_weight * bm25_sim,
            0.0,
            1.0,
        )

    def recognize(
        self,
        text: str,
        reference_corpus: List[str],
        reference_labels: Optional[List[str]] = None,
    ) -> List[SegmentMatch]:
        """
        Находит фрагменты текста, потенциально заимствованные из корпуса.

        Returns:
            Список SegmentMatch с флагом is_borrowing и уровнем риска.
        """
        text = self._prepare_text(text)
        query_segments = split_into_segments(text)
        corpus_segments, _ = self._prepare_corpus(reference_corpus, reference_labels)

        if not query_segments:
            return []

        if not corpus_segments:
            return [
                SegmentMatch(
                    segment_index=i,
                    segment_text=seg,
                    source_index=-1,
                    source_text="",
                    tfidf_score=0.0,
                    bm25_score=0.0,
                    combined_score=0.0,
                    is_borrowing=False,
                    risk_level="none",
                )
                for i, seg in enumerate(query_segments)
            ]

        tfidf_sim, bm25_sim = self._lexical.compute_matrices(query_segments, corpus_segments)
        combined_sim = self._combined_matrix(tfidf_sim, bm25_sim)

        matches: List[SegmentMatch] = []
        for i, segment in enumerate(query_segments):
            best_j = int(np.argmax(combined_sim[i]))
            tfidf_score = float(np.clip(tfidf_sim[i][best_j], 0.0, 1.0))
            bm25_score = float(np.clip(bm25_sim[i][best_j], 0.0, 1.0))
            combined = float(combined_sim[i][best_j])
            risk = classify_risk(combined)

            matches.append(
                SegmentMatch(
                    segment_index=i,
                    segment_text=segment,
                    source_index=best_j,
                    source_text=corpus_segments[best_j],
                    tfidf_score=round(tfidf_score, 4),
                    bm25_score=round(bm25_score, 4),
                    combined_score=round(combined, 4),
                    is_borrowing=combined >= self.threshold,
                    risk_level=risk,
                )
            )

        return matches

    def compare_segments(self, text_a: str, text_b: str) -> dict:
        """Попарное сравнение двух текстов (режим STS)."""
        text_a = self._prepare_text(text_a)
        text_b = self._prepare_text(text_b)
        segments_a = split_into_segments(text_a)
        segments_b = split_into_segments(text_b)

        if not segments_a or not segments_b:
            return {
                "similarity_percent": 0.0,
                "tfidf_percent": 0.0,
                "bm25_percent": 0.0,
                "verdict": "Недостаточно текста для сравнения",
                "originality_percent": 100.0,
            }

        tfidf_sim, bm25_sim = self._lexical.compute_matrices(segments_a, segments_b)
        combined_sim = self._combined_matrix(tfidf_sim, bm25_sim)

        best_pairs = []
        best_tfidf = []
        best_bm25 = []
        for i in range(len(segments_a)):
            j = int(np.argmax(combined_sim[i]))
            best_pairs.append(float(combined_sim[i, j]))
            best_tfidf.append(float(np.clip(tfidf_sim[i, j], 0.0, 1.0)))
            best_bm25.append(float(np.clip(bm25_sim[i, j], 0.0, 1.0)))

        avg_combined = float(np.mean(best_pairs))
        avg_tfidf = float(np.mean(best_tfidf))
        avg_bm25 = float(np.mean(best_bm25))

        if avg_combined >= 0.75:
            verdict = "Высокая лексическая близость — возможное заимствование"
        elif avg_combined >= 0.55:
            verdict = "Умеренная лексическая близость — тематическое сходство"
        elif avg_combined >= 0.35:
            verdict = "Слабая связь — частичное пересечение терминов"
        else:
            verdict = "Тексты лексически не связаны"

        return {
            "similarity_percent": round(avg_combined * 100, 1),
            "tfidf_percent": round(avg_tfidf * 100, 1),
            "bm25_percent": round(avg_bm25 * 100, 1),
            "verdict": verdict,
            "originality_percent": round(max(0, 100 - avg_combined * 100), 1),
        }
