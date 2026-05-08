from fastapi import UploadFile

from app.services.ingestion.reader_factory import get_reader

SUPPORTED_FORMATS_MESSAGE = "Formato no soportado. Admitidos: txt, pdf, epub, doc, docx"


class FileReadError(Exception):
    """Error controlado al leer o interpretar un archivo subido."""
    pass


async def read_uploaded_file(file: UploadFile) -> str | list[str]:
    filename = (file.filename or "").strip()

    try:
        data = await file.read()
    except Exception as exc:
        raise FileReadError("No se pudo leer el archivo subido.") from exc

    return read_uploaded_file_data(filename=filename, data=data)


def read_uploaded_file_data(filename: str, data: bytes) -> str | list[str]:
    filename = filename.strip()

    if not filename:
        raise FileReadError("El archivo no tiene nombre.")

    try:
        reader = get_reader(filename)
    except ValueError as exc:
        raise FileReadError(SUPPORTED_FORMATS_MESSAGE) from exc

    if not data:
        raise FileReadError("El archivo esta vacio.")

    try:
        content = reader.read(data)
    except Exception as exc:
        raise FileReadError(f"Error leyendo archivo: {str(exc)}") from exc

    if content is None:
        raise FileReadError("No se pudo extraer contenido del archivo.")

    if isinstance(content, str):
        if not content.strip():
            raise FileReadError("El archivo no contiene texto legible.")

    elif isinstance(content, list):
        has_text = any(isinstance(block, str) and block.strip() for block in content)
        if not has_text:
            raise FileReadError("El archivo no contiene texto legible.")
    else:
        raise FileReadError("El reader devolvio un formato de contenido no valido.")

    return content
