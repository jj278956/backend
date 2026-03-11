import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ShoppingCart(Base):
    __tablename__ = "shopping_carts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship(back_populates="owned_carts", lazy="selectin")
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", lazy="selectin", cascade="all, delete-orphan"
    )
    shared_with_groups: Mapped[list["CartGroupShare"]] = relationship(
        back_populates="cart", lazy="selectin", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shopping_carts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_checked: Mapped[bool] = mapped_column(default=False)
    added_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cart: Mapped["ShoppingCart"] = relationship(back_populates="items", lazy="selectin")
    added_by: Mapped["User"] = relationship(lazy="selectin")


class CartGroupShare(Base):
    __tablename__ = "cart_group_shares"
    __table_args__ = (UniqueConstraint("cart_id", "group_id", name="uq_cart_group"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shopping_carts.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    permission: Mapped[str] = mapped_column(String(50), default="edit")
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cart: Mapped["ShoppingCart"] = relationship(back_populates="shared_with_groups", lazy="selectin")
    group: Mapped["Group"] = relationship(back_populates="shared_carts", lazy="selectin")


from app.models.user import User  # noqa: E402
from app.models.group import Group  # noqa: E402
