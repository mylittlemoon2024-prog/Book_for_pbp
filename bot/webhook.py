"""Entry point: runs the bot in webhook mode, for serverless hosts (Google
Cloud Run, etc.) that scale to zero and need an HTTP endpoint to wake up on,
rather than a long-running polling loop like bot/main.py uses.

Requires WEBHOOK_URL to be set to the service's own public base URL (no
trailing slash needed) once it's known — see README for the Cloud Run
deploy steps, which set it after the first deploy.
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import settings
from bot.handlers import register_routers

# The bot token is folded into the path so a stray request to this public
# URL can't feed a fake update into the bot without also knowing the token.
WEBHOOK_PATH = f"/webhook/{settings.bot_token}"


async def _on_startup(bot: Bot) -> None:
    if not settings.webhook_url:
        # Expected on the very first deploy: the host (e.g. Cloud Run) only
        # hands out the service's own public URL *after* it's created, so
        # WEBHOOK_URL can't be known yet. Log and keep serving rather than
        # crash — that would fail the platform's health check and the
        # service would never come up long enough to learn its own URL.
        # Set WEBHOOK_URL once you have it and redeploy.
        logging.warning(
            "WEBHOOK_URL is not set — skipping set_webhook for now. The bot "
            "will not receive updates until it's set and the service is "
            "redeployed."
        )
        return
    url = settings.webhook_url.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(url, drop_pending_updates=True)
    logging.info("Webhook set to %s", url)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_routers(dp)
    dp.startup.register(_on_startup)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
