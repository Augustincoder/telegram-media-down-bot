import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import config
from bot.database.session import AsyncSessionLocal, init_models
from bot.handlers import get_routers
from bot.middlewares.db import DbSessionMiddleware
from bot.services.instagram import ig_service
from bot.services.story_monitor import start_story_monitor
from bot.services.telegram_userbot import userbot_service

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting bot initialization...")

    # Init Database
    await init_models()
    logger.info("Database models initialized.")

    # Init Instagram Service (Login using Session ID or Credentials)
    if config.instagram_session_id or (
        config.instagram_username and config.instagram_password
    ):
        async with AsyncSessionLocal() as session:
            await ig_service.login(
                session=session,
                username=config.instagram_username,
                password=config.instagram_password,
                session_id=config.instagram_session_id,
            )

    # Setup Bot and Dispatcher
    bot = Bot(
        token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register Middlewares
    dp.update.middleware(DbSessionMiddleware(session_pool=AsyncSessionLocal))

    # Ro'yxatdan o'tkazish
    for r in get_routers():
        dp.include_router(r)

    logger.info("Bot is now polling...")
    try:
        # Orqa fonda (background) story monitoring ni ishga tushirish
        if config.instagram_session_id or (
            config.instagram_username and config.instagram_password
        ):
            # asyncio.create_task(start_instagram_polling(bot))  # DM polling vaqtincha o'chirildi (Ban xavfi)
            asyncio.create_task(start_story_monitor(bot))

        # Start Telegram Userbot (if configured)
        asyncio.create_task(userbot_service.start())
        
        # Start DB cron cleaner
        from bot.services.cron_cleaner import start_cron_cleaner
        asyncio.create_task(start_cron_cleaner())

        # Start Highlight Engine Workers
        from bot.services.highlight_engine import start_ig_highlight_worker, start_tg_highlight_worker
        asyncio.create_task(start_ig_highlight_worker(bot))
        asyncio.create_task(start_tg_highlight_worker(bot))

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped gracefully.")
