from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    pass


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    chunk_index: int = Field(sa_column=Column(Integer, nullable=False))
    text: str = Field(sa_column=Column(Text, nullable=False))
    token_count: int = Field(sa_column=Column(Integer, nullable=False))
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1536), nullable=True),
    )
    embedding_model: str | None = Field(sa_column=Column(Text, nullable=True))
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
