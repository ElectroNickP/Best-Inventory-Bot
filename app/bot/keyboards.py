from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ─────────────────────────── Reply keyboards ────────────────────────────────

def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📦 Оборудование")],
        [KeyboardButton(text="🎒 Мои позиции")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Панель администратора")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📂 Категории"), KeyboardButton(text="📋 Позиции")],
        [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="👥 Пользователи")],
        [KeyboardButton(text="📊 Обзор"), KeyboardButton(text="← Вернуться в меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)


# ─────────────────────── User: category / item lists ────────────────────────

def categories_keyboard(
    categories: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cid, name in categories:
        rows.append([InlineKeyboardButton(text=f"📂 {name}", callback_data=f"cat:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def items_keyboard(
    items: list[tuple[int, str, str]],
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    """items: list of (item_id, name, status_label)"""
    STATUS_EMOJI = {
        "available": "✅",
        "taken": "🔴",
        "lost": "❓",
        "maintenance": "🔧",
    }
    rows: list[list[InlineKeyboardButton]] = []
    for item_id, name, status_label in items:
        emoji = STATUS_EMOJI.get(status_label, "•")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {name}",
                    callback_data=f"item:{item_id}",
                )
            ]
        )
    if show_back:
        rows.append(
            [InlineKeyboardButton(text="← Назад к категориям", callback_data="back:categories")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_actions_keyboard(
    item_id: int,
    can_take: bool,
    can_return: bool,
    category_id: int | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if can_take:
        buttons.append(
            [InlineKeyboardButton(text="✋ Взять позицию", callback_data=f"take:{item_id}")]
        )
    if can_return:
        buttons.append(
            [InlineKeyboardButton(text="↩️ Вернуть позицию", callback_data=f"return:{item_id}")]
        )
    back_data = f"back:items:{item_id}"
    buttons.append(
        [InlineKeyboardButton(text="← Назад к списку", callback_data=back_data)]
    )
    buttons.append(
        [InlineKeyboardButton(text="← К категориям", callback_data="back:categories")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────── Admin: category management ───────────────────────────

def admin_categories_keyboard(
    categories: list[tuple[int, str, bool]],
) -> InlineKeyboardMarkup:
    """categories: list of (id, name, is_active)"""
    rows: list[list[InlineKeyboardButton]] = []
    for cid, name, is_active in categories:
        icon = "📂" if is_active else "🗂"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {name}",
                    callback_data=f"adm_cat:{cid}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="➕ Создать категорию", callback_data="adm_cat:create")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_category_actions_keyboard(category_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "🔴 Деактивировать" if is_active else "🟢 Активировать"
    toggle_data = f"adm_cat_deact:{category_id}" if is_active else f"adm_cat_act:{category_id}"
    buttons = [
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"adm_cat_rename:{category_id}")],
        [InlineKeyboardButton(text="📋 Позиции категории", callback_data=f"adm_items:{category_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton(text="🗑 Удалить навсегда", callback_data=f"adm_cat_del:{category_id}")],
        [InlineKeyboardButton(text="← Назад к категориям", callback_data="adm_back:categories")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_confirm_delete_category_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить", callback_data=f"adm_cat_del_yes:{category_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"adm_cat:{category_id}"
                ),
            ]
        ]
    )


# ───────────────────── Admin: item management ────────────────────────────────

def admin_items_keyboard(
    items: list[tuple[int, str, str]],
    category_id: int,
) -> InlineKeyboardMarkup:
    """items: list of (item_id, name, status)"""
    STATUS_EMOJI = {
        "available": "✅",
        "taken": "🔴",
        "lost": "❓",
        "maintenance": "🔧",
    }
    rows: list[list[InlineKeyboardButton]] = []
    for item_id, name, status in items:
        emoji = STATUS_EMOJI.get(status, "•")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {name}",
                    callback_data=f"adm_item:{item_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить позицию",
                callback_data=f"adm_item_create:{category_id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="← Назад к категории", callback_data=f"adm_cat:{category_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_item_actions_keyboard(item_id: int, category_id: int, status: str) -> InlineKeyboardMarkup:
    STATUS_LIST = [
        ("available", "✅ Доступно"),
        ("taken", "🔴 Выдано"),
        ("maintenance", "🔧 На обслуживании"),
        ("lost", "❓ Утеряно"),
    ]
    status_buttons = []
    for st_key, st_label in STATUS_LIST:
        if st_key != status:
            status_buttons.append(
                InlineKeyboardButton(
                    text=f"→ {st_label}",
                    callback_data=f"adm_item_status:{item_id}:{st_key}",
                )
            )
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"adm_item_rename:{item_id}")],
        [InlineKeyboardButton(text="🏷 Изменить инв. код", callback_data=f"adm_item_code:{item_id}")],
        status_buttons,
        [InlineKeyboardButton(text="🗑 Удалить позицию", callback_data=f"adm_item_del:{item_id}")],
        [InlineKeyboardButton(text="← Назад к списку", callback_data=f"adm_items:{category_id}")],
    ]
    # remove empty rows
    buttons = [row for row in buttons if row]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_confirm_delete_item_keyboard(item_id: int, category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить", callback_data=f"adm_item_del_yes:{item_id}:{category_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"adm_item:{item_id}"
                ),
            ]
        ]
    )


# ─────────────────────── Admin: user management ─────────────────────────────

def admin_users_keyboard(
    users: list[tuple[int, str, bool]],
) -> InlineKeyboardMarkup:
    """users: list of (user_id, display_name, is_admin)"""
    rows: list[list[InlineKeyboardButton]] = []
    for uid, name, is_admin in users:
        icon = "👑" if is_admin else "👤"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {name}",
                    callback_data=f"adm_user:{uid}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions_keyboard(user_id: int, is_admin: bool) -> InlineKeyboardMarkup:
    toggle_text = "⬇️ Снять права админа" if is_admin else "⬆️ Назначить админом"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text, callback_data=f"adm_user_toggle:{user_id}"
                )
            ],
            [InlineKeyboardButton(text="← Назад к пользователям", callback_data="adm_back:users")],
        ]
    )


