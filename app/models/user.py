import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owned_groups: Mapped[list["Group"]] = relationship(back_populates="owner", lazy="selectin")
    memberships: Mapped[list["GroupMembership"]] = relationship(back_populates="user", lazy="selectin")
    owned_carts: Mapped[list["ShoppingCart"]] = relationship(back_populates="owner", lazy="selectin")


from app.models.group import Group, GroupMembership  # noqa: E402
from app.models.cart import ShoppingCart  # noqa: E402
