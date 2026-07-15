"""Нормализация ответов API аналитики — всегда один и тот же набор полей."""
from __future__ import annotations

from typing import Any, Optional

from database.platform import ALGORITHM_ID

ANALYTICS_STATUSES = ("pending", "queued", "processing", "done", "failed")


def _round_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def normalize_fragment(raw: dict[str, Any]) -> dict[str, Any]:
    """Фиксированная структура элемента matched_fragments."""
    combined = raw.get("combined_percent")
    if combined is None and raw.get("combined_score") is not None:
        combined = float(raw["combined_score"]) * 100
    copy_p = raw.get("tfidf_percent")
    if copy_p is None and raw.get("tfidf_score") is not None:
        copy_p = float(raw["tfidf_score"]) * 100
    deep_p = raw.get("semantic_percent")
    if deep_p is None and raw.get("semantic_score") is not None:
        deep_p = float(raw["semantic_score"]) * 100

    return {
        "segment_index": raw.get("segment_index"),
        "segment_text": raw.get("segment_text") or "",
        "source_text": raw.get("source_text") or "",
        "source_label": raw.get("source_label") or "",
        "combined_percent": _round_percent(combined),
        "copy_percent": _round_percent(copy_p),
        "deep_borrow_percent": _round_percent(deep_p),
        "is_borrowing": bool(raw.get("is_borrowing", False)),
        "match_type": raw.get("match_type") or "",
        "risk_level": raw.get("risk_level") or "",
        "risk_label": raw.get("risk_label") or "",
    }


def normalize_borrowing_item(raw: dict[str, Any]) -> dict[str, Any]:
    fragments = raw.get("matched_fragments") or []
    if not isinstance(fragments, list):
        fragments = []

    return {
        "id": raw.get("id"),
        "target_document_id": int(raw["target_document_id"]),
        "target_title": raw.get("target_title"),
        "target_filename": raw.get("target_filename"),
        "similarity_percent": _round_percent(raw.get("similarity_percent")) or 0.0,
        "copy_percent": _round_percent(raw.get("copy_percent")),
        "deep_borrow_percent": _round_percent(raw.get("deep_borrow_percent")),
        "algorithm": raw.get("algorithm") or ALGORITHM_ID,
        "matched_fragments": [normalize_fragment(f) for f in fragments if isinstance(f, dict)],
    }


def normalize_analyze_result(raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    return {
        "document_id": raw.get("document_id"),
        "analytics_status": raw.get("analytics_status") or "done",
        "originality_percent": _round_percent(raw.get("originality_percent")),
        "plagiarism_percent_ml": _round_percent(
            raw.get("plagiarism_percent_ml", raw.get("plagiarism_percent"))
        ),
        "copy_percent_ml": _round_percent(raw.get("copy_percent_ml", raw.get("copy_percent"))),
        "deep_borrow_percent_ml": _round_percent(
            raw.get("deep_borrow_percent_ml", raw.get("deep_borrow_percent"))
        ),
        "ai_percent_ml": _round_percent(raw.get("ai_percent_ml", raw.get("ai_percent"))),
        "borrowings_count": int(raw.get("borrowings_count") or 0),
        "processing_time_ms": raw.get("processing_time_ms"),
        "algorithm": raw.get("algorithm") or ALGORITHM_ID,
    }


def normalize_borrowings_response(data: dict[str, Any]) -> dict[str, Any]:
    borrowings = [
        normalize_borrowing_item(b)
        for b in (data.get("borrowings") or [])
        if isinstance(b, dict)
    ]
    return {
        "document_id": data["document_id"],
        "title": data.get("title"),
        "analytics_status": data.get("analytics_status") or "pending",
        "analytics_error": data.get("analytics_error"),
        "originality_percent": _round_percent(data.get("originality_percent")),
        "plagiarism_percent_ml": _round_percent(data.get("plagiarism_percent_ml")),
        "copy_percent_ml": _round_percent(data.get("copy_percent_ml")),
        "deep_borrow_percent_ml": _round_percent(data.get("deep_borrow_percent_ml")),
        "ai_percent_ml": _round_percent(data.get("ai_percent_ml")),
        "borrowings_count": len(borrowings),
        "borrowings": borrowings,
    }


def normalize_status_response(doc: dict[str, Any], document_id: int) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "analytics_status": doc.get("analytics_status") or "pending",
        "analytics_error": doc.get("analytics_error"),
        "originality_percent": _round_percent(doc.get("originality_percent")),
        "plagiarism_percent_ml": _round_percent(doc.get("plagiarism_percent_ml")),
        "copy_percent_ml": _round_percent(doc.get("copy_percent_ml")),
        "deep_borrow_percent_ml": _round_percent(doc.get("deep_borrow_percent_ml")),
        "ai_percent_ml": _round_percent(doc.get("ai_percent_ml")),
    }
