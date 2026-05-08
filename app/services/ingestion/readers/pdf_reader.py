from PyPDF2 import PdfReader
from io import BytesIO

class PdfReaderService:
    def read(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)