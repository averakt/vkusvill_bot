import os
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.search_product.return_value = {
        "name": "Молоко 3,2%",
        "id": 17525,
        "xmlid": 17525,
        "price": "104 ₽",
        "url": "https://vkusvill.ru/goods/moloko-3-17525/",
    }
    client.add_to_cart.return_value = {"success": "Y", "id": "17525", "qty": 1}
    client.get_cart_link.return_value = "https://vkusvill.ru/?share_basket=123"
    return client


@pytest.mark.asyncio
async def test_search_and_add_found(mock_client):
    from service import search_and_add

    result = await search_and_add(mock_client, "молоко")
    assert "✓" in result
    assert "Молоко 3,2%" in result
    assert "104 ₽" in result
    mock_client.search_product.assert_awaited_once_with("молоко")


@pytest.mark.asyncio
async def test_search_and_add_not_found(mock_client):
    from service import search_and_add

    mock_client.search_product.return_value = None
    result = await search_and_add(mock_client, "неттакоготовара")
    assert "✗" in result
    assert "не найден" in result


@pytest.mark.asyncio
async def test_search_and_add_error(mock_client):
    from service import search_and_add

    mock_client.search_product.side_effect = Exception("Network error")
    result = await search_and_add(mock_client, "молоко")
    assert "✗" in result
    assert "Network error" in result


@pytest.mark.asyncio
async def test_build_cart_reply(mock_client):
    from service import build_cart_reply

    results = await build_cart_reply(mock_client, ["молоко", "хлеб"])
    assert len(results) == 3
    assert "Корзина: https://vkusvill.ru" in results[-1]
    assert mock_client.search_product.await_count == 2


@pytest.mark.asyncio
async def test_build_cart_reply_all_not_found(mock_client):
    from service import build_cart_reply

    mock_client.search_product.return_value = None
    results = await build_cart_reply(mock_client, ["нет1", "нет2"])
    assert len(results) == 3
    assert "не найден" in results[0]
    assert "Корзина:" in results[-1]


@patch("service.resolve")
@pytest.mark.asyncio
async def test_handle_dish_with_prefix(mock_resolve, mock_client):
    mock_resolve.return_value = ["капуста", "свёкла", "картошка"]

    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "блюдо борщ"
    msg.answer = AsyncMock()

    with patch("telegram_bot.VkusVillClient", return_value=mock_client):
        await handle_message(msg)

    mock_resolve.assert_called_once_with("борщ")
    assert msg.answer.call_count >= 2


@patch("service.resolve_via_llm")
@patch("service.resolve")
@pytest.mark.asyncio
async def test_handle_dish_not_found(mock_resolve, mock_llm, mock_client):
    mock_resolve.return_value = None
    mock_llm.return_value = None

    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "блюдо несуществующее"
    msg.answer = AsyncMock()

    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
        await handle_message(msg)
    msg.answer.assert_any_call("Не удалось найти рецепт для «несуществующее»")


@pytest.mark.asyncio
async def test_handle_products_with_prefix(mock_client):
    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "продукты молоко, хлеб, яйца"
    msg.answer = AsyncMock()

    with patch("telegram_bot.VkusVillClient", return_value=mock_client):
        await handle_message(msg)

    assert mock_client.search_product.await_count == 3


@pytest.mark.asyncio
async def test_handle_products_prefix_empty(mock_client):
    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "продукты"
    msg.answer = AsyncMock()

    await handle_message(msg)
    msg.answer.assert_any_call("Напиши продукты после «продукты»")


@pytest.mark.asyncio
async def test_handle_cart(mock_client):
    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "корзина"
    msg.answer = AsyncMock()

    await handle_message(msg)
    msg.answer.assert_any_call("https://vkusvill.ru/cart/")


@patch("service.resolve")
@pytest.mark.asyncio
async def test_fallback_dish(mock_resolve, mock_client):
    mock_resolve.return_value = ["капуста", "свёкла"]

    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "борщ"
    msg.answer = AsyncMock()

    with patch("telegram_bot.VkusVillClient", return_value=mock_client):
        await handle_message(msg)

    mock_resolve.assert_called_once_with("борщ")


@pytest.mark.asyncio
async def test_fallback_comma_separated(mock_client):
    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "молоко, хлеб"
    msg.answer = AsyncMock()

    with patch("telegram_bot.VkusVillClient", return_value=mock_client):
        await handle_message(msg)

    assert mock_client.search_product.await_count == 2


@patch("service.resolve")
@pytest.mark.asyncio
async def test_fallback_single_product(mock_resolve, mock_client):
    mock_resolve.return_value = None

    from telegram_bot import handle_message

    msg = AsyncMock()
    msg.text = "молоко"
    msg.answer = AsyncMock()

    with patch("telegram_bot.VkusVillClient", return_value=mock_client):
        await handle_message(msg)

    mock_client.search_product.assert_awaited_once_with("молоко")


@patch("resolver.load_recipes")
def test_resolve_exact(mock_load):
    mock_load.return_value = {"борщ": ["свёкла", "капуста", "картошка"]}
    from resolver import resolve

    result = resolve("борщ")
    assert result == ["свёкла", "капуста", "картошка"]


@patch("resolver.load_recipes")
def test_resolve_not_found(mock_load):
    mock_load.return_value = {"борщ": ["свёкла"]}
    from resolver import resolve

    result = resolve("asdfghjk")
    assert result is None
