from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Optional


class ImageStorageService:
    """
    Servicio para almacenar imágenes generadas en una carpeta pública
    accesible desde el frontend.
    """

    def __init__(
        self,
        public_folder: str = "./public/images/generated",
        base_url: str = "http://localhost:8000",
    ):
        self.public_folder = Path(public_folder)
        self.public_folder.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")

    def _generate_filename(self) -> str:
        """
        Genera un nombre de archivo único basado en hash aleatorio.

        :return: Nombre de archivo sin extensión
        """
        # Usar secrets para generar bytes aleatorios criptográficamente seguros
        random_bytes = secrets.token_bytes(16)
        hash_name = hashlib.sha256(random_bytes).hexdigest()[:12]
        return hash_name

    def save_image(self, image_data: bytes, extension: str = "png") -> tuple[str, str]:
        """
        Guarda la imagen en la carpeta pública.

        :param image_data: Datos binarios de la imagen
        :param extension: Extensión del archivo (sin punto)
        :return: Tupla (ruta_relativa, url_completa)
        """
        if not extension:
            extension = "png"

        # Asegurar que la extensión no tenga punto
        extension = extension.lstrip(".")

        filename = f"{self._generate_filename()}.{extension}"
        file_path = self.public_folder / filename

        # Escribir archivo
        with open(file_path, "wb") as f:
            f.write(image_data)

        # Retornar ruta relativa y URL
        relative_path = f"/images/generated/{filename}"
        full_url = f"{self.base_url}{relative_path}"

        return relative_path, full_url

    def cleanup_old_images(self, max_age_hours: int = 24) -> None:
        """
        Limpia imágenes antiguas (opcional para mantenimiento).

        :param max_age_hours: Edad máxima en horas
        """
        import time

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for file in self.public_folder.glob("*"):
            if file.is_file():
                file_age = current_time - file.stat().st_mtime
                if file_age > max_age_seconds:
                    file.unlink()
