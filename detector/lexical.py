"""
Лексическое сравнение текстов: TF-IDF + BM25.

Гибридный score: 60% TF-IDF + 40% BM25 (настраивается в конструкторе).
"""
from typing import List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .utils import normalize_score, tokenize


class LexicalMatcher:
    """Матрицы лексического сходства между фрагментами запроса и корпуса."""

    def __init__(self, tfidf_weight: float = 0.60, bm25_weight: float = 0.40):
        self.tfidf_weight = tfidf_weight
        self.bm25_weight = bm25_weight
        self._tfidf_vectorizer = TfidfVectorizer(
            analyzer=tokenize,
            min_df=1,
            sublinear_tf=True,
        )

    def compute_matrices(
        self, query_segments: List[str], corpus_segments: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Строит две матрицы сходства размером (n_query × n_corpus).

        tfidf_sim[i][j] — косинусное сходство TF-IDF векторов
        bm25_sim[i][j]  — нормализованный BM25 score
        """
        all_texts = query_segments + corpus_segments
        tfidf_matrix = self._tfidf_vectorizer.fit_transform(all_texts)

        query_tfidf = tfidf_matrix[: len(query_segments)]
        corpus_tfidf = tfidf_matrix[len(query_segments) :]
        tfidf_sim = cosine_similarity(query_tfidf, corpus_tfidf)

        tokenized_corpus = [tokenize(seg) for seg in corpus_segments]
        bm25 = BM25Okapi(tokenized_corpus)

        bm25_sim = np.zeros((len(query_segments), len(corpus_segments)))
        for i, segment in enumerate(query_segments):
            scores = bm25.get_scores(tokenize(segment))
            if scores.max() > 0:
                bm25_sim[i] = scores / scores.max()

        return tfidf_sim, bm25_sim

    def hybrid_score(self, tfidf: float, bm25: float) -> float:
        """Итоговый лексический score."""
        return normalize_score(self.tfidf_weight * tfidf + self.bm25_weight * bm25)
