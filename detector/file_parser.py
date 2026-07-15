import os
from typing import Optional, Set, Tuple

from .document_extractor import ExtractionStats, extract_docx, extract_pdf, ocr_available

ALLOWED_EXTENSIONS: Set[str] = {".txt", ".md", ".docx", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class FileParseError(Exception):
    pass


def allowed_file(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS


def extract_text(content: bytes, filename: str) -> str:
    text, _ = extract_text_with_stats(content, filename)
    return text


def extract_text_with_stats(
    content: bytes, filename: str
) -> Tuple[str, Optional[ExtractionStats]]:
    ext = os.path.splitext(filename.lower())[1]

    if len(content) > MAX_FILE_SIZE:
        raise FileParseError(f"Файл слишком большой (максимум {MAX_FILE_SIZE // (1024 * 1024)} МБ).")

    if ext in {".txt", ".md"}:
        return _extract_plain_text(content), None

    if ext == ".docx":
        return _extract_docx_safe(content)

    if ext == ".pdf":
        return _extract_pdf_safe(content)

    raise FileParseError(f"Неподдерживаемый формат. Допустимо: {', '.join(sorted(ALLOWED_EXTENSIONS))}")


def _extract_plain_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise FileParseError("Не удалось определить кодировку текстового файла.")


def _extract_docx_safe(content: bytes) -> Tuple[str, ExtractionStats]:
    try:
        text, stats = extract_docx(content)
    except ImportError as exc:
        raise FileParseError(
            "Для файлов .docx установите зависимость: pip install python-docx"
        ) from exc
    except Exception as exc:
        raise FileParseError(f"Ошибка чтения .docx: {exc}") from exc

    if not text:
        hint = ""
        if not stats.ocr_available:
            hint = " OCR недоступен — установите rapidocr-onnxruntime и Pillow."
        raise FileParseError(
            "Документ .docx не содержит извлекаемого текста."
            + hint
        )
    return text, stats


def _extract_pdf_safe(content: bytes) -> Tuple[str, ExtractionStats]:
    try:
        text, stats = extract_pdf(content)
    except ImportError as exc:
        raise FileParseError(
            "Для файлов .pdf установите зависимость: pip install pdfplumber Pillow"
        ) from exc
    except Exception as exc:
        raise FileParseError(f"Ошибка чтения .pdf: {exc}") from exc

    if not text:
        hint = ""
        if not stats.ocr_available:
            hint = " Для сканов установите rapidocr-onnxruntime."
        raise FileParseError(
            "PDF не содержит извлекаемого текста (возможно, только изображения без OCR)."
            + hint
        )
    return text, stats


def read_uploaded_file(storage) -> tuple[str, str]:
    text, filename, _ = read_uploaded_file_with_stats(storage)
    return text, filename


def read_uploaded_file_with_stats(storage) -> tuple[str, str, Optional[ExtractionStats]]:
    if not storage or not storage.filename:
        raise FileParseError("Файл не выбран.")

    if not allowed_file(storage.filename):
        raise FileParseError(
            f"Формат «{os.path.splitext(storage.filename)[1]}» не поддерживается. "
            f"Используйте: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    content = storage.read()
    text, stats = extract_text_with_stats(content, storage.filename)
    if not text:
        raise FileParseError("Файл пуст или не содержит текста.")

    return text, storage.filename, stats
