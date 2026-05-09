"""
EJEMPLO: Cómo usar StatusLogPublisher en el backend

El StatusLogPublisher permite enviar logs línea a línea al frontend,
donde se mostrarán en el div "stat-bot" con auto-scroll automático.

# INSTALACIÓN EN MAIN.PY:

## Paso 1: Importar la clase

from app.core.status_log_publisher import StatusLogPublisher

## Paso 2: Crear instancia en la función de procesamiento

async def process_upload_job(\*, job_id: str, filename: str, data: bytes) -> None:
progress = JobProgressPublisher(jobs, job_id)
logger = StatusLogPublisher(jobs, job_id) # ← Añade esta línea

    try:
        await logger.append(f"Archivo recibido: {filename}")

        # Tu código aquí...
        content = read_uploaded_file_data(filename=filename, data=data)
        await logger.append("Archivo leído correctamente")

        chunks = chunk_uploaded_content(content)
        await logger.append(f"Se han calculado {len(chunks)} chunks")

        # Más procesamiento...

    except Exception as exc:
        await logger.append(f"ERROR: {str(exc)}")

# MÉTODOS DISPONIBLES:

1. append(message, step="logging")
   └─ Añade una línea de texto simple
   └─ Ej: await logger.append("Comenzando...")

2. append_titled(title, message, step="logging")
   └─ Añade una línea con formato [título] mensaje
   └─ Ej: await logger.append_titled("Chunking", "Se crearon 42 chunks")

3. append_multiline(text, step="logging")
   └─ Procesa un texto multilínea y lo añade línea por línea
   └─ Ej: await logger.append_multiline("Línea 1\\nLínea 2\\nLínea 3")

# VENTAJAS:

✓ Reutilizable en cualquier función del backend
✓ Logs en tiempo real en el frontend
✓ Auto-scroll inteligente (solo scrollea si el usuario estaba viendo el final)
✓ API simple y consistente
✓ Se integra con la infraestructura SSE existente

# DIFERENCIA CON JobProgressPublisher:

JobProgressPublisher (existente):

- Envía eventos estructurados con step, message y porcentaje
- Para barra de progreso y eventos de flujo

StatusLogPublisher (nuevo):

- Envía líneas de log simples
- Para mostrar texto incremental en un div scrolleable
- No incluye porcentaje (es solo para el log)
  """
