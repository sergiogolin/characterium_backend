from pathlib import Path


# Ruta base:
# - Este archivo está en: app/services/llm/prompt_loader.py
# - Los prompts están en: app/core/prompts/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = BASE_DIR / "core" / "prompts"


def load_prompt(relative_path: str) -> str:
    """
    Carga un prompt desde app/prompts usando una ruta relativa.

    Ejemplos de relative_path:
    - "character_extraction/system.md"
    - "character_extraction/user.md"
    """
    path = PROMPTS_DIR / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de prompt: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"La ruta indicada no es un archivo válido: {path}"
        )

    return path.read_text(encoding="utf-8")


def render_prompt(template: str, **kwargs) -> str:
    """
    Reemplaza placeholders del tipo {{variable}} dentro del texto del prompt.

    Ejemplo:
    template = "Hola {{name}}, tu chunk es {{chunk_index}}"
    render_prompt(template, name="Sergio", chunk_index=3)

    Resultado:
    "Hola Sergio, tu chunk es 3"
    """
    result = template

    for key, value in kwargs.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))

    return result


# -----------------------------------------------------------------------------
# EJEMPLOS DE USO
# -----------------------------------------------------------------------------
#
# 1) Cargar un prompt sin variables
#
# system_prompt = load_prompt("character_extraction/system.md")
# print(system_prompt)
#
#
# 2) Cargar un prompt plantilla y rellenarlo con variables
#
# user_template = load_prompt("character_extraction/user.md")
#
# user_prompt = render_prompt(
#     user_template,
#     chunk_index=3,
#     chunk_text="Tom entró en la habitación y Mary lo miró en silencio.",
#     spacy_candidates="Tom, Mary"
# )
#
# print(user_prompt)
#
#
# 3) Ejemplo de contenido de app/prompts/character_extraction/user.md
#
# Analiza el siguiente fragmento.
#
# CHUNK_INDEX: {{chunk_index}}
#
# TEXTO:
# {{chunk_text}}
#
# PERSONAJES DETECTADOS POR SPACY:
# {{spacy_candidates}}
#
#
# 4) Ejemplo típico de uso dentro de un servicio
#
# def build_character_extraction_messages(chunk_index: int, chunk_text: str, spacy_candidates: str) -> dict:
#     system_prompt = load_prompt("character_extraction/system.md")
#     user_template = load_prompt("character_extraction/user.md")
#
#     user_prompt = render_prompt(
#         user_template,
#         chunk_index=chunk_index,
#         chunk_text=chunk_text,
#         spacy_candidates=spacy_candidates,
#     )
#
#     return {
#         "system": system_prompt,
#         "user": user_prompt,
#     }
#
#
# 5) Uso con una llamada a LLM
#
# messages = build_character_extraction_messages(
#     chunk_index=5,
#     chunk_text="El inspector miró a Julia antes de hablar.",
#     spacy_candidates="inspector, Julia"
# )
#
# response = client.responses.create(
#     model="gpt-4.1-mini",
#     input=[
#         {"role": "system", "content": messages["system"]},
#         {"role": "user", "content": messages["user"]},
#     ]
# )
# -----------------------------------------------------------------------------
