# app/services/consolidation/character_identity_scoring.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.consolidation.character_identity import (
    looks_like_descriptive_form,
    normalize_text,
)


AUTO_MERGE_THRESHOLD = 0.90
LLM_REVIEW_THRESHOLD = 0.60

COMMON_NAME_TOKENS = {
    "a",
    "al",
    "ante",
    "bajo",
    "con",
    "contra",
    "de",
    "del",
    "desde",
    "durante",
    "e",
    "el",
    "ella",
    "en",
    "entre",
    "hacia",
    "hasta",
    "la",
    "las",
    "lo",
    "los",
    "mediante",
    "o",
    "para",
    "por",
    "segun",
    "sin",
    "sobre",
    "su",
    "sus",
    "tras",
    "tu",
    "tus",
    "un",
    "una",
    "unas",
    "unos",
    "y",
    "viejo",
    "vieja",
    "joven",
    "pequeno",
    "pequena",
    "grande",
    "alto",
    "alta",
    "baja",
    "rojo",
    "roja",
    "azul",
    "verde",
    "negro",
    "negra",
    "blanco",
    "blanca",
    "gris",
    "dorado",
    "dorada",
}

GENERIC_PERSON_TOKENS = {
    "adulto",
    "adulta",
    "anciano",
    "anciana",
    "chico",
    "chica",
    "hombre",
    "joven",
    "mujer",
    "nino",
    "nina",
    "persona",
}


@dataclass
class IdentityMatchResult:
    """
    Representa el resultado de comparar dos identidades de personaje.

    :param score: Puntuacion normalizada de similitud entre 0.0 y 1.0
    :param should_merge: Indica si los personajes deben fusionarse automaticamente
    :param needs_llm_review: Indica si el caso debe enviarse al resolvedor LLM
    :param reasons: Explicaciones programaticas que justifican la decision
    """
    score: float
    should_merge: bool
    needs_llm_review: bool
    reasons: list[str]


def get_all_identity_names(character: dict[str, Any]) -> set[str]:
    """
    Recupera todos los nombres comparables de un personaje consolidado.

    :param character: Personaje consolidado o candidato
    :return: Conjunto de nombres normalizados disponibles para comparar
    """
    names = {
        character.get("canonical_name", ""),
        character.get("display_name", ""),
        *(character.get("aliases") or []),
        *(character.get("specific_appellations") or []),
    }
    names.update(
        item.get("value", "")
        for item in character.get("identity_names", [])
        if isinstance(item, dict)
    )

    return {
        normalize_text(name)
        for name in names
        if name and normalize_text(name) and not looks_like_descriptive_form(name)
    }


def split_name(name: str) -> list[str]:
    """
    Divide un nombre normalizado en partes.

    :param name: Nombre original a dividir
    :return: Lista de tokens normalizados del nombre
    """
    return normalize_text(name).split()


def get_substantial_name_tokens(name: str) -> list[str]:
    """
    Devuelve las partes de nombre que cuentan como identidad fuerte.

    :param name: Nombre normalizado a evaluar
    :return: Tokens sin determinantes, conectores ni descriptores comunes
    """
    return [
        part
        for part in split_name(name)
        if len(part) > 1 and part not in COMMON_NAME_TOKENS
    ]


def is_substantial_multiword_name(name: str) -> bool:
    """
    Comprueba si un nombre exacto tiene al menos dos partes no comunes.

    :param name: Nombre normalizado a evaluar
    :return: True si parece nombre + apellido u otra identidad compuesta fuerte
    """
    if looks_like_descriptive_form(name):
        return False

    return len(get_substantial_name_tokens(name)) >= 2


def is_specific_appellation_name(name: str) -> bool:
    """
    Detecta apelativos especificos como "la reina roja" sin depender de mayusculas.

    :param name: Nombre normalizado a evaluar
    :return: True si parece un apelativo concreto y no una descripcion generica
    """
    parts = split_name(name)

    if len(parts) < 3:
        return False

    if parts[0] not in {"el", "la", "los", "las"}:
        return False

    return parts[1] not in GENERIC_PERSON_TOKENS


