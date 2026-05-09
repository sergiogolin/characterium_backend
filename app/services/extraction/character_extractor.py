from __future__ import annotations

import json
from typing import Any

from app.core.config import is_debug_pipeline_enabled
from app.core.job_progress import IndexedProgressUpdate, JobProgressPublisher
from app.services.llm.llm_factory import get_extraction_llm
from app.services.llm.json_utils import parse_json_object_response
from app.services.prompts.prompt_loader import load_prompt, render_prompt


character_extraction_progress = IndexedProgressUpdate(
    step="character_extraction",
    message_template="Extrayendo los personajes del chunk {index}/{total}",
    end_pct=95,
)


def _debug_print(*values: Any) -> None:
    if is_debug_pipeline_enabled():
        print(*values)


def _parse_llm_json_response(response: str) -> dict[str, Any]:
    """
    Parsea respuestas JSON aunque el LLM las envuelva en fences markdown.
    """

    try:
        return parse_json_object_response(response)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Respuesta no es JSON valido:\n{response}") from e


async def extract_characters_from_chunk(
    chunk_text: str,
    chunk_index: int,
    llm: Any,
    system_prompt: str,
    user_template: str,
) -> dict[str, Any]:
    """
    Extrae observaciones de personajes de un único chunk usando el LLM.
    """

    user_prompt = render_prompt(
        user_template,
        CHUNK_INDEX=chunk_index,
        CHUNK_TEXT=chunk_text,
    )

    response = await llm.call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    response = _parse_llm_json_response(response)

    _debug_print(f"\nResultado chunk {chunk_index}:")
    _debug_print(json.dumps(response, indent=2, ensure_ascii=False))
    _debug_print("-" * 50)

    return response


async def extract_characters_from_chunks(
    chunks: list[str],
    progress: JobProgressPublisher | None = None,
) -> list[dict[str, Any]]:
    """
    Itera los chunks y devuelve un array con los datos extraídos de cada uno.
    """

    _debug_print("\nIterando chunks para extracción de personajes...")
    
    llm = get_extraction_llm()

    system_prompt = load_prompt("character_extraction/system.md")
    user_template = load_prompt("character_extraction/user.md")

    results: list[dict[str, Any]] = []
    total_chunks = len(chunks)

    for chunk_index, chunk_text in enumerate(chunks[:6]):
        display_index = chunk_index + 1
        await character_extraction_progress.publish(
            progress,
            index=display_index,
            total=total_chunks,
        )

        try:
            chunk_result = await extract_characters_from_chunk(
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                llm=llm,
                system_prompt=system_prompt,
                user_template=user_template,
            )

            # Asegurar consistencia mínima
            chunk_result.setdefault("chunk_index", chunk_index)
            chunk_result.setdefault("characters", [])

            results.append(chunk_result)

        except Exception as e:
            _debug_print(f"ERROR EN CHUNK {chunk_index}: {e}")

            results.append({
                "chunk_index": chunk_index,
                "characters": [],
                "error": str(e),
            })

    return results
