import json

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.config import is_debug_pipeline_enabled
from app.core.job_progress import JobProgressPublisher
from app.core.jobs import InMemoryJobStore
from app.core.types import JobResult
from app.services.ingestion.upload_reader import FileReadError, read_uploaded_file_data
from app.services.llm.llm_factory import get_consolidation_llm
from app.services.consolidation.character_consolidation_llm import CharacterConsolidationLLM
from app.services.consolidation.character_consolidator import CharacterConsolidator
from app.services.extraction.character_extractor import extract_characters_from_chunks
from app.services.text_processing.chunking_service import ChunkingError, chunk_uploaded_content


jobs = InMemoryJobStore()
app = FastAPI()


def _debug_pipeline_print(*values) -> None:
    if is_debug_pipeline_enabled():
        print(*values)


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

    try:
        content = read_uploaded_file_data(filename=filename, data=data)

        if isinstance(content, list):
            _debug_pipeline_print(f"\nReader devolvio {len(content)} bloques")
            total_chars = sum(len(x) for x in content)
        else:
            total_chars = len(content)

        _debug_pipeline_print(f"Longitud total texto: {total_chars} caracteres")

        await progress.publish(
            step="chunking",
            message="Dividiendo el archivo en chunks...",
        )

        chunks = chunk_uploaded_content(content)
        _debug_pipeline_print(f"\nTotal chunks generados: {len(chunks)}")

        await progress.publish(
            step="chunking",
            message=f"Se han calculado {len(chunks)} chunks.",
        )

        chunk_results = await extract_characters_from_chunks(chunks, progress=progress)

        await progress.publish(
            step="character_extraction",
            message="Extraccion de personajes completada.",
            pct=95,
        )

        await progress.publish(
            step="character_consolidation",
            message="Consolidando personajes extraidos...",
        )

        llm = get_consolidation_llm()
        llm_resolver = CharacterConsolidationLLM(llm)
        consolidator = CharacterConsolidator(llm_resolver=llm_resolver)

        result = await consolidator.consolidate(chunk_results)

        _debug_pipeline_print("\n\nRESULTADO CONSOLIDACION PERSONAJES:")
        _debug_pipeline_print(json.dumps(result, indent=2, ensure_ascii=False))
        _debug_pipeline_print("-" * 50)

        await progress.publish(
            step="character_consolidation",
            message="Consolidacion de personajes completada.",
            pct=99,
        )

        jobs.set_done(
            job_id,
            JobResult(
                language="es",
                characters=result.get("characters", []),
                characters_text="",
                prompts=[],
            ),
        )
        await progress.publish(
            step="done",
            message="Pipeline de personajes completado.",
            pct=100,
        )

    except (FileReadError, ChunkingError) as exc:
        jobs.set_error(job_id, str(exc))
        await progress.publish(step="error", message=str(exc))
    except Exception as exc:
        jobs.set_error(job_id, str(exc))
        await progress.publish(step="error", message=f"Error: {exc}")


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

    return app


main()