# ─────────────────────── Cancel keyboard ────────────────────────────────────

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="adm_cancel")]
        ]
    )


# ─────────────────────── Overview keyboards ──────────────────────────────────

def overview_on_hands_keyboard(
    items: list[tuple[int, str, str]],
) -> InlineKeyboardMarkup:
    """
    items: list of (item_id, item_name, holder_display)
    """
    rows: list[list[InlineKeyboardButton]] = []
    for item_id, item_name, holder in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔴 {item_name} — {holder}",
                    callback_data=f"ovr_item:{item_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="✅ Доступные позиции", callback_data="ovr_available")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def overview_available_keyboard(
    items: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """items: list of (item_id, name)"""
    rows: list[list[InlineKeyboardButton]] = []
    for item_id, name in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ {name}",
                    callback_data=f"ovr_item:{item_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="← Назад к обзору", callback_data="ovr_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_history_keyboard(
    transactions: list[tuple[int, str, str, str]],
    item_id: int,
) -> InlineKeyboardMarkup:
    """
    transactions: list of (tx_id, action_label, user_name, date_str)
    """
    rows: list[list[InlineKeyboardButton]] = []
    for tx_id, action_label, user_name, date_str in transactions:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{action_label} {user_name} · {date_str}",
                    callback_data=f"ovr_tx:{tx_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="← Назад к обзору", callback_data="ovr_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tx_photo_keyboard(tx_id: int, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Посмотреть фото",
                    callback_data=f"ovr_photo:{tx_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Назад к истории",
                    callback_data=f"ovr_item:{item_id}",
                )
            ],
        ]
    )


def admin_search_results_keyboard(
    items: list[tuple[int, str, str]],
) -> InlineKeyboardMarkup:
    """items: list of (item_id, name, status)"""
    STATUS_EMOJI = {
        "available": "✅",
        "taken": "🔴",
        "lost": "❓",
        "maintenance": "🔧",
    }
    rows: list[list[InlineKeyboardButton]] = []
    for item_id, name, status in items:
        emoji = STATUS_EMOJI.get(status, "•")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {name}",
                    callback_data=f"ovr_item:{item_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="← Назад", callback_data="adm_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
