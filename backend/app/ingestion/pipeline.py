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
        duplicate_detection_enabled: bool = True,
        duplicate_near_threshold: float = 0.92,
        duplicate_match_ratio: float = 0.5,
    ) -> None:
        self._sf = session_factory
        self._blob = blob_store
        self._embedder = embedding_provider
        self._dedup_enabled = duplicate_detection_enabled
        self._dedup_threshold = duplicate_near_threshold
        self._dedup_ratio = duplicate_match_ratio

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
                uploaded_by = doc.uploaded_by

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

            # Duplicate detection before embedding (only when embedder is available)
            if self._dedup_enabled and self._embedder is not None and normalized:
                try:
                    from app.curation.duplicate_detector import find_duplicates
                    matches = await find_duplicates(
                        new_content=normalized,
                        new_document_user_id=uploaded_by,
                        file_category=file_category,
                        filename=filename,
                        session_factory=self._sf,
                        embedding_provider=self._embedder,
                        threshold_near=self._dedup_threshold,
                        match_ratio=self._dedup_ratio,
                    )
                    if matches:
                        async with self._sf() as session:
                            doc = await session.get(Document, document_id)
                            if doc is not None:
                                doc.status = "awaiting_user_decision"
                                doc.duplicate_check = [
                                    {
                                        "existing_document_id": str(m.existing_document_id),
                                        "existing_filename": m.existing_filename,
                                        "similarity": m.similarity,
                                        "match_type": m.match_type,
                                        "matching_chunks": m.matching_chunks,
                                    }
                                    for m in matches
                                ]
                                await session.commit()
                        log.info(
                            "document_id=%s status=awaiting_user_decision matches=%d",
                            document_id, len(matches),
                        )
                        return
                except Exception as exc:
                    log.warning(
                        "document_id=%s duplicate detection failed (non-fatal): %s",
                        document_id, exc,
                    )

            await self._embed_and_index(document_id, detected_lang, file_category)

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

    async def resume_ingestion(self, document_id: UUID) -> None:
        """Resume embedding after the user resolves a duplicate check."""
        async with self._sf() as session:
            doc = await session.get(Document, document_id)
            if doc is None:
                return
            detected_lang = doc.detected_language
            file_category = doc.file_category
        await self._embed_and_index(document_id, detected_lang, file_category)

    async def _embed_and_index(
        self, document_id: UUID, detected_lang: str | None, file_category: str
    ) -> None:
        log = logger.getChild(str(document_id)[:8])
        if self._embedder is not None:
            await self._set_status(document_id, "chunking")
            await self._set_status(document_id, "embedding")
            await embed_chunks(document_id, self._sf, self._embedder)
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

    async def _set_status(self, document_id: UUID, status: str) -> None:
        async with self._sf() as session:
            doc = await session.get(Document, document_id)
            if doc is not None:
                doc.status = status
                await session.commit()
