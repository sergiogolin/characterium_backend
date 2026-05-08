# app/services/consolidation/character_merge.py

from __future__ import annotations

from typing import Any

from app.services.consolidation.character_identity import normalize_text


def make_reference(chunk_index: int, local_id: str) -> dict[str, Any]:
    """
    Construye una referencia minima a la aparicion de un personaje en un chunk.

    :param chunk_index: Indice del chunk donde aparece el personaje
    :param local_id: Identificador local del personaje en ese chunk
    :return: Diccionario de referencia normalizado
    """
    return {
        "chunk_index": chunk_index,
        "local_id": local_id,
    }


def merge_character_groups(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """
    Fusiona los datos de un grupo de personaje fuente dentro de un grupo destino.

    :param target: Grupo consolidado que recibira la informacion
    :param source: Grupo consolidado que se integrara en el destino
    :return: Grupo destino actualizado
    """
    target["references"] = merge_references_bulk(
        target.get("references", []),
        source.get("references", []),
    )

    target["identity_names"] = merge_identity_names(
        target.get("identity_names", []),
        source.get("identity_names", []),
    )

    for identity_name in [source.get("canonical_name"), source.get("display_name")]:
        if identity_name and normalize_text(identity_name) != normalize_text(
            target.get("canonical_name", "")
        ):
            append_unique_string(target["aliases"], identity_name)

    for alias in source.get("aliases", []):
        if normalize_text(alias) != normalize_text(target.get("canonical_name", "")):
            append_unique_string(target["aliases"], alias)

    for appellation in source.get("specific_appellations", []):
        append_unique_string(target["specific_appellations"], appellation)

    target["titles_roles_descriptors"] = merge_object_list_by_value(
        target.get("titles_roles_descriptors", []),
        source.get("titles_roles_descriptors", []),
    )

    for section in ["appearance", "personality_behavior", "social_context", "scene_context"]:
        for key, value in source.get(section, {}).items():
            if isinstance(value, list):
                target[section][key] = merge_object_list_by_value(
                    target[section].get(key, []),
                    value,
                )
            elif isinstance(value, dict):
                target[section][key] = merge_consolidated_field_object(
                    target[section].get(key),
                    value,
                )

    target["motivations_goals"] = merge_object_list_by_value(
        target.get("motivations_goals", []),
        source.get("motivations_goals", []),
    )

    target["needs_llm_review"] = target.get("needs_llm_review", False) or source.get("needs_llm_review", False)

    target["ambiguity_reasons"] = list(
        dict.fromkeys(
            target.get("ambiguity_reasons", []) + source.get("ambiguity_reasons", [])
        )
    )

    return target


def merge_identity_names(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fusiona variantes de identidad observadas y acumula sus referencias.

    :param existing: Variantes ya consolidadas
    :param incoming: Variantes nuevas
    :return: Lista de variantes fusionada por valor normalizado
    """
    merged = existing[:]

    for item in incoming:
        value = item.get("value")
        if not value:
            continue

        merged = merge_identity_name(
            merged,
            value=value,
            name_type=item.get("type", "name"),
            references=item.get("references", []),
        )

    return merged


def merge_identity_name(
    existing: list[dict[str, Any]],
    value: str,
    name_type: str,
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Anade o actualiza una variante de identidad observada.

    :param existing: Variantes ya consolidadas
    :param value: Forma textual observada
    :param name_type: Tipo de forma: name, alias, specific_appellation o title
    :param references: Referencias donde aparece
    :return: Lista de variantes actualizada
    """
    normalized = normalize_text(value)

    for item in existing:
        if normalize_text(item.get("value", "")) != normalized:
            continue

        item["references"] = merge_references_bulk(
            item.get("references", []),
            references,
        )
        item["type"] = choose_stronger_identity_type(
            item.get("type", "name"),
            name_type,
        )
        return existing

    existing.append(
        {
            "value": value,
            "type": name_type,
            "references": references,
        }
    )
    return existing


def choose_stronger_identity_type(existing: str, incoming: str) -> str:
    """
    Conserva el tipo de identidad mas util para seleccion canonica.

    :param existing: Tipo ya registrado
    :param incoming: Tipo entrante
    :return: Tipo con mayor prioridad
    """
    priority = {
        "name": 4,
        "alias": 3,
        "specific_appellation": 2,
        "title": 1,
    }

    if priority.get(incoming, 0) > priority.get(existing, 0):
        return incoming

    return existing


def merge_consolidated_field_object(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Fusiona dos campos simples ya consolidados, conservando conflictos.

    :param existing: Valor consolidado existente
    :param incoming: Valor consolidado entrante
    :return: Campo fusionado o None
    """
    if not incoming or not incoming.get("value"):
        return existing

    if not existing or not existing.get("value"):
        return incoming

    if normalize_text(existing["value"]) == normalize_text(incoming["value"]):
        existing["references"] = merge_references_bulk(
            existing.get("references", []),
            incoming.get("references", []),
        )
        conflicts = merge_conflict_objects(
            existing.get("conflicts", []),
            incoming.get("conflicts", []),
        )
        if conflicts:
            existing["conflicts"] = conflicts
        return existing

    conflict = {
        key: val
        for key, val in incoming.items()
        if key != "conflicts"
    }
    existing["conflicts"] = merge_conflict_objects(
        existing.get("conflicts", []),
        [conflict] + incoming.get("conflicts", []),
    )
    return existing


def merge_conflict_objects(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fusiona conflictos evitando duplicados por valor normalizado.

    :param existing: Conflictos ya registrados
    :param incoming: Conflictos nuevos
    :return: Lista de conflictos fusionada
    """
    by_value: dict[str, dict[str, Any]] = {}

    for item in existing + incoming:
        value = item.get("value")
        if not value:
            continue

        normalized = normalize_text(value)

        if normalized not in by_value:
            by_value[normalized] = item
        else:
            by_value[normalized]["references"] = merge_references_bulk(
                by_value[normalized].get("references", []),
                item.get("references", []),
            )

    return list(by_value.values())


def merge_field_object(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    chunk_index: int,
    local_id: str,
) -> dict[str, Any] | None:
    """
    Fusiona un campo objeto simple, conservando conflictos cuando los valores discrepan.

    :param existing: Valor consolidado existente
    :param incoming: Valor nuevo procedente del chunk actual
    :param chunk_index: Indice del chunk de origen
    :param local_id: Identificador local del personaje de origen
    :return: Objeto fusionado, conflicto registrado o None
    """
    if not incoming or not incoming.get("value"):
        return existing

    clean_incoming = {
        key: val
        for key, val in incoming.items()
        if key != "evidence_quote"
    }

    clean_incoming["references"] = [
        {
            "chunk_index": chunk_index,
            "local_id": local_id,
        }
    ]

    if not existing or not existing.get("value"):
        return clean_incoming

    if normalize_text(existing["value"]) == normalize_text(incoming["value"]):
        existing["references"] = merge_references(
            existing.get("references", []),
            clean_incoming["references"][0],
        )
        return existing

    return {
        "value": existing["value"],
        "source": existing.get("source", "unknown"),
        "references": existing.get("references", []),
        "conflicts": [
            clean_incoming
        ],
    }


def merge_unique_values(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    chunk_index: int,
    local_id: str,
    value_key: str = "value",
) -> list[dict[str, Any]]:
    """
    Fusiona listas de objetos por valor normalizado y acumula sus referencias.

    :param existing: Objetos ya consolidados
    :param incoming: Objetos nuevos procedentes de un chunk
    :param chunk_index: Indice del chunk de origen
    :param local_id: Identificador local del personaje de origen
    :param value_key: Campo usado como clave textual de deduplicacion
    :return: Lista consolidada de objetos unicos
    """
    by_value: dict[str, dict[str, Any]] = {}

    for item in existing:
        value = item.get(value_key)
        if value:
            by_value[normalize_text(value)] = item

    for item in incoming or []:
        value = item.get(value_key)

        if not value:
            continue

        normalized = normalize_text(value)

        clean_item = {
            key: val
            for key, val in item.items()
            if key != "evidence_quote"
        }

        clean_item["references"] = [
            {
                "chunk_index": chunk_index,
                "local_id": local_id,
            }
        ]

        if normalized not in by_value:
            by_value[normalized] = clean_item
        else:
            by_value[normalized]["references"] = merge_references(
                by_value[normalized].get("references", []),
                clean_item["references"][0],
            )

    return list(by_value.values())


def merge_references(existing: list[dict[str, Any]], new_ref: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Fusiona una nueva referencia evitando duplicados por chunk y local_id.

    :param existing: Referencias ya acumuladas
    :param new_ref: Nueva referencia a incorporar
    :return: Lista de referencias actualizada
    """
    key = (new_ref["chunk_index"], new_ref["local_id"])

    existing_keys = {
        (ref["chunk_index"], ref["local_id"])
        for ref in existing
    }

    if key not in existing_keys:
        existing.append(new_ref)

    return existing


def merge_references_bulk(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fusiona varias referencias en una lista existente evitando duplicados.

    :param existing: Referencias ya acumuladas
    :param incoming: Referencias nuevas a incorporar
    :return: Lista de referencias actualizada
    """
    for ref in incoming:
        existing = merge_references(existing, ref)

    return existing


def append_unique_string(target: list[str], value: str) -> None:
    """
    Anade una cadena a una lista si no existe ya con la misma forma normalizada.

    :param target: Lista de cadenas a actualizar
    :param value: Valor candidato a anadir
    :return: None
    """
    normalized = normalize_text(value)

    if not any(normalize_text(existing) == normalized for existing in target):
        target.append(value)


def merge_object_list_by_value(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    value_key: str = "value",
) -> list[dict[str, Any]]:
    """
    Fusiona listas de objetos usando un campo textual como identidad.

    :param existing: Objetos ya acumulados
    :param incoming: Objetos nuevos a incorporar
    :param value_key: Campo usado para comparar objetos
    :return: Lista de objetos fusionada por valor normalizado
    """
    by_value: dict[str, dict[str, Any]] = {}

    for item in existing:
        value = item.get(value_key)
        if value:
            by_value[normalize_text(value)] = item

    for item in incoming:
        value = item.get(value_key)

        if not value:
            existing.append(item)
            continue

        normalized = normalize_text(value)

        if normalized not in by_value:
            by_value[normalized] = item
        else:
            by_value[normalized]["references"] = merge_references_bulk(
                by_value[normalized].get("references", []),
                item.get("references", []),
            )

    return list(by_value.values())
