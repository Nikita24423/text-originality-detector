"""Индексация корпуса в PostgreSQL + Qdrant."""
from __future__ import annotations

from typing import List, Optional

from qdrant_client.models import PointStruct

from config import get_settings
from database.corpus import create_source, insert_chunks, new_point_id
from detector.chunking import split_text
from detector.semantic import SemanticEncoder
from services.qdrant_store import QdrantStore
import uuid


class CorpusIndexer:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.encoder = SemanticEncoder(
            settings.embed_model,
            settings.rubert_model,
            device="cpu",
        )
        self.qdrant = QdrantStore(
            url=settings.qdrant_url,
            bge_collection=settings.qdrant_collection,
            rubert_collection=settings.rubert_collection,
            enabled=settings.qdrant_enabled,
        )

    def index_source(
        self,
        label: str,
        filename: str,
        content: str,
    ) -> dict:
        source_id = create_source(label, filename, content)
        chunks = split_text(content)
        if not chunks:
            return {"source_id": source_id, "chunk_count": 0}

        bge_vectors = self.encoder.encode_bge(chunks)
        rubert_vectors = self.encoder.encode_rubert(chunks)

        db_chunks: List[dict] = []
        bge_points: List[PointStruct] = []
        rubert_points: List[PointStruct] = []

        for i, chunk in enumerate(chunks):
            point_id = new_point_id()
            bge_vec = self.encoder.to_list(bge_vectors[i])
            rubert_vec = self.encoder.to_list(rubert_vectors[i])
            db_chunks.append(
                {
                    "chunk_index": i,
                    "content": chunk,
                    "embedding": bge_vec,
                    "rubert_embedding": rubert_vec,
                    "qdrant_point_id": point_id,
                }
            )
            bge_points.append(
                PointStruct(
                    id=point_id,
                    vector=bge_vec,
                    payload={
                        "text": chunk,
                        "label": label,
                        "source_id": source_id,
                        "filename": filename,
                    },
                )
            )
            rubert_points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=rubert_vec,
                    payload={
                        "text": chunk,
                        "label": label,
                        "source_id": source_id,
                    },
                )
            )

        insert_chunks(source_id, db_chunks)
        self.qdrant.upsert_bge_points(bge_points)
        self.qdrant.upsert_rubert_points(rubert_points)

        return {
            "source_id": source_id,
            "chunk_count": len(chunks),
            "label": label,
            "filename": filename,
            "qdrant": self.qdrant.available,
        }


def index_text(label: str, filename: str, content: str) -> dict:
    return CorpusIndexer().index_source(label, filename, content)
