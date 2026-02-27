from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    admin_categories_keyboard,
    admin_category_actions_keyboard,
    admin_confirm_delete_category_keyboard,
    admin_confirm_delete_item_keyboard,
    admin_item_actions_keyboard,
    admin_items_keyboard,
    admin_main_keyboard,
    admin_user_actions_keyboard,
    admin_users_keyboard,
    cancel_keyboard,
    item_history_keyboard,
    main_menu_keyboard,
    overview_available_keyboard,
    overview_on_hands_keyboard,
    tx_photo_keyboard,
    admin_search_results_keyboard,
)
from app.bot.states import (
    AdminCreateCategory,
    AdminCreateItem,
    AdminEditCategory,
    AdminEditItem,
    AdminSearch,
)
from app.config import get_settings
from app.core.admin_service import AdminService
from app.core.inventory_service import InventoryService
from app.db.models import ItemStatus
from app.db.session import get_session


admin_router = Router()


# ────────────────────────── Helpers ─────────────────────────────────────────

async def _get_admin_user(from_user):
    """Return User if admin, else None."""
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        user = await inv.ensure_user(
            telegram_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        await session.commit()
    return user if user.is_admin else None


async def _require_admin(message_or_cb) -> bool:
    """Send error and return False if not admin."""
    from_user = getattr(message_or_cb, "from_user", None)
    if from_user is None:
        return False
    if isinstance(message_or_cb, CallbackQuery):
        user = await _get_admin_user(from_user)
        if not user:
            await message_or_cb.answer("⛔ Нет доступа.", show_alert=True)
            return False
    else:
        user = await _get_admin_user(from_user)
        if not user:
            await message_or_cb.answer("⛔ У вас нет прав администратора.")
            return False
    return True


def _user_display(user) -> str:
    parts = []
    if user.first_name:
        parts.append(user.first_name)
    if user.last_name:
        parts.append(user.last_name)
    name = " ".join(parts) if parts else "—"
    if user.username:
        name += f" (@{user.username})"
    return name


# ──────────────────────── Admin entry / back ─────────────────────────────────

@admin_router.message(F.text == "⚙️ Панель администратора")
async def admin_entry(message: Message) -> None:
    if not await _require_admin(message):
        return
    await message.answer("⚙️ Панель администратора:", reply_markup=admin_main_keyboard())


@admin_router.message(F.text == "← Вернуться в меню")
@admin_router.message(F.text == "← Вернуться в меню")
async def back_to_user_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        user = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
    await message.answer(
        "🏠 Главное меню:",
        reply_markup=main_menu_keyboard(is_admin=user.is_admin),
    )


# ─────────────────────── Inventory overview ─────────────────────────────────

def _fmt_dt(dt) -> str:
    """Format datetime to readable local-ish string."""
    if dt is None:
        return "—"
    # Store is UTC, display as-is with label
    return dt.strftime("%d.%m.%Y %H:%M")


def _user_short(user) -> str:
    if user is None:
        return "неизвестно"
    parts = []
    if user.first_name:
        parts.append(user.first_name)
    if user.last_name:
        parts.append(user.last_name)
    name = " ".join(parts) if parts else ""
    if user.username:
        name = f"{name} (@{user.username})".strip()
    return name or f"ID {user.telegram_id}"


async def _build_overview_text_and_kb():
    """Build overview: on-hands items with real names + date taken."""
    from app.db.repositories import ItemRepository, TransactionRepository, CategoryRepository
    from app.db.models import ItemStatus

    async with get_session() as session:
        item_repo = ItemRepository(session)
        tx_repo = TransactionRepository(session)
        cat_repo = CategoryRepository(session)

        on_hands = await item_repo.list_on_hands()
        available = await item_repo.list_available()
        categories = await cat_repo.list_all()

        # Get last TAKE tx for each taken item
        on_hands_details = []
        for item in on_hands:
            tx = await tx_repo.get_latest_take_for_item(item.id)
            holder_name = _user_short(tx.user) if tx else "неизвестно"
            date_str = _fmt_dt(tx.created_at) if tx else "—"
            on_hands_details.append((item.id, item.name, holder_name, date_str))

    total_cats = len([c for c in categories if c.is_active])
    text_lines = [
        "<b>📊 Обзор инвентаря</b>",
        "",
        f"📂 Активных категорий: <b>{total_cats}</b>",
        f"✅ Доступно: <b>{len(available)}</b>   🔴 Выдано: <b>{len(on_hands)}</b>",
    ]

    if on_hands_details:
        text_lines.append("")
        text_lines.append("<b>Выдано сейчас — нажми для истории:</b>")
        for _, name, holder, date_str in on_hands_details:
            text_lines.append(f"  🔴 <b>{name}</b>")
            text_lines.append(f"      👤 {holder}  📅 {date_str}")
    else:
        text_lines.append("")
        text_lines.append("<i>Все позиции доступны.</i>")

    kb_items = [(iid, iname, holder) for iid, iname, holder, _ in on_hands_details]
    return "\n".join(text_lines), kb_items, len(available)


@admin_router.message(F.text == "📊 Обзор")
async def inventory_overview(message: Message) -> None:
    if not await _require_admin(message):
        return

    text, kb_items, available_count = await _build_overview_text_and_kb()
    await message.answer(
        text,
        reply_markup=overview_on_hands_keyboard(kb_items),
    )


@admin_router.callback_query(F.data == "ovr_back")
async def ovr_back_to_overview(callback: CallbackQuery) -> None:
    text, kb_items, _ = await _build_overview_text_and_kb()
    await callback.message.edit_text(text, reply_markup=overview_on_hands_keyboard(kb_items))
    await callback.answer()


@admin_router.callback_query(F.data == "ovr_available")
async def ovr_show_available(callback: CallbackQuery) -> None:
    async with get_session() as session:
        from app.db.repositories import ItemRepository
        item_repo = ItemRepository(session)
        available = await item_repo.list_available()

    if not available:
        await callback.answer("✅ Нет доступных позиций", show_alert=True)
        return

    items_data = [(it.id, it.name) for it in available]
    await callback.message.edit_text(
        f"✅ <b>Доступные позиции</b> ({len(available)} шт.):",
        reply_markup=overview_available_keyboard(items_data),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("ovr_item:"))
async def ovr_item_history(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])

    async with get_session() as session:
        from app.db.repositories import ItemRepository, TransactionRepository
        from app.db.models import TransactionAction
        item_repo = ItemRepository(session)
        tx_repo = TransactionRepository(session)

        item = await item_repo.get_by_id(item_id)
        if item is None:
            await callback.answer("❌ Позиция не найдена", show_alert=True)
            return

        transactions = await tx_repo.list_for_item_with_user(item_id, limit=30)

    STATUS_LABELS = {
        "available": "✅ Доступно",
        "taken": "🔴 Выдано",
        "lost": "❓ Утеряно",
        "maintenance": "🔧 На обслуживании",
    }
    status_label = STATUS_LABELS.get(item.status.value, item.status.value)
    code_info = f"\nКод: <code>{item.inventory_code}</code>" if item.inventory_code else ""

    if transactions:
        # Current holder info from last TAKE
        from app.db.models import TransactionAction as TA
        last_take = next((t for t in transactions if t.action.value == "take"), None)
        holder_info = ""
        if last_take and item.status.value == "taken":
            holder_info = (
                f"\n👤 Держатель: <b>{_user_short(last_take.user)}</b>"
                f"\n📅 Взято: <b>{_fmt_dt(last_take.created_at)}</b>"
            )

        tx_data = []
        for t in transactions:
            action_emoji = "✋" if t.action.value == "take" else "↩️"
            date_str = _fmt_dt(t.created_at)
            u_name = _user_short(t.user)
            tx_data.append((t.id, action_emoji, u_name, date_str))

        text = (
            f"<b>📦 {item.name}</b>"
            f"\nСтатус: {status_label}"
            f"{code_info}"
            f"{holder_info}"
            f"\n\n<b>История ({len(transactions)} записей):</b>"
            f"\n<i>Нажми на запись — увидишь детали и фото</i>"
        )
        await callback.message.edit_text(
            text,
            reply_markup=item_history_keyboard(tx_data, item_id),
        )
    else:
        text = (
            f"<b>📦 {item.name}</b>"
            f"\nСтатус: {status_label}"
            f"{code_info}"
            f"\n\n<i>История операций пуста.</i>"
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад к обзору", callback_data="ovr_back")]
        ])
        await callback.message.edit_text(text, reply_markup=kb)

    await callback.answer()


