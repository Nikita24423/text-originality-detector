"""
Перед сравнением текстов убираем служебные части курсовой:
титул, реферат, содержание, задание, перечень сокращений.

Сравнение начинается с «Введение» или с главы «1 …».
"""
import re
from dataclasses import dataclass


# Минимальная длина текста после обрезки — иначе считаем, что угадали неверно
MIN_BODY_CHARS = 200

PAGE_MARKER_RE = re.compile(r"^---\s*Страница\s+\d+\s*---\s*$", re.IGNORECASE)
TABLE_MARKER_RE = re.compile(r"^\[Таблица\s+\d+\]", re.IGNORECASE)
SECTION_HEADER_RE = re.compile(
    r"^(?:"
    r"реферат|аннотация|содержание|оглавление|задание|введение|"
    r"перечень условных|перечень сокращений|"
    r"1(?:\s+|\.\s+)\S"
    r")",
    re.IGNORECASE,
)

# Заголовки разделов, которые не участвуют в сравнении
SERVICE_HEADERS = (
    "реферат",
    "аннотация",
    "содержание",
    "оглавление",
    "задание",
    "задание на курсовой проект",
    "задание на курсовую работу",
    "задание на дипломный проект",
    "перечень условных обозначений",
    "перечень сокращений",
    "перечень условных обозначений, символов и терминов",
)

# Фразы, по которым узнаём титульный лист
TITLE_PHRASES = (
    "министерство образования",
    "к защите допустить",
    "пояснительная записка",
    "к курсовому проекту",
    "к курсовой работе",
    "выполнил студент",
    "бгуир кп",
    "учреждение образования",
    "факультет ",
    "кафедра ",
)


@dataclass
class FrontMatterStats:
    removed_chars: int = 0
    body_start_marker: str = ""

    @property
    def was_stripped(self):
        return self.removed_chars > 0

    def format_note(self):
        if not self.was_stripped:
            return ""
        return f"удалено {self.removed_chars} симв., начало с «{self.body_start_marker}»"


def is_noise_line(line: str) -> bool:
    """Служебные строки PDF/docx, не участвующие в сравнении."""
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_MARKER_RE.match(stripped):
        return True
    if TABLE_MARKER_RE.match(stripped):
        return True
    return False


def meaningful_lines(paragraph: str) -> list[str]:
    """Строки абзаца без маркеров страниц и таблиц."""
    return [
        line.strip()
        for line in paragraph.split("\n")
        if line.strip() and not is_noise_line(line)
    ]


def normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def is_toc_line(line: str) -> bool:
    """Строка оглавления: «Введение 5» или «1 Анализ … 6»."""
    line = line.strip()
    if not line:
        return False
    if is_noise_line(line):
        return False
    if re.search(r"\t\d+\s*$", line):
        return True
    parts = line.rsplit(None, 1)
    return len(parts) == 2 and parts[1].isdigit() and len(parts[0]) > 2


def is_service_header(text: str) -> bool:
    norm = normalize(text)
    return any(norm == header or norm.startswith(header) for header in SERVICE_HEADERS)


def is_title_page(paragraph: str) -> bool:
    lines = meaningful_lines(paragraph)
    if not lines:
        return False
    sample = " ".join(lines[:6]).lower()
    return any(phrase in sample for phrase in TITLE_PHRASES)


def is_toc_paragraph(paragraph: str) -> bool:
    lines = meaningful_lines(paragraph)
    if not lines:
        return False
    if is_service_header(lines[0]):
        return True
    toc_lines = [line for line in lines if is_toc_line(line)]
    return len(toc_lines) >= 2 or (
        len(toc_lines) == 1 and normalize(lines[0]) in ("содержание", "оглавление")
    )


def is_introduction(paragraph: str) -> bool:
    lines = meaningful_lines(paragraph)
    for index, line in enumerate(lines):
        if normalize(line) != "введение":
            continue
        if index + 1 >= len(lines):
            return True
        # в содержании после «Введение» стоит только номер страницы
        return len(lines[index + 1]) >= 40
    return False


