import os
from dotenv import load_dotenv

from app.core.runtime_config import get_config_bool, get_config_str, get_config_value

load_dotenv()


def get_str(name: str, default: str | None = None) -> str:
    val = get_config_str(name, os.getenv(name, default))
    return (val or "").strip()


def get_bool(name: str, default: bool = False) -> bool:
    if get_config_value(name) is not None:
        return get_config_bool(name, default)

    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


LLM_MODE = get_str("LLM_MODE", "ollama")
DEBUG_INGESTION = get_bool("DEBUG_INGESTION", False)
DEBUG_PIPELINE = get_bool("DEBUG_PIPELINE", False)


def is_debug_pipeline_enabled() -> bool:
    load_dotenv(override=True)
    return get_bool("DEBUG_PIPELINE", False)
