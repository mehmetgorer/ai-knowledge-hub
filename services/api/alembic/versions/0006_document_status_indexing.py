"""Add INDEXING to document_status enum.

Revision ID: 0006_document_status_indexing
Revises: 0005_document_chunk_embeddings
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_document_status_indexing"
down_revision: str | Sequence[str] | None = "0005_document_chunk_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'INDEXING'")


def downgrade() -> None:
    pass
