# app/services/consolidation/character_consolidation_llm.py

from __future__ import annotations

import json
from typing import Any

from app.services.llm.base import BaseLLM
from app.services.llm.json_utils import parse_json_object_response


class CharacterConsolidationLLM:
    def __init__(self, llm: BaseLLM) -> None:
        """
        Inicializa el resolvedor LLM de ambiguedades de consolidacion.

        :param llm: Cliente LLM usado para decidir fusiones ambiguas
        :return: None
        """
        self.llm = llm

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
        developer_prompt = self._build_developer_prompt()
        user_prompt = self._build_user_prompt(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            reasons=reasons,
            score=score,
        )

        response = await self.llm.call_llm(
            system_prompt=developer_prompt,
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

    def _build_developer_prompt(self) -> str:
        """
        Construye el prompt de sistema para evaluar ambiguedades de identidad.

        :return: Prompt con reglas de consolidacion y formato JSON esperado
        """
        return """
Eres un sistema experto en consolidación de personajes literarios.

Tu tarea es decidir si dos referencias extraídas de una obra narrativa corresponden al mismo personaje.

Reglas obligatorias:
1. Devuelve SOLO JSON válido.
2. No escribas texto fuera del JSON.
3. No inventes información.
4. Usa únicamente los datos proporcionados.
5. No fusiones personajes si hay contradicciones fuertes de identidad, género, edad, rol o contexto.
6. Los pronombres son evidencia débil.
7. Los títulos, cargos o descriptores no cuentan como alias, pero pueden ayudar a identificar.
8. Nombres parciales pueden corresponder al mismo personaje si son compatibles con nombres completos.
9. Apelativos específicos como "el Mago Gris" o "la Reina Roja" pueden identificar a un personaje.
10. Ante duda real, devuelve should_merge=false.

Formato obligatorio:
{
  "should_merge": true,
  "confidence": "high",
  "reason": "explicación breve"
}
""".strip()

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
        :return: Payload JSON serializado para enviar al LLM
        """
        payload = {
            "programmatic_score": score,
            "programmatic_reasons": reasons,
            "candidate_a": candidate_a,
            "candidate_b": candidate_b,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2)
