# Characterium Cast Studio

Backend para analizar manuscritos y extraer personajes de forma asistida por LLM.

La API está desarrollada con **Python 3.11** y **FastAPI**. Permite subir libros o documentos, extraer texto, dividirlo en chunks narrativos, detectar personajes por fragmentos y consolidar identidades repetidas o ambiguas.

## Estado actual

- Subida de archivos en formatos **TXT**, **PDF**, **EPUB**, **DOC** y **DOCX**.
- Extracción de texto mediante readers específicos por formato.
- Jobs en memoria para procesamiento asíncrono.
- Stream de progreso mediante **Server-Sent Events (SSE)**.
- Chunking jerárquico por capítulos/párrafos, con overlap.
- Filtrado conservador de material no narrativo: índice, copyright, dedicatorias, notas, reseñas, etc.
- Extracción de personajes por chunks usando prompts versionados en `app/core/prompts`.
- Consolidación de personajes, alias, apelativos, rasgos, relaciones y conflictos.
- Resolución opcional de ambigüedades con LLM.
- Providers LLM configurables por variables de entorno: `ollama`, `gemini`, `openrouter` y `hugging_face`.

## Requisitos

- Windows 11
- Python **3.11**
- PowerShell
- Recomendado: Visual Studio Code

## Estructura real del proyecto

```text
.
+-- app/
|   +-- main.py
|   +-- core/
|   |   +-- config.py
|   |   +-- job_progress.py
|   |   +-- jobs.py
|   |   +-- types.py
|   |   +-- prompts/
|   |       +-- character_extraction/
|   |           +-- system.md
|   |           +-- user.md
|   +-- services/
|       +-- consolidation/
|       +-- extraction/
|       +-- ingestion/
|       |   +-- readers/
|       +-- llm/
|       |   +-- providers/
|       +-- prompts/
|       +-- text_processing/
+-- requirements.txt
+-- start.bat
+-- test.txt
+-- README.md
```

## Instalación

Desde la raiz del backend:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

La configuración se divide en tres piezas:

- `env.example`: plantilla de variables de entorno. No contiene secretos.
- `.env`: archivo local con secretos reales. No debe subirse al repositorio.
- `config/app_config.yml`: configuración no secreta del pipeline LLM.

### Variables de entorno

Copia `env.example` a `.env` antes de arrancar el backend:

```powershell
Copy-Item env.example .env
```

Después, edita `.env` y rellena solo las claves de los proveedores que vayas a usar. No hace falta configurar todas las `API_KEY`.

Ejemplo:

```env
PYTHONDONTWRITEBYTECODE=1

# PROVIDER SECRETS:
OLLAMA_API_KEY=ollama
OPENROUTER_API_KEY=sk-...
GEMINI_API_KEY=
HUGGING_FACE_API_KEY=
```

Para Ollama local normalmente basta con dejar `OLLAMA_API_KEY=ollama`, porque el servidor compatible con OpenAI requiere un valor aunque no valide una clave real.

Claves reconocidas por proveedor:

- `ollama`: `OLLAMA_API_KEY`
- `openrouter`: `OPENROUTER_API_KEY` u `OPEN_ROUTER_API_KEY`
- `gemini`: `GEMINI_API_KEY`
- `hugging_face`: `HUGGING_FACE_API_KEY` o `HF_TOKEN`

También existe `LLM_API_KEY` como fallback genérico si el proveedor seleccionado no tiene una clave específica.

### Configuración de providers

La configuración no secreta vive en `config/app_config.yml` y se recarga en caliente cuando cambia el archivo. Ahí puedes tocar provider, modelos, temperaturas, URLs base y flags como `DEBUG_PIPELINE` sin reiniciar el servidor.

Configuración mínima recomendada para Ollama:

```json
{
  "LLM_MODE": "ollama",
  "LLM_MODEL_ID": "llama3.1",
  "LLM_TEMPERATURE": 0.2,
  "OLLAMA_BASE_URL": "http://localhost:11434/v1"
}
```

Providers soportados y URLs base habituales:

```json
{
  "LLM_MODE": "ollama",
  "OLLAMA_BASE_URL": "http://localhost:11434/v1",

  "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",

  "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",

  "HUGGING_FACE_BASE_URL": "https://router.huggingface.co/v1"
}
```

Para cambiar de proveedor global, modifica `LLM_MODE` y `LLM_MODEL_ID`:

```json
{
  "LLM_MODE": "openrouter",
  "LLM_MODEL_ID": "openrouter/auto",
  "LLM_TEMPERATURE": 0.2,
  "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"
}
```

También se pueden definir providers, modelos y temperaturas distintos por fase. Si una configuración por fase esta incompleta, el sistema vuelve a la configuración global.

