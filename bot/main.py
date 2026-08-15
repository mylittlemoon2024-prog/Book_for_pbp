"""Entry point: starts the Telegram bot in long-polling mode."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import register_routers


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            # Messages link to t.me/... (own bot, partner channels) — without
            # this, Telegram renders a preview card (name + description)
            # under every such message, which looks cluttered.
            link_preview_is_disabled=True,
        ),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_routers(dp)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