@admin_router.callback_query(F.data.startswith("ovr_tx:"))
async def ovr_transaction_detail(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":", maxsplit=1)[1])

    async with get_session() as session:
        from app.db.repositories import TransactionRepository
        from sqlalchemy.orm import joinedload
        from sqlalchemy import select
        from app.db.models import Transaction
        from app.db.session import _session_factory

        tx_repo = TransactionRepository(session)
        # Fetch with user and item eagerly loaded
        from sqlalchemy.orm import joinedload
        stmt = (
            select(Transaction)
            .where(Transaction.id == tx_id)
            .options(
                joinedload(Transaction.user),
                joinedload(Transaction.item),
            )
        )
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()

    if tx is None:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    action_label = "✋ Взятие" if tx.action.value == "take" else "↩️ Возврат"
    item_name = tx.item.name if tx.item else f"#{tx.item_id}"
    user_name = _user_short(tx.user)
    date_str = _fmt_dt(tx.created_at)
    comment = f"\n💬 Комментарий: {tx.comment}" if tx.comment else ""

    text = (
        f"<b>{action_label}</b>"
        f"\n\n📦 Позиция: <b>{item_name}</b>"
        f"\n👤 Пользователь: <b>{user_name}</b>"
        f"\n📅 Дата: <b>{date_str}</b>"
        f"{comment}"
        f"\n\n📸 Фото прикреплено — нажмите кнопку ниже чтобы посмотреть"
    )
    await callback.message.edit_text(
        text,
        reply_markup=tx_photo_keyboard(tx_id=tx.id, item_id=tx.item_id),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("ovr_photo:"))
