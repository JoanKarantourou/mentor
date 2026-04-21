from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: UUID
    status: str


class DocumentRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    blob_path: str
    detected_language: str | None
    file_category: str
    status: str
    error_message: str | None
    uploaded_by: str
    scope: str
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: UUID
    filename: str
    status: str
    file_category: str
    detected_language: str | None
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentContentResponse(BaseModel):
    document_id: UUID
    content: str
    detected_language: str | None


class ChunkRead(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    token_count: int
    embedding_model: str | None
    meta: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    document_ids: list[UUID] | None = None
    file_category: str | None = None


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    text: str
    score: float
    token_count: int


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    query: str
    embedding_model: str
