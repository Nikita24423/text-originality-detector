"""Переранжирование кандидатов BAAI/bge-reranker-v2-m3."""
from __future__ import annotations

from typing import List, Optional, Tuple

from sentence_transformers import CrossEncoder


class SemanticReranker:
    def __init__(self, model_name: str, device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model: Optional[CrossEncoder] = None

    def _ensure_loaded(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self._model_name, device=self._device)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[str],
    ) -> Tuple[float, str, int]:
        if not candidates or not query.strip():
            return 0.0, "", -1

        model = self._ensure_loaded()
        pairs = [[query, cand] for cand in candidates]
        scores = model.predict(pairs)
        best_idx = int(max(range(len(scores)), key=lambda i: float(scores[i])))
        return float(scores[best_idx]), candidates[best_idx], best_idx

    def rerank_batch(
        self,
        queries: List[str],
        candidates_per_query: List[List[str]],
    ) -> List[Tuple[float, str, int]]:
        results = []
        for query, cands in zip(queries, candidates_per_query):
            results.append(self.rerank(query, cands))
        return results
