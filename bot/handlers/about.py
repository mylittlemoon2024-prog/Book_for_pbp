"""Handlers for the 'About the project', 'Cooperation' screens and the
suggestion-submission flow reachable from the about screen.
"""
import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import about_kb, back_to_menu_kb, cancel_fsm_kb, main_menu_kb
from bot.states import SuggestionForm

# Imported here (rather than at the top with the rest) to reuse the single
# shared SheetsService instance that registration.py owns — importing it
# forces registration.py to load first, same pattern as books.py.
from bot.handlers.registration import sheets  # noqa: E402

router = Router(name="about")

ABOUT_TEXT = (
    "Томик — бот, который поможет не только подобрать книгу, но и вдохновит "
    "на саморазвитие.\n"
    "Проект создан в рамках книжного клуба «<b>ВМЕСТЕ</b>» — это "
    'коллаборация <a href="https://t.me/pagebypageSN">Page by Page</a> и '
    '<a href="https://t.me/study_with_my_little_moon">My little moon</a>.\n\n'
    "<i>Хотите помочь сделать бота ещё лучше?</i>\n"
    "Поделитесь своими идеями — мы будем рады любым предложениям!"
)

# No public contacts yet — update this once they're available.
COOPERATION_TEXT = (
    "🤝 Сотрудничество\n\n"
    "Пока мы не публикуем контакты для сотрудничества — раздел скоро "
    "обновится. Загляните сюда чуть позже!"
)

SUGGESTION_THANKS_TEXT = "Спасибо! Мы обязательно прочитаем ваше предложение 💛"


@router.callback_query(F.data == "about_project")
async def cb_about_project(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.message.answer(ABOUT_TEXT, reply_markup=about_kb())
    await callback.answer()


@router.callback_query(F.data == "cooperation")
async def cb_cooperation(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.message.answer(COOPERATION_TEXT, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "leave_suggestion")
async def cb_leave_suggestion_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SuggestionForm.name)
    await callback.message.delete()
    await callback.message.answer("Как вас зовут?", reply_markup=cancel_fsm_kb())
    await callback.answer()


@router.message(SuggestionForm.name)
async def process_suggestion_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Пожалуйста, напишите имя текстом.")
        return
    await state.update_data(name=name)
    await state.set_state(SuggestionForm.text)
    await message.answer(
        "Какое у вас предложение? Пишите как есть — мы всё прочитаем.",
        reply_markup=cancel_fsm_kb(),
    )


@router.message(SuggestionForm.text)
async def process_suggestion_text(message: Message, state: FSMContext) -> None:
    suggestion = (message.text or "").strip()
    if not suggestion:
        await message.answer("Пожалуйста, напишите предложение текстом.")
        return

    data = await state.get_data()
    name = data["name"]

    await asyncio.to_thread(
        sheets.add_suggestion,
        name,
        suggestion,
        message.from_user.id,
        message.from_user.username or "",
    )
    await state.clear()
    await message.answer(SUGGESTION_THANKS_TEXT, reply_markup=main_menu_kb())