```json
{
  "EXTRACTION_LLM_MODE": "ollama",
  "EXTRACTION_LLM_MODEL_ID": "llama3.1",
  "EXTRACTION_LLM_TEMPERATURE": 0.1,

  "CONSOLIDATION_LLM_MODE": "ollama",
  "CONSOLIDATION_LLM_MODEL_ID": "llama3.1",
  "CONSOLIDATION_LLM_TEMPERATURE": 0.0,

  "PROMPT_GENERATION_LLM_MODE": "ollama",
  "PROMPT_GENERATION_LLM_MODEL_ID": "llama3.1",
  "PROMPT_GENERATION_LLM_TEMPERATURE": 0.4
}
```

Las fases configurables son:

- `EXTRACTION`: extracción de personajes por fragmentos.
- `CONSOLIDATION`: consolidación y resolución de identidades ambiguas.
- `PROMPT_GENERATION`: generación de prompts visuales cuando se use ese flujo.

Cada fase puede usar un proveedor diferente, siempre que su `API_KEY` correspondiente esté definida en `.env` si el proveedor la requiere.

## Ejecucion

```powershell
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

Documentación interactiva:

```text
http://localhost:8000/docs
```

El backend tiene CORS habilitado para:

```text
http://localhost:5173
```

## Endpoints

### `POST /upload`

Recibe un archivo como `multipart/form-data` en el campo `file`.

Formatos admitidos:

- `.txt`
- `.pdf`
- `.epub`
- `.doc`
- `.docx`

Respuesta:

```json
{
  "job_id": "..."
}
```

### `GET /jobs/{job_id}`

Devuelve el estado actual del job.

Estados posibles:

- `queued`
- `running`
- `done`
- `error`

Cuando el job termina, `result.characters` contiene los personajes consolidados.

Ejemplo de respuesta final simplificada:

```json
{
  "job_id": "...",
  "status": "done",
  "error": null,
  "result": {
    "language": "es",
    "characters": [],
    "characters_text": "",
    "prompts": []
  }
}
```

### `GET /jobs/{job_id}/events`

Devuelve un stream SSE con eventos de progreso.

Ejemplo:

```text
event: progress
data: {"ts":"...","step":"character_extraction","pct":35,"message":"Extrayendo los personajes del chunk 3/8"}
```

El stream termina cuando llega un evento con `step` igual a `done` o `error`.

## Flujo interno

1. `POST /upload` crea un job en memoria y marca el estado como `running`.
2. FastAPI lanza `process_upload_job` como tarea en segundo plano.
3. `upload_reader` valida el nombre, formato y contenido del archivo.
4. `reader_factory` selecciona el reader adecuado.
5. `chunking_service` divide el texto y descarta chunks no narrativos.
6. `character_extractor` llama al LLM por chunk con los prompts de `app/core/prompts/character_extraction`.
7. `CharacterConsolidator` agrupa identidades, alias, rasgos y relaciones.
8. `CharacterConsolidationLLM` intenta resolver casos ambiguos si hay provider configurado.
9. El job se marca como `done` o `error`.
10. El frontend consulta `/jobs/{job_id}` o escucha `/jobs/{job_id}/events`.

## Resultado de personajes

Cada personaje consolidado puede incluir:

- `canonical_name` y `display_name`
- `entity_type`
- `aliases`
- `specific_appellations`
- `titles_roles_descriptors`
- `references`
- `appearance`
- `personality_behavior`
- `social_context`
- `motivations_goals`
- `scene_context`
- `confidence`
- `needs_llm_review`
- `ambiguity_reasons`

## Limitaciones actuales

- Los jobs se guardan solo en memoria.
- Si se reinicia el servidor, se pierden los jobs activos y completados.
- El procesamiento depende de que el provider LLM devuelva JSON valido.
- La API todavía no persiste resultados en base de datos.
- Los prompts de generación visual existen como concepto en el modelo de salida, pero el flujo actual se centra en extracción y consolidación de personajes.

## Próximos pasos sugeridos

- Persistencia de jobs y resultados con SQLite.
- Validación estricta del JSON devuelto por LLM.
- Endpoint dedicado para generar prompts visuales por personaje.
- Parametrizar límite de chunks y tamano de chunk desde configuración.
- Mejorar soporte real de `.doc` si se necesitan documentos Word antiguos.
- Tests automáticos para readers, chunking, filtrado y consolidación.

## Notas tecnicas

- `app/core/jobs.py` implementa el almacén en memoria y el stream SSE.
- `app/core/job_progress.py` centraliza la publicación de progreso.
- `app/services/llm/llm_config.py` permite configuración global o por fase.
- `app/services/llm/llm_factory.py` instancia el provider seleccionado.
- Los providers `ollama`, `gemini` y `openrouter` usan `AsyncOpenAI`.
- `hugging_face` usa `AsyncInferenceClient` de `huggingface_hub`.

Characterium Cast Studio queda preparado para evolucionar de MVP a pipeline persistente de casting visual de personajes.
