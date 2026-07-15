"""Детекция ИИ через sberbank-ai/rugpt3small (perplexity / rank-based)."""
from __future__ import annotations

import math
import zlib
from typing import List, Optional

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class RuGPTAIDetector:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.device = device
        self._model_name = model_name
        self._tokenizer: Optional[AutoTokenizer] = None
        self._model: Optional[AutoModelForCausalLM] = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModelForCausalLM.from_pretrained(self._model_name).to(self.device)
        self._model.eval()

    def score_chunk(self, text: str) -> float:
        text = (text or "").strip()
        if len(text) < 50:
            return 0.0

        self._ensure_loaded()
        assert self._tokenizer is not None and self._model is not None

        token_ids = self._tokenizer.encode(
            text, return_tensors="pt", max_length=1024, truncation=True
        ).to(self.device)
        if token_ids.shape[1] < 2:
            return 0.0

        with torch.no_grad():
            logits = self._model(token_ids).logits[0, :-1, :]
            actual_next = token_ids[0, 1:].unsqueeze(-1)
            sorted_indices = torch.argsort(logits, dim=-1, descending=True)
            ranks = (
                (sorted_indices == actual_next).nonzero(as_tuple=True)[1].cpu().numpy() + 1
            )

        total_words = len(ranks)
        if total_words == 0:
            return 0.0

        p_ratio = np.sum(ranks <= 50) / total_words
        p_score = 1.0 / (1.0 + math.exp(-20.0 * (p_ratio - 0.85)))
        m_ratio = np.sum(ranks > 1000) / total_words
        m_score = 1.0 / (1.0 + math.exp(300.0 * (m_ratio - 0.01)))
        text_bytes = text.encode("utf-8")
        if not text_bytes:
            return 0.0
        c_ratio = len(zlib.compress(text_bytes)) / len(text_bytes)
        c_score = (
            1.0 / (1.0 + math.exp(15.0 * (c_ratio - 0.45))) * min(1.0, len(text_bytes) / 1000.0)
        )
        raw = math.sqrt(0.60 * p_score + 0.30 * m_score + 0.10 * c_score * 100) / 100
        return max(0.0, min(1.0, raw))

    def score_document(self, chunks: List[str]) -> float:
        scores = [self.score_chunk(c) for c in chunks if len(c.strip()) > 100]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores) * 100, 2)
