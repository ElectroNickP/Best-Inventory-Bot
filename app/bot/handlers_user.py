from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    cancel_keyboard,
    categories_keyboard,
    item_actions_keyboard,
    items_keyboard,
    main_menu_keyboard,
)
from app.bot.states import ReturnItemStates, TakeItemStates
from app.config import get_settings
from app.core.admin_service import AdminService
from app.core.inventory_service import InventoryService
from app.db.models import ItemStatus
from app.db.session import get_session


user_router = Router()


async def _ensure_user(from_user):
    settings = get_settings()
    async with get_session() as session:
        service = InventoryService(session)
        user = await service.ensure_user(
            telegram_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        await session.commit()
    return user


# ────────────────────────── /start ──────────────────────────────────────────

@user_router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _ensure_user(message.from_user)
    name = message.from_user.first_name or "!"
    await message.answer(
        f"👋 Привет, {name}!\n\nЯ помогу вам управлять инвентарём.\n"
        "Выберите действие в меню ниже:",
        reply_markup=main_menu_keyboard(is_admin=user.is_admin),
    )


# ──────────────────── Equipment list ────────────────────────────────────────

@user_router.message(F.text == "📦 Оборудование")
async def show_categories(message: Message) -> None:
    async with get_session() as session:
        service = InventoryService(session)
        categories = await service.list_categories()

    if not categories:
        await message.answer(
            "📂 Категорий пока нет.\nОбратитесь к администратору."
        )
        return

    data = [(c.id, c.name) for c in categories]
    await message.answer(
        "📂 Выберите категорию:",
        reply_markup=categories_keyboard(data),
    )


# ─────────────────────── My items ───────────────────────────────────────────

@user_router.message(F.text == "🎒 Мои позиции")
async def my_items(message: Message) -> None:
    settings = get_settings()
    async with get_session() as session:
        service = InventoryService(session)
        user = await service.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        items = await service.list_items_for_user(user.id)

    if not items:
        await message.answer("🎒 У вас нет выданных позиций.")
        return

    formatted = [(item.id, item.name, "taken") for item in items]
    await message.answer(
        f"🎒 Ваши позиции ({len(items)} шт.):",
        reply_markup=items_keyboard(formatted, show_back=False),
    )


# ─────────────────────── Category selected ───────────────────────────────────

@user_router.callback_query(F.data.startswith("cat:"))
async def on_category_selected(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        service = InventoryService(session)
        items = await service.list_items_for_category(category_id)

    if not items:
        await callback.message.edit_text(
            "📦 В этой категории пока нет позиций.\n",
            reply_markup=__back_to_cats_kb(),
        )
        await callback.answer()
        return

    formatted = [(item.id, item.name, item.status.value) for item in items]
    await callback.message.edit_text(
        f"📦 Выберите позицию ({len(items)} шт.):",
        reply_markup=items_keyboard(formatted),
    )
    await callback.answer()


def __back_to_cats_kb():
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← К категориям", callback_data="back:categories")]
        ]
    )


@user_router.callback_query(F.data == "back:categories")
async def back_to_categories(callback: CallbackQuery) -> None:
    async with get_session() as session:
        service = InventoryService(session)
        categories = await service.list_categories()

    if not categories:
        await callback.message.edit_text(
            "📂 Категорий пока нет. Обратитесь к администратору."
        )
        await callback.answer()
        return

    data = [(c.id, c.name) for c in categories]
    await callback.message.edit_text(
        "📂 Выберите категорию:",
        reply_markup=categories_keyboard(data),
    )
    await callback.answer()


# ─────────────────────── Item selected ───────────────────────────────────────

@user_router.callback_query(F.data.startswith("item:"))
async def on_item_selected(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    settings = get_settings()
    async with get_session() as session:
        service = InventoryService(session)
        user = await service.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        item = await service.items.get_by_id(item_id)

    if item is None:
        await callback.answer("❌ Позиция не найдена", show_alert=True)
        return

    can_take = item.status == ItemStatus.AVAILABLE
    can_return = item.status == ItemStatus.TAKEN and item.current_holder_id == user.id

    STATUS_LABELS = {
        "available": "✅ Доступно",
        "taken": "🔴 Выдано",
        "lost": "❓ Утеряно",
        "maintenance": "🔧 На обслуживании",
    }
    code_info = f"\nИнв. код: <code>{item.inventory_code}</code>" if item.inventory_code else ""
    text = (
        f"<b>📦 {item.name}</b>\n"
        f"Статус: {STATUS_LABELS.get(item.status.value, item.status.value)}"
        f"{code_info}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=item_actions_keyboard(
            item_id=item.id,
            can_take=can_take,
            can_return=can_return,
            category_id=item.category_id,
        ),
    )
    await callback.answer()


