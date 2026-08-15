"""Inline keyboards used across the bot."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.sheets import Meeting


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="ℹ️ О проекте", callback_data="about_project")
    builder.button(text="📅 Записаться на встречу", callback_data="list_meetings")
    builder.button(text="📝 Мои записи", callback_data="my_registrations")
    builder.button(text="📚 Выбрать книгу", callback_data="browse_books")
    builder.button(text="🎓 Лекции", callback_data="browse_lectures")
    builder.button(text="🤝 Контактная информация", callback_data="cooperation")
    builder.adjust(1)
    return builder.as_markup()


def about_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Оставить предложение", callback_data="leave_suggestion")
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    return builder.as_markup()


def genres_kb(genres: list[str]) -> InlineKeyboardMarkup:
    # Genres are referenced by their position in the list rather than
    # embedding the raw text in callback_data — keeps payloads short and safe
    # regardless of how long a genre name is.
    builder = InlineKeyboardBuilder()
    for idx, genre in enumerate(genres):
        builder.button(text=genre, callback_data=f"genre_idx:{idx}")
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def book_card_kb(genre_idx: int, book_id: str, has_more: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_more:
        builder.button(text="🔀 Другая книга", callback_data=f"book_reroll:{genre_idx}:{book_id}")
    builder.button(text="⬅️ Другой жанр", callback_data="browse_books")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def lecture_categories_kb(categories: list[str]) -> InlineKeyboardMarkup:
    # Same positional-index trick as genres_kb — keeps callback_data short
    # regardless of how long a category name is.
    builder = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        builder.button(text=category, callback_data=f"lecture_cat_idx:{idx}")
    builder.button(text="⬅️ В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def lecture_card_kb(category_idx: int, lecture_id: str, has_more: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_more:
        builder.button(
            text="🔀 Другая лекция", callback_data=f"lecture_reroll:{category_idx}:{lecture_id}"
        )
    builder.button(text="⬅️ Другое направление", callback_data="browse_lectures")
    builder.button(text="🏠 В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def meetings_list_kb(meetings: list[Meeting]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for meeting in meetings:
        builder.button(text=meeting.label(), callback_data=f"meeting:{meeting.id}")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def meeting_card_kb(
    meeting_id: str, is_registered: bool, can_cancel: bool = True
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_registered:
        if can_cancel:
            builder.button(text="❌ Отменить запись", callback_data=f"cancel:{meeting_id}")
    else:
        builder.button(text="✅ Записаться", callback_data=f"register:{meeting_id}")
    builder.button(text="⬅️ К списку встреч", callback_data="list_meetings")
    builder.adjust(1)
    return builder.as_markup()


def cancel_fsm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="main_menu")
    return builder.as_markup()


def consent_kb(agree_callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен(на), продолжить", callback_data=agree_callback_data)
    builder.button(text="❌ Отмена", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
