from docx import Document
from io import BytesIO

class DocxReaderService:
    def read(self, data: bytes) -> str:
        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)