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

from resolver import resolve
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

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для ВкусВилла.\n\n"
        "Команды:\n"
        "• «блюдо борщ» — разложить блюдо на продукты\n"
        "• «продукты молоко, хлеб, яйца» — найти товары и создать корзину\n"
        "• «корзина» — ссылка на корзину"
    )


@dp.message(Command("cart"))
async def cmd_cart(message: types.Message):
    await message.answer("https://vkusvill.ru/cart/")


async def search_and_add(client: VkusVillClient, item: str) -> str:
    try:
        product = await client.search_product(item)
        if not product:
            return f"\u2717 {item}: не найден"
        add_result = await client.add_to_cart(product, 1)
        success = add_result.get("success") == "Y"
        if success:
            price_s = product["price"].replace("\n", "").replace("  ", " ").strip()
            return f"\u2713 {product['name']} \u2014 {price_s}"
        else:
            return f"\u2717 {item}: {add_result.get('error', 'ошибка')}"
    except Exception as e:
        return f"\u2717 {item}: {e}"


async def build_cart_reply(client: VkusVillClient, items: list[str]) -> list[str]:
    results = [await search_and_add(client, item) for item in items]
    cart_url = await client.get_cart_link()
    if cart_url:
        results.append(f"\nКорзина: {cart_url}")
    return results


@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if not text:
        return

    lowered = text.lower()

    if lowered in ("корзина", "cart"):
        return await cmd_cart(message)

    if lowered.startswith("блюдо "):
        dish = text[6:].strip()
        resolved = await asyncio.to_thread(resolve, dish)
        if not resolved:
            await message.answer(f"Блюдо «{dish}» не найдено в рецептах")
            return
        await message.answer(
            f"«{dish}» \u2192 {len(resolved)} ингредиентов:\n"
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

    if lowered.startswith("продукты ") or lowered == "продукты":
        raw = text[9:].strip()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        if not items:
            await message.answer("Напиши продукты после «продукты»")
            return
        await message.answer(f"Ищу {len(items)} товаров...")
        client = VkusVillClient()
        try:
            reply_lines = await build_cart_reply(client, items)
            await message.answer("\n".join(reply_lines))
        finally:
            await client.close()
        return

    resolved = await asyncio.to_thread(resolve, text)
    if resolved:
        await message.answer(
            f"«{text}» \u2192 {len(resolved)} ингредиентов:\n"
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
        await message.answer(f"Ищу {len(items)} товаров...")
        client = VkusVillClient()
        try:
            reply_lines = await build_cart_reply(client, items)
            await message.answer("\n".join(reply_lines))
        finally:
            await client.close()
        return

    await message.answer(f"Ищу «{text}»...")
    client = VkusVillClient()
    try:
        reply_lines = await build_cart_reply(client, [text])
        await message.answer("\n".join(reply_lines))
    finally:
        await client.close()


async def main():
    session = NoVerifySession()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
