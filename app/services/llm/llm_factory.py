from dataclasses import replace
import os

from app.core.runtime_config import get_config_str
from app.services.llm.llm_config import LLMConfig, get_llm_config
from app.services.llm.providers.gemini import GeminiLLM
from app.services.llm.providers.ollama import OllamaLLM
from app.services.llm.providers.openrouter import OpenRouterLLM
from app.services.llm.providers.hugging_face import HuggingFaceLLM


_BASE_URL_ENV_BY_MODE = {
    "gemini": "GEMINI_BASE_URL",
    "hugging_face": "HUGGING_FACE_BASE_URL",
    "ollama": "OLLAMA_BASE_URL",
    "openrouter": "OPENROUTER_BASE_URL",
}


def _with_provider_base_url(config: LLMConfig) -> LLMConfig:
    env_name = _BASE_URL_ENV_BY_MODE.get(config.mode)
    if not env_name:
        return config

    base_url = config.base_url or get_config_str(env_name) or os.getenv(env_name)
    if not base_url or not base_url.strip():
        raise RuntimeError(f"Falta {env_name} en config/app_config.yml o .env")

    return replace(config, base_url=base_url.strip())


def create_llm(config: LLMConfig):
    config = _with_provider_base_url(config)

    if config.mode == "ollama":
        return OllamaLLM(config)

    if config.mode == "hugging_face":
        return HuggingFaceLLM(config)

    if config.mode == "openrouter":
        return OpenRouterLLM(config)

    if config.mode == "gemini":
        return GeminiLLM(config)

    raise RuntimeError(f"Provider LLM no soportado: {config.mode}")


def get_extraction_llm():
    return create_llm(get_llm_config("EXTRACTION"))


def get_consolidation_llm():
    return create_llm(get_llm_config("CONSOLIDATION"))


def get_prompt_generation_llm():
    return create_llm(get_llm_config("PROMPT_GENERATION"))


def get_image_generation_llm():
    return create_llm(get_llm_config("IMAGE_GENERATION"))
