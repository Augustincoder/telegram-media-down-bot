"""
Handlers for the bot.
"""

from aiogram import Router

from .commands import router as commands_router
from .messages import router as messages_router
from .pairing import router as pairing_router
from .saved import router as saved_router
from .show_all_saved import router as show_all_saved_router


def get_routers() -> list[Router]:
    return [
        commands_router,
        pairing_router,
        saved_router,
        show_all_saved_router,
        messages_router,
    ]
