# app/services/consolidation/character_consolidation_llm.py

from __future__ import annotations

import json
from typing import Any

from app.services.llm.base import BaseLLM
from app.services.llm.json_utils import parse_json_object_response
from app.services.prompts.prompt_loader import load_prompt, render_prompt
from app.services.source_tools.character_source_tools import CharacterSourceTools


class CharacterConsolidationLLM:
    def __init__(self, llm: BaseLLM, source_tools: CharacterSourceTools | None = None) -> None:
        """
        Inicializa el resolvedor LLM de ambiguedades de consolidacion.

        :param llm: Cliente LLM usado para decidir fusiones ambiguas
        :param source_tools: Herramientas opcionales de consulta del texto fuente
        :return: None
        """
        self.llm = llm
        self.source_tools = source_tools

    async def resolve_ambiguity(
        self,
        candidate_a: dict[str, Any],
        candidate_b: dict[str, Any],
        reasons: list[str],
        score: float,
    ) -> dict[str, Any]:
        """
        Pide al LLM decidir si dos candidatos ambiguos representan el mismo personaje.

        :param candidate_a: Primer candidato con datos consolidados relevantes
        :param candidate_b: Segundo candidato con datos consolidados relevantes
        :param reasons: Razones programaticas que motivan la ambiguedad
        :param score: Puntuacion programatica calculada antes del LLM
        :return: Decision normalizada con should_merge, confidence y reason
        """
        system_prompt = load_prompt("character_consolidation/system.md")
        user_prompt = self._build_user_prompt(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            reasons=reasons,
            score=score,
        )

        response = await self.llm.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        decision = parse_json_object_response(response)

        if not isinstance(decision.get("should_merge"), bool):
            decision["should_merge"] = False

        if decision.get("confidence") not in {"low", "medium", "high"}:
            decision["confidence"] = "low"

        if not isinstance(decision.get("reason"), str):
            decision["reason"] = ""

        return decision

    def _build_user_prompt(
        self,
        candidate_a: dict[str, Any],
        candidate_b: dict[str, Any],
        reasons: list[str],
        score: float,
    ) -> str:
        """
        Construye el prompt de usuario con los candidatos y evidencias a comparar.

        :param candidate_a: Primer candidato a comparar
        :param candidate_b: Segundo candidato a comparar
        :param reasons: Razones programaticas de similitud o duda
        :param score: Score programatico asociado a la comparacion
        :return: Prompt de usuario renderizado para enviar al LLM
        """
        user_template = load_prompt("character_consolidation/user.md")

        return render_prompt(
            user_template,
            PROGRAMMATIC_SCORE=score,
            PROGRAMMATIC_REASONS_JSON=json.dumps(reasons, ensure_ascii=False, indent=2),
            CANDIDATE_A_JSON=json.dumps(candidate_a, ensure_ascii=False, indent=2),
            CANDIDATE_B_JSON=json.dumps(candidate_b, ensure_ascii=False, indent=2),
            SOURCE_CONTEXT_JSON=json.dumps(
                self._build_source_context(candidate_a, candidate_b),
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _build_source_context(
        self,
        candidate_a: dict[str, Any],
        candidate_b: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Prepara resultados de herramientas de fuente para el prompt de ambiguedad.
        """
        if not self.source_tools:
            return {}

        names_a = self._identity_terms(candidate_a)
        names_b = self._identity_terms(candidate_b)

        return {
            "candidate_a_source_snippets": self.source_tools.get_source_snippets(
                candidate_a.get("references", []),
                query_terms=names_a,
            ),
            "candidate_b_source_snippets": self.source_tools.get_source_snippets(
                candidate_b.get("references", []),
                query_terms=names_b,
            ),
            "candidate_a_mentions": self.source_tools.find_character_mentions(names_a),
            "candidate_b_mentions": self.source_tools.find_character_mentions(names_b),
        }

    def _identity_terms(self, candidate: dict[str, Any]) -> list[str]:
        terms: list[str] = []

        for value in [
            candidate.get("canonical_name"),
            candidate.get("display_name"),
            *(candidate.get("aliases") or []),
            *(candidate.get("specific_appellations") or []),
        ]:
            if isinstance(value, str) and value.strip():
                terms.append(value.strip())

        for item in candidate.get("identity_names", []) or []:
            value = item.get("value") if isinstance(item, dict) else None
            if isinstance(value, str) and value.strip():
                terms.append(value.strip())

        return terms
