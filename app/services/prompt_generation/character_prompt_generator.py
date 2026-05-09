from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import is_debug_pipeline_enabled
from app.core.job_progress import IndexedProgressUpdate, JobProgressPublisher
from app.services.consolidation.character_identity import normalize_text
from app.services.llm.llm_factory import get_prompt_generation_llm
from app.services.prompt_generation.character_prompt_generation_llm import CharacterPromptGenerationLLM
from app.services.source_tools.character_source_tools import CharacterSourceTools


PLACEHOLDER_CHARACTER_NAMES = {"", "unknown", "desconocido", "personaje", "character"}

PLURAL_GROUP_ARTICLES = {"los", "las", "unos", "unas"}

SINGULAR_REFERENCE_ARTICLES = {"el", "la", "un", "una"}

GENERIC_INDIVIDUAL_TERMS = {
    "adulto",
    "adulta",
    "anciano",
    "anciana",
    "chico",
    "chica",
    "hombre",
    "joven",
    "muchacha",
    "muchacho",
    "mujer",
    "nina",
    "nino",
    "persona",
}

GROUP_REFERENCE_TERMS = {
    "aldeanos",
    "alumnos",
    "amigos",
    "ancianos",
    "chicos",
    "chicas",
    "ciudadanos",
    "companeros",
    "criadas",
    "criados",
    "familia",
    "familiares",
    "gente",
    "grupo",
    "guardias",
    "hombres",
    "invitados",
    "jovenes",
    "maestros",
    "muchachas",
    "muchachos",
    "mujeres",
    "ninas",
    "ninos",
    "padres",
    "personas",
    "profesores",
    "sirvientes",
    "soldados",
    "vecinos",
}


prompt_generation_progress = IndexedProgressUpdate(
    step="prompt_generation",
    message_template="Generando ficha y prompt del personaje {index}/{total}",
    start_pct=97,
    end_pct=99,
)


def _debug_print(*values: Any) -> None:
    if is_debug_pipeline_enabled():
        print(*values)


async def generate_character_prompts(
    characters: list[dict[str, Any]],
    *,
    book_language: str,
    progress: JobProgressPublisher | None = None,
    source_tools: CharacterSourceTools | None = None,
) -> list[dict[str, Any]]:
    """
    Genera fichas finales para personajes consolidados no anecdoticos.

    :param characters: Personajes consolidados por la fase anterior
    :param book_language: Idioma objetivo para los textos generados
    :param progress: Publicador opcional de progreso del job
    :return: Lista de fichas generadas
    """
    selected_characters = [
        character
        for character in characters
        if should_generate_character_prompt(character)
    ]

    _debug_print(
        f"\nGenerando prompts finales para {len(selected_characters)} "
        f"personajes de {len(characters)} consolidados..."
    )

    if not selected_characters:
        return []

    llm = get_prompt_generation_llm()
    generator = CharacterPromptGenerationLLM(llm, source_tools=source_tools)

    generated_characters: list[dict[str, Any]] = []
    total = len(selected_characters)

    for index, character in enumerate(selected_characters, start=1):
        await prompt_generation_progress.publish(
            progress,
            index=index,
            total=total,
        )

        character_id = build_generated_character_id(character)

        try:
            generated = await generator.generate_character_prompt(
                character=build_prompt_generation_payload(character),
                book_language=book_language,
            )
        except Exception as exc:
            generated = {
                "id": character_id,
                "main_name": character.get("canonical_name") or character.get("display_name") or "Unknown",
                "aliases": _clean_string_list(character.get("aliases", [])),
                "description": "",
                "image_prompt": "",
                "confidence": "low",
                "warnings": [f"Prompt generation failed: {exc}"],
            }
            generated_characters.append(generated)
            _debug_generated_character(index, generated)
            continue

        generated["id"] = character_id

        if character.get("needs_llm_review"):
            generated["confidence"] = "low"
            generated.setdefault("warnings", []).append(
                "El personaje conserva marcas de ambiguedad tras la consolidacion."
            )

        generated_characters.append(generated)
        _debug_generated_character(index, generated)

    return generated_characters


def _debug_generated_character(index: int, generated: dict[str, Any]) -> None:
    main_name = generated.get("main_name") or f"personaje {index}"

    _debug_print("\n" + "=" * 80 + "\n")
    _debug_print(f"DESCRIPCION DE {main_name}")
    _debug_print(json.dumps(generated, indent=2, ensure_ascii=False))
    _debug_print("-" * 50)


