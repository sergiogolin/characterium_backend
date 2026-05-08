# app/services/consolidation/character_identity.py

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


TITLE_PATTERNS = [
    r"^(sr\.?|sra\.?|señor|señora|señorita|don|doña)\s+",
    r"^(dr\.?|dra\.?|doctor|doctora|profesor|profesora)\s+",
    r"^(alcalde|alcaldesa|rey|reina|príncipe|princesa|capitán|capitana)\s+",
]


DESCRIPTIVE_FORMS = {
    "un hombre",
    "una mujer",
    "un niño",
    "una niña",
    "el hombre",
    "la mujer",
    "el niño",
    "la niña",
    "los hombres",
    "las mujeres",
    "los profesores",
    "las profesoras",
}

ADDITIONAL_DESCRIPTIVE_FORMS = {
    "un nino",
    "una nina",
    "el nino",
    "la nina",
    "hombre",
    "mujer",
    "nino",
    "nina",
}

DESCRIPTIVE_CONNECTORS = {
    "que",
    "quien",
    "cuyo",
    "cuya",
    "cuyos",
    "cuyas",
    "donde",
}


@dataclass(frozen=True)
class IdentityCandidate:
    value: str
    normalized: str
    without_titles: str
    token_count: int
    has_title: bool
    is_specific_appellation: bool
    source_chunk_index: int
    source_local_id: str


def normalize_text(value: str) -> str:
    """
    Normaliza texto para comparaciones de identidad.

    :param value: Texto original a normalizar
    :return: Texto en minusculas, sin acentos y con espacios compactados
    """
    value = value.strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value


def looks_like_generated_local_id(value: str) -> bool:
    """
    Detecta IDs tecnicos que no deberian convertirse en nombres canonicos.

    :param value: Identificador local recibido del extractor
    :return: True si parece un ID generado y no un nombre narrativo
    """
    normalized = normalize_text(value).replace("-", "_")

    if normalized in {"unknown", "desconocido", "personaje", "character"}:
        return True

    return bool(
        re.match(
            r"^(character|personaje|person|char|entity|unknown|desconocido|id)?_?\d+$",
            normalized,
        )
    )


def remove_leading_titles(value: str) -> tuple[str, bool]:
    """
    Elimina titulos iniciales de una posible referencia de personaje.

    :param value: Texto original con o sin titulo inicial
    :return: Texto sin titulo inicial y bandera que indica si se elimino alguno
    """
    cleaned = value.strip()
    had_title = False

    for pattern in TITLE_PATTERNS:
        new_value = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        if new_value != cleaned:
            cleaned = new_value
            had_title = True
            break

    return cleaned, had_title


def looks_like_descriptive_form(value: str) -> bool:
    """
    Detecta si un texto parece una descripcion generica y no una identidad concreta.

    :param value: Texto a evaluar
    :return: True si el texto coincide con una forma descriptiva generica
    """
    normalized = normalize_text(value)
    descriptive_forms = {normalize_text(form) for form in DESCRIPTIVE_FORMS}
    descriptive_forms.update(ADDITIONAL_DESCRIPTIVE_FORMS)

    if normalized in descriptive_forms:
        return True

    tokens = normalized.split()

    if len(tokens) >= 5 and any(token in DESCRIPTIVE_CONNECTORS for token in tokens):
        return True

    if len(tokens) >= 5 and tokens[0] in {"el", "la", "los", "las", "un", "una", "unos", "unas"}:
        return True

    return False


def looks_like_specific_appellation(value: str) -> bool:
    """
    Detecta si un texto parece un apelativo especifico de personaje.

    :param value: Texto a evaluar, como "el Mago Gris" o "la Reina Roja"
    :return: True si parece un apelativo concreto y no una descripcion generica
    """
    value = value.strip()

    if looks_like_descriptive_form(value):
        return False

    return bool(
        re.match(r"^(el|la|los|las)\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ-]+", value)
    )


def extract_identity_candidates(
    character: dict[str, Any],
    chunk_index: int,
) -> list[IdentityCandidate]:
    """
    Extrae candidatos de identidad desde nombres, menciones y display_name.

    :param character: Personaje extraido de un chunk
    :param chunk_index: Indice del chunk del que procede el personaje
    :return: Lista de candidatos normalizados para agrupar identidades
    """
    candidates: list[IdentityCandidate] = []

    identity = character.get("identity") or {}
    local_id = character.get("local_id") or character.get("display_name") or "unknown"

    raw_values: list[str] = []

    for item in identity.get("name_variants") or []:
        value = item.get("value")
        if value:
            raw_values.append(value)

    for mention in identity.get("mentions") or []:
        if mention.get("mention_type") in {"name", "title"}:
            value = mention.get("surface_form")
            if value:
                raw_values.append(value)

    if local_id and not looks_like_generated_local_id(local_id):
        raw_values.append(local_id)

    display_name = character.get("display_name")
    if display_name:
        raw_values.append(display_name)

    seen: set[str] = set()

    for raw_value in raw_values:
        raw_value = raw_value.strip()

        if not raw_value:
            continue

        if looks_like_descriptive_form(raw_value):
            continue

        without_titles, has_title = remove_leading_titles(raw_value)
        normalized = normalize_text(without_titles)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)

        candidates.append(
            IdentityCandidate(
                value=raw_value,
                normalized=normalized,
                without_titles=without_titles,
                token_count=len(without_titles.split()),
                has_title=has_title,
                is_specific_appellation=looks_like_specific_appellation(raw_value),
                source_chunk_index=chunk_index,
                source_local_id=local_id,
            )
        )

    return candidates


def choose_best_canonical_name(candidates: list[IdentityCandidate], fallback: str) -> str:
    """
    Elige el mejor nombre canonico para representar un grupo de personaje.

    :param candidates: Candidatos de identidad disponibles
    :param fallback: Nombre alternativo si no hay candidatos utiles
    :return: Nombre canonico seleccionado
    """
    if not candidates:
        if looks_like_descriptive_form(fallback):
            return "unknown"
        return fallback

    normal_names = [c for c in candidates if not c.has_title and not c.is_specific_appellation]

    pool = normal_names or candidates

    best = sorted(
        pool,
        key=lambda c: (
            c.token_count,
            len(c.without_titles),
            not c.has_title,
        ),
        reverse=True,
    )[0]

    return best.without_titles
