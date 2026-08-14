from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_kb

router = Router(name="start")

WELCOME_TEXT = (
    "Привет! Я бот книжного клуба 📚\n\n"
    "Здесь можно посмотреть ближайшие встречи и записаться на них."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    # The previous screen may be a photo (book card), which can't be edited
    # back into plain text — delete and send a fresh message instead.
    await callback.message.delete()
    await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()
