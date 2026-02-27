from __future__ import annotations

from typing import Sequence

from sqlalchemy import Select, delete, select, update
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.models import ItemStatus, TransactionAction


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_from_telegram(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        make_admin: bool = False,
    ) -> models.User:
        stmt: Select[tuple[models.User]] = select(models.User).where(
            models.User.telegram_id == telegram_id
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            if make_admin and not user.is_admin:
                user.is_admin = True
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            return user

        user = models.User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=make_admin,
        )
        self.session.add(user)
        return user

    async def get_by_id(self, user_id: int) -> models.User | None:
        return await self.session.get(models.User, user_id)

    async def list_all(self) -> Sequence[models.User]:
        stmt: Select[tuple[models.User]] = select(models.User).order_by(models.User.id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_admins(self) -> Sequence[models.User]:
        """Return list of all admin users."""
        stmt: Select[tuple[models.User]] = (
            select(models.User)
            .where(models.User.is_admin == True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def toggle_admin(self, user_id: int) -> bool | None:
        """Returns new is_admin value, or None if user not found."""
        user = await self.session.get(models.User, user_id)
        if user is None:
            return None
        user.is_admin = not user.is_admin
        return user.is_admin


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> Sequence[models.Category]:
        stmt: Select[tuple[models.Category]] = (
            select(models.Category)
            .where(models.Category.is_active.is_(True))
            .order_by(models.Category.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[models.Category]:
        stmt: Select[tuple[models.Category]] = select(models.Category).order_by(models.Category.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, category_id: int) -> models.Category | None:
        return await self.session.get(models.Category, category_id)

    async def create(self, name: str, description: str | None = None) -> models.Category:
        category = models.Category(name=name, description=description)
        self.session.add(category)
        return category

    async def update(
        self,
        category_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        values: dict = {}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if not values:
            return False
        stmt = (
            update(models.Category)
            .where(models.Category.id == category_id)
            .values(**values)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def rename(self, category_id: int, new_name: str) -> bool:
        stmt = (
            update(models.Category)
            .where(models.Category.id == category_id)
            .values(name=new_name)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def soft_delete(self, category_id: int) -> bool:
        stmt = (
            update(models.Category)
            .where(models.Category.id == category_id)
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def hard_delete(self, category_id: int) -> bool:
        stmt = delete(models.Category).where(models.Category.id == category_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def set_active(self, category_id: int, active: bool) -> bool:
        stmt = (
            update(models.Category)
            .where(models.Category.id == category_id)
            .values(is_active=active)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_category(self, category_id: int) -> Sequence[models.Item]:
        stmt: Select[tuple[models.Item]] = (
            select(models.Item)
            .where(models.Item.category_id == category_id)
            .order_by(models.Item.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_on_hands(self) -> Sequence[models.Item]:
        stmt: Select[tuple[models.Item]] = select(models.Item).where(
            models.Item.status == ItemStatus.TAKEN
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_available(self) -> Sequence[models.Item]:
        stmt: Select[tuple[models.Item]] = (
            select(models.Item)
            .where(models.Item.status == models.ItemStatus.AVAILABLE)
            .order_by(models.Item.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_holder(self, user_id: int) -> Sequence[models.Item]:
        stmt: Select[tuple[models.Item]] = (
            select(models.Item)
            .where(models.Item.current_holder_id == user_id)
            .order_by(models.Item.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search(self, query: str) -> Sequence[models.Item]:
        """Search items by name or inventory code."""
        # Use simple substring search for name and code
        pattern = f"%{query}%"
        stmt = (
            select(models.Item)
            .where(
                or_(
                    models.Item.name.ilike(pattern),
                    models.Item.inventory_code.ilike(pattern),
                )
            )
            .order_by(models.Item.name)
            .limit(50)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, item_id: int) -> models.Item | None:
        return await self.session.get(models.Item, item_id)

    async def create(
        self,
        category_id: int,
        name: str,
        inventory_code: str | None = None,
    ) -> models.Item:
        item = models.Item(
            category_id=category_id,
            name=name,
            inventory_code=inventory_code,
        )
        self.session.add(item)
        return item

    async def update(
        self,
        item_id: int,
        name: str | None = None,
        inventory_code: str | None = None,
    ) -> bool:
        values: dict = {}
        if name is not None:
            values["name"] = name
        if inventory_code is not None:
            values["inventory_code"] = inventory_code
        if not values:
            return False
        stmt = (
            update(models.Item)
            .where(models.Item.id == item_id)
            .values(**values)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def delete(self, item_id: int) -> bool:
        stmt = delete(models.Item).where(models.Item.id == item_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_transaction(
        self,
        item_id: int,
        user_id: int,
        action: TransactionAction,
        photo_file_id: str,
        comment: str | None = None,
    ) -> models.Transaction:
        tx = models.Transaction(
            item_id=item_id,
            user_id=user_id,
            action=action,
            photo_file_id=photo_file_id,
            comment=comment,
        )
        self.session.add(tx)
        return tx

    async def list_for_item(self, item_id: int, limit: int = 20) -> Sequence[models.Transaction]:
        stmt: Select[tuple[models.Transaction]] = (
            select(models.Transaction)
            .where(models.Transaction.item_id == item_id)
            .order_by(models.Transaction.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_user(self, user_id: int, limit: int = 20) -> Sequence[models.Transaction]:
        stmt: Select[tuple[models.Transaction]] = (
            select(models.Transaction)
            .where(models.Transaction.user_id == user_id)
            .order_by(models.Transaction.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_item_with_user(
        self, item_id: int, limit: int = 50
    ) -> Sequence[models.Transaction]:
        """Returns transactions for an item with user eagerly loaded."""
        stmt: Select[tuple[models.Transaction]] = (
            select(models.Transaction)
            .where(models.Transaction.item_id == item_id)
            .options(joinedload(models.Transaction.user))
            .order_by(models.Transaction.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().all()

    async def get_latest_take_for_item(
        self, item_id: int
    ) -> models.Transaction | None:
        """Get the most recent TAKE transaction for an item."""
        stmt: Select[tuple[models.Transaction]] = (
            select(models.Transaction)
            .where(
                models.Transaction.item_id == item_id,
                models.Transaction.action == TransactionAction.TAKE,
            )
            .options(joinedload(models.Transaction.user))
            .order_by(models.Transaction.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_on_hands_with_details(
        self,
    ) -> Sequence[models.Transaction]:
        """For all currently TAKEN items, return last TAKE transaction with user."""
        # Subquery: latest TAKE per item
        from sqlalchemy import func
        subq = (
            select(
                models.Transaction.item_id,
                func.max(models.Transaction.id).label("max_id"),
            )
            .where(models.Transaction.action == TransactionAction.TAKE)
            .group_by(models.Transaction.item_id)
            .subquery()
        )
        stmt = (
            select(models.Transaction)
            .join(subq, models.Transaction.id == subq.c.max_id)
            .options(
                joinedload(models.Transaction.user),
                joinedload(models.Transaction.item),
            )
            .order_by(models.Transaction.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().all()


class AdminLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(self, admin_id: int | None, action: str, details: str | None = None) -> models.AdminLog:
        entry = models.AdminLog(admin_id=admin_id, action=action, details=details)
        self.session.add(entry)
        return entry
