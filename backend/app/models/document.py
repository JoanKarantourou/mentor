import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=127)
    size_bytes: int
    blob_path: str = Field(max_length=1024)

    normalized_content: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.Text, nullable=True),
    )
    detected_language: str | None = Field(default=None, max_length=10)
    file_category: str = Field(default="document", max_length=20)
    status: str = Field(default="pending", max_length=20)
    error_message: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.Text, nullable=True),
    )
    uploaded_by: str = Field(default="dev", max_length=255)
    scope: str = Field(default="private", max_length=20)

    deleted_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
