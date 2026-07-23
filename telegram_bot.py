#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession


class NoVerifySession(AiohttpSession):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connector_init["ssl"] = False

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command

from service import (
    load_allowlist,
    is_allowed,
    add_to_allowlist,
    remove_from_allowlist,
    resolve_dish,
    build_cart_reply,
)
from vkusvill import VkusVillClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("VKUSVILL_BOT_TOKEN") or ""
if not TOKEN:
    print("VKUSVILL_BOT_TOKEN не задан. Создай .env или установи переменную окружения.")
    sys.exit(1)

ALLOWED_USERS = load_allowlist()
dp = Dispatcher()


async def check_access(message: types.Message) -> bool:
    if not is_allowed(message.from_user.id, ALLOWED_USERS):
        await message.answer("Доступ запрещён")
        return False
    return True


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not await check_access(message):
        return
    await message.answer(
        "Привет! Я бот для ВкусВилла.\n\n"
        "Команды:\n"
        "• «блюдо борщ» — разложить блюдо на продукты\n"
        "• «продукты молоко, хлеб, яйца» — найти товары и создать корзину\n"
        "• «корзина» — ссылка на корзину"
    )


@dp.message(Command("cart"))
async def cmd_cart(message: types.Message):
    if not await check_access(message):
        return
    await message.answer("https://vkusvill.ru/cart/")


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>")


@dp.message(Command("allow"))
async def cmd_allow(message: types.Message):
    global ALLOWED_USERS
    if not await check_access(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /allow <telegram_id>")
        return
    user_id = int(args[1].strip())
    add_to_allowlist(user_id, ALLOWED_USERS)
    await message.answer(f"Пользователь {user_id} добавлен в список доступа")


@dp.message(Command("deny"))
async def cmd_deny(message: types.Message):
    global ALLOWED_USERS
    if not await check_access(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /deny <telegram_id>")
        return
    user_id = int(args[1].strip())
    remove_from_allowlist(user_id, ALLOWED_USERS)
    await message.answer(f"Пользователь {user_id} удалён из списка доступа")


async def process_dish(message: types.Message, dish: str):
    resolved, from_llm = await resolve_dish(dish)
    if not resolved:
        if os.environ.get("DEEPSEEK_API_KEY"):
            await message.answer(f"Не удалось найти рецепт для «{dish}»")
        else:
            await message.answer(
                f"Блюдо «{dish}» не найдено в рецептах.\n"
                "Подсказка: задай DEEPSEEK_API_KEY для поиска через LLM"
            )
        return
    label = "Через LLM" if from_llm else "Из рецептов"
    await message.answer(
        f"«{dish}» \u2192 {len(resolved)} ингредиентов ({label}):\n"
        + "\n".join(f"\u2022 {i}" for i in resolved)
        + "\n\nИщу и добавляю..."
    )
    client = VkusVillClient()
    try:
        reply_lines = await build_cart_reply(client, resolved)
        await message.answer("\n".join(reply_lines))
    finally:
        await client.close()


async def process_products(message: types.Message, items: list[str]):
    await message.answer(f"Ищу {len(items)} товаров...")
    client = VkusVillClient()
    try:
        reply_lines = await build_cart_reply(client, items)
        await message.answer("\n".join(reply_lines))
    finally:
        await client.close()


@dp.message()
async def handle_message(message: types.Message):
    if not await check_access(message):
        return
    text = message.text.strip()
    if not text:
        return

    lowered = text.lower()

    if lowered in ("корзина", "cart"):
        return await cmd_cart(message)

    if lowered.startswith("блюдо "):
        return await process_dish(message, text[6:].strip())

    if lowered.startswith("продукты ") or lowered == "продукты":
        raw = text[9:].strip()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        if not items:
            await message.answer("Напиши продукты после «продукты»")
            return
        return await process_products(message, items)

    resolved, from_llm = await resolve_dish(text)
    if resolved:
        label = "Через LLM" if from_llm else "Из рецептов"
        await message.answer(
            f"«{text}» \u2192 {len(resolved)} ингредиентов ({label}):\n"
            + "\n".join(f"\u2022 {i}" for i in resolved)
            + "\n\nИщу и добавляю..."
        )
        client = VkusVillClient()
        try:
            reply_lines = await build_cart_reply(client, resolved)
            await message.answer("\n".join(reply_lines))
        finally:
            await client.close()
        return

    if "," in text:
        items = [x.strip() for x in text.split(",") if x.strip()]
        return await process_products(message, items)

    return await process_products(message, [text])


async def main():
    session = NoVerifySession()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
