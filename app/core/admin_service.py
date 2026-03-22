from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from aiogram import Bot

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db import models
from app.db.models import ItemStatus, TransactionAction
from app.db.repositories import (
    AdminLogRepository,
    CategoryRepository,
    ItemRepository,
    ProblemReportRepository,
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

    @property
    def problem_reports(self) -> ProblemReportRepository:
        return ProblemReportRepository(self.session)

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

    async def send_user_message(
        self, bot: Bot, admin: models.User, target_user: models.User, text: str, reply_markup=None
    ) -> bool:
        """Send a message from an admin to a specific user and log it."""
        try:
            await bot.send_message(
                chat_id=target_user.telegram_id,
                text=f"✉️ <b>Сообщение от администратора {admin.first_name}:</b>\n\n{text}",
                reply_markup=reply_markup,
            )
            await self.logs.log(
                admin_id=admin.id,
                action="send_user_msg",
                details=f"target_user_id={target_user.id},text={text[:50]}...",
            )
            await self.session.flush()
            return True
        except Exception as e:
            logging.error(f"Failed to send message to user {target_user.telegram_id}: {e}")
            return False

    # ── Statistics & Problems ────────────────────────────────────────────────

    async def list_unresolved_problems(self) -> Sequence[models.ProblemReport]:
        return await self.problem_reports.list_unresolved()

    async def resolve_problem(self, admin: models.User, report_id: int) -> bool:
        ok = await self.problem_reports.resolve(report_id)
        if ok:
            await self.logs.log(
                admin_id=admin.id,
                action="resolve_problem",
                details=f"report_id={report_id}",
            )
            await self.session.flush()
        return ok

    async def get_statistics(self) -> dict:
        """Calculate various bot statistics."""
        # 1. Total items counts by status
        status_counts = {}
        for status in ItemStatus:
            stmt = select(func.count(models.Item.id)).where(models.Item.status == status)
            result = await self.session.execute(stmt)
            status_counts[status.value] = result.scalar() or 0

        # 2. Most active items (top 5 by transaction count)
        items_stmt = (
            select(models.Item.name, func.count(models.Transaction.id).label("tx_count"))
            .join(models.Transaction, models.Item.id == models.Transaction.item_id)
            .group_by(models.Item.id)
            .order_by(func.count(models.Transaction.id).desc())
            .limit(5)
        )
        items_result = await self.session.execute(items_stmt)
        top_items = [
            {"name": r[0], "count": r[1]} for r in items_result.all()
        ]

        # 3. Most active users (top 5 by transaction count)
        users_stmt = (
            select(models.User, func.count(models.Transaction.id).label("tx_count"))
            .join(models.Transaction, models.User.id == models.Transaction.user_id)
            .group_by(models.User.id)
            .order_by(func.count(models.Transaction.id).desc())
            .limit(5)
        )
        users_result = await self.session.execute(users_stmt)
        top_users = [
            {"name": f"{u.first_name} {u.last_name or ''}".strip() or u.username or str(u.telegram_id), "count": cnt}
            for u, cnt in users_result.all()
        ]

        return {
            "status_counts": status_counts,
            "top_items": top_items,
            "top_users": top_users,
        }
