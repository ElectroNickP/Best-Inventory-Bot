from aiogram.fsm.state import State, StatesGroup


# ── User flows ──────────────────────────────────────────────────────────────

class TakeItemStates(StatesGroup):
    waiting_for_photo = State()


class ReturnItemStates(StatesGroup):
    waiting_for_photo = State()


# ── Admin: Category management ───────────────────────────────────────────────

class AdminCreateCategory(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()


class AdminEditCategory(StatesGroup):
    waiting_for_new_name = State()


# ── Admin: Item management ───────────────────────────────────────────────────

class AdminCreateItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_code = State()


class AdminEditItem(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_code = State()


class AdminSearch(StatesGroup):
    waiting_for_query = State()
