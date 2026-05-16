# app/services/consolidation/character_consolidator.py

from __future__ import annotations

from typing import Any

from app.services.consolidation.character_consolidation_llm import CharacterConsolidationLLM
from app.services.consolidation.character_identity import (
    IdentityCandidate,
    choose_best_canonical_name,
    extract_identity_candidates,
    looks_like_descriptive_form,
    normalize_for_alias_comparison,
    normalize_text,
)
from app.services.consolidation.character_identity_scoring import score_identity_match
from app.services.consolidation.character_merge import (
    make_reference,
    merge_character_groups,
    merge_field_object,
    merge_identity_name,
    merge_references,
    merge_unique_values,
)


class CharacterConsolidator:
    def __init__(self, llm_resolver: CharacterConsolidationLLM | None = None) -> None:
        """
        Inicializa el consolidador de personajes con un resolvedor LLM opcional.

        :param llm_resolver: Servicio opcional para resolver grupos ambiguos
        :return: None
        """
        self.llm_resolver = llm_resolver

    async def consolidate(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Consolida personajes extraidos de varios chunks en identidades unificadas.

        :param chunks: Chunks procesados con listas de personajes extraidos
        :return: Diccionario con personajes consolidados y grupos ambiguos restantes
        """
        groups: dict[str, dict[str, Any]] = {}
        ambiguous_groups: list[dict[str, Any]] = []

        for chunk in chunks:
            characters = chunk.get("characters") or []

            if not characters:
                continue

            chunk_index = chunk.get("chunk_index", 0)

            for character in characters:
                candidates = extract_identity_candidates(character, chunk_index)
                fallback_name = character.get("display_name") or character.get("local_id") or "unknown"

                canonical_name = choose_best_canonical_name(candidates, fallback=fallback_name)
                group_key = self._build_group_key(candidates, canonical_name)

                local_id = character.get("local_id") or fallback_name

                if group_key not in groups:
                    groups[group_key] = self._create_group(
                        canonical_name=canonical_name,
                        character=character,
                        candidates=candidates,
                        chunk_index=chunk_index,
                        local_id=local_id,
                    )
                else:
                    self._merge_character_into_group(
                        group=groups[group_key],
                        character=character,
                        candidates=candidates,
                        chunk_index=chunk_index,
                        local_id=local_id,
                    )

        consolidated = list(groups.values())

        consolidated, ambiguous_groups = await self._merge_until_stable(consolidated)

        self._apply_unresolved_ambiguity_flags(consolidated, ambiguous_groups)

        for character in consolidated:
            self._update_canonical_identity(character)

        for character in consolidated:
            self._mark_conflicts(character)

        for character in consolidated:
            self._update_final_confidence(character)

        return {
            "characters": consolidated,
            "ambiguous_groups": ambiguous_groups,
        }

    async def _merge_until_stable(
        self,
        characters: list[dict[str, Any]],
        max_iterations: int = 5,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Repite fusiones hasta que no cambie el numero de personajes o se alcance el limite.

        :param characters: Grupos consolidados iniciales
        :param max_iterations: Numero maximo de pasadas de fusion
        :return: Tupla con personajes estabilizados y ambiguedades pendientes
        """
        all_ambiguous_groups: list[dict[str, Any]] = []

        for _ in range(max_iterations):
            previous_count = len(characters)

            characters, ambiguous_groups = self._merge_similar_groups(characters)

            if self.llm_resolver and ambiguous_groups:
                characters, unresolved = await self._resolve_ambiguous_groups_with_llm(
                    characters,
                    ambiguous_groups,
                )
                all_ambiguous_groups = unresolved
            else:
                all_ambiguous_groups = ambiguous_groups

            if len(characters) == previous_count:
                break

        return characters, all_ambiguous_groups

    def _merge_similar_groups(
        self,
        characters: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Fusiona grupos claramente equivalentes y separa los casos ambiguos.

        :param characters: Lista de grupos consolidados a comparar
        :return: Tupla con grupos fusionados y grupos que requieren revision
        """
        merged: list[dict[str, Any]] = []
        consumed_indexes: set[int] = set()
        ambiguous_groups: list[dict[str, Any]] = []

        for i, current in enumerate(characters):
            if i in consumed_indexes:
                continue

            base = current

            for j in range(i + 1, len(characters)):
                if j in consumed_indexes:
                    continue

                candidate = characters[j]
                match = score_identity_match(base, candidate)

                if match.should_merge:
                    base = merge_character_groups(base, candidate)
                    consumed_indexes.add(j)

                elif match.needs_llm_review:
                    ambiguous_groups.append(
                        {
                            "candidate_a": {
                                "canonical_name": base["canonical_name"],
                                "display_name": base.get("display_name"),
                                "aliases": base.get("aliases", []),
                                "identity_names": base.get("identity_names", []),
                                "specific_appellations": base.get("specific_appellations", []),
                                "references": base.get("references", []),
                            },
                            "candidate_b": {
                                "canonical_name": candidate["canonical_name"],
                                "display_name": candidate.get("display_name"),
                                "aliases": candidate.get("aliases", []),
                                "identity_names": candidate.get("identity_names", []),
                                "specific_appellations": candidate.get("specific_appellations", []),
                                "references": candidate.get("references", []),
                            },
                            "score": match.score,
                            "reasons": match.reasons,
                        }
                    )

            merged.append(base)

        return merged, ambiguous_groups

    async def _resolve_ambiguous_groups_with_llm(
        self,
        characters: list[dict[str, Any]],
        ambiguous_groups: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Usa el LLM para resolver grupos ambiguos que el scoring no puede decidir solo.

        :param characters: Grupos consolidados disponibles
        :param ambiguous_groups: Pares ambiguos pendientes de decision
        :return: Tupla con personajes actualizados y ambiguedades no resueltas
        """
        unresolved: list[dict[str, Any]] = []

        for ambiguous in ambiguous_groups:
            name_a = ambiguous["candidate_a"]["canonical_name"]
            name_b = ambiguous["candidate_b"]["canonical_name"]

            character_a = self._find_character_by_name(characters, name_a)
            character_b = self._find_character_by_name(characters, name_b)

            if not character_a or not character_b:
                unresolved.append(ambiguous)
                continue

            try:
                decision = await self.llm_resolver.resolve_ambiguity(
                    candidate_a=self._build_llm_candidate_payload(character_a),
                    candidate_b=self._build_llm_candidate_payload(character_b),
                    reasons=ambiguous.get("reasons", []),
                    score=ambiguous.get("score", 0.0),
                )
            except Exception as exc:
                ambiguous["llm_error"] = str(exc)
                unresolved.append(ambiguous)
                continue

            should_merge = decision.get("should_merge") is True

            if should_merge:
                character_a = merge_character_groups(character_a, character_b)
                characters.remove(character_b)

                character_a["needs_llm_review"] = False
                character_a["confidence"] = decision.get("confidence", "medium")
                character_a["ambiguity_reasons"].append(
                    f"LLM merged with '{name_b}': {decision.get('reason', '')}"
                )
            else:
                ambiguous["llm_decision"] = decision

        return characters, unresolved

    def _apply_unresolved_ambiguity_flags(
        self,
        characters: list[dict[str, Any]],
        ambiguous_groups: list[dict[str, Any]],
    ) -> None:
        """
        Marca solo las ambiguedades que no han sido resueltas por reglas ni por LLM.

        :param characters: Personajes consolidados finales
        :param ambiguous_groups: Pares ambiguos todavia pendientes
        :return: None
        """
        for ambiguous in ambiguous_groups:
            name_a = ambiguous["candidate_a"]["canonical_name"]
            name_b = ambiguous["candidate_b"]["canonical_name"]

            character_a = self._find_character_by_name(characters, name_a)
            character_b = self._find_character_by_name(characters, name_b)

            if character_a:
                character_a["needs_llm_review"] = True
                character_a["confidence"] = "low"
                character_a["ambiguity_reasons"].append(
                    f"Possible same character as '{name_b}'"
                )

            if character_b:
                character_b["needs_llm_review"] = True
                character_b["confidence"] = "low"
                character_b["ambiguity_reasons"].append(
                    f"Possible same character as '{name_a}'"
                )

    def _build_group_key(
        self,
        candidates: list[IdentityCandidate],
        canonical_name: str,
    ) -> str:
        """
        Construye la clave inicial de agrupacion para un personaje.

        :param candidates: Candidatos de identidad detectados para el personaje
        :param canonical_name: Nombre canonico elegido como fallback
        :return: Clave normalizada usada para agrupar personajes
        """
        if candidates:
            best = choose_best_canonical_name(candidates, fallback=canonical_name)
            return normalize_text(best)

        return normalize_text(canonical_name)

    def _create_group(
        self,
        canonical_name: str,
        character: dict[str, Any],
        candidates: list[IdentityCandidate],
        chunk_index: int,
        local_id: str,
    ) -> dict[str, Any]:
        """
        Crea la estructura base de un grupo consolidado a partir de un personaje.

        :param canonical_name: Nombre canonico del nuevo grupo
        :param character: Personaje extraido que origina el grupo
        :param candidates: Candidatos de identidad del personaje
        :param chunk_index: Indice del chunk de origen
        :param local_id: Identificador local del personaje de origen
        :return: Grupo consolidado inicializado y rellenado
        """
        reference_type = character.get("reference_type", "descriptive")

        group = {
            "canonical_name": canonical_name,
            "display_name": canonical_name,
            "entity_type": "named" if reference_type == "named" else "descriptive",
            "aliases": [],
            "identity_names": [],
            "specific_appellations": [],
            "titles_roles_descriptors": [],
            "references": [
                make_reference(chunk_index, local_id)
            ],
            "appearance": {
                "gender": None,
                "apparent_age": None,
                "physical_traits": [],
                "clothing_accessories": [],
                "distinctive_markers": [],
            },
            "personality_behavior": {
                "personality_traits": [],
                "emotional_state": [],
                "behavioral_tendencies": [],
            },
            "social_context": {
                "role_status": [],
                "relationships": [],
            },
            "motivations_goals": [],
            "scene_context": {
                "locations": [],
                "actions": [],
                "notes": [],
            },
            "confidence": "medium",
            "needs_llm_review": False,
            "ambiguity_reasons": [],
        }

        self._merge_identity(group, character, candidates)
        self._merge_character_into_group(group, character, candidates, chunk_index, local_id)

        return group

    def _merge_character_into_group(
        self,
        group: dict[str, Any],
        character: dict[str, Any],
        candidates: list[IdentityCandidate],
        chunk_index: int,
        local_id: str,
    ) -> None:
        """
        Integra los atributos extraidos de un personaje dentro de un grupo consolidado.

        :param group: Grupo consolidado que recibira los datos
        :param character: Personaje extraido desde un chunk
        :param candidates: Candidatos de identidad del personaje
        :param chunk_index: Indice del chunk de origen
        :param local_id: Identificador local del personaje de origen
        :return: None
        """
        group["references"] = merge_references(
            group["references"],
            make_reference(chunk_index, local_id),
        )

        self._merge_identity(group, character, candidates)

        appearance = character.get("appearance") or {}
        group["appearance"]["gender"] = merge_field_object(
            group["appearance"].get("gender"),
            appearance.get("gender"),
            chunk_index,
            local_id,
        )
        group["appearance"]["apparent_age"] = merge_field_object(
            group["appearance"].get("apparent_age"),
            appearance.get("apparent_age"),
            chunk_index,
            local_id,
        )
        group["appearance"]["physical_traits"] = merge_unique_values(
            group["appearance"]["physical_traits"],
            appearance.get("physical_traits") or [],
            chunk_index,
            local_id,
        )
        group["appearance"]["clothing_accessories"] = merge_unique_values(
            group["appearance"]["clothing_accessories"],
            appearance.get("clothing_accessories") or [],
            chunk_index,
            local_id,
        )
        group["appearance"]["distinctive_markers"] = merge_unique_values(
            group["appearance"]["distinctive_markers"],
            appearance.get("distinctive_markers") or [],
            chunk_index,
            local_id,
        )

        personality = character.get("personality_behavior") or {}
        group["personality_behavior"]["personality_traits"] = merge_unique_values(
            group["personality_behavior"]["personality_traits"],
            personality.get("personality_traits") or [],
            chunk_index,
            local_id,
        )
        group["personality_behavior"]["emotional_state"] = merge_unique_values(
            group["personality_behavior"]["emotional_state"],
            personality.get("emotional_state") or [],
            chunk_index,
            local_id,
        )
        group["personality_behavior"]["behavioral_tendencies"] = merge_unique_values(
            group["personality_behavior"]["behavioral_tendencies"],
            personality.get("behavioral_tendencies") or [],
            chunk_index,
            local_id,
        )

        social = character.get("social_context") or {}
        group["social_context"]["role_status"] = merge_unique_values(
            group["social_context"]["role_status"],
            social.get("role_status") or [],
            chunk_index,
            local_id,
        )
        group["social_context"]["relationships"] = merge_unique_values(
            group["social_context"]["relationships"],
            social.get("relationships") or [],
            chunk_index,
            local_id,
            value_key="relation",
        )

        group["motivations_goals"] = merge_unique_values(
            group["motivations_goals"],
            character.get("motivations_goals") or [],
            chunk_index,
            local_id,
        )

        scene = character.get("scene_context") or {}
        group["scene_context"]["locations"] = merge_unique_values(
            group["scene_context"]["locations"],
            scene.get("locations") or [],
            chunk_index,
            local_id,
        )
        group["scene_context"]["actions"] = merge_unique_values(
            group["scene_context"]["actions"],
            scene.get("actions") or [],
            chunk_index,
            local_id,
        )
        group["scene_context"]["notes"] = merge_unique_values(
            group["scene_context"]["notes"],
            scene.get("notes") or [],
            chunk_index,
            local_id,
        )

    def _merge_identity(
        self,
        group: dict[str, Any],
        character: dict[str, Any],
        candidates: list[IdentityCandidate],
    ) -> None:
        """
        Fusiona nombres, alias, apelativos y descriptores de identidad en un grupo.

        :param group: Grupo consolidado que recibira la identidad
        :param character: Personaje extraido del que leer identidad
        :param candidates: Candidatos de identidad ya calculados
        :return: None
        """
        canonical_normalized = normalize_for_alias_comparison(group["canonical_name"])

        for candidate in candidates:
            value_normalized = normalize_for_alias_comparison(candidate.without_titles)

            if looks_like_descriptive_form(candidate.without_titles):
                continue

            if candidate.is_specific_appellation:
                self._merge_identity_name(
                    group,
                    value=candidate.value,
                    name_type="specific_appellation",
                    chunk_index=candidate.source_chunk_index,
                    local_id=candidate.source_local_id,
                )
                self._append_unique(group["specific_appellations"], candidate.value)
                continue

            if candidate.has_title:
                self._merge_identity_name(
                    group,
                    value=candidate.value,
                    name_type="title",
                    chunk_index=candidate.source_chunk_index,
                    local_id=candidate.source_local_id,
                )
                self._merge_identity_name(
                    group,
                    value=candidate.without_titles,
                    name_type="name",
                    chunk_index=candidate.source_chunk_index,
                    local_id=candidate.source_local_id,
                )
                continue

            self._merge_identity_name(
                group,
                value=candidate.without_titles,
                name_type="name",
                chunk_index=candidate.source_chunk_index,
                local_id=candidate.source_local_id,
            )

            if value_normalized != canonical_normalized:
                self._append_unique(group["aliases"], candidate.without_titles)

        identity = character.get("identity") or {}

        for item in identity.get("titles_roles_descriptors") or []:
            value = item.get("value")
            if value:
                clean_item = {
                    key: val
                    for key, val in item.items()
                    if key != "evidence_quote"
                }
                self._append_unique_object(
                    group["titles_roles_descriptors"],
                    clean_item,
                    key="value",
                )

    def _merge_identity_name(
        self,
        group: dict[str, Any],
        value: str,
        name_type: str,
        chunk_index: int,
        local_id: str,
    ) -> None:
        """
        Registra una forma observada de identidad con su referencia de origen.

        :param group: Grupo consolidado que recibira la variante
        :param value: Forma textual observada
        :param name_type: Tipo de forma: name, alias, specific_appellation o title
        :param chunk_index: Indice de chunk de origen
        :param local_id: Identificador local de origen
        :return: None
        """
        if not value:
            return

        group["identity_names"] = merge_identity_name(
            group.get("identity_names", []),
            value=value,
            name_type=name_type,
            references=[make_reference(chunk_index, local_id)],
        )

    def _update_canonical_identity(self, character: dict[str, Any]) -> None:
        """
        Recalcula el nombre canonico desde todas las variantes consolidadas.

        :param character: Personaje consolidado a actualizar
        :return: None
        """
        identity_names = character.get("identity_names", [])
        valid_names = [
            item
            for item in identity_names
            if self._is_valid_canonical_identity_name(item)
        ]

        if not valid_names:
            return

        best_name = sorted(
            valid_names,
            key=self._canonical_identity_score,
            reverse=True,
        )[0]["value"]

        previous_name = character.get("canonical_name")

        character["canonical_name"] = best_name
        character["display_name"] = best_name

        if previous_name and normalize_for_alias_comparison(previous_name) != normalize_for_alias_comparison(best_name):
            self._append_unique(character["aliases"], previous_name)

        self._sync_identity_alias_lists(character)

    def _is_valid_canonical_identity_name(self, item: dict[str, Any]) -> bool:
        """
        Decide si una variante puede actuar como nombre canonico final.

        :param item: Variante de identidad observada
        :return: True si es una candidata canonica util
        """
        value = item.get("value", "")
        normalized = normalize_text(value)

        if not value or looks_like_descriptive_form(value):
            return False

        if normalized in {"unknown", "desconocido", "personaje", "character"}:
            return False

        return item.get("type") != "title"

    def _canonical_identity_score(self, item: dict[str, Any]) -> tuple[int, int, int, int]:
        """
        Puntua una variante para elegir el nombre mas representativo.

        :param item: Variante de identidad observada
        :return: Tupla ordenable de prioridad
        """
        value = item.get("value", "")
        normalized = normalize_text(value)
        type_priority = {
            "name": 4,
            "alias": 3,
            "specific_appellation": 2,
            "title": 1,
        }

        return (
            type_priority.get(item.get("type", "name"), 0),
            len(normalized.split()),
            len(value),
            len(item.get("references", [])),
        )

    def _sync_identity_alias_lists(self, character: dict[str, Any]) -> None:
        """
        Sincroniza alias y apelativos desde el registro completo de identidad.

        :param character: Personaje consolidado a actualizar
        :return: None
        """
        canonical_normalized = normalize_for_alias_comparison(character.get("canonical_name", ""))

        for item in character.get("identity_names", []):
            value = item.get("value")
            if not value or normalize_for_alias_comparison(value) == canonical_normalized:
                continue

            if item.get("type") == "specific_appellation":
                self._append_unique(character["specific_appellations"], value)
            elif item.get("type") in {"name", "alias"}:
                self._append_unique(character["aliases"], value)

        character["aliases"] = [
            alias
            for alias in character.get("aliases", [])
            if normalize_for_alias_comparison(alias) != canonical_normalized
        ]

    def _mark_conflicts(self, character: dict[str, Any]) -> None:
        """
        Marca un personaje para revision si contiene conflictos consolidados relevantes.

        :param character: Personaje consolidado a inspeccionar
        :return: None
        """
        conflict_paths = []

        gender = character.get("appearance", {}).get("gender")
        age = character.get("appearance", {}).get("apparent_age")

        if isinstance(gender, dict) and gender.get("conflicts"):
            conflict_paths.append("appearance.gender")

        if isinstance(age, dict) and age.get("conflicts"):
            conflict_paths.append("appearance.apparent_age")

        if conflict_paths:
            character["needs_llm_review"] = True
            character["confidence"] = "low"
            character["ambiguity_reasons"].append(
                "Conflicting consolidated attributes: " + ", ".join(conflict_paths)
            )

    def _update_final_confidence(self, character: dict[str, Any]) -> None:
        """
        Calcula la confianza final de un personaje consolidado segun evidencias y conflictos.

        :param character: Personaje consolidado a actualizar
        :return: None
        """
        if character.get("needs_llm_review"):
            character["confidence"] = "low"
            return

        references_count = len(character.get("references", []))
        aliases_count = len(character.get("aliases", []))
        has_conflicts = bool(character.get("ambiguity_reasons"))

        if has_conflicts:
            character["confidence"] = "low"
        elif references_count >= 3 or aliases_count >= 2:
            character["confidence"] = "high"
        else:
            character["confidence"] = "medium"

    def _find_character_by_name(
        self,
        characters: list[dict[str, Any]],
        canonical_name: str,
    ) -> dict[str, Any] | None:
        """
        Busca un personaje consolidado por nombre canonico normalizado.

        :param characters: Lista de personajes consolidados
        :param canonical_name: Nombre canonico a localizar
        :return: Personaje encontrado o None si no existe
        """
        normalized_name = normalize_text(canonical_name)

        for character in characters:
            if normalize_text(character.get("canonical_name", "")) == normalized_name:
                return character

        return None

    def _build_llm_candidate_payload(
        self,
        character: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Construye el subconjunto de datos de un personaje que se envia al LLM.

        :param character: Personaje consolidado de origen
        :return: Payload reducido y serializable para comparar identidades
        """
        return {
            "canonical_name": character.get("canonical_name"),
            "display_name": character.get("display_name"),
            "entity_type": character.get("entity_type"),
            "aliases": character.get("aliases", []),
            "identity_names": character.get("identity_names", []),
            "specific_appellations": character.get("specific_appellations", []),
            "titles_roles_descriptors": character.get("titles_roles_descriptors", []),
            "references": character.get("references", []),
            "appearance": character.get("appearance", {}),
            "personality_behavior": character.get("personality_behavior", {}),
            "social_context": character.get("social_context", {}),
            "motivations_goals": character.get("motivations_goals", []),
            "scene_context": character.get("scene_context", {}),
        }

    def _append_unique(self, target: list[str], value: str) -> None:
        """
        Anade un texto a una lista evitando duplicados normalizados.

        :param target: Lista de textos a actualizar
        :param value: Texto candidato a anadir
        :return: None
        """
        normalized = normalize_text(value)

        if not any(normalize_text(existing) == normalized for existing in target):
            target.append(value)

    def _append_unique_object(
        self,
        target: list[dict[str, Any]],
        item: dict[str, Any],
        key: str,
    ) -> None:
        """
        Anade un objeto a una lista si su clave textual no existe ya normalizada.

        :param target: Lista de objetos a actualizar
        :param item: Objeto candidato a anadir
        :param key: Campo usado para comparar duplicados
        :return: None
        """
        value = item.get(key)

        if not value:
            return

        normalized = normalize_text(value)

        if not any(normalize_text(existing.get(key, "")) == normalized for existing in target):
            target.append(item)