@user_router.callback_query(F.data.startswith("back:items:"))
async def back_to_items(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", maxsplit=2)[2])
    async with get_session() as session:
        service = InventoryService(session)
        item = await service.items.get_by_id(item_id)
        if item is None:
            await callback.answer("❌ Позиция не найдена", show_alert=True)
            return
        items = await service.list_items_for_category(item.category_id)

    if not items:
        await callback.message.edit_text(
            "📦 Позиций нет.",
            reply_markup=__back_to_cats_kb(),
        )
        await callback.answer()
        return

    formatted = [(it.id, it.name, it.status.value) for it in items]
    await callback.message.edit_text(
        f"📦 Выберите позицию ({len(items)} шт.):",
        reply_markup=items_keyboard(formatted),
    )
    await callback.answer()


# ─────────────────────── Take item ───────────────────────────────────────────

@user_router.callback_query(F.data.startswith("take:"))
async def start_take_item(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(item_id=item_id)
    await state.set_state(TakeItemStates.waiting_for_photo)
    await callback.message.edit_text(
        "📸 Отправьте фото позиции для подтверждения получения.\n"
        "<i>Нажмите «Отменить» чтобы отказаться.</i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@user_router.message(TakeItemStates.waiting_for_photo, F.photo)
async def receive_take_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    item_id = data.get("item_id")
    if item_id is None:
        await message.answer("❌ Ошибка: позиция не задана.")
        await state.clear()
        return

    photo = message.photo[-1]
    settings = get_settings()
    async with get_session() as session:
        service = InventoryService(session)
        user = await service.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        try:
            await service.take_item(
                item_id=item_id,
                user=user,
                photo_file_id=photo.file_id,
            )
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return

        # Notify admins
        item = await service.items.get_by_id(item_id)
        admin_svc = AdminService(session)
        user_display = message.from_user.full_name or message.from_user.username or f"ID {message.from_user.id}"
        await admin_svc.notify_admins(
            bot=message.bot,
            text=f"✋ <b>Позиция взята</b>\n\n📦 Предмет: {item.name}\n👤 Кто: {user_display}",
            photo=photo.file_id,
        )
        await session.commit()

    await state.clear()
    user_name = message.from_user.first_name or "Вы"
    await message.answer(
        f"✅ {user_name}, позиция взята и зафиксирована!\n"
        "Не забудьте вернуть её после использования.",
        reply_markup=main_menu_keyboard(is_admin=user.is_admin),
    )


@user_router.message(TakeItemStates.waiting_for_photo)
async def expect_photo_for_take(message: Message) -> None:
    await message.answer("📸 Пожалуйста, отправьте фото (не текст).")


# ─────────────────────── Return item ─────────────────────────────────────────

@user_router.callback_query(F.data.startswith("return:"))
async def start_return_item(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(item_id=item_id)
    await state.set_state(ReturnItemStates.waiting_for_photo)
    await callback.message.edit_text(
        "📸 Отправьте фото позиции для подтверждения возврата.\n"
        "<i>Нажмите «Отменить» чтобы отказаться.</i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@user_router.message(ReturnItemStates.waiting_for_photo, F.photo)
async def receive_return_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    item_id = data.get("item_id")
    if item_id is None:
        await message.answer("❌ Ошибка: позиция не задана.")
        await state.clear()
        return

    photo = message.photo[-1]
    settings = get_settings()
    async with get_session() as session:
        service = InventoryService(session)
        user = await service.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        try:
            await service.return_item(
                item_id=item_id,
                user=user,
                photo_file_id=photo.file_id,
            )
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return

        # Notify admins
        item = await service.items.get_by_id(item_id)
        admin_svc = AdminService(session)
        user_display = message.from_user.full_name or message.from_user.username or f"ID {message.from_user.id}"
        await admin_svc.notify_admins(
            bot=message.bot,
            text=f"↩️ <b>Позиция возвращена</b>\n\n📦 Предмет: {item.name}\n👤 Кто: {user_display}",
            photo=photo.file_id,
        )
        await session.commit()

    await state.clear()
    user_name = message.from_user.first_name or "Вы"
    await message.answer(
        f"✅ {user_name}, позиция успешно возвращена!",
        reply_markup=main_menu_keyboard(is_admin=user.is_admin),
    )


@user_router.message(ReturnItemStates.waiting_for_photo)
async def expect_photo_for_return(message: Message) -> None:
    await message.answer("📸 Пожалуйста, отправьте фото (не текст).")


# ─────────────────────── Cancel ──────────────────────────────────────────────

@user_router.callback_query(F.data == "adm_cancel")
async def user_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()