def is_chapter_one(paragraph: str) -> bool:
    lines = meaningful_lines(paragraph)
    for index, line in enumerate(lines):
        if not re.match(r"^1(\s+|\.\s+)(?!\d)", line):
            continue
        if is_toc_line(line):
            continue
        rest = lines[index:]
        if len(rest) == 1:
            return len(line) >= 50
        if len(rest[1]) >= 30:
            return True
        return len("\n".join(rest)) >= 100
    return False


def extract_body_from_paragraph(paragraph: str) -> tuple[str, str] | tuple[None, str]:
    """Если основной текст начинается внутри абзаца — вернуть его часть."""
    lines = meaningful_lines(paragraph)
    for index, line in enumerate(lines):
        subsection = "\n".join(lines[index:])
        if normalize(line) == "введение" and is_introduction(subsection):
            return subsection, "Введение"
        if re.match(r"^1(\s+|\.\s+)(?!\d)", line) and is_chapter_one(subsection):
            return subsection, line[:60]
    return None, ""


def should_skip_before_body(paragraph: str) -> bool:
    """Абзац из начала документа, который не нужен для сравнения."""
    lines = meaningful_lines(paragraph)
    if not lines:
        return True

    first_line = lines[0]
    if is_service_header(first_line) or is_service_header(paragraph[:120]):
        return True
    if is_title_page(paragraph) or is_toc_paragraph(paragraph):
        return True
    if normalize(first_line) in ("введение", "содержание", "реферат"):
        return True
    if all(is_toc_line(line) for line in lines):
        return True
    return True


def _group_lines_into_paragraphs(lines: list[str]) -> list[str]:
    """Разбивает сплошной текст на блоки по заголовкам разделов."""
    chunks: list[str] = []
    current: list[str] = []

    for line in lines:
        norm = normalize(line)
        is_header = (
            SECTION_HEADER_RE.match(norm) is not None
            or is_toc_line(line)
            or is_noise_line(line)
            or (
                len(line) < 120
                and any(phrase in line.lower() for phrase in TITLE_PHRASES)
            )
        )
        if is_header and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current))
    return chunks if len(chunks) > 1 else ["\n".join(lines)]


def split_paragraphs(text: str) -> list[str]:
    """Текст → список абзацев (между пустыми строками)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    if len(paragraphs) == 1 and "\n" in paragraphs[0]:
        raw_lines = [line.strip() for line in paragraphs[0].split("\n") if line.strip()]
        if len(raw_lines) >= 8:
            return _group_lines_into_paragraphs(raw_lines)

    return paragraphs


def _strip_noise_lines(text: str) -> str:
    kept = [line for line in text.split("\n") if line.strip() and not is_noise_line(line)]
    return "\n".join(kept).strip()


def strip_academic_front_matter(text: str):
    """
    Убирает служебные разделы. Возвращает (очищенный текст, статистика).
    """
    if not text or not text.strip():
        return text, FrontMatterStats()

    paragraphs = split_paragraphs(text)
    kept: list[str] = []
    in_body = False
    marker = ""

    for paragraph in paragraphs:
        if not in_body:
            extracted, found_marker = extract_body_from_paragraph(paragraph)
            if extracted:
                in_body = True
                marker = found_marker
                kept.append(extracted)
                continue
            if is_introduction(paragraph):
                in_body = True
                marker = "Введение"
                kept.append(_strip_noise_lines(paragraph))
            elif is_chapter_one(paragraph):
                in_body = True
                marker = meaningful_lines(paragraph)[0][:60]
                kept.append(_strip_noise_lines(paragraph))
            elif should_skip_before_body(paragraph):
                continue
            continue

        if is_toc_paragraph(paragraph) or is_title_page(paragraph):
            continue

        lines = meaningful_lines(paragraph)
        if not lines:
            continue

        if is_service_header(lines[0]):
            continue

        kept.append(_strip_noise_lines(paragraph))

    result = "\n\n".join(kept).strip()
    if len(result) < MIN_BODY_CHARS:
        return text, FrontMatterStats()

    return result, FrontMatterStats(
        removed_chars=len(text) - len(result),
        body_start_marker=marker,
    )
