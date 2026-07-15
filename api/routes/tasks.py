from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import TaskCreateResponse, TaskStatusResponse
from database import create_task, get_task, queue_position
from detector.file_parser import FileParseError
from services.text_helpers import (
    merge_extraction_meta,
    parse_corpus_text,
    parse_source_ids,
    read_upload_text,
    task_priority_from_meta,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse)
async def create_analysis_task(
    mode: str = Form("corpus"),
    text: str = Form(""),
    corpus: str = Form(""),
    reference_text: str = Form(""),
    corpus_source_ids: str = Form(""),
    text_file: Optional[UploadFile] = File(None),
    reference_file: Optional[UploadFile] = File(None),
    corpus_files: List[UploadFile] = File(default=[]),
):
    filename = "document"
    body_text = text.strip()
    extraction_meta = {}
    uploaded_names: List[str] = []

    try:
        if text_file and text_file.filename:
            body_text, filename, file_meta = await read_upload_text(text_file)
            extraction_meta = merge_extraction_meta(extraction_meta, file_meta)
            uploaded_names.append(text_file.filename)

        if not body_text:
            raise FileParseError("Введите текст для анализа или прикрепите файл.")

        payload: dict = {"text": body_text, "filename": filename}

        if mode == "compare":
            ref = reference_text.strip()
            ref_name = "reference"
            if reference_file and reference_file.filename:
                ref, ref_name, ref_meta = await read_upload_text(reference_file)
                extraction_meta = merge_extraction_meta(extraction_meta, ref_meta)
                uploaded_names.append(reference_file.filename)
            if not ref:
                raise FileParseError("Введите эталонный текст или прикрепите файл.")
            payload["reference_text"] = ref
            payload["reference_filename"] = ref_name
        else:
            corpus_texts: List[str] = []
            corpus_labels: List[str] = []
            source_ids = parse_source_ids(corpus_source_ids)

            valid_files = [f for f in corpus_files if f and f.filename]
            for f in valid_files:
                content, fname, file_meta = await read_upload_text(f)
                title = fname.rsplit(".", 1)[0] if "." in fname else fname
                corpus_texts.append(content)
                corpus_labels.append(title)
                extraction_meta = merge_extraction_meta(extraction_meta, file_meta)
                uploaded_names.append(fname)

            if not corpus_texts and corpus.strip():
                corpus_texts, corpus_labels = parse_corpus_text(corpus)

            if source_ids:
                payload["corpus_source_ids"] = source_ids
            elif corpus_texts:
                payload["corpus_texts"] = corpus_texts
                payload["corpus_labels"] = corpus_labels
                payload["corpus"] = corpus
            else:
                raise FileParseError("Добавьте хотя бы один источник для сравнения.")

        if extraction_meta:
            payload["extraction_meta"] = extraction_meta

        priority = task_priority_from_meta(extraction_meta, uploaded_names)
        task_id = create_task(
            mode=mode,
            payload=payload,
            filename=filename,
            priority=priority,
        )
        pos = queue_position(task_id)
        queue_hint = " (документ с таблицами/OCR — приоритет 2)" if priority == 2 else ""
        return TaskCreateResponse(
            task_id=task_id,
            status="PENDING",
            queue_position=pos,
            message=f"Задача #{task_id} в очереди (позиция {pos}){queue_hint}",
        )
    except FileParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_analysis_task(task_id: int):
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    result = row.get("result_json")
    if isinstance(result, str):
        result = json.loads(result)

    resp = TaskStatusResponse(
        task_id=task_id,
        status=row["status"],
        progress=row.get("progress"),
        error=row.get("error_message"),
        result=result,
        plagiarism_pct=row.get("plagiarism_pct"),
        copy_pct=row.get("copy_pct"),
        deep_borrow_pct=row.get("deep_borrow_pct"),
        ai_pct=row.get("ai_pct"),
    )
    if row["status"] == "PENDING":
        resp.queue_position = queue_position(task_id)
    return resp
