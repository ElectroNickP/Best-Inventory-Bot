from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.models import ItemStatus
from app.db.repositories import (
    AdminLogRepository,
    CategoryRepository,
    ItemRepository,
    TransactionRepository,
    UserRepository,
)


@dataclass
class AdminService:
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

    @property
    def logs(self) -> AdminLogRepository:
        return AdminLogRepository(self.session)

    # ── Categories ──────────────────────────────────────────────────────────

    async def create_category(
        self,
        admin: models.User,
        name: str,
        description: str | None = None,
    ) -> models.Category:
        category = await self.categories.create(name=name, description=description)
        await self.logs.log(
            admin_id=admin.id,
            action="create_category",
            details=f"name={name}",
        )
        await self.session.flush()
        return category

    async def rename_category(
        self,
        admin: models.User,
        category_id: int,
        new_name: str,
    ) -> bool:
        ok = await self.categories.rename(category_id, new_name)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="rename_category",
                details=f"id={category_id},new_name={new_name}",
            )
        return ok

    async def deactivate_category(self, admin: models.User, category_id: int) -> bool:
        ok = await self.categories.soft_delete(category_id)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="deactivate_category",
                details=f"id={category_id}",
            )
        return ok

    async def activate_category(self, admin: models.User, category_id: int) -> bool:
        ok = await self.categories.set_active(category_id, active=True)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="activate_category",
                details=f"id={category_id}",
            )
        return ok

    async def delete_category(self, admin: models.User, category_id: int) -> bool:
        ok = await self.categories.hard_delete(category_id)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="delete_category",
                details=f"id={category_id}",
            )
        return ok

    # ── Items ────────────────────────────────────────────────────────────────

    async def create_item(
        self,
        admin: models.User,
        category_id: int,
        name: str,
        inventory_code: str | None = None,
    ) -> models.Item:
        item = await self.items.create(
            category_id=category_id,
            name=name,
            inventory_code=inventory_code,
        )
        await self.logs.log(
            admin_id=admin.id,
            action="create_item",
            details=f"category_id={category_id},name={name}",
        )
        await self.session.flush()
        return item

    async def rename_item(
        self,
        admin: models.User,
        item_id: int,
        new_name: str,
    ) -> bool:
        ok = await self.items.update(item_id, name=new_name)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="rename_item",
                details=f"id={item_id},new_name={new_name}",
            )
        return ok

    async def update_item_code(
        self,
        admin: models.User,
        item_id: int,
        new_code: str,
    ) -> bool:
        ok = await self.items.update(item_id, inventory_code=new_code)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="update_item_code",
                details=f"id={item_id},new_code={new_code}",
            )
        return ok

    async def delete_item(self, admin: models.User, item_id: int) -> bool:
        ok = await self.items.delete(item_id)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="delete_item",
                details=f"id={item_id}",
            )
        return ok

    async def set_item_status(
        self,
        admin: models.User,
        item_id: int,
        status: ItemStatus,
    ) -> bool:
        item = await self.items.get_by_id(item_id)
        if item is None:
            return False
        item.status = status
        if status != ItemStatus.TAKEN:
            item.current_holder_id = None
        await self.logs.log(
            admin_id=admin.id,
            action="set_item_status",
            details=f"item_id={item_id},status={status.value}",
        )
        await self.session.flush()
        return True

    # ── Users ────────────────────────────────────────────────────────────────

    async def toggle_admin(self, admin: models.User, target_user_id: int) -> bool | None:
        new_value = await self.users.toggle_admin(target_user_id)
        if new_value is not None:
            await self.logs.log(
                admin_id=admin.id,
                action="toggle_admin",
                details=f"target_user_id={target_user_id},new_is_admin={new_value}",
            )
            await self.session.flush()
        return new_value

    async def notify_admins(self, bot: Bot, text: str, photo: str | None = None) -> None:
        """Send a message to all administrators."""
        admins = await self.users.list_admins()
        for admin in admins:
            try:
                if photo:
                    await bot.send_photo(
                        chat_id=admin.telegram_id,
                        photo=photo,
                        caption=text,
                    )
                else:
                    await bot.send_message(
                        chat_id=admin.telegram_id,
                        text=text,
                    )
            except Exception as e:
                logging.error(f"Failed to notify admin {admin.telegram_id}: {e}")
