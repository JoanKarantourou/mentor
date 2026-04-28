"""stage8_curation

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-04-28 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="upload"),
    )
    op.add_column(
        "documents",
        sa.Column("source_conversation_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("duplicate_check", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "duplicate_check")
    op.drop_column("documents", "source_conversation_id")
    op.drop_column("documents", "source_type")
