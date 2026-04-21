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
