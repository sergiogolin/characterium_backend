from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object_response(content: str) -> dict[str, Any]:
    """
    Parsea un objeto JSON aunque el LLM lo envuelva en markdown o texto.
    """

    cleaned_content = content.strip()

    fenced_match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced_match:
        cleaned_content = fenced_match.group(1).strip()

    try:
        data = json.loads(cleaned_content)
    except json.JSONDecodeError:
        data = json.loads(_extract_first_json_object(cleaned_content))

    if not isinstance(data, dict):
        raise ValueError(f"Respuesta JSON invalida: {type(data)}")

    return data


def _extract_first_json_object(content: str) -> str:
    start = content.find("{")
    if start == -1:
        raise ValueError("La respuesta no contiene un objeto JSON")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(content)):
        char = content[index]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]

    raise ValueError("La respuesta contiene un objeto JSON incompleto")
