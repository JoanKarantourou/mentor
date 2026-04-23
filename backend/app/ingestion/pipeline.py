import logging
import traceback
from collections.abc import Callable
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingestion.categorizer import categorize
from app.ingestion.embedding import embed_chunks
from app.ingestion.language import detect_language
from app.ingestion.normalizer import normalize
from app.ingestion.parsers.code_parser import CodeParser
from app.ingestion.parsers.document_parser import DocumentParser
from app.models.document import Document
from app.providers.embeddings import EmbeddingProvider
from app.storage.base import BlobStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        blob_store: BlobStore,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._sf = session_factory
        self._blob = blob_store
        self._embedder = embedding_provider

    async def run(self, document_id: UUID) -> None:
        log = logger.getChild(str(document_id)[:8])
        log.info("document_id=%s ingestion starting", document_id)
        try:
            await self._set_status(document_id, "processing")

            async with self._sf() as session:
                doc = await session.get(Document, document_id)
                if doc is None:
                    log.error("document_id=%s row not found", document_id)
                    return
                blob_path = doc.blob_path
                filename = doc.filename
                content_type = doc.content_type

            data = await self._blob.get(blob_path)

            file_category = categorize(filename, content_type)
            parser = CodeParser() if file_category == "code" else DocumentParser()
            parsed = await parser.parse(data, filename)
            detected_lang = detect_language(parsed.text)
            normalized = normalize(parsed, file_category, filename)

            async with self._sf() as session:
                doc = await session.get(Document, document_id)
                if doc is None:
                    return
                doc.file_category = file_category
                doc.normalized_content = normalized
                doc.detected_language = detected_lang
                doc.status = "ready"
                await session.commit()

            if self._embedder is not None:
                await self._set_status(document_id, "chunking")
                await self._set_status(document_id, "embedding")
                await embed_chunks(document_id, self._sf, self._embedder)
                # embed_chunks may have set status=failed on error — only advance if not.
                async with self._sf() as session:
                    current = await session.get(Document, document_id)
                    if current is not None and current.status != "failed":
                        current.status = "indexed"
                        await session.commit()
                        log.info(
                            "document_id=%s status=indexed language=%s category=%s",
                            document_id, detected_lang, file_category,
                        )
                    else:
                        log.warning(
                            "document_id=%s embedding failed, status=%s",
                            document_id,
                            current.status if current else "unknown",
                        )
            else:
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
