"""Семантические эмбеддинги BAAI/bge-m3 и быстрый rubert-tiny2."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticEncoder:
    def __init__(
        self,
        bge_model: str,
        rubert_model: str,
        device: str = "cpu",
    ):
        self.device = device
        self._bge: Optional[SentenceTransformer] = None
        self._rubert: Optional[SentenceTransformer] = None
        self._bge_name = bge_model
        self._rubert_name = rubert_model

    def _ensure_bge(self) -> SentenceTransformer:
        if self._bge is None:
            self._bge = SentenceTransformer(self._bge_name, device=self.device)
        return self._bge

    def _ensure_rubert(self) -> SentenceTransformer:
        if self._rubert is None:
            self._rubert = SentenceTransformer(self._rubert_name, device=self.device)
        return self._rubert

    def encode_bge(self, texts: List[str], batch_size: int = 8) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1024), dtype=np.float32)
        model = self._ensure_bge()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_rubert(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        if not texts:
            return np.zeros((0, 312), dtype=np.float32)
        model = self._ensure_rubert()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.asarray(vectors, dtype=np.float32)

    @staticmethod
    def to_list(vector: np.ndarray) -> list[float]:
        return [float(x) for x in vector.tolist()]
