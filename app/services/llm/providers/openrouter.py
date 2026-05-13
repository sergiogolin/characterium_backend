from __future__ import annotations

import base64

from openai import AsyncOpenAI

from app.services.llm.base import BaseLLM
from app.services.llm.llm_config import LLMConfig


class OpenRouterLLM(BaseLLM):
    def __init__(self, config: LLMConfig) -> None:
        model_id = config.model_id
        api_key = config.api_key

        if not api_key:
            raise RuntimeError("Falta API_KEY para OpenRouter en .env")
        if not model_id:
            raise RuntimeError("Falta MODEL_ID para OpenRouter en .env")
        if not config.base_url:
            raise RuntimeError("Falta BASE_URL para OpenRouter en .env")

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
            raise ValueError("Respuesta vacia del modelo")

        return content

    async def generate_image(self, prompt: str) -> bytes:
        response = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "user", "content": prompt},
            ],
            extra_body={
                "modalities": ["image"],
                "image_config": {
                    "aspect_ratio": "3:4",
                },
            },
        )

        data = response.model_dump()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Respuesta sin choices del modelo de imagen")

        message = choices[0].get("message") or {}
        images = message.get("images") or []
        if not images:
            raise ValueError("Respuesta sin imagenes del modelo")

        image_url = (images[0].get("image_url") or {}).get("url")
        if not image_url or "," not in image_url:
            raise ValueError("Respuesta de imagen invalida del modelo")

        return base64.b64decode(image_url.split(",", 1)[1])
