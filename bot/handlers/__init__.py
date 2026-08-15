from aiogram import Dispatcher

from bot.handlers.about import router as about_router
from bot.handlers.books import router as books_router
from bot.handlers.lectures import router as lectures_router
from bot.handlers.registration import router as registration_router
from bot.handlers.start import router as start_router


def register_routers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(books_router)
    dp.include_router(lectures_router)
    dp.include_router(about_router)