async def ovr_show_photo(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":", maxsplit=1)[1])

    async with get_session() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.db.models import Transaction
        stmt = (
            select(Transaction)
            .where(Transaction.id == tx_id)
            .options(
                joinedload(Transaction.user),
                joinedload(Transaction.item),
            )
        )
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()

    if tx is None:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    if not tx.photo_file_id:
        await callback.answer("📸 Фото отсутствует", show_alert=True)
        return

    action_label = "✋ Взятие" if tx.action.value == "take" else "↩️ Возврат"
    item_name = tx.item.name if tx.item else f"#{tx.item_id}"
    user_name = _user_short(tx.user)
    date_str = _fmt_dt(tx.created_at)

    caption = (
        f"<b>{action_label}</b> — {item_name}"
        f"\n👤 {user_name}   📅 {date_str}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад к истории", callback_data=f"ovr_item:{tx.item_id}")]
    ])

    await callback.message.answer_photo(
        photo=tx.photo_file_id,
        caption=caption,
        reply_markup=back_kb,
    )
    await callback.answer()


# ─────────────────────── Search ──────────────────────────────────────────────

@admin_router.message(F.text == "🔍 Поиск")
async def admin_search_start(message: Message, state: FSMContext) -> None:
    if not await _require_admin(message):
        return
    await state.set_state(AdminSearch.waiting_for_query)
    await message.answer(
        "🔎 <b>Поиск по инвентарю</b>\n\n"
        "Введите название предмета или инвентарный код:",
        reply_markup=cancel_keyboard(),
    )


