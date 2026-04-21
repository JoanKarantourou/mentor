import asyncio
from io import BytesIO

from app.ingestion.parsers.base import ParsedContent, Parser


class DocumentParser(Parser):
    async def parse(self, data: bytes, filename: str) -> ParsedContent:
        elements = await asyncio.to_thread(self._partition_sync, data, filename)
        text = "\n\n".join(e.text for e in elements if getattr(e, "text", None) and e.text.strip())
        structure_hints = {
            "elements": [
                {"type": type(e).__name__, "text": e.text}
                for e in elements
                if getattr(e, "text", None) and e.text.strip()
            ]
        }
        return ParsedContent(text=text, structure_hints=structure_hints)

    @staticmethod
    def _partition_sync(data: bytes, filename: str):
        from unstructured.partition.auto import partition  # lazy: heavy import

        return partition(file=BytesIO(data), metadata_filename=filename)
