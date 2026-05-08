from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from io import BytesIO


class EpubReaderService:
    def read(self, data: bytes) -> list[str]:
        book = epub.read_epub(BytesIO(data))
        chapters = []

        for item in book.get_items():
            if item.get_type() == ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                text = soup.get_text(separator="\n").strip()
                if text:
                    chapters.append(text)

        return chapters