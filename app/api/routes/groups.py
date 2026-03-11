import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.group import Group, GroupMembership
from app.models.user import User
from app.schemas.group import (
    AddMemberRequest,
    GroupCreate,
    GroupDetail,
    GroupMemberRead,
    GroupRead,
    GroupUpdate,
)

router = APIRouter(prefix="/groups", tags=["groups"])


async def _assert_membership(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMembership:
    result = await db.execute(
        select(GroupMembership).where(GroupMembership.group_id == group_id, GroupMembership.user_id == user_id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this group")
    return membership


async def _assert_admin_or_owner(db: AsyncSession, group: Group, user: User) -> None:
    if group.owner_id == user.id:
        return
    membership = await _assert_membership(db, group.id, user.id)
    if membership.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")


@router.post("/", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = Group(name=body.name, description=body.description, owner_id=current_user.id)
    db.add(group)
    await db.flush()

    membership = GroupMembership(group_id=group.id, user_id=current_user.id, role="owner")
    db.add(membership)
    await db.commit()
    await db.refresh(group)

    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        created_at=group.created_at,
        member_count=1,
    )


@router.get("/", response_model=list[GroupRead])
async def list_my_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subq = (
        select(GroupMembership.group_id)
        .where(GroupMembership.user_id == current_user.id)
        .subquery()
    )
    result = await db.execute(select(Group).where(Group.id.in_(select(subq))))
    groups = result.scalars().all()

    out = []
    for g in groups:
        count_result = await db.execute(
            select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == g.id)
        )
        out.append(
            GroupRead(
                id=g.id,
                name=g.name,
                description=g.description,
                owner_id=g.owner_id,
                created_at=g.created_at,
                member_count=count_result.scalar_one(),
            )
        )
    return out


@router.get("/{group_id}", response_model=GroupDetail)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    await _assert_membership(db, group.id, current_user.id)

    members_result = await db.execute(
        select(GroupMembership).where(GroupMembership.group_id == group_id)
    )
    members = members_result.scalars().all()

    member_reads = []
    for m in members:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        u = user_result.scalar_one_or_none()
        member_reads.append(
            GroupMemberRead(
                id=m.id,
                user_id=m.user_id,
                user_name=u.name if u else None,
                user_email=u.email if u else None,
                role=m.role,
                joined_at=m.joined_at,
            )
        )

    return GroupDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        created_at=group.created_at,
        member_count=len(member_reads),
        members=member_reads,
    )


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    await _assert_admin_or_owner(db, group, current_user)

    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    await db.commit()
    await db.refresh(group)

    count_result = await db.execute(
        select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == group.id)
    )
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        created_at=group.created_at,
        member_count=count_result.scalar_one(),
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if group.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete this group")

    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", response_model=GroupMemberRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: uuid.UUID,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    await _assert_admin_or_owner(db, group, current_user)

    existing = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == body.user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    target_user_result = await db.execute(select(User).where(User.id == body.user_id))
    target_user = target_user_result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    membership = GroupMembership(group_id=group_id, user_id=body.user_id, role=body.role)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return GroupMemberRead(
        id=membership.id,
        user_id=membership.user_id,
        user_name=target_user.name,
        user_email=target_user.email,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    is_self_removal = user_id == current_user.id
    if not is_self_removal:
        await _assert_admin_or_owner(db, group, current_user)

    if user_id == group.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the group owner")

    mem_result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == user_id
        )
    )
    membership = mem_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await db.delete(membership)
    await db.commit()
