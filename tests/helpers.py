"""Helper utilities for tests."""

from aiogram import types


async def run_handler(handler, text: str):
    """Run a message handler with a simulated message."""
    msg = types.Message(
        message_id=1,
        date=0,
        chat=types.Chat(id=1, type="private"),
        from_user=types.User(id=1, is_bot=False, first_name="Test"),
        text=text,
    )
    return await handler(msg)
