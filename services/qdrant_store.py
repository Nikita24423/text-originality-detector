"""Интеграция с Qdrant для быстрого ANN-поиска."""
from __future__ import annotations

import socket
from typing import Any, List, Optional
from urllib.parse import urlparse


def _host_port_reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6333
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class QdrantStore:
    BGE_DIM = 1024
    RUBERT_DIM = 312

    def __init__(
        self,
        url: str,
        bge_collection: str,
        rubert_collection: str,
        enabled: bool = True,
    ):
        self.url = url
        self.bge_collection = bge_collection
        self.rubert_collection = rubert_collection
        self._client = None
        self._available = False

        if not enabled:
            return
        if not _host_port_reachable(url):
            return

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            client = QdrantClient(url=url, prefer_grpc=False, timeout=5.0)
            client.get_collections()
            self._ensure_collections(client, Distance, VectorParams)
            self._client = client
            self._available = True
        except Exception:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._client is not None

    def _ensure_collections(self, client, Distance, VectorParams) -> None:
        existing = {c.name for c in client.get_collections().collections}
        if self.bge_collection not in existing:
            client.create_collection(
                collection_name=self.bge_collection,
                vectors_config=VectorParams(size=self.BGE_DIM, distance=Distance.COSINE),
            )
        if self.rubert_collection not in existing:
            client.create_collection(
                collection_name=self.rubert_collection,
                vectors_config=VectorParams(size=self.RUBERT_DIM, distance=Distance.COSINE),
            )

    def upsert_bge_points(self, points: list) -> None:
        if not self.available or not points:
            return
        self._client.upsert(collection_name=self.bge_collection, points=points)

    def upsert_rubert_points(self, points: list) -> None:
        if not self.available or not points:
            return
        self._client.upsert(collection_name=self.rubert_collection, points=points)

    def search_bge(
        self,
        vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.75,
    ) -> List[dict[str, Any]]:
        if not self.available or not vector:
            return []
        try:
            hits = self._client.search(
                collection_name=self.bge_collection,
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold,
            )
            return [
                {
                    "content": hit.payload.get("text", "") if hit.payload else "",
                    "label": hit.payload.get("label", "") if hit.payload else "",
                    "source_id": hit.payload.get("source_id") if hit.payload else None,
                    "score": float(hit.score),
                }
                for hit in hits
            ]
        except Exception:
            return []

    def search_rubert_batch(
        self,
        vectors: List[List[float]],
        limit: int = 1,
        score_threshold: float = 0.92,
    ) -> List[bool]:
        if not self.available:
            return [False] * len(vectors)
        results = []
        for vec in vectors:
            try:
                hits = self._client.search(
                    collection_name=self.rubert_collection,
                    query_vector=vec,
                    limit=limit,
                    score_threshold=score_threshold,
                )
                results.append(len(hits) > 0)
            except Exception:
                results.append(False)
        return results
