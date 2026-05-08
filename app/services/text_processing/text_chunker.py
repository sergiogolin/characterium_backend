import re
from typing import List, Union

from app.core.runtime_config import get_config_value


def _get_config_int(name: str, default: int) -> int:
    return int(get_config_value(name, default))


def _resolve_chunk_params(
    max_chars: int | None,
    overlap_paragraphs: int | None,
) -> tuple[int, int]:
    return (
        _get_config_int("DEFAULT_MAX_CHARS", 5000) if max_chars is None else max_chars,
        _get_config_int("DEFAULT_OVERLAP_PARAGRAPHS", 1)
        if overlap_paragraphs is None
        else overlap_paragraphs,
    )


class TextChunker:
    """Utilidad para dividir texto en chunks de manera jerárquica y optimizada."""

    # ========== CONSTANTES ==========
    CHAPTER_SEPARATORS = [
        r"\n(?:Capítulo|Capitulo|Chapter)\s+[\w\dIVXLC]+",
        r"\n(?:Parte|Part)\s+[\w\dIVXLC]+",
    ]
    
    PARAGRAPH_SEPARATORS = [
        r"\n\n",   # Doble salto de línea
        r"\.\n",   # Punto y aparte
        r"\n",     # Salto simple
    ]
    
    PARAGRAPH_SEPARATOR_CHAR = "\n"
    SEPARATOR_LENGTH = 1

    # ========== MÉTODOS PÚBLICOS - ENTRY POINT ==========

    @staticmethod
    def chunk(
        content: Union[str, List[str]],
        max_chars: int | None = None,
        overlap_paragraphs: int | None = None
    ) -> List[str]:
        """
        Orquesta el chunking jerárquico:
        1. Divide en capítulos
        2. Divide cada capítulo en párrafos
        3. Construye chunks por tamaño a partir de esos párrafos
        4. Une todos los chunks de todos los capítulos en un único listado

        Args:
            content: string con texto completo o lista de strings (ej. capítulos de EPUB)
            max_chars: tamaño máximo de cada chunk en caracteres
            overlap_paragraphs: número de párrafos del overlap entre chunks

        Returns:
            Lista de chunks de texto.
        """

        if not content:
            return []

        max_chars, overlap_paragraphs = _resolve_chunk_params(
            max_chars,
            overlap_paragraphs,
        )

        source_blocks = TextChunker._prepare_source_blocks(content)
        if not source_blocks:
            return []

        all_chunks: List[str] = []

        for block in source_blocks:
            chapters = TextChunker.split_by_chapters(block)

            for chapter in chapters:
                paragraphs = TextChunker.split_by_paragraphs(chapter)

                if not paragraphs:
                    continue

                chapter_chunks = TextChunker.build_chunks_from_paragraphs(
                    paragraphs=paragraphs,
                    max_chars=max_chars,
                    overlap_paragraphs=overlap_paragraphs
                )

                all_chunks.extend(chapter_chunks)

        return all_chunks

    # ========== MÉTODOS PÚBLICOS - DIVISIÓN POR NIVELES ==========

    @staticmethod
    def split_by_chapters(text: str) -> List[str]:
        """
        Divide el texto en capítulos usando patrones jerárquicos de prioridad.

        Patrones ordenados por prioridad:
        1. Inicio de capítulo
        2. Inicio de parte

        Si no encuentra separadores válidos, devuelve el texto completo
        como un único capítulo.

        Returns:
            Lista de capítulos divididos.
        """
        return TextChunker._split_by_separators(text, TextChunker.CHAPTER_SEPARATORS)

    @staticmethod
    def split_by_paragraphs(text: str) -> List[str]:
        """
        Divide un capítulo en párrafos usando patrones jerárquicos de prioridad.

        Patrones ordenados por prioridad:
        1. Doble salto de línea
        2. Punto y aparte
        3. Salto simple
        
        Filtra chunks vacíos o que solo contienen espacios en blanco.

        Returns:
            Lista de párrafos divididos.
        """
        return TextChunker._split_by_separators(text, TextChunker.PARAGRAPH_SEPARATORS)

    @staticmethod
    def build_chunks_from_paragraphs(
        paragraphs: List[str],
        max_chars: int | None = None,
        overlap_paragraphs: int | None = None
    ) -> List[str]:
        """
        Construye chunks a partir de párrafos completos.

        Reglas:
        - Se añaden párrafos al chunk actual mientras quepan.
        - Si el siguiente no cabe, se cierra el chunk.
        - El nuevo chunk empieza con los últimos `overlap_paragraphs`
          del chunk anterior.
        - El overlap cuenta para el límite máximo.
        - Los párrafos se unen con salto de línea simple.

        Args:
            paragraphs: Lista de párrafos
            max_chars: Tamaño máximo del chunk
            overlap_paragraphs: Párrafos del overlap

        Returns:
            Lista de chunks generados.
        """

        if not paragraphs:
            return []

        max_chars, overlap_paragraphs = _resolve_chunk_params(
            max_chars,
            overlap_paragraphs,
        )

        TextChunker._validate_chunk_params(max_chars, overlap_paragraphs)

        clean_paragraphs = TextChunker._clean_chunks(paragraphs)
        if not clean_paragraphs:
            return []

        chunks = []
        current_chunk = []
        current_length = 0

        for paragraph in clean_paragraphs:
            current_chunk, current_length = TextChunker._add_paragraph_to_chunk(
                current_chunk, current_length, paragraph, chunks, max_chars, overlap_paragraphs
            )

        if current_chunk:
            chunks.append(TextChunker._join_paragraphs(current_chunk))

        return chunks

    # ========== MÉTODOS PRIVADOS - UTILIDADES BÁSICAS ==========

    @staticmethod
    def _clean_chunks(chunks: List[str]) -> List[str]:
        """Limpia chunks removiendo espacios y filtrando vacíos."""
        return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]

    @staticmethod
    def _join_paragraphs(paragraphs: List[str]) -> str:
        """Une párrafos con separador de línea."""
        return TextChunker.PARAGRAPH_SEPARATOR_CHAR.join(paragraphs)

    @staticmethod
    def _calculate_chunk_length(paragraphs: List[str]) -> int:
        """Calcula longitud total incluyendo separadores entre párrafos."""
        if not paragraphs:
            return 0
        total_chars = sum(len(p) for p in paragraphs)
        separators = max(0, len(paragraphs) - 1) * TextChunker.SEPARATOR_LENGTH
        return total_chars + separators

    # ========== MÉTODOS PRIVADOS - PREPARACIÓN Y DIVISIÓN ==========

    @staticmethod
    def _prepare_source_blocks(content: Union[str, List[str]]) -> List[str]:
        """Prepara los bloques de texto fuente, validando y limpiando."""
        if isinstance(content, list):
            return TextChunker._clean_chunks(content)
        
        cleaned = content.strip()
        return [cleaned] if cleaned else []

    @staticmethod
    def _split_by_separators(text: str, separators: List[str]) -> List[str]:
        """
        Divide texto usando una lista de separadores por prioridad.
        Usa el primer separador que genere más de un chunk.
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            return []

        for separator in separators:
            chunks = re.split(separator, text)

            if len(chunks) > 1:
                result = TextChunker._clean_chunks(chunks)
                if result:
                    return result

        return [cleaned_text]

    # ========== MÉTODOS PRIVADOS - VALIDACIÓN ==========

    @staticmethod
    def _validate_chunk_params(max_chars: int, overlap_paragraphs: int) -> None:
        """Valida los parámetros de construcción de chunks."""
        if max_chars <= 0:
            raise ValueError("max_chars debe ser mayor que 0")
        if overlap_paragraphs < 0:
            raise ValueError("overlap_paragraphs no puede ser negativo")

    # ========== MÉTODOS PRIVADOS - LÓGICA DE CONSTRUCCIÓN ==========

    @staticmethod
    def _fits_in_chunk(current_length: int, paragraph_len: int, max_chars: int) -> bool:
        """Comprueba si un párrafo cabe en el chunk actual."""
        new_length = current_length + TextChunker.SEPARATOR_LENGTH + paragraph_len
        return new_length <= max_chars

    @staticmethod
    def _handle_paragraph_overflow(
        current_chunk: List[str],
        paragraph: str,
        chunks: List[str],
        overlap_paragraphs: int
    ) -> tuple[List[str], int]:
        """
        Maneja el caso donde un párrafo no cabe en el chunk actual.
        Devuelve el nuevo chunk inicial (con overlap) y su longitud.
        """
        chunks.append(TextChunker._join_paragraphs(current_chunk))

        if overlap_paragraphs > 0:
            new_chunk = current_chunk[-overlap_paragraphs:]
        else:
            new_chunk = []

        new_chunk.append(paragraph)
        new_length = TextChunker._calculate_chunk_length(new_chunk)

        return new_chunk, new_length

    @staticmethod
    def _add_paragraph_to_chunk(
        current_chunk: List[str],
        current_length: int,
        paragraph: str,
        chunks: List[str],
        max_chars: int,
        overlap_paragraphs: int
    ) -> tuple[List[str], int]:
        """
        Añade un párrafo al chunk actual, manejando tres casos:
        1. Chunk vacío → inicializar
        2. Cabe → agregar
        3. No cabe → overflow
        
        Returns:
            Tupla con (nuevo_chunk, nueva_longitud)
        """
        paragraph_len = len(paragraph)

        # Primer párrafo del chunk
        if not current_chunk:
            current_chunk.append(paragraph)
            return current_chunk, paragraph_len

        # Comprueba si cabe
        if TextChunker._fits_in_chunk(current_length, paragraph_len, max_chars):
            current_chunk.append(paragraph)
            new_length = current_length + TextChunker.SEPARATOR_LENGTH + paragraph_len
            return current_chunk, new_length

        # No cabe: overflow
        return TextChunker._handle_paragraph_overflow(
            current_chunk, paragraph, chunks, overlap_paragraphs
        )
