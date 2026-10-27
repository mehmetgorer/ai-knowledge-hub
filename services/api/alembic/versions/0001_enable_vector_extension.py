"""Enable pgvector extension.

Revision ID: 0001_enable_vector
Revises:
Create Date: 2026-03-27

Downgrade does not execute ``DROP EXTENSION vector``. Removing the extension in
shared or production-like databases could destroy vector indexes and data. Only
the Alembic version row is reverted on downgrade.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_vector"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    pass
