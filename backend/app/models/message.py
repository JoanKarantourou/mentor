import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        sa.Index("ix_messages_conversation_index", "conversation_id", "message_index"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    role: str = Field(max_length=20)
    content: str = Field(sa_column=Column(Text, nullable=False))
    message_index: int = Field(sa_column=Column(Integer, nullable=False))

    retrieved_chunk_ids: list | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    cited_chunk_ids: list | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    model_used: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    input_tokens: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    output_tokens: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    low_confidence: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
