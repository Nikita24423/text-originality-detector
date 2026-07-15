"""Работа с таблицами платформы: documents, plagiarism_matches."""
from __future__ import annotations

import json
from typing import Any, Optional

from database.pool import db_connection

ALGORITHM_ID = "bge-m3+reranker+tfidf-bm25+rugpt3"


def _json_safe(value: Any) -> Any:
    """Приводит numpy-типы и прочее к JSON-сериализуемому виду."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, float):
        return round(value, 6)
    return value


def get_document(document_id: int) -> Optional[dict[str, Any]]:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, filename, content, status, analytics_status,
                   analytics_error,
                   originality_percent, plagiarism_percent_ml, ai_percent_ml,
                   copy_percent_ml, deep_borrow_percent_ml, user_id,
                   word_count, upload_date, file_format
            FROM documents WHERE id = %s
            """,
            (document_id,),
        ).fetchone()
        return dict(row) if row else None


def list_documents(limit: int = 200) -> list[dict[str, Any]]:
    """Список работ для UI (без полного content)."""
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, filename, status, analytics_status,
                   originality_percent, plagiarism_percent_ml, ai_percent_ml,
                   copy_percent_ml, deep_borrow_percent_ml,
                   word_count, upload_date, file_format,
                   length(coalesce(content, '')) AS content_len
            FROM documents
            ORDER BY upload_date DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_document(
    title: str,
    content: str,
    filename: Optional[str] = None,
    file_format: Optional[str] = None,
    user_id: str = "demo",
) -> int:
    content = (content or "").strip()
    if not content:
        raise ValueError("Пустое содержимое документа")
    word_count = len(content.split())
    with db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO documents (
                title, filename, content, word_count, user_id,
                document_type_id, faculty_id, institution_id,
                status, file_format, category, analytics_status
            ) VALUES (
                %s, %s, %s, %s, %s,
                (SELECT id FROM document_types WHERE name = 'coursework' LIMIT 1),
                'fac-demo', 'inst-demo',
                'uploaded', %s, 'lab', 'pending'
            )
            RETURNING id
            """,
            (
                title or (filename or "document"),
                filename,
                content,
                word_count,
                user_id,
                file_format,
            ),
        ).fetchone()
        conn.commit()
        return int(row["id"])


def count_documents() -> int:
    with db_connection() as conn:
        row = conn.execute("SELECT COUNT(*)::int AS c FROM documents").fetchone()
        return int(row["c"])


def list_corpus_documents(exclude_id: int) -> list[dict[str, Any]]:
    """Все работы кроме проверяемой — корпус для сравнения."""
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, filename, content
            FROM documents
            WHERE id != %s AND content IS NOT NULL AND length(trim(content)) > 0
            ORDER BY upload_date DESC
            """,
            (exclude_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_analytics_status(
    document_id: int,
    status: str,
    error: Optional[str] = None,
) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE documents
            SET analytics_status = %s, analytics_error = %s
            WHERE id = %s
            """,
            (status, error, document_id),
        )
        conn.commit()


def save_analytics_result(
    document_id: int,
    result: dict[str, Any],
    matches_by_target: list[dict[str, Any]],
    processing_time_ms: int,
) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE documents SET
                originality_percent = %s,
                plagiarism_percent_ml = %s,
                ai_percent_ml = %s,
                copy_percent_ml = %s,
                deep_borrow_percent_ml = %s,
                processing_time_ms = %s,
                analytics_status = 'done',
                analytics_error = NULL,
                analytics_updated_at = now(),
                status = 'analyzed'
            WHERE id = %s
            """,
            (
                result.get("originality_percent"),
                result.get("plagiarism_percent"),
                result.get("ai_percent"),
                result.get("copy_percent"),
                result.get("deep_borrow_percent"),
                processing_time_ms,
                document_id,
            ),
        )
        conn.execute(
            "DELETE FROM plagiarism_matches WHERE source_document_id = %s",
            (document_id,),
        )
        for m in matches_by_target:
            conn.execute(
                """
                INSERT INTO plagiarism_matches (
                    source_document_id, target_document_id,
                    similarity_percent, copy_percent, deep_borrow_percent,
                    matched_fragments, algorithm
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_document_id, target_document_id) DO UPDATE SET
                    similarity_percent = EXCLUDED.similarity_percent,
                    copy_percent = EXCLUDED.copy_percent,
                    deep_borrow_percent = EXCLUDED.deep_borrow_percent,
                    matched_fragments = EXCLUDED.matched_fragments,
                    algorithm = EXCLUDED.algorithm,
                    created_at = now()
                """,
                (
                    document_id,
                    m["target_document_id"],
                    m["similarity_percent"],
                    m.get("copy_percent"),
                    m.get("deep_borrow_percent"),
                    json.dumps(_json_safe(m.get("fragments", [])), ensure_ascii=False),
                    m.get("algorithm", ALGORITHM_ID),
                ),
            )
        conn.commit()


def save_empty_analytics_result(document_id: int) -> None:
    """Нет других работ для сравнения — 100% оригинальность, пустые matches."""
    save_analytics_result(
        document_id,
        {
            "originality_percent": 100.0,
            "plagiarism_percent": 0.0,
            "ai_percent": 0.0,
            "copy_percent": 0.0,
            "deep_borrow_percent": 0.0,
        },
        [],
        0,
    )


def get_borrowings(document_id: int) -> Optional[dict[str, Any]]:
    doc = get_document(document_id)
    if not doc:
        return None

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT pm.id, pm.target_document_id, pm.similarity_percent,
                   pm.copy_percent, pm.deep_borrow_percent,
                   pm.matched_fragments, pm.algorithm, pm.created_at,
                   d.title AS target_title, d.filename AS target_filename,
                   d.user_id AS target_user_id
            FROM plagiarism_matches pm
            JOIN documents d ON d.id = pm.target_document_id
            WHERE pm.source_document_id = %s
            ORDER BY pm.similarity_percent DESC
            """,
            (document_id,),
        ).fetchall()

    borrowings = []
    for r in rows:
        item = dict(r)
        fragments = item.pop("matched_fragments", None)
        if isinstance(fragments, str):
            try:
                item["matched_fragments"] = json.loads(fragments)
            except json.JSONDecodeError:
                item["matched_fragments"] = fragments
        borrowings.append(item)

    return {
        "document_id": document_id,
        "title": doc.get("title"),
        "analytics_status": doc.get("analytics_status"),
        "analytics_error": doc.get("analytics_error"),
        "originality_percent": doc.get("originality_percent"),
        "plagiarism_percent_ml": doc.get("plagiarism_percent_ml"),
        "copy_percent_ml": doc.get("copy_percent_ml"),
        "deep_borrow_percent_ml": doc.get("deep_borrow_percent_ml"),
        "ai_percent_ml": doc.get("ai_percent_ml"),
        "borrowings": borrowings,
        "borrowings_count": len(borrowings),
    }
