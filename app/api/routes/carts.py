import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.cart import CartGroupShare, CartItem, ShoppingCart
from app.models.group import Group, GroupMembership
from app.models.user import User
from app.schemas.cart import (
    CartCreate,
    CartDetail,
    CartItemCreate,
    CartItemRead,
    CartItemUpdate,
    CartRead,
    CartShareRead,
    CartShareRequest,
    CartUpdate,
)

router = APIRouter(prefix="/carts", tags=["carts"])


async def _get_cart_or_404(db: AsyncSession, cart_id: uuid.UUID) -> ShoppingCart:
    result = await db.execute(select(ShoppingCart).where(ShoppingCart.id == cart_id))
    cart = result.scalar_one_or_none()
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


async def _user_can_access_cart(db: AsyncSession, cart: ShoppingCart, user: User) -> bool:
    """Owner always has access. Members of groups the cart is shared with also have access."""
    if cart.owner_id == user.id:
        return True
    shares_result = await db.execute(
        select(CartGroupShare.group_id).where(CartGroupShare.cart_id == cart.id)
    )
    shared_group_ids = [row[0] for row in shares_result.all()]
    if not shared_group_ids:
        return False
    membership_result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id.in_(shared_group_ids),
            GroupMembership.user_id == user.id,
        )
    )
    return membership_result.scalar_one_or_none() is not None


async def _user_can_edit_cart(db: AsyncSession, cart: ShoppingCart, user: User) -> bool:
    if cart.owner_id == user.id:
        return True
    shares_result = await db.execute(
        select(CartGroupShare).where(CartGroupShare.cart_id == cart.id, CartGroupShare.permission == "edit")
    )
    edit_group_ids = [s.group_id for s in shares_result.scalars().all()]
    if not edit_group_ids:
        return False
    membership_result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id.in_(edit_group_ids),
            GroupMembership.user_id == user.id,
        )
    )
    return membership_result.scalar_one_or_none() is not None


