"""
Handlers for the bot.
"""
from aiogram import Router

from .commands import router as commands_router
from .messages import router as messages_router

def get_routers() -> list[Router]:
    return [
        commands_router,
        messages_router,
    ]
