#!/usr/bin/env python3

import asyncio
import json
import sys

from resolver import resolve
from vkusvill import VkusVillClient


async def cmd_resolve(args):
    dish = " ".join(args)
    result = resolve(dish)
    print(json.dumps(result, ensure_ascii=False) if result else "null")


async def cmd_search(args):
    name = " ".join(args)
    client = VkusVillClient()
    try:
        product = await client.search_product(name)
        print(json.dumps(product, ensure_ascii=False) if product
              else json.dumps({"error": "Товар не найден"}, ensure_ascii=False))
    finally:
        await client.close()


async def cmd_add(args):
    name = " ".join(args)
    client = VkusVillClient()
    try:
        product = await client.search_product(name)
        if product:
            add_result = await client.add_to_cart(product)
            cart_url = await client.get_cart_link()
            result = {**product, "add_result": add_result, "cart_url": cart_url}
        else:
            result = {"error": "Товар не найден", "query": name}
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await client.close()


async def cmd_multy(args):
    items = json.loads(args[0]) if args else []
    client = VkusVillClient()
    try:
        results = []
        for item in items:
            product = await client.search_product(item)
            if product:
                await client.add_to_cart(product)
                results.append(product)
            else:
                results.append({"error": "Товар не найден", "query": item})
        cart_url = await client.get_cart_link()
        print(json.dumps({"results": results, "cart_url": cart_url}, ensure_ascii=False))
    finally:
        await client.close()


async def cmd_cart(args):
    print("https://vkusvill.ru/cart/")


async def cmd_ensure_login(args):
    # MCP API не требует логина
    print("OK")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "resolve": cmd_resolve,
        "search": cmd_search,
        "add": cmd_add,
        "multy": cmd_multy,
        "cart": cmd_cart,
        "ensure_login": cmd_ensure_login,
    }

    handler = commands.get(command)
    if not handler:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)

    result = handler(args)
    if result is not None:
        await result


if __name__ == "__main__":
    asyncio.run(main())
