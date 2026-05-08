# Characterium Cast Studio

Backend para analizar manuscritos y extraer personajes de forma asistida por LLM.

La API esta desarrollada con **Python 3.11** y **FastAPI**. Permite subir libros o documentos, extraer texto, dividirlo en chunks narrativos, detectar personajes por fragmentos y consolidar identidades repetidas o ambiguas.

## Estado actual

- Subida de archivos en formatos **TXT**, **PDF**, **EPUB**, **DOC** y **DOCX**.
- Extraccion de texto mediante readers especificos por formato.
- Jobs en memoria para procesamiento asincrono.
- Stream de progreso mediante **Server-Sent Events (SSE)**.
- Chunking jerarquico por capitulos/parrafos, con overlap.
- Filtrado conservador de material no narrativo: indice, copyright, dedicatorias, notas, resenas, etc.
- Extraccion de personajes por chunks usando prompts versionados en `app/core/prompts`.
- Consolidacion de personajes, alias, apelativos, rasgos, relaciones y conflictos.
- Resolucion opcional de ambiguedades con LLM.
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

## Instalacion

Desde la raiz del backend:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Configuracion

La configuracion no secreta vive en `config/app_config.json` y se recarga en caliente cuando cambia el archivo. Ahi puedes tocar provider, modelos, temperaturas, URLs base y flags como `DEBUG_PIPELINE` sin reiniciar el servidor.

Configuracion minima recomendada para Ollama:

```json
{
  "LLM_MODE": "ollama",
  "LLM_MODEL_ID": "llama3.1",
  "LLM_TEMPERATURE": 0.2,
  "OLLAMA_BASE_URL": "http://localhost:11434/v1"
}
```

El archivo `.env` queda reservado para secretos, y tambien se usa como fallback si una clave no existe en el JSON:

```env
LLM_API_KEY=...
OPENROUTER_API_KEY=...
GEMINI_API_KEY=...
HUGGING_FACE_API_KEY=...
```

Providers soportados:

```json
{
  "LLM_MODE": "ollama",
  "OLLAMA_BASE_URL": "http://localhost:11434/v1",

  "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",

  "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",

  "HUGGING_FACE_BASE_URL": "https://router.huggingface.co/v1"
}
```

Las claves de API correspondientes siguen en `.env`:

```env
# Ollama, compatible con cliente OpenAI
OLLAMA_API_KEY=ollama

# Gemini
GEMINI_API_KEY=...

# OpenRouter
OPENROUTER_API_KEY=...

# Hugging Face
HUGGING_FACE_API_KEY=...
```

Tambien se pueden definir modelos distintos por fase. Si una configuracion por fase esta incompleta, el sistema vuelve a la configuracion global.

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

## Ejecucion

```powershell
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

Documentacion interactiva:

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
- La extraccion procesa actualmente un maximo de 8 chunks por subida.
- La API todavia no persiste resultados en base de datos.
- Los prompts de generacion visual existen como concepto en el modelo de salida, pero el flujo actual se centra en extraccion y consolidacion de personajes.

## Proximos pasos sugeridos

- Persistencia de jobs y resultados con SQLite.
- Validacion estricta del JSON devuelto por LLM.
- Endpoint dedicado para generar prompts visuales por personaje.
- Parametrizar limite de chunks y tamano de chunk desde configuracion.
- Mejorar soporte real de `.doc` si se necesitan documentos Word antiguos.
- Tests automaticos para readers, chunking, filtrado y consolidacion.

## Notas tecnicas

- `app/core/jobs.py` implementa el almacen en memoria y el stream SSE.
- `app/core/job_progress.py` centraliza la publicacion de progreso.
- `app/services/llm/llm_config.py` permite configuracion global o por fase.
- `app/services/llm/llm_factory.py` instancia el provider seleccionado.
- Los providers `ollama`, `gemini` y `openrouter` usan `AsyncOpenAI`.
- `hugging_face` usa `AsyncInferenceClient` de `huggingface_hub`.

Characterium Cast Studio queda preparado para evolucionar de MVP a pipeline persistente de casting visual de personajes.
