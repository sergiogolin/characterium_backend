import json
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.core.config import is_debug_pipeline_enabled
from app.core.job_progress import JobProgressPublisher
from app.core.jobs import InMemoryJobStore
from app.core.types import JobResult
from app.core.status_log_publisher import StatusLogPublisher
from app.services.image_generation.image_generator import ImageGenerator, ImageGenerationError
from app.services.ingestion.upload_reader import FileReadError, read_uploaded_file_data
from app.services.llm.llm_factory import get_consolidation_llm
from app.services.consolidation.character_consolidation_llm import CharacterConsolidationLLM
from app.services.consolidation.character_consolidator import CharacterConsolidator
from app.services.extraction.character_extractor import extract_characters_from_chunks
from app.services.prompt_generation.character_prompt_generator import generate_character_prompts
from app.services.source_tools.character_source_tools import CharacterSourceTools
from app.services.text_processing.chunking_service import ChunkingError, chunk_uploaded_content


jobs = InMemoryJobStore()
app = FastAPI()


# Modelo para el request de generación de imagen
class ImageGenerationRequest(BaseModel):
    prompt: str
    style: str = "fotorrealista"  # Valor por defecto


# Almacenamiento en memoria para estado de generación
_image_generation_status = {}


def _debug_pipeline_print(*values) -> None:
    if is_debug_pipeline_enabled():
        print(*values)


def _detect_book_language(content: str | list[str]) -> str:
    """
    Detecta de forma ligera el idioma principal del texto de entrada.

    :param content: Texto leido del archivo o lista de bloques textuales
    :return: Codigo de idioma usado por el resultado del job
    """
    text = "\n".join(content) if isinstance(content, list) else content
    sample = f" {text[:20000].lower()} "

    spanish_markers = [
        " el ",
        " la ",
        " los ",
        " las ",
        " que ",
        " de ",
        " en ",
        " una ",
        " con ",
        " para ",
        " como ",
        " pero ",
        " por ",
        " del ",
        " se ",
        " no ",
    ]
    english_markers = [
        " the ",
        " and ",
        " that ",
        " of ",
        " in ",
        " to ",
        " with ",
        " for ",
        " as ",
        " but ",
        " by ",
        " from ",
        " was ",
        " were ",
        " not ",
    ]

    spanish_score = sum(sample.count(marker) for marker in spanish_markers)
    english_score = sum(sample.count(marker) for marker in english_markers)

    if spanish_score >= english_score and spanish_score > 0:
        return "es"

    if english_score > spanish_score:
        return "en"

    return "source"


def _book_language_instruction(language: str) -> str:
    """
    Convierte el codigo interno en una instruccion comprensible para el LLM.

    :param language: Codigo detectado
    :return: Etiqueta/instruccion de idioma
    """
    labels = {
        "es": "espanol",
        "en": "ingles",
    }

    return labels.get(language, "el mismo idioma de los datos del personaje")


@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    filename = file.filename or ""
    state = jobs.create()
    jobs.set_running(state.job_id)
    progress = JobProgressPublisher(jobs, state.job_id)

    _debug_pipeline_print("\n" + "=" * 70)
    _debug_pipeline_print(f"Archivo recibido: {filename}")
    _debug_pipeline_print("=" * 70)

    await progress.publish(
        step="reading",
        message="Leyendo el archivo...",
    )

    try:
        data = await file.read()
    except Exception as exc:
        jobs.set_error(state.job_id, str(exc))
        await progress.publish(step="error", message=f"Error leyendo archivo: {exc}")
        return {"job_id": state.job_id}

    background_tasks.add_task(
        process_upload_job,
        job_id=state.job_id,
        filename=filename,
        data=data,
    )

    return {"job_id": state.job_id}


