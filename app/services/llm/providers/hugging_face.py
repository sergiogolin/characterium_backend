from typing import Any

from huggingface_hub import AsyncInferenceClient

from app.services.llm.base import BaseLLM
from app.services.llm.llm_config import LLMConfig


class HuggingFaceLLM(BaseLLM):

    def __init__(self, config: LLMConfig) -> None:
        model_id = config.model_id
        api_key = config.api_key

        if not api_key:
            raise RuntimeError("Falta API_KEY en .env")
        if not model_id:
            raise RuntimeError("Falta MODEL_ID en .env")

        client_kwargs: dict[str, Any] = {
            "provider": "hf-inference",
            "api_key": api_key,
        }
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
            self._passes_model_per_request = True
        else:
            client_kwargs["model"] = model_id
            self._passes_model_per_request = False

        self.client = AsyncInferenceClient(**client_kwargs)

        self.model_id = model_id
        self.temperature = float(config.temperature)


    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        request_kwargs: dict[str, Any] = {}
        if self._passes_model_per_request:
            request_kwargs["model"] = self.model_id

        response = await self.client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            **request_kwargs,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Respuesta vacia del modelo")

        return content
