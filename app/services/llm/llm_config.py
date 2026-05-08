# app/services/llm/config.py

from dataclasses import dataclass
import os

from dotenv import load_dotenv

from app.core.runtime_config import get_config_float, get_config_str

load_dotenv()


@dataclass
class LLMConfig:
    mode: str
    model_id: str
    temperature: float
    base_url: str | None = None
    api_key: str | None = None


_REQUIRED_FIELDS_BY_MODE = {
    "gemini": ("model_id", "api_key"),
    "hugging_face": ("model_id", "api_key"),
    "ollama": ("model_id",),
    "openrouter": ("model_id", "api_key"),
}

_API_KEY_ENV_BY_MODE = {
    "gemini": ("GEMINI_API_KEY",),
    "hugging_face": ("HUGGING_FACE_API_KEY", "HF_TOKEN"),
    "ollama": ("OLLAMA_API_KEY",),
    "openrouter": ("OPEN_ROUTER_API_KEY", "OPENROUTER_API_KEY"),
}

def _has_value(value: str | float | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _has_required_provider_data(config: LLMConfig) -> bool:
    required_fields = _REQUIRED_FIELDS_BY_MODE.get(config.mode)
    if required_fields is None:
        return False

    return all(_has_value(getattr(config, field)) for field in required_fields)


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default

    value = value.strip()
    return value or default


def _config_value(name: str, default: str | None = None) -> str | None:
    value = get_config_str(name)
    if value is not None:
        return value

    return _env_value(name, default)


def _first_env_value(*names: str) -> str | None:
    for name in names:
        value = _env_value(name)
        if value is not None:
            return value

    return None


def _provider_api_key(mode: str, prefix: str | None = None) -> str | None:
    env_names: list[str] = []

    if prefix:
        env_names.append(f"{prefix}_LLM_API_KEY")

    env_names.extend(_API_KEY_ENV_BY_MODE.get(mode, ()))
    env_names.append("LLM_API_KEY")

    return _first_env_value(*env_names)


def _provider_model_id(mode: str, prefix: str | None = None) -> str | None:
    env_names: list[str] = []

    if prefix:
        env_names.append(f"{prefix}_LLM_MODEL_ID")

    env_names.append("LLM_MODEL_ID")

    for name in env_names:
        value = _config_value(name)
        if value is not None:
            return value

    return None


def _env_float(name: str, default: float) -> float:
    config_value = get_config_str(name)
    if config_value is not None:
        return float(config_value)

    value = _env_value(name)
    if value is None:
        return default

    return float(value)


def _read_global_llm_config() -> LLMConfig:
    mode = (_config_value("LLM_MODE", "ollama") or "ollama").lower()

    return LLMConfig(
        mode=mode,
        model_id=_provider_model_id(mode) or "",
        temperature=get_config_float("LLM_TEMPERATURE", _env_float("LLM_TEMPERATURE", 0.2)),
        base_url=_config_value("LLM_BASE_URL"),
        api_key=_provider_api_key(mode),
    )


def get_llm_config(prefix: str | None = None) -> LLMConfig:
    """
    prefix ejemplos:
    - EXTRACTION
    - CONSOLIDATION
    - PROMPT_GENERATION
    """

    global_config = _read_global_llm_config()

    if not prefix:
        return global_config

    mode = (_config_value(f"{prefix}_LLM_MODE", global_config.mode) or global_config.mode).lower()

    prefixed_config = LLMConfig(
        mode=mode,
        model_id=_provider_model_id(mode, prefix) or "",
        temperature=get_config_float(
            f"{prefix}_LLM_TEMPERATURE",
            _env_float(f"{prefix}_LLM_TEMPERATURE", global_config.temperature),
        ),
        base_url=_config_value(f"{prefix}_LLM_BASE_URL"),
        api_key=_provider_api_key(mode, prefix),
    )

    if not _has_required_provider_data(prefixed_config):
        return global_config

    return prefixed_config
