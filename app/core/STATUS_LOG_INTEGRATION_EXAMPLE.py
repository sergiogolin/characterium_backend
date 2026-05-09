"""
EJEMPLO COMPLETO: Integración de StatusLogPublisher en process_upload_job

Este archivo muestra cómo integrar StatusLogPublisher en la función
process_upload_job existente en main.py para ver logs en tiempo real
en el div "stat-bot" del frontend.
"""

# PASO 1: Importar la clase en main.py
# =====================================
# from app.core.status_log_publisher import StatusLogPublisher


# PASO 2: Modificar la función process_upload_job
# ================================================

async def process_upload_job_EJEMPLO(
    *, job_id: str, filename: str, data: bytes
) -> None:
    """VERSIÓN CON LOGS"""
    progress = JobProgressPublisher(jobs, job_id)
    logger = StatusLogPublisher(jobs, job_id)  # ← NUEVA LÍNEA
    
    try:
        # Log inicial
        await logger.append(f"📄 Archivo: {filename}")
        
        # Leer archivo
        content = read_uploaded_file_data(filename=filename, data=data)
        await logger.append("✓ Archivo leído correctamente")
        
        if isinstance(content, list):
            await logger.append(f"  → {len(content)} bloques detectados")
            total_chars = sum(len(x) for x in content)
        else:
            total_chars = len(content)
        
        await logger.append(f"  → {total_chars:,} caracteres totales")
        
        # Progreso en barra (mantiene la barra de progreso)
        await progress.publish(
            step="reading",
            message="Archivo leído",
            pct=20
        )
        
        # Chunking
        await logger.append("⏳ Dividiendo en chunks...")
        chunks = chunk_uploaded_content(content)
        await logger.append(f"✓ {len(chunks)} chunks generados")
        
        source_tools = CharacterSourceTools(chunks)
        
        await progress.publish(
            step="chunking",
            message=f"{len(chunks)} chunks",
            pct=30
        )
        
        # Extracción de personajes
        await logger.append("🔍 Extrayendo personajes...")
        chunk_results = await extract_characters_from_chunks(
            chunks, progress=progress
        )
        await logger.append(f"✓ Extracción completada")
        
        # Consolidación
        await logger.append("🔗 Consolidando personajes...")
        llm = get_consolidation_llm()
        llm_resolver = CharacterConsolidationLLM(
            llm, source_tools=source_tools
        )
        consolidator = CharacterConsolidator(llm_resolver=llm_resolver)
        
        result = await consolidator.consolidate(chunk_results)
        await logger.append(f"✓ {len(result)} personajes únicos identificados")
        
        await progress.publish(
            step="character_consolidation",
            message="Consolidación completada",
            pct=75
        )
        
        # Generación de prompts
        await logger.append("✍️  Generando prompts...")
        book_language = _detect_book_language(content)
        
        prompts = await generate_character_prompts(
            result,
            language=book_language,
            progress=progress,
        )
        await logger.append(f"✓ {len(prompts)} prompts generados")
        
        # Finalización
        await logger.append("=" * 50)
        await logger.append("✅ PROCESAMIENTO COMPLETADO")
        
        jobs.set_result(
            job_id,
            JobResult(
                characters_text="\n".join([c.get("name", "") for c in result]),
                prompts=prompts,
            )
        )
        
        await progress.publish(
            step="done",
            message="Procesamiento completado",
            pct=100
        )
        
    except Exception as exc:
        # Log de error
        await logger.append(f"❌ ERROR: {str(exc)}")
        await logger.append_multiline(
            "Detalles del error:\n" + traceback.format_exc()
        )
        jobs.set_error(job_id, str(exc))
        await progress.publish(step="error", message=f"Error: {exc}")


# COMPARATIVA: Sin logs vs Con logs
# ==================================
# 
# SIN LOGS:
# ---------
# Usuario sube archivo → barra de progreso se mueve → resultado
# 
# CON LOGS (RECOMENDADO):
# ----------------------
# Usuario sube archivo → ve cada paso en el div "stat-bot":
#   📄 Archivo: mi_novela.pdf
#   ✓ Archivo leído correctamente
#     → 12 bloques detectados
#     → 245,892 caracteres totales
#   ⏳ Dividiendo en chunks...
#   ✓ 523 chunks generados
#   🔍 Extrayendo personajes...
#   ✓ Extracción completada
#   🔗 Consolidando personajes...
#   ✓ 42 personajes únicos identificados
#   ✍️  Generando prompts...
#   ✓ 42 prompts generados
#   ==================================================
#   ✅ PROCESAMIENTO COMPLETADO


# INTEGRACIÓN MÍNIMA (3 líneas de cambio)
# ========================================
#
# 1. Importar:
#    from app.core.status_log_publisher import StatusLogPublisher
#
# 2. En process_upload_job, después de crear JobProgressPublisher:
#    logger = StatusLogPublisher(jobs, job_id)
#
# 3. En puntos clave del flujo:
#    await logger.append("Tu mensaje aquí")
