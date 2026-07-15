from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from detector.file_parser import FileParseError

router = APIRouter(prefix="/api", tags=["files"])


@router.post("/read-file")
async def read_file(file: UploadFile = File(...)):
    try:
        from services.text_helpers import read_upload_text

        text, filename, meta = await read_upload_text(file)
        return {
            "text": text,
            "filename": filename,
            "extraction": meta,
        }
    except FileParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
