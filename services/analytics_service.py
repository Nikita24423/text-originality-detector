"""Модуль аналитики: проверка документа против всех работ в БД."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from database.platform import (
    ALGORITHM_ID,
    get_document,
    list_corpus_documents,
    save_analytics_result,
    save_empty_analytics_result,
    set_analytics_status,
)
from detector.pipeline import AnalysisPipeline


def _label_to_document_id(label: str, label_to_id: dict[str, int]) -> int | None:
    if not label:
        return None
    if label in label_to_id:
        return label_to_id[label]
    if label.startswith("doc_"):
        try:
            return int(label.split("_", 1)[1].split(":")[0])
        except ValueError:
            return None
    return None


def _aggregate_matches_by_target(
    pipeline_result: dict[str, Any],
    label_to_id: dict[str, int],
) -> list[dict[str, Any]]:
    """Группирует совпадения фрагментов по документам-источникам."""
    by_target: dict[int, list[dict]] = defaultdict(list)

    for m in pipeline_result.get("matches", []):
        if not m.get("is_borrowing"):
            continue
        label = m.get("source_label") or ""
        target_id = _label_to_document_id(label, label_to_id)
        if target_id is None:
            continue
        by_target[target_id].append(m)

    aggregated: list[dict[str, Any]] = []
    for tid, fragments in by_target.items():
        if not fragments:
            continue
        combined = max(f.get("combined_score", 0) for f in fragments)
        copy_scores = [f.get("tfidf_score", 0) for f in fragments]
        deep_scores = [
            f.get("semantic_score")
            if f.get("semantic_score") is not None
            else (f.get("semantic_percent", 0) / 100.0)
            for f in fragments
        ]
        aggregated.append(
            {
                "target_document_id": tid,
                "similarity_percent": round(combined * 100, 2),
                "copy_percent": round(max(copy_scores) * 100, 2) if copy_scores else 0,
                "deep_borrow_percent": round(max(deep_scores) * 100, 2) if deep_scores else 0,
                "fragments": fragments[:20],
                "algorithm": ALGORITHM_ID,
            }
        )

    aggregated.sort(key=lambda x: x["similarity_percent"], reverse=True)
    return aggregated


def analyze_document(document_id: int, pipeline: AnalysisPipeline | None = None) -> dict[str, Any]:
    """
    Проверяет одну работу против всех остальных в таблице documents.
    Результат пишется в plagiarism_matches и поля documents.*_ml.
    """
    doc = get_document(document_id)
    if not doc:
        raise ValueError(f"Документ #{document_id} не найден")

    content = (doc.get("content") or "").strip()
    if not content:
        set_analytics_status(document_id, "failed", "Пустое содержимое документа")
        raise ValueError(f"Документ #{document_id}: пустой content")

    corpus = list_corpus_documents(document_id)
    if not corpus:
        save_empty_analytics_result(document_id)
        return {
            "document_id": document_id,
            "analytics_status": "done",
            "message": "Нет других работ в БД для сравнения",
            "originality_percent": 100.0,
            "plagiarism_percent_ml": 0.0,
            "copy_percent_ml": 0.0,
            "deep_borrow_percent_ml": 0.0,
            "ai_percent_ml": 0.0,
            "borrowings_count": 0,
            "processing_time_ms": 0,
            "algorithm": ALGORITHM_ID,
        }

    set_analytics_status(document_id, "processing")
    pipe = pipeline or AnalysisPipeline(device="cpu")
    texts = [c["content"] for c in corpus]
    labels = [f"doc_{c['id']}" for c in corpus]
    label_to_id = {label: int(c["id"]) for label, c in zip(labels, corpus)}

    started = time.perf_counter()
    try:
        result = pipe.analyze_corpus(
            doc["content"],
            texts,
            labels,
            filename=doc.get("filename") or doc.get("title") or "document",
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        matches_by_target = _aggregate_matches_by_target(result, label_to_id)
        save_analytics_result(document_id, result, matches_by_target, elapsed_ms)
        return {
            "document_id": document_id,
            "analytics_status": "done",
            "originality_percent": result.get("originality_percent"),
            "plagiarism_percent_ml": result.get("plagiarism_percent"),
            "copy_percent_ml": result.get("copy_percent"),
            "deep_borrow_percent_ml": result.get("deep_borrow_percent"),
            "ai_percent_ml": result.get("ai_percent"),
            "borrowings_count": len(matches_by_target),
            "processing_time_ms": elapsed_ms,
            "algorithm": ALGORITHM_ID,
        }
    except Exception as exc:
        set_analytics_status(document_id, "failed", str(exc))
        raise