def should_generate_character_prompt(character: dict[str, Any]) -> bool:
    """
    Decide si un personaje tiene suficiente peso narrativo para generar ficha final.

    :param character: Personaje consolidado candidato
    :return: True si conviene enviarlo al LLM de generacion
    """
    canonical_name = character.get("canonical_name") or character.get("display_name") or ""
    normalized_name = normalize_text(canonical_name)

    if normalized_name in PLACEHOLDER_CHARACTER_NAMES:
        return False

    references_count = len(character.get("references") or [])
    aliases_count = len(character.get("aliases") or [])
    substance_score = _character_substance_score(character)
    is_named = character.get("entity_type") == "named"
    is_group_reference = _looks_like_group_reference(character)

    if not is_group_reference:
        if is_named and references_count >= 1 and substance_score >= 1:
            return True

        if _has_individual_identity_signal(character) and references_count >= 1 and substance_score >= 2:
            return True

        if is_named and substance_score >= 3:
            return True

    if references_count >= 3 and substance_score >= 1:
        return True

    if is_named and references_count >= 2 and substance_score >= 2:
        return True

    if is_named and substance_score >= 4:
        return True

    return aliases_count >= 2 and references_count >= 2 and substance_score >= 2


def _looks_like_group_reference(character: dict[str, Any]) -> bool:
    canonical_name = character.get("canonical_name") or character.get("display_name") or ""
    normalized_name = normalize_text(canonical_name)
    tokens = normalized_name.split()

    if tokens and tokens[0] in PLURAL_GROUP_ARTICLES:
        return True

    if any(token in GROUP_REFERENCE_TERMS for token in tokens):
        return True

    for item in character.get("identity_names", []) or []:
        value = item.get("value") if isinstance(item, dict) else ""
        normalized_value = normalize_text(value)
        value_tokens = normalized_value.split()

        if value_tokens and value_tokens[0] in PLURAL_GROUP_ARTICLES:
            return True

        if any(token in GROUP_REFERENCE_TERMS for token in value_tokens):
            return True

    return False


def _has_individual_identity_signal(character: dict[str, Any]) -> bool:
    if character.get("specific_appellations"):
        return True

    canonical_name = character.get("canonical_name") or character.get("display_name") or ""
    normalized_name = normalize_text(canonical_name)
    tokens = normalized_name.split()

    if len(tokens) == 1 and tokens[0] not in GROUP_REFERENCE_TERMS:
        return True

    if len(tokens) == 2 and tokens[0] in SINGULAR_REFERENCE_ARTICLES:
        return tokens[1] not in GENERIC_INDIVIDUAL_TERMS

    return any(
        isinstance(item, dict) and item.get("type") in {"name", "alias", "specific_appellation"}
        for item in character.get("identity_names", []) or []
    )


def build_generated_character_id(character: dict[str, Any]) -> str:
    """
    Crea un identificador estable para la ficha generada.

    :param character: Personaje consolidado
    :return: Identificador slug del personaje
    """
    base_name = character.get("canonical_name") or character.get("display_name") or "character"
    normalized = normalize_text(base_name)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or "character"


def build_prompt_generation_payload(character: dict[str, Any]) -> dict[str, Any]:
    """
    Reduce el personaje consolidado a los datos utiles para generacion final.

    :param character: Personaje consolidado completo
    :return: Payload serializable para el LLM
    """
    return {
        "canonical_name": character.get("canonical_name"),
        "display_name": character.get("display_name"),
        "entity_type": character.get("entity_type"),
        "aliases": character.get("aliases", []),
        "identity_names": character.get("identity_names", []),
        "specific_appellations": character.get("specific_appellations", []),
        "titles_roles_descriptors": character.get("titles_roles_descriptors", []),
        "appearance": character.get("appearance", {}),
        "personality_behavior": character.get("personality_behavior", {}),
        "social_context": character.get("social_context", {}),
        "motivations_goals": character.get("motivations_goals", []),
        "scene_context": character.get("scene_context", {}),
        "confidence": character.get("confidence"),
        "needs_llm_review": character.get("needs_llm_review", False),
        "ambiguity_reasons": character.get("ambiguity_reasons", []),
        "references": character.get("references", []),
        "references_count": len(character.get("references") or []),
    }


def _character_substance_score(character: dict[str, Any]) -> int:
    score = 0

    appearance = character.get("appearance") or {}
    score += _field_has_value(appearance.get("gender"))
    score += _field_has_value(appearance.get("apparent_age"))
    score += min(len(appearance.get("physical_traits") or []), 3)
    score += min(len(appearance.get("clothing_accessories") or []), 2)
    score += min(len(appearance.get("distinctive_markers") or []), 2)

    personality = character.get("personality_behavior") or {}
    score += min(len(personality.get("personality_traits") or []), 2)
    score += min(len(personality.get("behavioral_tendencies") or []), 2)

    social = character.get("social_context") or {}
    score += min(len(social.get("role_status") or []), 2)
    score += min(len(social.get("relationships") or []), 3)

    score += min(len(character.get("motivations_goals") or []), 2)
    score += min(len(character.get("titles_roles_descriptors") or []), 2)

    scene = character.get("scene_context") or {}
    score += min(len(scene.get("locations") or []), 2)
    score += min(len(scene.get("actions") or []), 2)
    score += min(len(scene.get("notes") or []), 2)

    return score


def _field_has_value(value: Any) -> int:
    if isinstance(value, dict):
        return 1 if value.get("value") else 0

    return 1 if value else 0


def _clean_string_list(values: list[Any]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]
