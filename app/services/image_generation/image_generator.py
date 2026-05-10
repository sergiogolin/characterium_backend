from __future__ import annotations

import base64
import io
from typing import Optional

from app.services.image_generation.image_generation_llm import ImageGenerationLLM
from app.services.image_generation.image_storage import ImageStorageService
from app.services.llm.llm_factory import get_image_generation_llm


class ImageGenerationError(Exception):
    """Error durante la generación de imagen"""
    pass


class ImageGenerator:
    """
    Servicio principal para generar imágenes de personajes.
    Coordina: generación de prompt, llamada a LLM, almacenamiento.
    """

    def __init__(
        self,
        storage_service: Optional[ImageStorageService] = None,
    ):
        self.storage = storage_service or ImageStorageService()
        self.llm = get_image_generation_llm()

    async def generate_and_save_image(
        self,
        prompt: str,
        graphic_style: str = "fotorrealista",
    ) -> dict:
        """
        Genera una imagen a partir de un prompt y estilo gráfico,
        y la guarda en la carpeta pública.

        :param prompt: Descripción del personaje o escena
        :param graphic_style: Estilo gráfico (default: "fotorrealista")
        :return: Dict con imagePath y imageUrl
        :raises ImageGenerationError: Si falla la generación
        """
        if not graphic_style or not graphic_style.strip():
            graphic_style = "fotorrealista"

        try:
            # Paso 1: Generar prompt optimizado
            image_prompt = await self._generate_optimized_prompt(
                character_description=prompt,
                graphic_style=graphic_style,
            )

            # Paso 2: Llamar al LLM para generar la imagen
            image_data = await self._call_image_generation_llm(
                image_prompt=image_prompt,
            )

            # Paso 3: Guardar imagen
            relative_path, full_url = self.storage.save_image(image_data)

            return {
                "imagePath": relative_path,
                "imageUrl": full_url,
                "success": True,
            }

        except Exception as e:
            raise ImageGenerationError(f"Error generando imagen: {str(e)}") from e

    async def _generate_optimized_prompt(
        self,
        character_description: str,
        graphic_style: str,
    ) -> str:
        """
        Genera un prompt optimizado usando el LLM.
        """
        from app.services.image_generation.image_generation_llm import ImageGenerationLLM

        image_gen_llm = ImageGenerationLLM(self.llm)

        try:
            optimized_prompt = await image_gen_llm.generate_image_prompt(
                character_description=character_description,
                graphic_style=graphic_style,
            )
            return optimized_prompt
        except Exception as e:
            raise ImageGenerationError(
                f"Error generando prompt optimizado: {str(e)}"
            ) from e

    async def _call_image_generation_llm(self, image_prompt: str) -> bytes:
        """
        Llama al LLM para generar la imagen.

        Este método es un placeholder que debe ser implementado según
        el provider LLM seleccionado. Actualmente soporta proveedores
        que tienen capacidad de generación de imágenes (Ollama con modelos especiales,
        OpenRouter, etc.).

        :param image_prompt: Prompt optimizado para la imagen
        :return: Datos binarios de la imagen (PNG/JPEG)
        :raises ImageGenerationError: Si la generación falla
        """
        # Este es un placeholder. La implementación real dependerá del provider LLM
        # que soporte generación de imágenes. Para ahora, retorna un error informativo.

        raise ImageGenerationError(
            "La generación de imágenes requiere un modelo LLM compatible. "
            "Asegúrate de usar un provider que soporte image generation "
            "(ej: OpenRouter con modelos de imagen, Ollama con flux.1, etc.)"
        )
