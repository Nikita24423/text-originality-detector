"""Разбиение текста на чанки для семантического анализа."""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )


def split_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = get_text_splitter().split_text(text)
    return [c.strip() for c in chunks if c.strip()]
