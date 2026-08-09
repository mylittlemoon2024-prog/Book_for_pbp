"""Inline keyboards used across the bot."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.sheets import Meeting


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Ближайшие встречи", callback_data="list_meetings")
    builder.button(text="📝 Мои записи", callback_data="my_registrations")
    builder.adjust(1)
    return builder.as_markup()


def meetings_list_kb(meetings: list[Meeting]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for meeting in meetings:
        builder.button(text=meeting.label(), callback_data=f"meeting:{meeting.id}")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def meeting_card_kb(meeting_id: str, is_registered: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_registered:
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
