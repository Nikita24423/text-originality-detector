"""Вспомогательные функции для API и workers."""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Tuple

from detector.file_parser import FileParseError, extract_text_with_stats, read_uploaded_file
from detector.image_ocr import extract_with_image_priority


def parse_corpus_text(raw_corpus: str) -> Tuple[List[str], List[str]]:
    if not raw_corpus.strip():
        return [], []

    sources: List[str] = []
    labels: List[str] = []
    blocks = [b.strip() for b in raw_corpus.split("---") if b.strip()]
    for i, block in enumerate(blocks, 1):
        lines = block.split("\n", 1)
        if len(lines) == 2 and len(lines[0]) < 80:
            labels.append(lines[0].strip())
            sources.append(lines[1].strip())
        else:
            labels.append(f"Источник {i}")
            sources.append(block)
    return sources, labels


def extraction_meta_from_stats(stats) -> dict[str, Any]:
    if stats is None:
        return {}
    return {
        "paragraphs": stats.paragraphs,
        "tables": stats.tables,
        "images_ocr": stats.images_ocr,
        "pages": stats.pages,
        "ocr_available": stats.ocr_available,
    }


def merge_extraction_meta(*items: Optional[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "paragraphs": 0,
        "tables": 0,
        "images_ocr": 0,
        "pages": 0,
        "ocr_available": False,
        "formats": [],
    }
    for item in items:
        if not item:
            continue
        for key in ("paragraphs", "tables", "images_ocr", "pages"):
            merged[key] = int(merged.get(key, 0)) + int(item.get(key, 0))
        if item.get("ocr_available"):
            merged["ocr_available"] = True
        fmt = item.get("format")
        if fmt and fmt not in merged["formats"]:
            merged["formats"].append(fmt)
    return merged


def task_priority_from_meta(meta: Optional[dict[str, Any]], filenames: List[str]) -> int:
    """
  Приоритет очереди:
    1 — текстовый анализ (обрабатывается раньше)
    2 — документы с таблицами / OCR изображений
    """
    meta = meta or {}
    if int(meta.get("images_ocr", 0)) > 0:
        return 2
    if int(meta.get("tables", 0)) > 0:
        return 2
    doc_exts = {".pdf", ".docx"}
    for name in filenames:
        ext = os.path.splitext((name or "").lower())[1]
        if ext in doc_exts:
            return 2
    if any(fmt in {"pdf", "docx"} for fmt in meta.get("formats", [])):
        return 2
    return 1


async def read_upload_text(upload) -> Tuple[str, str, dict[str, Any]]:
    if not upload or not upload.filename:
        raise FileParseError("Файл не выбран.")
    content = await upload.read()
    text, meta = extract_with_image_priority(content, upload.filename)
    if not text.strip():
        raise FileParseError("Файл пуст или не содержит текста.")
    return text, upload.filename, meta


def read_bytes_with_meta(content: bytes, filename: str) -> Tuple[str, dict[str, Any]]:
    ext = os.path.splitext(filename.lower())[1]
    if ext in {".txt", ".md"}:
        for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
            try:
                text = content.decode(encoding).strip()
                return text, {"format": ext.lstrip(".")}
            except UnicodeDecodeError:
                continue
        raise FileParseError("Не удалось определить кодировку текстового файла.")

    text, stats = extract_text_with_stats(content, filename)
    meta = extraction_meta_from_stats(stats)
    meta["format"] = ext.lstrip(".")
    return text, meta


def parse_source_ids(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data]
    except json.JSONDecodeError:
        pass
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
