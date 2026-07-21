import re

from vvmcp.client import VkusvillClient as MCPClient


class VkusVillClient:
    def __init__(self):
        self._client = MCPClient()
        self._cart_items: list[dict] = []

    async def search_product(self, name: str) -> dict | None:
        result = await self._client.search_products(name, page=1)
        items = result.get("data", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        price_info = item.get("price", {})
        price_str = f"{price_info.get('current', '?')} ₽" if price_info else "?"
        return {
            "name": item["name"],
            "id": item.get("id"),
            "xmlid": item.get("xml_id"),
            "price": price_str,
            "url": item.get("url"),
        }

    async def add_to_cart(self, product: dict, quantity: int = 1) -> dict:
        xmlid = product.get("xmlid") or product.get("id")
        self._cart_items.append({"xml_id": xmlid, "quantity": quantity})
        return {"success": "Y", "id": str(product.get("id", "")), "qty": quantity}

    async def get_cart_link(self) -> str | None:
        if not self._cart_items:
            return None
        return await self._client.create_cart_link(self._cart_items)

    async def close(self):
        self._cart_items = []
        await self._client.close()
