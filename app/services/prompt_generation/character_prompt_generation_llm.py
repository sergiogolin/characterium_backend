from __future__ import annotations

import json
from typing import Any

from app.services.consolidation.character_identity import normalize_text
from app.services.llm.base import BaseLLM
from app.services.llm.json_utils import parse_json_object_response
from app.services.prompts.prompt_loader import load_prompt, render_prompt


class CharacterPromptGenerationLLM:
    def __init__(self, llm: BaseLLM) -> None:
        """
        Inicializa el generador LLM de fichas finales de personaje.

        :param llm: Cliente LLM usado para generar textos finales
        :return: None
        """
        self.llm = llm

    async def generate_character_prompt(
        self,
        character: dict[str, Any],
        book_language: str,
    ) -> dict[str, Any]:
        """
        Genera nombre principal, alias, descripcion y prompt visual de un personaje.

        :param character: Personaje consolidado de entrada
        :param book_language: Idioma en el que deben escribirse los textos
        :return: Resultado normalizado de generacion
        """
        system_prompt = load_prompt("prompt_generation/system.md")
        user_prompt = self._build_user_prompt(
            character=character,
            book_language=book_language,
        )

        response = await self.llm.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        generated = parse_json_object_response(response)
        return self._normalize_response(generated, character)

    def _build_user_prompt(
        self,
        character: dict[str, Any],
        book_language: str,
    ) -> str:
        """
        Construye el prompt de usuario con el personaje consolidado.

        :param character: Personaje consolidado de entrada
        :param book_language: Idioma objetivo de salida
        :return: Prompt renderizado para enviar al LLM
        """
        user_template = load_prompt("prompt_generation/user.md")

        return render_prompt(
            user_template,
            BOOK_LANGUAGE=book_language,
            CHARACTER_JSON=json.dumps(character, ensure_ascii=False, indent=2),
        )

    def _normalize_response(
        self,
        generated: dict[str, Any],
        character: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normaliza la respuesta del LLM para mantener un contrato estable.

        :param generated: Respuesta parseada del LLM
        :param character: Personaje consolidado usado como fallback
        :return: Diccionario con las claves finales esperadas
        """
        main_name = generated.get("main_name")
        if not isinstance(main_name, str) or not main_name.strip():
            main_name = character.get("canonical_name") or character.get("display_name") or "Unknown"

        aliases = generated.get("aliases")
        if not isinstance(aliases, list):
            aliases = []

        normalized_main = normalize_text(main_name)
        clean_aliases = []
        seen_aliases = set()

        for alias in aliases:
            if not isinstance(alias, str):
                continue

            clean_alias = alias.strip()
            normalized_alias = normalize_text(clean_alias)

            if not clean_alias or normalized_alias == normalized_main or normalized_alias in seen_aliases:
                continue

            clean_aliases.append(clean_alias)
            seen_aliases.add(normalized_alias)

        description = generated.get("description")
        if not isinstance(description, str):
            description = ""

        image_prompt = generated.get("image_prompt")
        if not isinstance(image_prompt, str):
            image_prompt = ""

        confidence = generated.get("confidence")
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"

        warnings = generated.get("warnings")
        if not isinstance(warnings, list):
            warnings = []

        clean_warnings = [warning.strip() for warning in warnings if isinstance(warning, str) and warning.strip()]

        return {
            "main_name": main_name.strip(),
            "aliases": clean_aliases,
            "description": description.strip(),
            "image_prompt": image_prompt.strip(),
            "confidence": confidence,
            "warnings": clean_warnings,
        }
