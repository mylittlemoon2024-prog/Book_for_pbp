"""Handlers for the 'Choose a book' catalog: genre -> random book card."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.keyboards import book_card_kb, genres_kb
from bot.services.sheets import GENRES, Book

logger = logging.getLogger(__name__)
router = Router(name="books")

# Imported lazily from registration.py to reuse the single SheetsService
# instance rather than opening a second connection to the spreadsheet.
from bot.handlers.registration import sheets  # noqa: E402


async def _send_book_card(callback: CallbackQuery, genre: str, genre_idx: int, book: Book) -> None:
    all_in_genre = await asyncio.to_thread(sheets.books_by_genre, genre)
    kb = book_card_kb(genre_idx, book.id, has_more=len(all_in_genre) > 1)

    await callback.message.delete()
    if book.photo_url:
        try:
            await callback.message.answer_photo(
                photo=book.photo_url, caption=book.caption(), reply_markup=kb
            )
            return
        except TelegramBadRequest:
            logger.warning("Could not load photo for book %s: %s", book.id, book.photo_url)
    await callback.message.answer(book.caption(), reply_markup=kb)


@router.callback_query(F.data == "browse_books")
async def cb_browse_books(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.message.answer("Выберите жанр:", reply_markup=genres_kb(list(GENRES)))
    await callback.answer()


@router.callback_query(F.data.startswith("genre_idx:"))
async def cb_genre_selected(callback: CallbackQuery) -> None:
    idx = int(callback.data.split(":", 1)[1])
    if idx >= len(GENRES):
        await callback.answer("Этот жанр больше недоступен, откройте список заново", show_alert=True)
        return
    genre = GENRES[idx]

    book = await asyncio.to_thread(sheets.random_book, genre)
    if book is None:
        await callback.answer("В этом жанре пока нет книг", show_alert=True)
        return

    await _send_book_card(callback, genre, idx, book)
    await callback.answer()


@router.callback_query(F.data.startswith("book_reroll:"))
async def cb_book_reroll(callback: CallbackQuery) -> None:
    _, idx_str, last_book_id = callback.data.split(":", 2)
    idx = int(idx_str)
    if idx >= len(GENRES):
        await callback.answer("Этот жанр больше недоступен, откройте список заново", show_alert=True)
        return
    genre = GENRES[idx]

    book = await asyncio.to_thread(sheets.random_book, genre, exclude_id=last_book_id)
    if book is None:
        await callback.answer("В этом жанре пока нет книг", show_alert=True)
        return

    await _send_book_card(callback, genre, idx, book)
    await callback.answer()