def is_auto_merge_exact_name(name: str) -> bool:
    """
    Decide si un nombre exacto compartido es suficientemente especifico para fusionar.

    :param name: Nombre normalizado compartido
    :return: True si el nombre exacto permite fusion automatica sin conflictos
    """
    return is_substantial_multiword_name(name) or is_specific_appellation_name(name)


def is_comparable_name_variant(name: str) -> bool:
    """
    Decide si un texto puede actuar como variante de nombre y no como frase descriptiva.

    :param name: Nombre normalizado a evaluar
    :return: True si es suficientemente parecido a un nombre o apelativo breve
    """
    parts = split_name(name)

    if not parts:
        return False

    if looks_like_descriptive_form(name):
        return False

    return len(parts) <= 4


def has_shared_surname(name_a: str, name_b: str) -> bool:
    """
    Comprueba si dos nombres comparten el ultimo token como apellido.

    :param name_a: Primer nombre a comparar
    :param name_b: Segundo nombre a comparar
    :return: True si ambos nombres tienen apellido comparable y coincide
    """
    parts_a = split_name(name_a)
    parts_b = split_name(name_b)

    if len(parts_a) < 2 and len(parts_b) < 2:
        return False

    return parts_a[-1] == parts_b[-1]


def is_name_contained(short_name: str, long_name: str) -> bool:
    """
    Comprueba si todas las partes de un nombre aparecen dentro de otro.

    :param short_name: Nombre potencialmente parcial
    :param long_name: Nombre potencialmente completo
    :return: True si el nombre corto esta contenido en el largo
    """
    short_parts_list = split_name(short_name)
    long_parts_list = split_name(long_name)

    if len(short_parts_list) > len(long_parts_list):
        short_parts_list, long_parts_list = long_parts_list, short_parts_list
        short_name, long_name = long_name, short_name

    if not is_comparable_name_variant(short_name) or not is_comparable_name_variant(long_name):
        return False

    short_parts = set(short_parts_list)
    long_parts = set(long_parts_list)

    if not short_parts or not long_parts:
        return False

    if len(short_parts) == 1 and len(long_parts) > 2:
        return False

    return short_parts.issubset(long_parts)


def has_exact_name_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """
    Comprueba si dos personajes comparten algun nombre identico normalizado.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :return: True si existe al menos una identidad textual exacta compartida
    """
    return bool(get_all_identity_names(a) & get_all_identity_names(b))


def get_substantial_exact_name_matches(
    names_a: set[str],
    names_b: set[str],
) -> set[str]:
    """
    Obtiene nombres exactos compartidos que bastan para una fusion automatica.

    :param names_a: Nombres normalizados del primer personaje
    :param names_b: Nombres normalizados del segundo personaje
    :return: Nombres exactos compartidos suficientemente especificos
    """
    return {
        name
        for name in names_a & names_b
        if is_auto_merge_exact_name(name)
    }


def get_gender_value(character: dict[str, Any]) -> str | None:
    """
    Obtiene el genero normalizado de la apariencia de un personaje.

    :param character: Personaje del que leer la apariencia
    :return: Genero normalizado o None si no esta disponible
    """
    gender = character.get("appearance", {}).get("gender")

    if isinstance(gender, dict):
        value = gender.get("value")
        return normalize_text(value) if value else None

    return None


def get_age_value(character: dict[str, Any]) -> str | None:
    """
    Obtiene la edad aparente normalizada de un personaje.

    :param character: Personaje del que leer la apariencia
    :return: Edad aparente normalizada o None si no esta disponible
    """
    age = character.get("appearance", {}).get("apparent_age")

    if isinstance(age, dict):
        value = age.get("value")
        return normalize_text(value) if value else None

    return None


def compatible_gender(a: dict[str, Any], b: dict[str, Any]) -> bool | None:
    """
    Evalua si el genero de dos personajes es compatible.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :return: True si coincide, False si contradice o None si falta informacion
    """
    gender_a = get_gender_value(a)
    gender_b = get_gender_value(b)

    if not gender_a or not gender_b:
        return None

    return gender_a == gender_b


def compatible_age(a: dict[str, Any], b: dict[str, Any]) -> bool | None:
    """
    Evalua si la edad aparente de dos personajes es compatible.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :return: True si coincide, False si contradice o None si falta informacion
    """
    age_a = get_age_value(a)
    age_b = get_age_value(b)

    if not age_a or not age_b:
        return None

    return age_a == age_b