async def _assert_access(db: AsyncSession, cart: ShoppingCart, user: User) -> None:
    if not await _user_can_access_cart(db, cart, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this cart")


async def _assert_edit(db: AsyncSession, cart: ShoppingCart, user: User) -> None:
    if not await _user_can_edit_cart(db, cart, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No edit permission for this cart")


def _cart_to_read(cart: ShoppingCart, item_count: int) -> CartRead:
    return CartRead(
        id=cart.id,
        name=cart.name,
        owner_id=cart.owner_id,
        is_active=cart.is_active,
        created_at=cart.created_at,
        item_count=item_count,
    )


# ── Cart CRUD ──────────────────────────────────────────────────────

@router.post("/", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def create_cart(
    body: CartCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = ShoppingCart(name=body.name, owner_id=current_user.id)
    db.add(cart)
    await db.commit()
    await db.refresh(cart)
    return _cart_to_read(cart, 0)


@router.get("/", response_model=list[CartRead])
async def list_my_carts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_shared: bool = True,
):
    owned_result = await db.execute(
        select(ShoppingCart).where(ShoppingCart.owner_id == current_user.id)
    )
    carts = list(owned_result.scalars().all())

    if include_shared:
        my_groups_result = await db.execute(
            select(GroupMembership.group_id).where(GroupMembership.user_id == current_user.id)
        )
        my_group_ids = [row[0] for row in my_groups_result.all()]
        if my_group_ids:
            shared_cart_ids_result = await db.execute(
                select(CartGroupShare.cart_id).where(CartGroupShare.group_id.in_(my_group_ids))
            )
            shared_cart_ids = {row[0] for row in shared_cart_ids_result.all()}
            owned_ids = {c.id for c in carts}
            new_ids = shared_cart_ids - owned_ids
            if new_ids:
                shared_result = await db.execute(
                    select(ShoppingCart).where(ShoppingCart.id.in_(new_ids))
                )
                carts.extend(shared_result.scalars().all())

    out = []
    for c in carts:
        items_result = await db.execute(
            select(CartItem).where(CartItem.cart_id == c.id)
        )
        out.append(_cart_to_read(c, len(items_result.scalars().all())))
    return out


@router.get("/{cart_id}", response_model=CartDetail)
async def get_cart(
    cart_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    await _assert_access(db, cart, current_user)

    items_result = await db.execute(select(CartItem).where(CartItem.cart_id == cart_id))
    items = items_result.scalars().all()

    shares_result = await db.execute(select(CartGroupShare).where(CartGroupShare.cart_id == cart_id))
    shares = shares_result.scalars().all()

    share_reads = []
    for s in shares:
        group_result = await db.execute(select(Group).where(Group.id == s.group_id))
        g = group_result.scalar_one_or_none()
        share_reads.append(
            CartShareRead(
                id=s.id,
                group_id=s.group_id,
                group_name=g.name if g else None,
                permission=s.permission,
                shared_at=s.shared_at,
            )
        )

    return CartDetail(
        id=cart.id,
        name=cart.name,
        owner_id=cart.owner_id,
        is_active=cart.is_active,
        created_at=cart.created_at,
        item_count=len(items),
        items=[CartItemRead.model_validate(i) for i in items],
        shared_with=share_reads,
    )


@router.patch("/{cart_id}", response_model=CartRead)
async def update_cart(
    cart_id: uuid.UUID,
    body: CartUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    if cart.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can update cart settings")

    if body.name is not None:
        cart.name = body.name
    if body.is_active is not None:
        cart.is_active = body.is_active
    await db.commit()
    await db.refresh(cart)

    items_result = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    return _cart_to_read(cart, len(items_result.scalars().all()))


@router.delete("/{cart_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart(
    cart_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    if cart.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete this cart")
    await db.delete(cart)
    await db.commit()


# ── Sharing ────────────────────────────────────────────────────────

@router.post("/{cart_id}/share", response_model=CartShareRead, status_code=status.HTTP_201_CREATED)
async def share_cart_with_group(
    cart_id: uuid.UUID,
    body: CartShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    if cart.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can share this cart")

    group_result = await db.execute(select(Group).where(Group.id == body.group_id))
    group = group_result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    existing = await db.execute(
        select(CartGroupShare).where(
            CartGroupShare.cart_id == cart_id, CartGroupShare.group_id == body.group_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cart already shared with this group")

    share = CartGroupShare(cart_id=cart_id, group_id=body.group_id, permission=body.permission)
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return CartShareRead(
        id=share.id,
        group_id=share.group_id,
        group_name=group.name,
        permission=share.permission,
        shared_at=share.shared_at,
    )


@router.delete("/{cart_id}/share/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_cart(
    cart_id: uuid.UUID,
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    if cart.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can manage sharing")

    share_result = await db.execute(
        select(CartGroupShare).where(
            CartGroupShare.cart_id == cart_id, CartGroupShare.group_id == group_id
        )
    )
    share = share_result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    await db.delete(share)
    await db.commit()


# ── Cart Items ─────────────────────────────────────────────────────

@router.post("/{cart_id}/items", response_model=CartItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    cart_id: uuid.UUID,
    body: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    await _assert_edit(db, cart, current_user)

    item = CartItem(
        cart_id=cart_id,
        name=body.name,
        quantity=body.quantity,
        unit=body.unit,
        price=body.price,
        notes=body.notes,
        added_by_id=current_user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return CartItemRead.model_validate(item)


@router.patch("/{cart_id}/items/{item_id}", response_model=CartItemRead)
async def update_item(
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
    body: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    await _assert_edit(db, cart, current_user)

    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return CartItemRead.model_validate(item)


@router.delete("/{cart_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await _get_cart_or_404(db, cart_id)
    await _assert_edit(db, cart, current_user)

    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    await db.delete(item)
    await db.commit()
