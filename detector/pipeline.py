"""
Пайплайн анализа (приоритет этапов):
  1. Глубокое заимствование — BAAI/bge-m3 + BAAI/bge-reranker-v2-m3
  2. Обычное копирование — TF-IDF + BM25 (scikit-learn, rank-bm25)
  3. Детекция ИИ — sberbank-ai/rugpt3small
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

import numpy as np

from config import Settings, get_settings
from database.corpus import search_pgvector
from detector.ai_rugpt import RuGPTAIDetector
from detector.borrowing_recognition import BorrowingRecognizer
from detector.chunking import split_text
from detector.originality_assessment import OriginalityAssessor
from detector.reranker import SemanticReranker
from detector.scorer import SegmentMatch, classify_risk, risk_label
from detector.semantic import SemanticEncoder
from detector.utils import normalize_score
from services.qdrant_store import QdrantStore


ProgressFn = Callable[[str], None]

MATCHING_MODE = (
    "Приоритет: bge-m3+reranker → TF-IDF+BM25 → rugpt3small"
)


@dataclass
class ChunkAnalysis:
    chunk_index: int
    text: str
    copy_score: float
    deep_score: float
    semantic_score: float
    rerank_score: float
    ai_score: float
    is_copy: bool
    is_deep_borrow: bool
    is_ai: bool
    match_type: str
    source_text: str
    source_label: str
    risk_level: str
    risk_label: str


class AnalysisPipeline:
    COPY_THRESHOLD = 0.75
    DEEP_SEMANTIC = 0.82
    DEEP_RERANK = 0.65
    AI_THRESHOLD = 0.55

    def __init__(self, settings: Optional[Settings] = None, device: str = "cpu"):
        self.settings = settings or get_settings()
        self.device = device
        self.encoder = SemanticEncoder(
            self.settings.embed_model,
            self.settings.rubert_model,
            device=device,
        )
        self.reranker = SemanticReranker(self.settings.reranker_model, device=device)
        self.ai_detector = RuGPTAIDetector(self.settings.ai_model, device=device)
        self.borrowing = BorrowingRecognizer(strip_front_matter=True)
        self.originality = OriginalityAssessor()
        self.qdrant = QdrantStore(
            url=self.settings.qdrant_url,
            bge_collection=self.settings.qdrant_collection,
            rubert_collection=self.settings.rubert_collection,
            enabled=self.settings.qdrant_enabled,
        )
        self.COPY_THRESHOLD = self.settings.copy_threshold
        self.DEEP_SEMANTIC = self.settings.deep_semantic_threshold
        self.DEEP_RERANK = self.settings.deep_rerank_threshold

    @staticmethod
    def _limit_chunks(chunks: List[str], max_chunks: int) -> List[str]:
        """Равномерно прореживает чанки по документу, если их слишком много."""
        limited, _ = AnalysisPipeline._limit_chunks_with_labels(chunks, None, max_chunks)
        return limited

    @staticmethod
    def _limit_chunks_with_labels(
        chunks: List[str],
        labels: Optional[List[str]],
        max_chunks: int,
    ) -> tuple[list[str], list[str]]:
        if max_chunks <= 0 or len(chunks) <= max_chunks:
            labs = list(labels) if labels else [""] * len(chunks)
            return list(chunks), labs[: len(chunks)]
        if max_chunks == 1:
            lab0 = labels[0] if labels else ""
            return [chunks[0]], [lab0]
        idxs = [
            int(round(i * (len(chunks) - 1) / (max_chunks - 1)))
            for i in range(max_chunks)
        ]
        seen: set[int] = set()
        out_c: list[str] = []
        out_l: list[str] = []
        for i in idxs:
            if i in seen:
                continue
            seen.add(i)
            out_c.append(chunks[i])
            out_l.append(labels[i] if labels and i < len(labels) else "")
        return out_c, out_l

    def _noop(self, msg: str) -> None:
        pass

    def _prepare_semantic_corpus(
        self,
        corpus_texts: List[str],
        corpus_labels: Optional[List[str]],
    ) -> tuple[list[str], list[str]]:
        chunks: list[str] = []
        labels: list[str] = []
        for i, ref in enumerate(corpus_texts):
            label = (
                corpus_labels[i]
                if corpus_labels and i < len(corpus_labels)
                else f"Источник {i + 1}"
            )
            cleaned = self.borrowing._prepare_text(ref)
            for piece in split_text(cleaned):
                chunks.append(piece)
                labels.append(label)
        return chunks, labels

    def _semantic_candidates(
        self,
        vector: list[float],
        corpus_source_ids: Optional[List[int]],
        corpus_chunks: List[str],
        corpus_labels: List[str],
        corpus_vectors: Optional[np.ndarray],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if self.qdrant.available and vector:
            candidates = self.qdrant.search_bge(vector, limit=self.settings.semantic_top_k)
        if not candidates and vector and corpus_source_ids:
            candidates = search_pgvector(
                vector,
                limit=self.settings.semantic_top_k,
                source_ids=corpus_source_ids,
            )
        if not candidates and corpus_vectors is not None and len(corpus_chunks):
            query = np.asarray(vector, dtype=np.float32)
            sims = corpus_vectors @ query
            top_k = min(self.settings.semantic_top_k, len(sims))
            if top_k > 0:
                order = np.argsort(sims)[-top_k:][::-1]
                for idx in order:
                    candidates.append(
                        {
                            "content": corpus_chunks[int(idx)],
                            "label": corpus_labels[int(idx)],
                            "score": float(sims[int(idx)]),
                        }
                    )
        return candidates

    def _is_deep_match(self, semantic_score: float, rerank_score: float) -> bool:
        normalized_rerank = normalize_score(rerank_score)
        return (
            semantic_score >= self.DEEP_SEMANTIC and normalized_rerank >= self.DEEP_RERANK
        ) or normalized_rerank >= (self.DEEP_RERANK + 0.1)

    def analyze_corpus(
        self,
        text: str,
        corpus_texts: List[str],
        corpus_labels: Optional[List[str]] = None,
        corpus_source_ids: Optional[List[int]] = None,
        filename: str = "document",
        extraction_meta: Optional[dict[str, Any]] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> dict[str, Any]:
        progress = on_progress or self._noop
        progress("chunking")

        chunks = split_text(text)
        chunks = self._limit_chunks(chunks, self.settings.max_chunks)
        if not chunks:
            return self._empty_result("Текст пуст или слишком короткий.")

        corpus_segments, segment_labels = self.borrowing._prepare_corpus(
            corpus_texts, corpus_labels
        )
        semantic_corpus, semantic_labels = self._prepare_semantic_corpus(
            corpus_texts, corpus_labels
        )
        semantic_corpus, semantic_labels = self._limit_chunks_with_labels(
            semantic_corpus, semantic_labels, self.settings.max_chunks
        )

        progress("deep_borrowing")
        batch = self.settings.encode_batch_size
        corpus_vectors: Optional[np.ndarray] = None
        if semantic_corpus and not corpus_source_ids and not self.qdrant.available:
            corpus_vectors = self.encoder.encode_bge(semantic_corpus, batch_size=batch)

        query_vectors = (
            self.encoder.encode_bge(chunks, batch_size=batch)
            if chunks
            else np.zeros((0, 1024))
        )

        use_reranker = self.settings.enable_reranker
        chunk_results: List[ChunkAnalysis] = []
        for i, chunk in enumerate(chunks):
            vector = self.encoder.to_list(query_vectors[i]) if len(query_vectors) else []
            candidates = self._semantic_candidates(
                vector,
                corpus_source_ids,
                semantic_corpus,
                semantic_labels,
                corpus_vectors,
            )

            semantic_score = float(candidates[0]["score"]) if candidates else 0.0
            # Rerank только при включённом флаге и реальном семантическом кандидате
            if use_reranker and candidates and semantic_score >= 0.55:
                cand_texts = [c["content"] for c in candidates]
                rerank_score, best_source, _ = self.reranker.rerank(chunk, cand_texts)
            elif candidates:
                rerank_score = 0.0
                best_source = candidates[0].get("content", "")
            else:
                rerank_score, best_source = 0.0, ""
            source_label = candidates[0].get("label", "") if candidates else ""
            normalized_rerank = normalize_score(rerank_score)
            if use_reranker:
                is_deep = self._is_deep_match(semantic_score, rerank_score)
            else:
                is_deep = semantic_score >= self.DEEP_SEMANTIC
            deep_score = max(semantic_score, normalized_rerank)

            if is_deep:
                risk = "high"
                match_type = "deep"
            elif semantic_score >= 0.7:
                risk = "medium"
                match_type = "none"
            else:
                risk = "none"
                match_type = "none"

            chunk_results.append(
                ChunkAnalysis(
                    chunk_index=i,
                    text=chunk,
                    copy_score=0.0,
                    deep_score=deep_score,
                    semantic_score=semantic_score,
                    rerank_score=normalized_rerank,
                    ai_score=0.0,
                    is_copy=False,
                    is_deep_borrow=is_deep,
                    is_ai=False,
                    match_type=match_type,
                    source_text=best_source if is_deep else "",
                    source_label=source_label if is_deep else "",
                    risk_level=risk,
                    risk_label=risk_label(risk),
                )
            )
            if on_progress and (i + 1) % 20 == 0:
                progress(f"deep_borrowing:{i + 1}/{len(chunks)}")

        progress("copy_detection")
        lexical_by_index: dict[int, SegmentMatch] = {}
        if corpus_segments and chunks:
            tfidf_sim, bm25_sim = self.borrowing._lexical.compute_matrices(
                chunks, corpus_segments
            )
            combined = self.borrowing._combined_matrix(tfidf_sim, bm25_sim)
            for i, chunk in enumerate(chunks):
                best_j = int(combined[i].argmax())
                combined_score = float(combined[i][best_j])
                risk = classify_risk(combined_score)
                lexical_by_index[i] = SegmentMatch(
                    segment_index=i,
                    segment_text=chunk,
                    source_index=best_j,
                    source_text=corpus_segments[best_j],
                    tfidf_score=round(float(tfidf_sim[i][best_j]), 4),
                    bm25_score=round(float(bm25_sim[i][best_j]), 4),
                    combined_score=round(combined_score, 4),
                    is_borrowing=combined_score >= self.borrowing.threshold,
                    risk_level=risk,
                )

        for cr in chunk_results:
            lex = lexical_by_index.get(cr.chunk_index)
            if not lex:
                continue
            cr.copy_score = lex.combined_score
            if cr.is_deep_borrow:
                continue
            is_copy = lex.combined_score >= self.COPY_THRESHOLD
            if is_copy:
                cr.is_copy = True
                cr.match_type = "copy"
                cr.source_text = lex.source_text
                cr.source_label = segment_labels[lex.source_index] if lex.source_index < len(segment_labels) else ""
                cr.risk_level = lex.risk_level
                cr.risk_label = risk_label(lex.risk_level)
                cr.deep_score = 0.0

        lexical_matches = list(lexical_by_index.values())

        progress("ai_detection")
        if self.settings.enable_ai:
            for cr in chunk_results:
                if len(cr.text.strip()) > 100:
                    cr.ai_score = self.ai_detector.score_chunk(cr.text)
                    cr.is_ai = cr.ai_score >= self.AI_THRESHOLD

        progress("aggregate")
        return self._build_corpus_result(
            chunk_results,
            lexical_matches,
            corpus_labels,
            len(corpus_texts),
            filename,
            extraction_meta=extraction_meta,
        )

    def analyze_compare(
        self,
        text_a: str,
        text_b: str,
        filename_a: str = "text_a",
        filename_b: str = "text_b",
        extraction_meta: Optional[dict[str, Any]] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> dict[str, Any]:
        progress = on_progress or self._noop

        progress("deep_borrowing")
        chunks_a = split_text(text_a)
        chunks_b = split_text(text_b)
        deep_flags_a = 0
        if chunks_a and chunks_b:
            vectors_a = self.encoder.encode_bge(chunks_a)
            vectors_b = self.encoder.encode_bge(chunks_b)
            for i, chunk in enumerate(chunks_a):
                sims = vectors_b @ vectors_a[i]
                top_k = min(self.settings.semantic_top_k, len(sims))
                order = np.argsort(sims)[-top_k:][::-1]
                candidates = [chunks_b[int(j)] for j in order]
                scores = [float(sims[int(j)]) for j in order]
                rerank_score, _, _ = self.reranker.rerank(chunk, candidates)
                semantic_score = scores[0] if scores else 0.0
                if self._is_deep_match(semantic_score, rerank_score):
                    deep_flags_a += 1

        deep_pct = round(deep_flags_a / len(chunks_a) * 100, 2) if chunks_a else 0.0

        progress("copy_detection")
        compare = self.borrowing.compare_segments(text_a, text_b)

        progress("ai_detection")
        if getattr(self.settings, "enable_ai", True):
            ai_a = self.ai_detector.score_document(split_text(text_a))
            ai_b = self.ai_detector.score_document(split_text(text_b))
        else:
            ai_a = ai_b = 0.0

        return {
            "mode": "compare",
            "similarity_percent": compare["similarity_percent"],
            "tfidf_percent": compare["tfidf_percent"],
            "bm25_percent": compare["bm25_percent"],
            "verdict": compare["verdict"],
            "originality_percent": compare["originality_percent"],
            "copy_percent": compare["similarity_percent"],
            "deep_borrow_percent": deep_pct,
            "plagiarism_percent": round(
                max(compare["similarity_percent"], deep_pct), 2
            ),
            "ai_percent": round((ai_a + ai_b) / 2, 2),
            "matching_mode": MATCHING_MODE,
            "ai_analysis_a": {
                "ai_probability_percent": ai_a,
                "human_probability_percent": round(100 - ai_a, 2),
                "detection_mode": "rugpt3small",
                "verdict": self._ai_verdict(ai_a),
            },
            "ai_analysis_b": {
                "ai_probability_percent": ai_b,
                "human_probability_percent": round(100 - ai_b, 2),
                "detection_mode": "rugpt3small",
                "verdict": self._ai_verdict(ai_b),
            },
            "source_files": {"text": filename_a, "reference": filename_b},
            "document_extraction": extraction_meta or {},
            "front_matter_note": self.borrowing.last_strip_stats.format_note()
            if self.borrowing.last_strip_stats
            else "",
        }

    def _build_corpus_result(
        self,
        chunks: List[ChunkAnalysis],
        lexical_matches: list,
        corpus_labels: Optional[List[str]],
        source_count: int,
        filename: str,
        extraction_meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        total = len(chunks)
        copy_count = sum(1 for c in chunks if c.is_copy)
        deep_count = sum(1 for c in chunks if c.is_deep_borrow)
        plagiarized = sum(1 for c in chunks if c.is_copy or c.is_deep_borrow)

        copy_pct = round(copy_count / total * 100, 2) if total else 0.0
        deep_pct = round(deep_count / total * 100, 2) if total else 0.0
        plagiarism_pct = round(plagiarized / total * 100, 2) if total else 0.0
        ai_scores = [c.ai_score for c in chunks if c.ai_score > 0]
        ai_pct = round(sum(ai_scores) / len(ai_scores) * 100, 2) if ai_scores else 0.0
        originality_pct = round(max(0.0, 100.0 - plagiarism_pct), 2)

        if plagiarism_pct >= 60:
            risk_level = "high"
        elif plagiarism_pct >= 35:
            risk_level = "medium"
        elif plagiarism_pct >= 15:
            risk_level = "low"
        else:
            risk_level = "none"

        matches = []
        for c in chunks:
            combined = max(c.copy_score, c.deep_score)
            matches.append(
                {
                    "segment_index": c.chunk_index,
                    "segment_text": c.text,
                    "source_text": c.source_text,
                    "source_label": c.source_label,
                    "tfidf_score": round(c.copy_score, 4),
                    "bm25_score": 0.0,
                    "combined_score": round(combined, 4),
                    "tfidf_percent": round(c.copy_score * 100, 1),
                    "bm25_percent": 0.0,
                    "combined_percent": round(combined * 100, 1),
                    "semantic_percent": round(c.semantic_score * 100, 1),
                    "semantic_score": round(c.semantic_score, 4),
                    "rerank_percent": round(c.rerank_score * 100, 1),
                    "is_borrowing": c.is_copy or c.is_deep_borrow,
                    "match_type": c.match_type,
                    "risk_level": c.risk_level,
                    "risk_label": c.risk_label,
                    "is_ai": c.is_ai,
                    "ai_percent": round(c.ai_score * 100, 1),
                }
            )

        lexical_result = self.originality.assess(lexical_matches)

        summary = (
            f"Оригинальность: {originality_pct}%. "
            f"Глубокое заимствование: {deep_pct}%. "
            f"Копирование: {copy_pct}%. "
            f"ИИ: {ai_pct}%. "
            f"Фрагментов: {total}, совпадений: {plagiarized}."
        )

        doc_note = ""
        if extraction_meta:
            parts = []
            if extraction_meta.get("tables"):
                parts.append(f"таблиц: {extraction_meta['tables']}")
            if extraction_meta.get("images_ocr"):
                parts.append(f"OCR изображений: {extraction_meta['images_ocr']}")
            if extraction_meta.get("pages"):
                parts.append(f"страниц: {extraction_meta['pages']}")
            if parts:
                doc_note = "Из документа извлечено — " + ", ".join(parts) + "."

        return {
            "mode": "corpus",
            "originality_percent": originality_pct,
            "borrowing_percent": plagiarism_pct,
            "plagiarism_percent": plagiarism_pct,
            "copy_percent": copy_pct,
            "deep_borrow_percent": deep_pct,
            "ai_percent": ai_pct,
            "risk_level": risk_level,
            "risk_label": risk_label(risk_level),
            "total_segments": total,
            "borrowed_segments": plagiarized,
            "copy_segments": copy_count,
            "deep_borrow_segments": deep_count,
            "summary": summary,
            "matching_mode": MATCHING_MODE,
            "analysis_priority": [
                "deep_borrowing",
                "copy_detection",
                "ai_detection",
            ],
            "method_weights": {
                "semantic": self.settings.embed_model,
                "reranker": self.settings.reranker_model,
                "lexical": {"tfidf": 0.6, "bm25": 0.4},
                "ai": self.settings.ai_model,
            },
            "source_count": source_count,
            "source_file": filename,
            "document_extraction": extraction_meta or {},
            "document_extraction_note": doc_note,
            "front_matter_note": self.borrowing.last_strip_stats.format_note()
            if self.borrowing.last_strip_stats
            else "",
            "matches": matches,
            "ai_analysis": {
                "ai_probability_percent": ai_pct,
                "human_probability_percent": round(100 - ai_pct, 2),
                "verdict": self._ai_verdict(ai_pct),
                "detection_mode": "rugpt3small",
                "summary": f"Вероятность генерации ИИ: {ai_pct}%.",
                "segments": [],
            },
            "lexical_originality_percent": lexical_result.originality_percent,
        }

    @staticmethod
    def _ai_verdict(ai_percent: float) -> str:
        if ai_percent >= 70:
            return "Высокая вероятность генерации ИИ"
        if ai_percent >= 50:
            return "Возможно частично сгенерирован ИИ"
        if ai_percent >= 30:
            return "Преимущественно человеческий текст"
        return "Скорее всего написан человеком"

    @staticmethod
    def _empty_result(message: str) -> dict[str, Any]:
        return {
            "mode": "corpus",
            "originality_percent": 100.0,
            "borrowing_percent": 0.0,
            "plagiarism_percent": 0.0,
            "copy_percent": 0.0,
            "deep_borrow_percent": 0.0,
            "ai_percent": 0.0,
            "risk_level": "none",
            "risk_label": risk_label("none"),
            "total_segments": 0,
            "borrowed_segments": 0,
            "summary": message,
            "matches": [],
        }
