"""add_web_search_to_messages

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-04-27 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("web_search_used", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "messages",
        sa.Column("web_search_results", JSONB(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("web_search_provider", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "web_search_provider")
    op.drop_column("messages", "web_search_results")
    op.drop_column("messages", "web_search_used")
