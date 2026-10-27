"""Collection model.

``owner_subject`` must eventually be set from a verified identity issued by a
trusted authentication provider (for example Neon Auth or another IdP). It must
never be taken directly from client input without server-side verification.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_knowledge_hub_api.models.base import Base

if TYPE_CHECKING:
    from ai_knowledge_hub_api.models.document import Document


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (Index("ix_collections_owner_subject", "owner_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )
