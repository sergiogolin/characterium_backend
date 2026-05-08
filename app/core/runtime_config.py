from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(os.getenv("APP_CONFIG_PATH", "config/app_config.json"))

_config_cache: dict[str, Any] = {}
_config_mtime_ns: int | None = None


def _load_config() -> dict[str, Any]:
    global _config_cache, _config_mtime_ns

    try:
        stat = CONFIG_PATH.stat()
    except FileNotFoundError:
        _config_cache = {}
        _config_mtime_ns = None
        return _config_cache

    if _config_mtime_ns == stat.st_mtime_ns:
        return _config_cache

    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        loaded = json.load(config_file)

    if not isinstance(loaded, dict):
        raise RuntimeError(f"{CONFIG_PATH} debe contener un objeto JSON")

    _config_cache = loaded
    _config_mtime_ns = stat.st_mtime_ns
    return _config_cache


def get_config_value(name: str, default: Any = None) -> Any:
    return _load_config().get(name, default)


def get_config_str(name: str, default: str | None = None) -> str | None:
    value = get_config_value(name)
    if value is None:
        return default

    value = str(value).strip()
    return value or default


def get_config_float(name: str, default: float) -> float:
    value = get_config_value(name)
    if value is None:
        return default

    return float(value)


def get_config_bool(name: str, default: bool = False) -> bool:
    value = get_config_value(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in ("1", "true", "yes")
