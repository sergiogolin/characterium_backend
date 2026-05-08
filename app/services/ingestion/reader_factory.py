from app.services.ingestion.readers.docx_reader import DocxReaderService
from app.services.ingestion.readers.epub_reader import EpubReaderService
from app.services.ingestion.readers.pdf_reader import PdfReaderService
from app.services.ingestion.readers.txt_reader import TxtReader


def get_reader(filename: str):
    if not filename or "." not in filename:
        raise ValueError("El archivo no tiene una extensión válida.")

    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "txt":
        return TxtReader()
    if ext == "pdf":
        return PdfReaderService()
    if ext in ("doc", "docx"):
        return DocxReaderService()
    if ext == "epub":
        return EpubReaderService()

    raise ValueError(f"Formato no soportado: {ext}")