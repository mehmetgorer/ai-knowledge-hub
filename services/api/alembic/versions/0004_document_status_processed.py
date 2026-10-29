"""Add PROCESSED to document_status enum.

Revision ID: 0004_document_status_processed
Revises: 0003_document_chunks
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_document_status_processed"
down_revision: str | Sequence[str] | None = "0003_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'PROCESSED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum labels safely; leave PROCESSED in place.
    pass