def has_existing_attribute_conflicts(character: dict[str, Any]) -> bool:
    """
    Detecta conflictos ya consolidados en atributos usados para identidad.

    :param character: Personaje consolidado o candidato
    :return: True si hay conflictos de genero o edad aparente
    """
    appearance = character.get("appearance") or {}

    for field in ("gender", "apparent_age"):
        value = appearance.get(field)

        if isinstance(value, dict) and value.get("conflicts"):
            return True

    return False


def has_identity_conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """
    Comprueba si dos personajes tienen conflictos programaticos de identidad.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :return: True si hay contradiccion de genero, edad o conflictos previos
    """
    if has_existing_attribute_conflicts(a) or has_existing_attribute_conflicts(b):
        return True

    return compatible_gender(a, b) is False or compatible_age(a, b) is False


def get_reference_chunks(character: dict[str, Any]) -> list[int]:
    """
    Extrae los indices de chunk asociados a las referencias de un personaje.

    :param character: Personaje del que leer referencias
    :return: Lista de indices de chunk encontrados
    """
    return [
        ref["chunk_index"]
        for ref in character.get("references", [])
        if "chunk_index" in ref
    ]


def are_chunks_close(a: dict[str, Any], b: dict[str, Any], max_distance: int = 2) -> bool:
    """
    Comprueba si dos personajes aparecen en chunks narrativamente cercanos.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :param max_distance: Distancia maxima permitida entre chunks
    :return: True si alguna referencia de ambos personajes esta suficientemente cerca
    """
    chunks_a = get_reference_chunks(a)
    chunks_b = get_reference_chunks(b)

    if not chunks_a or not chunks_b:
        return False

    return min(abs(ca - cb) for ca in chunks_a for cb in chunks_b) <= max_distance


def score_identity_match(a: dict[str, Any], b: dict[str, Any]) -> IdentityMatchResult:
    """
    Calcula una puntuacion de similitud para decidir si dos personajes son la misma identidad.

    :param a: Primer personaje a comparar
    :param b: Segundo personaje a comparar
    :return: Resultado con score, decision automatica, necesidad de LLM y razones
    """
    score = 0.0
    reasons: list[str] = []

    names_a = get_all_identity_names(a)
    names_b = get_all_identity_names(b)

    if not names_a or not names_b:
        return IdentityMatchResult(
            score=0.0,
            should_merge=False,
            needs_llm_review=False,
            reasons=["Missing comparable names"],
        )

    substantial_exact_matches = get_substantial_exact_name_matches(names_a, names_b)

    if substantial_exact_matches and not has_identity_conflict(a, b):
        return IdentityMatchResult(
            score=1.0,
            should_merge=True,
            needs_llm_review=False,
            reasons=[
                "Exact specific identity name match without conflicts: "
                + ", ".join(sorted(substantial_exact_matches))
            ],
        )

    if has_exact_name_match(a, b):
        score += 0.80
        reasons.append("Exact identity name match")

    else:
        for name_a in names_a:
            for name_b in names_b:
                if is_name_contained(name_a, name_b) or is_name_contained(name_b, name_a):
                    score += 0.75
                    reasons.append(f"Contained name variant: '{name_a}' / '{name_b}'")
                    break

                if has_shared_surname(name_a, name_b):
                    score += 0.55
                    reasons.append(f"Shared surname: '{name_a}' / '{name_b}'")
                    break

    gender_match = compatible_gender(a, b)

    if gender_match is True:
        score += 0.10
        reasons.append("Compatible gender")
    elif gender_match is False:
        score -= 0.40
        reasons.append("Conflicting gender")

    age_match = compatible_age(a, b)

    if age_match is True:
        score += 0.05
        reasons.append("Compatible apparent age")
    elif age_match is False:
        score -= 0.20
        reasons.append("Conflicting apparent age")

    if are_chunks_close(a, b):
        score += 0.05
        reasons.append("References appear in nearby chunks")

    score = max(0.0, min(score, 1.0))

    return IdentityMatchResult(
        score=score,
        should_merge=score >= AUTO_MERGE_THRESHOLD,
        needs_llm_review=LLM_REVIEW_THRESHOLD <= score < AUTO_MERGE_THRESHOLD,
        reasons=reasons,
    )
