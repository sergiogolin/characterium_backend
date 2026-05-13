from __future__ import annotations

import base64
import io
import json
import re
from typing import Optional

from app.services.image_generation.image_generation_llm import ImageGenerationLLM
from app.services.image_generation.image_storage import ImageStorageService
from app.services.llm.llm_factory import get_image_generation_llm


class ImageGenerationError(Exception):
    """Error durante la generación de imagen"""
    pass


def _extract_clean_error_message(error: Exception) -> str:
    """
    Extrae un mensaje de error limpio de una excepción.
    
    Intenta extraer el mensaje específico del error, especialmente si
    contiene estructuras como {'error': {'message': '...', 'code': ...}}
    
    :param error: La excepción a procesar
    :return: Mensaje de error limpio
    """
    error_str = str(error)
    
    # Intentar extraer diccionario JSON con estructura {'error': {'message': '...'}}
    try:
        # Buscar patrones de diccionario en el string
        dict_pattern = r"\{'error': \{'message': '([^']+)'.*?\}\}"
        match = re.search(dict_pattern, error_str)
        if match:
            return match.group(1)
    except:
        pass
    
    # Intentar parsear como JSON directo
    try:
        error_json = json.loads(error_str)
        if isinstance(error_json, dict):
            if 'error' in error_json and isinstance(error_json['error'], dict):
                if 'message' in error_json['error']:
                    return error_json['error']['message']
            elif 'message' in error_json:
                return error_json['message']
    except:
        pass
    
    # Retornar el error original si no se puede extraer
    return error_str


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

        except ImageGenerationError:
            # Si ya es un ImageGenerationError, re-lanzar tal cual
            raise
        except Exception as e:
            # Para otros errores, extraer mensaje limpio
            clean_message = _extract_clean_error_message(e)
            raise ImageGenerationError(clean_message) from e

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
            clean_message = _extract_clean_error_message(e)
            raise ImageGenerationError(clean_message) from e

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
