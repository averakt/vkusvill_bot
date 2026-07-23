import asyncio
import os
from pathlib import Path

from llm_resolver import resolve_via_llm
from resolver import resolve
from vkusvill import VkusVillClient

BASE_DIR = Path(__file__).parent
ALLOWLIST_FILE = BASE_DIR / "allowed_users.txt"


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


def save_allowlist(users: set[int]):
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_FILE.write_text("\n".join(str(uid) for uid in sorted(users)) + "\n")


def is_allowed(user_id: int, allowlist: set[int]) -> bool:
    return not allowlist or user_id in allowlist


def add_to_allowlist(user_id: int, allowlist: set[int]):
    allowlist.add(user_id)
    save_allowlist(allowlist)


def remove_from_allowlist(user_id: int, allowlist: set[int]):
    allowlist.discard(user_id)
    save_allowlist(allowlist)


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