@admin_router.message(AdminSearch.waiting_for_query)
async def admin_search_process(message: Message, state: FSMContext) -> None:
    query = message.text.strip() if message.text else ""
    if not query:
        await message.answer("❌ Запрос не может быть пустым. Попробуйте ещё раз:")
        return

    async with get_session() as session:
        svc = AdminService(session)
        items = await svc.items.search(query)

    if not items:
        await message.answer(
            f"🔎 По запросу «{query}» ничего не найдено.\n"
            "Попробуйте другое слово или код.",
            reply_markup=admin_main_keyboard(),
        )
        await state.clear()
        return

    results = [(it.id, it.name, it.status.value) for it in items]
    await message.answer(
        f"🔎 Результаты поиска по запросу «{query}» ({len(items)}):",
        reply_markup=admin_search_results_keyboard(results),
    )
    await state.clear()


# ══════════════════════ CATEGORIES MANAGEMENT ═══════════════════════════════

@admin_router.message(F.text == "📂 Категории")
async def admin_categories_list(message: Message, state: FSMContext) -> None:
    if not await _require_admin(message):
        return
    await state.clear()
    async with get_session() as session:
        svc = AdminService(session)
        categories = await svc.categories.list_all()

    data = [(c.id, c.name, c.is_active) for c in categories]
    if not data:
        text = "📂 Категорий ещё нет.\nНажмите ➕, чтобы создать первую."
    else:
        text = f"📂 <b>Категории</b> ({len(data)} шт.):"

    await message.answer(
        text,
        reply_markup=admin_categories_keyboard(data),
    )


