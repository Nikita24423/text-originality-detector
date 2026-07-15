"""OCR изображений из документов (приоритет 2)."""
from __future__ import annotations

import io
from typing import Optional

from detector.document_extractor import ExtractionStats, extract_docx, extract_pdf
from detector.file_parser import extract_text_with_stats


def extract_text_from_bytes(content: bytes, filename: str) -> tuple[str, Optional[dict]]:
    text, stats = extract_text_with_stats(content, filename)
    meta = None
    if stats is not None:
        meta = {
            "ocr_available": stats.ocr_available,
            "images_ocr": stats.images_ocr,
            "pages": stats.pages,
        }
    return text, meta


def extract_with_image_priority(content: bytes, filename: str) -> tuple[str, dict]:
    """Извлечение текста из документов: абзацы, таблицы, OCR изображений."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    meta: dict = {"format": ext}

    if ext == "docx":
        text, stats = extract_docx(content)
        meta.update(
            {
                "paragraphs": stats.paragraphs,
                "tables": stats.tables,
                "images_ocr": stats.images_ocr,
                "pages": 0,
                "ocr_available": stats.ocr_available,
            }
        )
        return text, meta
    if ext == "pdf":
        text, stats = extract_pdf(content)
        meta.update(
            {
                "paragraphs": stats.paragraphs,
                "tables": stats.tables,
                "images_ocr": stats.images_ocr,
                "pages": stats.pages,
                "ocr_available": stats.ocr_available,
            }
        )
        return text, meta

    text, stats = extract_text_with_stats(content, filename)
    if stats:
        meta.update(
            {
                "paragraphs": stats.paragraphs,
                "tables": stats.tables,
                "images_ocr": stats.images_ocr,
                "pages": stats.pages,
                "ocr_available": stats.ocr_available,
            }
        )
    return text, meta
