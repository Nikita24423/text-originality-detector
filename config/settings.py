"""Настройки приложения из переменных окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _env_bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str
    rubert_collection: str
    api_host: str
    api_port: int
    api_workers: int
    ml_workers: int
    embed_model: str
    reranker_model: str
    ai_model: str
    rubert_model: str
    copy_threshold: float
    deep_semantic_threshold: float
    deep_rerank_threshold: float
    chunk_size: int
    chunk_overlap: int
    semantic_top_k: int
    max_file_size: int
    qdrant_enabled: bool
    fast_mode: bool
    enable_ai: bool
    enable_reranker: bool
    max_chunks: int
    encode_batch_size: int

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    fast = _env_bool("FAST_MODE", "1")
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/originality",
        ),
        qdrant_host=os.environ.get("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.environ.get("QDRANT_PORT", "6333")),
        qdrant_collection=os.environ.get("QDRANT_COLLECTION", "corpus_bge_m3"),
        rubert_collection=os.environ.get("RUBERT_COLLECTION", "corpus_rubert"),
        api_host=os.environ.get("API_HOST", "127.0.0.1"),
        api_port=int(os.environ.get("API_PORT", "8001")),
        api_workers=int(os.environ.get("API_WORKERS", "4")),
        ml_workers=int(os.environ.get("ML_WORKERS", "1" if fast else "2")),
        embed_model=os.environ.get("EMBED_MODEL", "BAAI/bge-m3"),
        reranker_model=os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        ai_model=os.environ.get("AI_MODEL", "sberbank-ai/rugpt3small_based_on_gpt2"),
        rubert_model=os.environ.get("RUBERT_MODEL", "cointegrated/rubert-tiny2"),
        copy_threshold=float(os.environ.get("COPY_THRESHOLD", "0.75")),
        deep_semantic_threshold=float(os.environ.get("DEEP_SEMANTIC_THRESHOLD", "0.82")),
        deep_rerank_threshold=float(os.environ.get("DEEP_RERANK_THRESHOLD", "0.65")),
        chunk_size=int(os.environ.get("CHUNK_SIZE", "1000" if fast else "500")),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", "50")),
        semantic_top_k=int(os.environ.get("SEMANTIC_TOP_K", "2" if fast else "5")),
        max_file_size=int(os.environ.get("MAX_FILE_SIZE", str(12 * 1024 * 1024))),
        qdrant_enabled=_env_bool("QDRANT_ENABLED", "0"),
        fast_mode=fast,
        enable_ai=_env_bool("ENABLE_AI", "0" if fast else "1"),
        enable_reranker=_env_bool("ENABLE_RERANKER", "0" if fast else "1"),
        max_chunks=int(os.environ.get("MAX_CHUNKS", "60" if fast else "200")),
        encode_batch_size=int(os.environ.get("ENCODE_BATCH_SIZE", "16" if fast else "8")),
    )
