"""Helpers that swallow specific, harmless Telegram API errors.

Telegram raises TelegramBadRequest for conditions that aren't really
failures from the bot's point of view — editing a message with content
identical to what's already shown, or deleting a message Telegram no
longer lets anyone delete (too old, or already gone). Letting either
propagate crashes the whole update instead of just skipping a no-op.
"""
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

_IGNORED_EDIT_ERRORS = ("message is not modified",)
_IGNORED_DELETE_ERRORS = ("message can't be deleted", "message to delete not found")


async def safe_edit_text(
    message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if not any(marker in str(exc) for marker in _IGNORED_EDIT_ERRORS):
            raise


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest as exc:
        if not any(marker in str(exc) for marker in _IGNORED_DELETE_ERRORS):
            raise
