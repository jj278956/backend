import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CartItemCreate(BaseModel):
    name: str
    quantity: int = 1
    unit: str | None = None
    price: Decimal | None = None
    notes: str | None = None


class CartItemUpdate(BaseModel):
    name: str | None = None
    quantity: int | None = None
    unit: str | None = None
    price: Decimal | None = None
    notes: str | None = None
    is_checked: bool | None = None


class CartItemRead(BaseModel):
    id: uuid.UUID
    name: str
    quantity: int
    unit: str | None = None
    price: Decimal | None = None
    notes: str | None = None
    is_checked: bool
    added_by_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class CartCreate(BaseModel):
    name: str


class CartUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class CartShareRequest(BaseModel):
    group_id: uuid.UUID
    permission: str = "edit"


class CartShareRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str | None = None
    permission: str
    shared_at: datetime

    model_config = {"from_attributes": True}


class CartRead(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    is_active: bool
    created_at: datetime
    item_count: int = 0

    model_config = {"from_attributes": True}


class CartDetail(CartRead):
    items: list[CartItemRead] = []
    shared_with: list[CartShareRead] = []
