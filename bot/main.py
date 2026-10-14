"""Entry point: serves the Telegram bot via webhook.

Long polling needs the process to be continuously up to receive updates,
which gives a host with no inbound traffic (e.g. a sleeping free Render
service) nothing to wake it on. A webhook flips that: Telegram itself
sends an HTTP POST on every message, which is exactly the inbound
request that wakes a sleeping free-tier service — no external pinger
needed.
"""
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import settings
from bot.handlers import register_routers

WEBHOOK_PATH = "/webhook"


async def _on_startup(bot: Bot) -> None:
    webhook_url = os.environ["WEBHOOK_URL"].rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(webhook_url, drop_pending_updates=True)


def main() -> None:
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
    dp.startup.register(_on_startup)

    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="OK"))
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.getenv("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
