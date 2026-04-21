import logging
import traceback
from collections.abc import Callable
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingestion.categorizer import categorize
from app.ingestion.language import detect_language
from app.ingestion.normalizer import normalize
from app.ingestion.parsers.code_parser import CodeParser
from app.ingestion.parsers.document_parser import DocumentParser
from app.models.document import Document
from app.storage.base import BlobStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        blob_store: BlobStore,
    ) -> None:
        self._sf = session_factory
        self._blob = blob_store

    async def run(self, document_id: UUID) -> None:
        log = logger.getChild(str(document_id)[:8])
        log.info("document_id=%s ingestion starting", document_id)
        try:
            await self._set_status(document_id, "processing")

            # Load doc metadata (separate session, short-lived)
            async with self._sf() as session:
                doc = await session.get(Document, document_id)
                if doc is None:
                    log.error("document_id=%s row not found", document_id)
                    return
                blob_path = doc.blob_path
                filename = doc.filename
                content_type = doc.content_type

            # Fetch bytes outside any DB session
            data = await self._blob.get(blob_path)

            # Process
            file_category = categorize(filename, content_type)
            parser = CodeParser() if file_category == "code" else DocumentParser()
            parsed = await parser.parse(data, filename)
            detected_lang = detect_language(parsed.text)
            normalized = normalize(parsed, file_category, filename)

            # Persist results
            async with self._sf() as session:
                doc = await session.get(Document, document_id)
                if doc is None:
                    return
                doc.file_category = file_category
                doc.normalized_content = normalized
                doc.detected_language = detected_lang
                doc.status = "ready"
                await session.commit()

            log.info(
                "document_id=%s status=ready language=%s category=%s",
                document_id, detected_lang, file_category,
            )

        except Exception as exc:
            log.error(
                "document_id=%s failed: %s\n%s",
                document_id, exc, traceback.format_exc(),
            )
            try:
                async with self._sf() as session:
                    doc = await session.get(Document, document_id)
                    if doc is not None:
                        doc.status = "failed"
                        doc.error_message = str(exc)[:2000]
                        await session.commit()
            except Exception:
                log.exception("document_id=%s could not persist failure state", document_id)

    async def _set_status(self, document_id: UUID, status: str) -> None:
        async with self._sf() as session:
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.status = status
                await session.commit()
