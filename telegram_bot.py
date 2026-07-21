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
from llm_resolver import resolve_via_llm
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

ALLOWED_USERS: set[int] = set()
allowed_raw = os.environ.get("ALLOWED_USERS", "")
if allowed_raw:
    for part in allowed_raw.split(","):
        part = part.strip()
        if part.isdigit():
            ALLOWED_USERS.add(int(part))
allowed_file = BASE_DIR / "allowed_users.txt"
if allowed_file.exists():
    for line in allowed_file.read_text().strip().splitlines():
        line = line.strip()
        if line.isdigit():
            ALLOWED_USERS.add(int(line))

ALLOWLIST_FILE = BASE_DIR / "allowed_users.txt"

dp = Dispatcher()


def load_allowlist() -> set[int]:
    users: set[int] = set()
    raw = os.environ.get("ALLOWED_USERS", "")
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                users.add(int(part))
    if ALLOWLIST_FILE.exists():
        for line in ALLOWLIST_FILE.read_text().strip().splitlines():
            line = line.strip()
            if line.isdigit():
                users.add(int(line))
    return users


ALLOWED_USERS = load_allowlist()


def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


async def check_access(message: types.Message) -> bool:
    if not is_allowed(message.from_user.id):
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


async def resolve_dish(name: str) -> tuple[list[str] | None, bool]:
    """Try local recipes first, then LLM. Returns (ingredients_list, from_llm)."""
    resolved = await asyncio.to_thread(resolve, name)
    if resolved:
        return resolved, False
    llm_result = await asyncio.to_thread(resolve_via_llm, name)
    if llm_result:
        return [item["name"] for item in llm_result], True
    return None, False


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
    if not await check_access(message):
        return
    text = message.text.strip()
    if not text:
        return

    lowered = text.lower()

    if lowered in ("корзина", "cart"):
        return await cmd_cart(message)

    if lowered.startswith("блюдо "):
        dish = text[6:].strip()
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


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>")


@dp.message(Command("allow"))
async def cmd_allow(message: types.Message):
    if not await check_access(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /allow <telegram_id>")
        return
    user_id = int(args[1].strip())
    ALLOWED_USERS.add(user_id)
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = set()
    if ALLOWLIST_FILE.exists():
        for line in ALLOWLIST_FILE.read_text().strip().splitlines():
            line = line.strip()
            if line.isdigit():
                current.add(int(line))
    current.add(user_id)
    ALLOWLIST_FILE.write_text("\n".join(str(uid) for uid in sorted(current)) + "\n")
    await message.answer(f"Пользователь {user_id} добавлен в список доступа")


@dp.message(Command("deny"))
async def cmd_deny(message: types.Message):
    if not await check_access(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /deny <telegram_id>")
        return
    user_id = int(args[1].strip())
    ALLOWED_USERS.discard(user_id)
    if ALLOWLIST_FILE.exists():
        lines = [l for l in ALLOWLIST_FILE.read_text().strip().splitlines()
                 if l.strip() != str(user_id)]
        ALLOWLIST_FILE.write_text("\n".join(lines) + "\n" if lines else "")
    await message.answer(f"Пользователь {user_id} удалён из списка доступа")


async def main():
    session = NoVerifySession()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
