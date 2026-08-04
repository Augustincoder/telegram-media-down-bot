import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import config
from bot.database.session import init_models, AsyncSessionLocal
from bot.middlewares.db import DbSessionMiddleware
from bot.handlers import get_routers
from bot.services.instagram import ig_service

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
    session_id_to_use = config.instagram_session_id or config.instagram_sessionid
    if session_id_to_use or (config.instagram_username and config.instagram_password):
        ig_service.login(
            username=config.instagram_username, 
            password=config.instagram_password,
            session_id=session_id_to_use
        )
    
    # Setup Bot and Dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register Middlewares
    dp.update.middleware(DbSessionMiddleware(session_pool=AsyncSessionLocal))

    # Register Routers
    for router in get_routers():
        dp.include_router(router)

    logger.info("Bot is now polling...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped gracefully.")
