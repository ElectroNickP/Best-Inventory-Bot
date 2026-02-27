from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.models import ItemStatus, TransactionAction
from app.db.repositories import (
    CategoryRepository,
    ItemRepository,
    TransactionRepository,
    UserRepository,
)


@dataclass
class InventoryService:
    session: AsyncSession

    @property
    def users(self) -> UserRepository:
        return UserRepository(self.session)

    @property
    def categories(self) -> CategoryRepository:
        return CategoryRepository(self.session)

    @property
    def items(self) -> ItemRepository:
        return ItemRepository(self.session)

    @property
    def transactions(self) -> TransactionRepository:
        return TransactionRepository(self.session)

    async def ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        initial_admin_ids: list[int],
        initial_admin_usernames: list[str],
    ) -> models.User:
        normalized_username = (username or "").lstrip("@").lower()
        make_admin = telegram_id in initial_admin_ids or (
            normalized_username in initial_admin_usernames if normalized_username else False
        )
        user = await self.users.get_or_create_from_telegram(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            make_admin=make_admin,
        )
        await self.session.flush()
        return user

    async def list_categories(self) -> list[models.Category]:
        categories = await self.categories.list_active()
        return list(categories)

    async def list_items_for_category(self, category_id: int) -> list[models.Item]:
        items = await self.items.list_by_category(category_id)
        return list(items)

    async def list_items_for_user(self, user_id: int) -> list[models.Item]:
        items = await self.items.list_for_holder(user_id)
        return list(items)

    async def take_item(
        self,
        item_id: int,
        user: models.User,
        photo_file_id: str,
        comment: str | None = None,
    ) -> models.Transaction:
        item = await self.items.get_by_id(item_id)
        if item is None:
            raise ValueError("Item not found")
        if item.status != ItemStatus.AVAILABLE:
            raise ValueError("Item is not available")

        item.status = ItemStatus.TAKEN
        item.current_holder_id = user.id

        tx = await self.transactions.add_transaction(
            item_id=item.id,
            user_id=user.id,
            action=TransactionAction.TAKE,
            photo_file_id=photo_file_id,
            comment=comment,
        )
        await self.session.flush()
        return tx

    async def return_item(
        self,
        item_id: int,
        user: models.User,
        photo_file_id: str,
        comment: str | None = None,
    ) -> models.Transaction:
        item = await self.items.get_by_id(item_id)
        if item is None:
            raise ValueError("Item not found")
        if item.status != ItemStatus.TAKEN:
            raise ValueError("Item is not currently taken")
        if item.current_holder_id != user.id:
            # You can relax this rule or allow admin override elsewhere.
            raise ValueError("Item is held by another user")

        item.status = ItemStatus.AVAILABLE
        item.current_holder_id = None

        tx = await self.transactions.add_transaction(
            item_id=item.id,
            user_id=user.id,
            action=TransactionAction.RETURN,
            photo_file_id=photo_file_id,
            comment=comment,
        )
        await self.session.flush()
        return tx