@admin_router.callback_query(F.data == "adm_back:categories")
async def adm_back_to_categories(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        svc = AdminService(session)
        categories = await svc.categories.list_all()

    data = [(c.id, c.name, c.is_active) for c in categories]
    text = f"📂 <b>Категории</b> ({len(data)} шт.):" if data else "📂 Категорий пока нет."
    await callback.message.edit_text(text, reply_markup=admin_categories_keyboard(data))
    await callback.answer()


# ── Открыть конкретную категорию ─────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_cat:"))
async def adm_category_detail(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.split(":", maxsplit=1)[1]
    if raw == "create":
        await state.set_state(AdminCreateCategory.waiting_for_name)
        await callback.message.edit_text(
            "📝 Введите <b>название</b> новой категории:",
            reply_markup=cancel_keyboard(),
        )
        await callback.answer()
        return

    category_id = int(raw)
    async with get_session() as session:
        svc = AdminService(session)
        cat = await svc.categories.get_by_id(category_id)

    if cat is None:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    item_count = 0
    async with get_session() as session:
        svc = AdminService(session)
        items = await svc.items.list_by_category(category_id)
        item_count = len(items)

    status_icon = "✅ Активна" if cat.is_active else "🔴 Неактивна"
    text = (
        f"<b>📂 {cat.name}</b>\n"
        f"Статус: {status_icon}\n"
        f"Позиций: {item_count}\n"
        + (f"Описание: {cat.description}" if cat.description else "")
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_category_actions_keyboard(category_id, cat.is_active),
    )
    await callback.answer()


# ── Создать категорию ─────────────────────────────────────────────────────────

@admin_router.message(AdminCreateCategory.waiting_for_name)
async def adm_create_category_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return
    if len(name) > 128:
        await message.answer("❌ Слишком длинное название (макс. 128 символов). Попробуйте короче:")
        return

    await state.update_data(cat_name=name)
    await state.set_state(AdminCreateCategory.waiting_for_description)
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "📝 Введите описание категории (или /skip чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )


@admin_router.message(AdminCreateCategory.waiting_for_description)
async def adm_create_category_desc(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = data["cat_name"]
    description = None
    if message.text and message.text.strip() != "/skip":
        description = message.text.strip()

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        try:
            cat = await svc.create_category(admin=admin, name=name, description=description)
            await session.commit()
        except Exception as e:
            await state.clear()
            await message.answer(f"❌ Ошибка: {e}")
            return

    await state.clear()
    await message.answer(
        f"✅ Категория <b>{cat.name}</b> успешно создана!\n"
        f"ID: {cat.id}"
    )
    # refresh list
    async with get_session() as session:
        svc = AdminService(session)
        categories = await svc.categories.list_all()
    data_list = [(c.id, c.name, c.is_active) for c in categories]
    await message.answer(
        f"📂 <b>Категории</b> ({len(data_list)} шт.):",
        reply_markup=admin_categories_keyboard(data_list),
    )


# ── Переименовать категорию ───────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_cat_rename:"))
async def adm_rename_category_start(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AdminEditCategory.waiting_for_new_name)
    await callback.message.edit_text(
        "✏️ Введите <b>новое название</b> категории:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@admin_router.message(AdminEditCategory.waiting_for_new_name)
async def adm_rename_category_finish(message: Message, state: FSMContext) -> None:
    new_name = message.text.strip() if message.text else ""
    if not new_name:
        await message.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    category_id = data["category_id"]

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.rename_category(admin=admin, category_id=category_id, new_name=new_name)
        await session.commit()

    await state.clear()
    if ok:
        await message.answer(f"✅ Категория переименована в <b>{new_name}</b>.")
    else:
        await message.answer("❌ Категория не найдена.")


# ── Деактивировать / активировать категорию ───────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_cat_deact:"))
async def adm_deactivate_category(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.deactivate_category(admin=admin, category_id=category_id)
        await session.commit()

    if ok:
        await callback.answer("🔴 Категория деактивирована", show_alert=False)
        # refresh detail
        async with get_session() as session:
            svc = AdminService(session)
            cat = await svc.categories.get_by_id(category_id)
        if cat:
            items = []
            async with get_session() as session:
                svc = AdminService(session)
                items = await svc.items.list_by_category(category_id)
            text = (
                f"<b>📂 {cat.name}</b>\nСтатус: 🔴 Неактивна\nПозиций: {len(items)}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=admin_category_actions_keyboard(category_id, False),
            )
    else:
        await callback.answer("❌ Не удалось деактивировать", show_alert=True)


@admin_router.callback_query(F.data.startswith("adm_cat_act:"))
async def adm_activate_category(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.activate_category(admin=admin, category_id=category_id)
        await session.commit()

    if ok:
        await callback.answer("🟢 Категория активирована", show_alert=False)
        async with get_session() as session:
            svc = AdminService(session)
            cat = await svc.categories.get_by_id(category_id)
            items = await svc.items.list_by_category(category_id)
        if cat:
            text = (
                f"<b>📂 {cat.name}</b>\nСтатус: ✅ Активна\nПозиций: {len(items)}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=admin_category_actions_keyboard(category_id, True),
            )
    else:
        await callback.answer("❌ Не удалось активировать", show_alert=True)


# ── Удалить категорию (подтверждение) ─────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_cat_del:"))
async def adm_delete_category_confirm(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        svc = AdminService(session)
        cat = await svc.categories.get_by_id(category_id)
    name = cat.name if cat else f"#{category_id}"
    await callback.message.edit_text(
        f"⚠️ Удалить категорию <b>{name}</b>?\n"
        "Все позиции внутри тоже будут удалены. Это необратимо!",
        reply_markup=admin_confirm_delete_category_keyboard(category_id),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_cat_del_yes:"))
async def adm_delete_category_execute(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.delete_category(admin=admin, category_id=category_id)
        await session.commit()

    if ok:
        await callback.answer("🗑 Категория удалена", show_alert=False)
        # refresh list
        async with get_session() as session:
            svc = AdminService(session)
            categories = await svc.categories.list_all()
        data_list = [(c.id, c.name, c.is_active) for c in categories]
        text = f"📂 <b>Категории</b> ({len(data_list)} шт.):" if data_list else "📂 Категорий пока нет."
        await callback.message.edit_text(text, reply_markup=admin_categories_keyboard(data_list))
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


# ══════════════════════ ITEMS MANAGEMENT ════════════════════════════════════

@admin_router.message(F.text == "📋 Позиции")
async def admin_items_top(message: Message, state: FSMContext) -> None:
    """Entry: show categories to pick from."""
    if not await _require_admin(message):
        return
    await state.clear()
    async with get_session() as session:
        svc = AdminService(session)
        categories = await svc.categories.list_all()

    data = [(c.id, c.name, c.is_active) for c in categories]
    if not data:
        await message.answer(
            "📂 Сначала создайте хотя бы одну категорию (раздел «Категории»).",
        )
        return
    await message.answer(
        "📋 Выберите категорию для управления позициями:",
        reply_markup=admin_categories_keyboard(data),
    )


@admin_router.callback_query(F.data.startswith("adm_items:"))
async def adm_items_list(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        svc = AdminService(session)
        cat = await svc.categories.get_by_id(category_id)
        items = await svc.items.list_by_category(category_id)

    if cat is None:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    formatted = [(it.id, it.name, it.status.value) for it in items]
    text = f"📋 <b>{cat.name}</b> — позиции ({len(items)} шт.):"
    if not items:
        text += "\n<i>Позиций пока нет.</i>"

    await callback.message.edit_text(
        text,
        reply_markup=admin_items_keyboard(formatted, category_id=category_id),
    )
    await callback.answer()


# ── Открыть конкретную позицию ────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item:"))
async def adm_item_detail(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        svc = AdminService(session)
        item = await svc.items.get_by_id(item_id)

    if item is None:
        await callback.answer("❌ Позиция не найдена", show_alert=True)
        return

    STATUS_LABELS = {
        "available": "✅ Доступно",
        "taken": "🔴 Выдано",
        "lost": "❓ Утеряно",
        "maintenance": "🔧 На обслуживании",
    }
    status_label = STATUS_LABELS.get(item.status.value, item.status.value)
    holder_info = ""
    if item.current_holder_id:
        holder_info = f"\nДержатель: user_id={item.current_holder_id}"

    code_info = f"\nКод: <code>{item.inventory_code}</code>" if item.inventory_code else ""

    text = (
        f"<b>📦 {item.name}</b>\n"
        f"Статус: {status_label}"
        f"{code_info}"
        f"{holder_info}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_item_actions_keyboard(
            item_id=item.id,
            category_id=item.category_id,
            status=item.status.value,
        ),
    )
    await callback.answer()


# ── Создать позицию ───────────────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item_create:"))
async def adm_create_item_start(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(item_category_id=category_id)
    await state.set_state(AdminCreateItem.waiting_for_name)
    await callback.message.edit_text(
        "📝 Введите <b>название</b> новой позиции:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@admin_router.message(AdminCreateItem.waiting_for_name)
async def adm_create_item_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("❌ Название не может быть пустым:")
        return
    await state.update_data(item_name=name)
    await state.set_state(AdminCreateItem.waiting_for_code)
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "🏷 Введите инвентарный номер/код (или /skip чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )


@admin_router.message(AdminCreateItem.waiting_for_code)
async def adm_create_item_code(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = data["item_name"]
    category_id = data["item_category_id"]
    code = None
    if message.text and message.text.strip() != "/skip":
        code = message.text.strip()

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        try:
            item = await svc.create_item(
                admin=admin,
                category_id=category_id,
                name=name,
                inventory_code=code,
            )
            await session.commit()
        except Exception as e:
            await state.clear()
            await message.answer(f"❌ Ошибка: {e}")
            return

    await state.clear()
    code_info = f" (код: <code>{item.inventory_code}</code>)" if item.inventory_code else ""
    await message.answer(f"✅ Позиция <b>{item.name}</b>{code_info} добавлена!")

    # refresh items list
    async with get_session() as session:
        svc = AdminService(session)
        items = await svc.items.list_by_category(category_id)
        cat = await svc.categories.get_by_id(category_id)

    formatted = [(it.id, it.name, it.status.value) for it in items]
    cat_name = cat.name if cat else f"#{category_id}"
    await message.answer(
        f"📋 <b>{cat_name}</b> — позиции ({len(items)} шт.):",
        reply_markup=admin_items_keyboard(formatted, category_id=category_id),
    )


# ── Переименовать позицию ─────────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item_rename:"))
async def adm_rename_item_start(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(edit_item_id=item_id)
    await state.set_state(AdminEditItem.waiting_for_new_name)
    await callback.message.edit_text(
        "✏️ Введите <b>новое название</b> позиции:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@admin_router.message(AdminEditItem.waiting_for_new_name)
async def adm_rename_item_finish(message: Message, state: FSMContext) -> None:
    new_name = message.text.strip() if message.text else ""
    if not new_name:
        await message.answer("❌ Название не может быть пустым:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.rename_item(admin=admin, item_id=item_id, new_name=new_name)
        await session.commit()

    await state.clear()
    if ok:
        await message.answer(f"✅ Позиция переименована в <b>{new_name}</b>.")
    else:
        await message.answer("❌ Позиция не найдена.")


# ── Изменить инвентарный код ──────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item_code:"))
async def adm_item_code_start(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(edit_item_id=item_id)
    await state.set_state(AdminEditItem.waiting_for_new_code)
    await callback.message.edit_text(
        "🏷 Введите новый <b>инвентарный код</b> (или /skip чтобы сбросить):",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@admin_router.message(AdminEditItem.waiting_for_new_code)
async def adm_item_code_finish(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    new_code = "" if text == "/skip" else text

    data = await state.get_data()
    item_id = data["edit_item_id"]

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.update_item_code(admin=admin, item_id=item_id, new_code=new_code or "")
        await session.commit()

    await state.clear()
    if ok:
        if new_code:
            await message.answer(f"✅ Инвентарный код обновлён: <code>{new_code}</code>")
        else:
            await message.answer("✅ Инвентарный код сброшен.")
    else:
        await message.answer("❌ Позиция не найдена.")


# ── Изменить статус позиции ───────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item_status:"))
async def adm_item_set_status(callback: CallbackQuery) -> None:
    # adm_item_status:{item_id}:{status_key}
    parts = callback.data.split(":")
    item_id = int(parts[1])
    status_key = parts[2]

    STATUS_MAP = {
        "available": ItemStatus.AVAILABLE,
        "taken": ItemStatus.TAKEN,
        "lost": ItemStatus.LOST,
        "maintenance": ItemStatus.MAINTENANCE,
    }
    new_status = STATUS_MAP.get(status_key)
    if new_status is None:
        await callback.answer("❌ Неверный статус", show_alert=True)
        return

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.set_item_status(admin=admin, item_id=item_id, status=new_status)
        await session.commit()

    if ok:
        STATUS_LABELS = {
            "available": "✅ Доступно",
            "taken": "🔴 Выдано",
            "lost": "❓ Утеряно",
            "maintenance": "🔧 На обслуживании",
        }
        await callback.answer(f"Статус изменён → {STATUS_LABELS.get(status_key, status_key)}")
        # refresh item detail
        async with get_session() as session:
            svc = AdminService(session)
            item = await svc.items.get_by_id(item_id)
        if item:
            text = (
                f"<b>📦 {item.name}</b>\n"
                f"Статус: {STATUS_LABELS.get(item.status.value, '')}"
                + (f"\nКод: <code>{item.inventory_code}</code>" if item.inventory_code else "")
            )
            await callback.message.edit_text(
                text,
                reply_markup=admin_item_actions_keyboard(
                    item_id=item.id,
                    category_id=item.category_id,
                    status=item.status.value,
                ),
            )
    else:
        await callback.answer("❌ Позиция не найдена", show_alert=True)


# ── Удалить позицию ───────────────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_item_del:"))
async def adm_delete_item_confirm(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        svc = AdminService(session)
        item = await svc.items.get_by_id(item_id)

    if item is None:
        await callback.answer("❌ Позиция не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ Удалить позицию <b>{item.name}</b>?\nЭто необратимо!",
        reply_markup=admin_confirm_delete_item_keyboard(item_id, item.category_id),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_item_del_yes:"))
async def adm_delete_item_execute(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    item_id = int(parts[1])
    category_id = int(parts[2])

    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        ok = await svc.delete_item(admin=admin, item_id=item_id)
        await session.commit()

    if ok:
        await callback.answer("🗑 Позиция удалена", show_alert=False)
        # refresh items list
        async with get_session() as session:
            svc = AdminService(session)
            items = await svc.items.list_by_category(category_id)
            cat = await svc.categories.get_by_id(category_id)

        formatted = [(it.id, it.name, it.status.value) for it in items]
        cat_name = cat.name if cat else f"#{category_id}"
        text = f"📋 <b>{cat_name}</b> — позиции ({len(items)} шт.):"
        if not items:
            text += "\n<i>Позиций пока нет.</i>"
        await callback.message.edit_text(
            text,
            reply_markup=admin_items_keyboard(formatted, category_id=category_id),
        )
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


# ══════════════════════ USERS MANAGEMENT ════════════════════════════════════

@admin_router.message(F.text == "👥 Пользователи")
async def admin_users_list(message: Message) -> None:
    if not await _require_admin(message):
        return

    async with get_session() as session:
        svc = AdminService(session)
        users = await svc.users.list_all()

    data = [(u.id, _user_display(u), u.is_admin) for u in users]
    text = f"👥 <b>Пользователи</b> ({len(data)} чел.):"
    await message.answer(text, reply_markup=admin_users_keyboard(data))


@admin_router.callback_query(F.data == "adm_back:users")
async def adm_back_to_users(callback: CallbackQuery) -> None:
    async with get_session() as session:
        svc = AdminService(session)
        users = await svc.users.list_all()

    data = [(u.id, _user_display(u), u.is_admin) for u in users]
    text = f"👥 <b>Пользователи</b> ({len(data)} чел.):"
    await callback.message.edit_text(text, reply_markup=admin_users_keyboard(data))
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_user:"))
async def adm_user_detail(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        svc = AdminService(session)
        user = await svc.users.get_by_id(user_id)

    if user is None:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    role = "👑 Администратор" if user.is_admin else "👤 Пользователь"
    text = (
        f"<b>{_user_display(user)}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Роль: {role}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_user_actions_keyboard(user_id, user.is_admin),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_user_toggle:"))
async def adm_toggle_admin(callback: CallbackQuery) -> None:
    target_user_id = int(callback.data.split(":", maxsplit=1)[1])
    settings = get_settings()
    async with get_session() as session:
        inv = InventoryService(session)
        admin = await inv.ensure_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            initial_admin_ids=settings.initial_admin_ids,
            initial_admin_usernames=settings.initial_admin_usernames,
        )
        svc = AdminService(session)
        new_value = await svc.toggle_admin(admin=admin, target_user_id=target_user_id)
        await session.commit()

    if new_value is None:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    label = "👑 Назначен администратором" if new_value else "👤 Права администратора сняты"
    await callback.answer(label, show_alert=False)

    # refresh user detail
    async with get_session() as session:
        svc = AdminService(session)
        user = await svc.users.get_by_id(target_user_id)

    if user:
        role = "👑 Администратор" if user.is_admin else "👤 Пользователь"
        text = (
            f"<b>{_user_display(user)}</b>\n"
            f"Telegram ID: <code>{user.telegram_id}</code>\n"
            f"Роль: {role}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=admin_user_actions_keyboard(target_user_id, user.is_admin),
        )


# ── Universal cancel ──────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "adm_cancel")
async def adm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()
