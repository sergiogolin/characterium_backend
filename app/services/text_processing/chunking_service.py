from app.services.text_processing.text_chunker import TextChunker
from app.services.text_processing.non_narrative_filter import filter_non_narrative_chunks


class ChunkingError(Exception):
    """Error controlado durante el proceso de chunking."""
    pass


def chunk_uploaded_content(content: str | list[str]) -> list[str]:
    if content is None:
        raise ChunkingError("No hay contenido para dividir en chunks.")

    if isinstance(content, str):
        if not content.strip():
            raise ChunkingError("El contenido está vacío.")
    elif isinstance(content, list):
        if not any(isinstance(block, str) and block.strip() for block in content):
            raise ChunkingError("El contenido está vacío.")
    else:
        raise ChunkingError("El formato del contenido no es válido para chunking.")

    try:
        chunks = TextChunker.chunk(content=content)
    except Exception as exc:
        raise ChunkingError(f"Error durante el chunking: {str(exc)}") from exc

    if chunks is None:
        raise ChunkingError("El chunker no devolvió ningún resultado.")

    if not isinstance(chunks, list):
        raise ChunkingError("El chunker devolvió un formato no válido.")

    if not chunks:
        raise ChunkingError("No se pudieron generar chunks a partir del contenido.")

    valid_chunks = [chunk for chunk in chunks if isinstance(chunk, str) and chunk.strip()]

    if not valid_chunks:
        raise ChunkingError("Los chunks generados están vacíos.")

    narrative_chunks, _stats = filter_non_narrative_chunks(valid_chunks)

    if not narrative_chunks:
        raise ChunkingError("No se encontraron chunks narrativos para procesar.")

    return narrative_chunks
