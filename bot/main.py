"""Entry point: starts the Telegram bot in long-polling mode."""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from bot.config import settings
from bot.handlers import register_routers


async def _start_keepalive_server() -> None:
    """Binds an HTTP port so hosts that only offer free "web service" plans
    (e.g. Render) see the process as a web server and an external pinger
    (e.g. cron-job.org hitting this URL every few minutes) can stop it from
    being put to sleep for inactivity. The bot itself talks to Telegram via
    long polling and needs no incoming HTTP traffic."""
    port = int(os.getenv("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()


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
    await _start_keepalive_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
