from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Ejecuta una llamada de chat al modelo y devuelve el texto crudo.
        """
        raise NotImplementedError
