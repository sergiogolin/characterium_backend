import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkFilterStats:
    kept: int
    removed: int


NON_NARRATIVE_HEADING_PATTERNS = [
    r"agradecimientos?",
    r"acknowledg(?:e)?ments?",
    r"tabla de contenidos?",
    r"table of contents",
    r"contenido",
    r"contents",
    r"[ií]ndice",
    r"index",
    r"nota (?:de|del|de la) autor(?:a)?",
    r"author'?s note",
    r"palabras? (?:de|del|de la) autor(?:a)?",
    r"sobre (?:el|la) autor(?:a)?",
    r"about the author",
    r"dedicatoria",
    r"dedication",
    r"copyright",
    r"cr[eé]ditos?",
    r"credits?",
    r"reseñas?",
    r"reviews?",
    r"elogios? para",
    r"praise for",
    r"otros libros de",
    r"also by",
    r"bibliograf[ií]a",
    r"bibliography",
    r"glosario",
    r"glossary",
]

HEADING_RE = re.compile(
    rf"^\s*(?:{'|'.join(NON_NARRATIVE_HEADING_PATTERNS)})\s*[:.\-–—]?\s*$",
    re.IGNORECASE,
)

PAGE_OR_TOC_LINE_RE = re.compile(
    r"^\s*(?:"
    r"(?:cap[ií]tulo|chapter|parte|part)\s+[\w\dIVXLC]+"
    r"|[A-ZÁÉÍÓÚÑ][^.\n]{2,80}"
    r")\s*(?:\.{2,}|\s{2,})\s*\d+\s*$",
    re.IGNORECASE,
)

CHAPTER_START_RE = re.compile(
    r"(?:^|\n)\s*(?:cap[ií]tulo|chapter|parte|part)\s+[\w\dIVXLC]+\b",
    re.IGNORECASE,
)

COPYRIGHT_RE = re.compile(
    r"(?:copyright|all rights reserved|todos los derechos reservados|isbn|"
    r"publicado por|published by|editorial|primera edici[oó]n|"
    r"no se permite la reproducci[oó]n)",
    re.IGNORECASE,
)

REVIEW_RE = re.compile(
    r"(?:\b(?:dijo|dice|seg[uú]n|says)\b|[\"“”])[^.\n]{0,160}"
    r"(?:new york times|publishers weekly|kirkus|booklist|autor(?:a)?|escritor(?:a)?|novelist)",
    re.IGNORECASE,
)


def is_non_narrative_chunk(chunk: str) -> bool:
    """
    Detecta chunks claramente externos al relato: indices, copyright,
    agradecimientos, notas del autor, resenas y material editorial.

    La funcion es conservadora: ante duda devuelve False para no eliminar
    texto narrativo.
    """

    if not isinstance(chunk, str) or not chunk.strip():
        return True

    text = chunk.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True

    first_lines = lines[:5]
    first_text = "\n".join(first_lines)
    lower_text = text.lower()

    has_non_narrative_heading = any(HEADING_RE.match(line) for line in first_lines)
    if has_non_narrative_heading and not CHAPTER_START_RE.search(text):
        return True

    toc_lines = sum(1 for line in lines[:40] if PAGE_OR_TOC_LINE_RE.match(line))
    if toc_lines >= 3 and toc_lines / max(1, min(len(lines), 40)) >= 0.35:
        return True

    copyright_hits = len(COPYRIGHT_RE.findall(text))
    if copyright_hits >= 2:
        return True

    review_hits = len(REVIEW_RE.findall(text))
    if review_hits >= 2 and len(text) < 5000:
        return True

    heading_keyword_hits = sum(
        1
        for pattern in NON_NARRATIVE_HEADING_PATTERNS
        if re.search(rf"\b{pattern}\b", first_text, re.IGNORECASE)
    )
    if heading_keyword_hits >= 2:
        return True

    if "table of contents" in lower_text or "tabla de contenidos" in lower_text:
        return True

    return False


def filter_non_narrative_chunks(chunks: list[str]) -> tuple[list[str], ChunkFilterStats]:
    filtered = [
        chunk
        for chunk in chunks
        if isinstance(chunk, str) and chunk.strip() and not is_non_narrative_chunk(chunk)
    ]

    return filtered, ChunkFilterStats(
        kept=len(filtered),
        removed=len(chunks) - len(filtered),
    )
