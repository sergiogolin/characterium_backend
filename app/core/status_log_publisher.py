"""
Utilidad para publicar mensajes de estado/log que se muestren en el frontend
de forma incremental, línea por línea, con auto-scroll inteligente.

Uso:
    logger = StatusLogPublisher(jobs, job_id)
    await logger.append("Comenzando procesamiento...")
    await logger.append("Paso 1 completado")
    await logger.append("Paso 2 completado")
"""

from app.core.jobs import InMemoryJobStore
from app.core.types import JobProgressEvent


class StatusLogPublisher:
    """
    Publica mensajes de estado/log para un job específico.
    Cada mensaje se envía al frontend como una línea separada.
    """

    def __init__(self, jobs: InMemoryJobStore, job_id: str) -> None:
        """
        :param jobs: Almacén de jobs en memoria
        :param job_id: ID del job para el que publicar logs
        """
        self.jobs = jobs
        self.job_id = job_id

    async def append(self, message: str, step: str = "logging") -> None:
        """
        Añade una línea al log del frontend.

        :param message: Texto a mostrar en el log (se añadirá una nueva línea automáticamente)
        :param step: Paso/categoría del log (por defecto "logging")
        """
        await self.jobs.push(
            self.job_id,
            JobProgressEvent(step=step, message=message, pct=None),
        )

    async def append_titled(
        self,
        title: str,
        message: str,
        step: str = "logging",
    ) -> None:
        """
        Añade una línea con título y contenido (útil para secciones).

        :param title: Título o etiqueta de la sección
        :param message: Contenido de la sección
        :param step: Categoría del log
        """
        formatted = f"[{title}] {message}"
        await self.append(formatted, step)

    async def append_multiline(self, text: str, step: str = "logging") -> None:
        """
        Procesa un texto multilínea y lo añade línea por línea.

        :param text: Texto con múltiples líneas (separadas por \\n)
        :param step: Categoría del log
        """
        for line in text.strip().split("\n"):
            if line.strip():
                await self.append(line.strip(), step)
