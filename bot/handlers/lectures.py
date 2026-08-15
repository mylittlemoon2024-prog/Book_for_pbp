"""Handlers for the 'Lectures' catalog: direction -> random lecture with a
link to the video (YouTube/VK/Rutube — hosted externally, not sent as a
Telegram file)."""
import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import lecture_card_kb, lecture_categories_kb
from bot.services.sheets import LECTURE_CATEGORIES, Lecture

# Imported here (not at module scope) to reuse the single shared
# SheetsService instance that registration.py owns, same pattern as
# books.py/about.py.
from bot.handlers.registration import sheets  # noqa: E402

router = Router(name="lectures")


async def _send_lecture_card(callback: CallbackQuery, category: str, category_idx: int, lecture: Lecture) -> None:
    all_in_category = await asyncio.to_thread(sheets.lectures_by_category, category)
    kb = lecture_card_kb(category_idx, lecture.id, has_more=len(all_in_category) > 1)
    await callback.message.edit_text(lecture.caption(), reply_markup=kb)


@router.callback_query(F.data == "browse_lectures")
async def cb_browse_lectures(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите направление:", reply_markup=lecture_categories_kb(list(LECTURE_CATEGORIES))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lecture_cat_idx:"))
async def cb_lecture_category_selected(callback: CallbackQuery) -> None:
    idx = int(callback.data.split(":", 1)[1])
    if idx >= len(LECTURE_CATEGORIES):
        await callback.answer(
            "Это направление больше недоступно, откройте список заново", show_alert=True
        )
        return
    category = LECTURE_CATEGORIES[idx]

    lecture = await asyncio.to_thread(sheets.random_lecture, category)
    if lecture is None:
        await callback.answer("В этом направлении пока нет лекций", show_alert=True)
        return

    await _send_lecture_card(callback, category, idx, lecture)
    await callback.answer()


@router.callback_query(F.data.startswith("lecture_reroll:"))
async def cb_lecture_reroll(callback: CallbackQuery) -> None:
    _, idx_str, last_lecture_id = callback.data.split(":", 2)
    idx = int(idx_str)
    if idx >= len(LECTURE_CATEGORIES):
        await callback.answer(
            "Это направление больше недоступно, откройте список заново", show_alert=True
        )
        return
    category = LECTURE_CATEGORIES[idx]

    lecture = await asyncio.to_thread(sheets.random_lecture, category, exclude_id=last_lecture_id)
    if lecture is None:
        await callback.answer("В этом направлении пока нет лекций", show_alert=True)
        return

    await _send_lecture_card(callback, category, idx, lecture)
    await callback.answer()
