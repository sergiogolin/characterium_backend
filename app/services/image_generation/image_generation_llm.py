from __future__ import annotations

from app.services.llm.base import BaseLLM
from app.services.prompts.prompt_loader import load_prompt, render_prompt


class ImageGenerationLLM:
    """
    Servicio LLM para generar prompts optimizados para sistemas de generación de imágenes.
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_image_prompt(
        self,
        character_description: str,
        graphic_style: str,
    ) -> str:
        """
        Genera un prompt optimizado para un sistema de generación de imágenes
        basado en la descripción de un personaje y un estilo gráfico.

        :param character_description: Descripción del personaje
        :param graphic_style: Estilo gráfico solicitado (ej: "fotorrealista", "anime", etc.)
        :return: Prompt optimizado para generación de imagen
        """
        system_prompt = load_prompt("image_generation/system.md")
        user_template = load_prompt("image_generation/user.md")

        # Renderizar template con los valores
        user_prompt = render_prompt(
            user_template,
            CHARACTER_DESCRIPTION=character_description,
            GRAPHIC_STYLE=graphic_style,
        )

        result = await self.llm.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return result.strip()
