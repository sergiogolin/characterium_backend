from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = BASE_DIR / "core" / "prompts"


def load_prompt(relative_path: str) -> str:
    """
    Carga un prompt desde app/core/prompts usando una ruta relativa.

    Ejemplos:
    - "character_extraction/system.md"
    - "character_extraction/user.md"
    - "character_consolidation/system.md"
    - "character_consolidation/user.md"
    """
    path = PROMPTS_DIR / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"No se encontro el archivo de prompt: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"La ruta indicada no es un archivo valido: {path}"
        )

    return path.read_text(encoding="utf-8")


def render_prompt(template: str, **kwargs) -> str:
    """
    Reemplaza placeholders del tipo {{variable}} dentro del texto del prompt.
    """
    result = template

    for key, value in kwargs.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))

    return result
