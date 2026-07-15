from __future__ import annotations

import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import CorpusUploadResponse
from detector.file_parser import FileParseError
from services.text_helpers import read_upload_text
from workers.indexer import index_text

router = APIRouter(prefix="/api/corpus", tags=["corpus"])


@router.post("/upload", response_model=CorpusUploadResponse)
async def upload_corpus_source(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран.")
    try:
        content, filename = await read_upload_text(file)
        label = os.path.splitext(filename)[0]
        result = index_text(label, filename, content)
        return CorpusUploadResponse(
            source_id=result["source_id"],
            chunk_count=result["chunk_count"],
            label=result["label"],
            filename=result["filename"],
            qdrant=bool(result.get("qdrant")),
        )
    except FileParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sources")
async def list_corpus_sources():
    from database import list_sources

    return {"sources": list_sources()}
