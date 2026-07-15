from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from database.pool import db_connection, pgvector_available


def create_source(label: str, filename: str, content: str) -> int:
    with db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO corpus_sources (label, filename, content)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (label, filename, content),
        ).fetchone()
        conn.commit()
        return int(row["id"])


def insert_chunks(
    source_id: int,
    chunks: list[dict[str, Any]],
) -> None:
    use_pgvector = pgvector_available()
    with db_connection() as conn:
        for item in chunks:
            if use_pgvector:
                conn.execute(
                    """
                    INSERT INTO corpus_chunks
                        (source_id, chunk_index, content, embedding, rubert_embedding,
                         embedding_json, qdrant_point_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source_id,
                        item["chunk_index"],
                        item["content"],
                        item.get("embedding"),
                        item.get("rubert_embedding"),
                        json.dumps(item.get("embedding")),
                        item.get("qdrant_point_id"),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO corpus_chunks
                        (source_id, chunk_index, content, embedding_json, qdrant_point_id)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        source_id,
                        item["chunk_index"],
                        item["content"],
                        json.dumps(item.get("embedding")),
                        item.get("qdrant_point_id"),
                    ),
                )
        conn.execute(
            """
            UPDATE corpus_sources
            SET chunk_count = %s, indexed_at = now()
            WHERE id = %s
            """,
            (len(chunks), source_id),
        )
        conn.commit()


def mark_source_indexed(source_id: int, chunk_count: int) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE corpus_sources
            SET chunk_count = %s, indexed_at = now()
            WHERE id = %s
            """,
            (chunk_count, source_id),
        )
        conn.commit()


def list_sources() -> list[dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, label, filename, chunk_count, indexed_at, created_at
            FROM corpus_sources
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_source_content(source_id: int) -> Optional[str]:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT content FROM corpus_sources WHERE id = %s",
            (source_id,),
        ).fetchone()
        return row["content"] if row else None


def load_corpus_texts(source_ids: list[int]) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with db_connection() as conn:
        for sid in source_ids:
            row = conn.execute(
                "SELECT label, content FROM corpus_sources WHERE id = %s",
                (sid,),
            ).fetchone()
            if row:
                texts.append(row["content"])
                labels.append(row["label"])
    return texts, labels


def search_pgvector(
    embedding: list[float],
    limit: int = 5,
    source_ids: Optional[list[int]] = None,
) -> list[dict[str, Any]]:
    if not pgvector_available() or not embedding:
        return []

    vec_literal = "[" + ",".join(str(float(x)) for x in embedding) + "]"
    with db_connection() as conn:
        if source_ids:
            rows = conn.execute(
                """
                SELECT cc.id, cc.content, cc.source_id, cs.label,
                       1 - (cc.embedding <=> %s::vector) AS score
                FROM corpus_chunks cc
                JOIN corpus_sources cs ON cs.id = cc.source_id
                WHERE cc.embedding IS NOT NULL
                  AND cc.source_id = ANY(%s)
                ORDER BY cc.embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, source_ids, vec_literal, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT cc.id, cc.content, cc.source_id, cs.label,
                       1 - (cc.embedding <=> %s::vector) AS score
                FROM corpus_chunks cc
                JOIN corpus_sources cs ON cs.id = cc.source_id
                WHERE cc.embedding IS NOT NULL
                ORDER BY cc.embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, vec_literal, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def new_point_id() -> str:
    return str(uuid.uuid4())
