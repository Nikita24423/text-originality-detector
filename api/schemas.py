from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from database.platform import ALGORITHM_ID


class TaskCreateResponse(BaseModel):
    task_id: int
    status: str
    queue_position: int
    message: str = "Задача принята в очередь"


class TaskStatusResponse(BaseModel):
    task_id: int
    status: str
    progress: Optional[str] = None
    queue_position: Optional[int] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    plagiarism_pct: Optional[float] = None
    copy_pct: Optional[float] = None
    deep_borrow_pct: Optional[float] = None
    ai_pct: Optional[float] = None


class CorpusUploadResponse(BaseModel):
    source_id: int
    chunk_count: int
    label: str
    filename: str
    qdrant: bool


class HealthResponse(BaseModel):
    status: str
    database: bool
    database_message: str = ""
    pgvector: bool = False
    qdrant: bool
    ml_workers_hint: int


# --- Модуль аналитики: фиксированный контракт JSON ---

class MatchedFragment(BaseModel):
    """Один совпавший фрагмент текста — всегда одинаковые поля."""

    segment_index: Optional[int] = None
    segment_text: str = ""
    source_text: str = ""
    source_label: str = ""
    combined_percent: Optional[float] = None
    copy_percent: Optional[float] = None
    deep_borrow_percent: Optional[float] = None
    is_borrowing: bool = False
    match_type: str = ""
    risk_level: str = ""
    risk_label: str = ""


class AnalyticsResultBody(BaseModel):
    """Результат анализа (поле result в POST /analyze?sync=true)."""

    document_id: int
    analytics_status: str
    originality_percent: Optional[float] = None
    plagiarism_percent_ml: Optional[float] = None
    copy_percent_ml: Optional[float] = None
    deep_borrow_percent_ml: Optional[float] = None
    ai_percent_ml: Optional[float] = None
    borrowings_count: int = 0
    processing_time_ms: Optional[int] = None
    algorithm: str = ALGORITHM_ID


class AnalyticsAnalyzeResponse(BaseModel):
    document_id: int
    status: str
    message: str
    task_id: Optional[int] = None
    result: Optional[AnalyticsResultBody] = None


class AnalyticsStatusResponse(BaseModel):
    document_id: int
    analytics_status: str
    analytics_error: Optional[str] = None
    originality_percent: Optional[float] = None
    plagiarism_percent_ml: Optional[float] = None
    copy_percent_ml: Optional[float] = None
    deep_borrow_percent_ml: Optional[float] = None
    ai_percent_ml: Optional[float] = None


class BorrowingItem(BaseModel):
    id: Optional[int] = None
    target_document_id: int
    target_title: Optional[str] = None
    target_filename: Optional[str] = None
    similarity_percent: float
    copy_percent: Optional[float] = None
    deep_borrow_percent: Optional[float] = None
    algorithm: str = ALGORITHM_ID
    matched_fragments: list[MatchedFragment] = Field(default_factory=list)


class AnalyticsBorrowingsResponse(BaseModel):
    document_id: int
    title: Optional[str] = None
    analytics_status: str = "pending"
    analytics_error: Optional[str] = None
    originality_percent: Optional[float] = None
    plagiarism_percent_ml: Optional[float] = None
    copy_percent_ml: Optional[float] = None
    deep_borrow_percent_ml: Optional[float] = None
    ai_percent_ml: Optional[float] = None
    borrowings_count: int = 0
    borrowings: list[BorrowingItem] = Field(default_factory=list)


class DocumentListItem(BaseModel):
    id: int
    title: Optional[str] = None
    filename: Optional[str] = None
    analytics_status: Optional[str] = None
    originality_percent: Optional[float] = None
    plagiarism_percent_ml: Optional[float] = None
    ai_percent_ml: Optional[float] = None
    word_count: Optional[int] = None
    content_len: Optional[int] = None
    file_format: Optional[str] = None
    upload_date: Optional[Any] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem] = Field(default_factory=list)
    count: int = 0


class DocumentCreateResponse(BaseModel):
    document_id: int
    title: str
    filename: Optional[str] = None
    word_count: int = 0
    message: str = "Документ сохранён"