async def process_upload_job(*, job_id: str, filename: str, data: bytes) -> None:
    progress = JobProgressPublisher(jobs, job_id)
    logger = StatusLogPublisher(jobs, job_id)

    try:
        # Evento de prueba inicial
        await progress.publish(
            step="progress",
            message="Inicializando procesamiento...",
            pct=5,
        )

        await logger.append("=" * 60)
        await logger.append(f"📄 Archivo: {filename}")
        await logger.append("=" * 60)

        content = read_uploaded_file_data(filename=filename, data=data)

        if isinstance(content, list):
            _debug_pipeline_print(f"\nReader devolvio {len(content)} bloques")
            total_chars = sum(len(x) for x in content)
            await logger.append(f"✓ Lectura completada: {len(content)} bloques")
        else:
            total_chars = len(content)
            await logger.append(f"✓ Lectura completada: archivo monolítico")

        _debug_pipeline_print(f"Longitud total texto: {total_chars} caracteres")
        await logger.append(f"  Tamaño total: {total_chars:,} caracteres ({total_chars / 1024 / 1024:.2f} MB)")

        await progress.publish(
            step="chunking",
            message="Dividiendo el archivo en chunks...",
        )

        await logger.append("")
        await logger.append("⏳ [1/4] DIVISIÓN EN CHUNKS")
        await logger.append("-" * 60)

        chunks = chunk_uploaded_content(content)
        source_tools = CharacterSourceTools(chunks)
        _debug_pipeline_print(f"\nTotal chunks generados: {len(chunks)}")

        await logger.append(f"✓ {len(chunks)} chunks generados")
        await logger.append(f"  Promedio por chunk: {total_chars // len(chunks):,} caracteres")

        await progress.publish(
            step="chunking",
            message=f"Se han calculado {len(chunks)} chunks.",
        )

        await logger.append("")
        await logger.append("⏳ [2/4] EXTRACCIÓN DE PERSONAJES")
        await logger.append("-" * 60)
        await logger.append("Analizando chunks para extraer personajes...")

        chunk_results = await extract_characters_from_chunks(chunks, progress=progress)
        
        total_mentions = sum(len(cr.get("characters", [])) for cr in chunk_results)
        await logger.append(f"✓ Extracción completada")
        await logger.append(f"  Menciones de personajes encontradas: {total_mentions}")

        await progress.publish(
            step="character_extraction",
            message="Extraccion de personajes completada.",
            pct=95,
        )

        await logger.append("")
        await logger.append("⏳ [3/4] CONSOLIDACIÓN DE PERSONAJES")
        await logger.append("-" * 60)
        await logger.append("Resolviendo aliases y consolidando identidades...")

        await progress.publish(
            step="character_consolidation",
            message="Consolidando personajes extraidos...",
        )

        llm = get_consolidation_llm()
        llm_resolver = CharacterConsolidationLLM(llm, source_tools=source_tools)
        consolidator = CharacterConsolidator(llm_resolver=llm_resolver)

        result = await consolidator.consolidate(chunk_results)

        _debug_pipeline_print("\n\nRESULTADO CONSOLIDACION PERSONAJES:")
        _debug_pipeline_print(json.dumps(result, indent=2, ensure_ascii=False))
        _debug_pipeline_print("-" * 50)

        num_characters = len(result.get("characters", []))
        await logger.append(f"✓ Consolidación completada")
        await logger.append(f"  Personajes únicos identificados: {num_characters}")

        await progress.publish(
            step="character_consolidation",
            message="Consolidacion de personajes completada.",
            pct=97,
        )

        book_language = _detect_book_language(content)
        lang_label = "🇪🇸 Español" if book_language == "es" else "🇺🇸 Inglés" if book_language == "en" else "🌐 Idioma original"
        await logger.append(f"  Idioma detectado: {lang_label}")

        await logger.append("")
        await logger.append("⏳ [4/4] GENERACIÓN DE PROMPTS")
        await logger.append("-" * 60)
        await logger.append(f"Generando prompts para {num_characters} personajes...")

        await progress.publish(
            step="prompt_generation",
            message="Generando fichas y prompts visuales de personajes...",
            pct=97,
        )

        generated_characters = await generate_character_prompts(
            result.get("characters", []),
            book_language=_book_language_instruction(book_language),
            progress=progress,
            source_tools=source_tools,
        )

        await logger.append(f"✓ Prompts generados correctamente")
        await logger.append(f"  Total de prompts: {len(generated_characters)}")

        await progress.publish(
            step="prompt_generation",
            message="Generacion de fichas y prompts visuales completada.",
            pct=99,
        )

        await logger.append("")
        await logger.append("=" * 60)
        await logger.append("✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        await logger.append("=" * 60)

        jobs.set_done(
            job_id,
            JobResult(
                language=book_language,
                characters=result.get("characters", []),
                characters_text="",
                prompts=[],
                generated_characters=generated_characters,
            ),
        )
        await progress.publish(
            step="done",
            message="Pipeline de personajes completado.",
            pct=100,
        )

    except (FileReadError, ChunkingError) as exc:
        await logger.append("")
        await logger.append("❌ ERROR EN EL PROCESAMIENTO")
        await logger.append("-" * 60)
        await logger.append(f"Tipo: {type(exc).__name__}")
        await logger.append(f"Detalle: {str(exc)}")
        jobs.set_error(job_id, str(exc))
        await progress.publish(step="error", message=str(exc))
    except Exception as exc:
        await logger.append("")
        await logger.append("❌ ERROR INESPERADO")
        await logger.append("-" * 60)
        await logger.append(f"Tipo: {type(exc).__name__}")
        await logger.append(f"Detalle: {str(exc)}")
        jobs.set_error(job_id, str(exc))
        await progress.publish(step="error", message=f"Error: {exc}")


@app.post("/api/generate-image")
async def generate_image(
    background_tasks: BackgroundTasks,
    request: ImageGenerationRequest,
):
    """
    Endpoint para generar imágenes de personajes de forma asíncrona.

    Request:
    {
        "prompt": "Descripción del personaje",
        "style": "fotorrealista"  # opcional, default: "fotorrealista"
    }

    Response:
    {
        "jobId": "id-unico",
        "message": "Generación iniciada"
    }
    """
    import uuid
    import time

    job_id = str(uuid.uuid4())
    timestamp = time.time()

    _image_generation_status[job_id] = {
        "status": "processing",
        "prompt": request.prompt,
        "style": request.style,
        "started_at": timestamp,
        "result": None,
        "error": None,
    }

    _debug_pipeline_print("\n" + "=" * 70)
    _debug_pipeline_print(f"Generación de imagen iniciada: {job_id}")
    _debug_pipeline_print(f"Prompt: {request.prompt}")
    _debug_pipeline_print(f"Estilo: {request.style}")
    _debug_pipeline_print("=" * 70)

    background_tasks.add_task(
        _process_image_generation,
        job_id=job_id,
        prompt=request.prompt,
        style=request.style,
    )

    return {
        "jobId": job_id,
        "message": "Generación de imagen iniciada",
    }


async def _process_image_generation(*, job_id: str, prompt: str, style: str) -> None:
    """
    Procesa la generación de imagen en segundo plano.
    """
    try:
        generator = ImageGenerator()

        _debug_pipeline_print(f"Procesando generación de imagen: {job_id}")

        result = await generator.generate_and_save_image(
            prompt=prompt,
            graphic_style=style,
        )

        _image_generation_status[job_id]["status"] = "completed"
        _image_generation_status[job_id]["result"] = result

        _debug_pipeline_print(f"Imagen generada exitosamente: {job_id}")

    except ImageGenerationError as e:
        _image_generation_status[job_id]["status"] = "failed"
        _image_generation_status[job_id]["error"] = str(e)

        _debug_pipeline_print(f"Error generando imagen: {job_id}")
        _debug_pipeline_print(f"Detalles: {str(e)}")

    except Exception as e:
        _image_generation_status[job_id]["status"] = "failed"
        _image_generation_status[job_id]["error"] = f"Error inesperado: {str(e)}"

        _debug_pipeline_print(f"Error inesperado en generación: {job_id}")
        _debug_pipeline_print(f"Detalles: {str(e)}")


@app.get("/api/generate-image/{job_id}")
async def get_image_status(job_id: str):
    """
    Obtiene el estado de una generación de imagen.

    Response si está en proceso:
    {
        "status": "processing",
        "message": "Generando imagen..."
    }

    Response si completó exitosamente:
    {
        "status": "completed",
        "imagePath": "/images/generated/abc123.png",
        "imageUrl": "http://localhost:8000/images/generated/abc123.png"
    }

    Response si falló:
    {
        "status": "failed",
        "error": "Descripción del error"
    }
    """
    if job_id not in _image_generation_status:
        raise HTTPException(404, "Job no encontrado")

    status_info = _image_generation_status[job_id]

    if status_info["status"] == "processing":
        return {
            "status": "processing",
            "message": "Generando imagen...",
        }

    if status_info["status"] == "completed":
        result = status_info["result"]
        return {
            "status": "completed",
            "imagePath": result["imagePath"],
            "imageUrl": result["imageUrl"],
        }

    if status_info["status"] == "failed":
        return {
            "status": "failed",
            "error": status_info["error"],
        }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    st = jobs.get(job_id)
    if not st:
        raise HTTPException(404, "Job no encontrado")
    return st


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    st = jobs.get(job_id)
    if not st:
        raise HTTPException(404, "Job no encontrado")

    return StreamingResponse(
        jobs.sse_lines(job_id),
        media_type="text/event-stream",
    )


def main() -> FastAPI:
    app.title = "Characterium Cast Studio Backend (Mock)"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configurar carpeta de archivos estáticos para imágenes generadas
    public_path = Path(__file__).parent.parent / "public"
    if public_path.exists():
        app.mount("/images", StaticFiles(directory=str(public_path / "images")), name="images")

    return app


main()
