from __future__ import annotations

from openai import AsyncOpenAI

from app.services.llm.base import BaseLLM
from app.services.llm.llm_config import LLMConfig


class OllamaLLM(BaseLLM):
    def __init__(self, config: LLMConfig) -> None:
        model_id = config.model_id
        api_key = config.api_key or "ollama" # Ollama no requiere API key, pero el cliente OpenAI sí, así que ponemos un valor dummy.

        if not model_id:
            raise RuntimeError("Falta MODEL_ID en .env")
        if not config.base_url:
            raise RuntimeError("Falta BASE_URL para Ollama en .env")

        self.client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=api_key,
        )

        self.model_id = model_id
        self.temperature = float(config.temperature)


    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model_id,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Respuesta vacía del modelo")

        return content
