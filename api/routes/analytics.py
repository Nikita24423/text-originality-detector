"""API модуля аналитики для основного бэкенда и UI."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import (
    AnalyticsAnalyzeResponse,
    AnalyticsBorrowingsResponse,
    AnalyticsStatusResponse,
    DocumentCreateResponse,
    DocumentListResponse,
)
from database import create_task
from database.platform import (
    count_documents,
    create_document,
    get_borrowings,
    get_document,
    list_documents,
    set_analytics_status,
)
from detector.file_parser import FileParseError
from detector.image_ocr import extract_with_image_priority
from services.analytics_response import (
    normalize_analyze_result,
    normalize_borrowings_response,
    normalize_status_response,
)
from services.analytics_service import analyze_document

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ANALYTICS_PRIORITY = 0
_RESPONSE_OPTS = {"response_model_exclude_none": False}


@router.get("/documents", response_model=DocumentListResponse, **_RESPONSE_OPTS)
async def list_analytics_documents():
    """Список работ в БД для UI."""
    docs = list_documents()
    return DocumentListResponse(documents=docs, count=len(docs))


@router.post("/documents", response_model=DocumentCreateResponse, **_RESPONSE_OPTS)
async def upload_analytics_document(
    title: str = Form(""),
    text: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """
    Сохранить работу в documents.
    Сравнение потом идёт со всеми другими работами в БД — корпус вручную не нужен.
    """
    filename = None
    file_format = None
    content = (text or "").strip()

    try:
        if file and file.filename:
            raw = await file.read()
            content, meta = extract_with_image_priority(raw, file.filename)
            filename = file.filename
            file_format = filename.rsplit(".", 1)[-1].lower() if "." in filename else None
            if not title.strip():
                title = filename.rsplit(".", 1)[0]
            _ = meta
        if not content:
            raise FileParseError("Введите текст или прикрепите файл.")
        if not title.strip():
            title = filename or "Документ без названия"

        doc_id = create_document(
            title=title.strip(),
            content=content,
            filename=filename,
            file_format=file_format,
        )
        return DocumentCreateResponse(
            document_id=doc_id,
            title=title.strip(),
            filename=filename,
            word_count=len(content.split()),
            message=f"Документ #{doc_id} сохранён. В БД работ: {count_documents()}",
        )
    except FileParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/documents/{document_id}/analyze",
    response_model=AnalyticsAnalyzeResponse,
    **_RESPONSE_OPTS,
)
async def trigger_document_analysis(document_id: int, sync: bool = False):
    """
    Запуск анализа заимствований для работы document_id.

    - sync=false (по умолчанию): задача в очередь ML-воркеров
    - sync=true: ждать завершения в этом запросе (только для тестов)
    """
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Документ #{document_id} не найден")

    current_status = doc.get("analytics_status") or "pending"
    if not sync and current_status in ("queued", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Анализ документа #{document_id} уже выполняется ({current_status})",
        )

    if not (doc.get("content") or "").strip():
        raise HTTPException(
            status_code=400,
            detail=f"Документ #{document_id}: пустой content",
        )

    if sync:
        try:
            raw = analyze_document(document_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return AnalyticsAnalyzeResponse(
            document_id=document_id,
            status="done",
            message="Анализ завершён",
            task_id=None,
            result=normalize_analyze_result(raw),
        )

    task_id = create_task(
        mode="analytics",
        payload={"document_id": document_id},
        filename=doc.get("filename") or doc.get("title"),
        priority=ANALYTICS_PRIORITY,
    )
    set_analytics_status(document_id, "queued")
    return AnalyticsAnalyzeResponse(
        document_id=document_id,
        status="queued",
        message=f"Анализ поставлен в очередь (task #{task_id})",
        task_id=task_id,
        result=None,
    )


@router.get(
    "/documents/{document_id}/status",
    response_model=AnalyticsStatusResponse,
    **_RESPONSE_OPTS,
)
async def get_document_analytics_status(document_id: int):
    """Статус анализа работы (для опроса после POST /analyze)."""
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Документ #{document_id} не найден")
    return AnalyticsStatusResponse(**normalize_status_response(doc, document_id))


@router.get(
    "/documents/{document_id}/borrowings",
    response_model=AnalyticsBorrowingsResponse,
    **_RESPONSE_OPTS,
)
async def get_document_borrowings(document_id: int):
    """
    Все заимствования для работы — то, что просит основной бэкенд.

    Читает plagiarism_matches + сводные проценты из documents.
    """
    data = get_borrowings(document_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Документ #{document_id} не найден")
    return AnalyticsBorrowingsResponse(**normalize_borrowings_response(data))
