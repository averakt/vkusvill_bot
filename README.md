# VkusVill Bot

Telegram-бот для поиска товаров и создания корзины на [ВкусВилл](https://www.vkusvill.ru) через официальный MCP API.

Бот: [@AveraktBot](https://t.me/AveraktBot)

## Возможности

- **Поиск по блюду** — `блюдо борщ` → разложит на ингредиенты → найдёт → корзина
- **Поиск через LLM** — если блюда нет в локальной базе, запрос уходит в DeepSeek
- **Список товаров** — `продукты молоко, хлеб, яйца` → поиск + корзина
- **Свободный ввод** — просто `борщ` или `молоко, хлеб` — бот сам определит
- **Не требует браузера** — всё через HTTP API
- **Ограничение доступа** — белый список пользователей

## Быстрый старт

```bash
cd ~/vkusvill_bot
pip install -e ~/vkusvill_list/vv_mcp
pip install -r requirements.txt
python3 telegram_bot.py
```

### Обход VPN для ВкусВилла

Если используется VPN (Телеграм работает через VPN, а ВкусВилл блокирует VPN-IP), нужно вывести трафик к ВкусВиллу напрямую:

```bash
# Узнать IP MCP API сервера
host mcp001.vkusvill.ru

# Добавить маршрут через локальный шлюз (замените 192.168.31.1 на ваш)
sudo route add -host 178.248.238.54 192.168.1.1
```

Проверить, что маршрут работает:

```bash
curl -s -o /dev/null -w "%{http_code}" https://mcp001.vkusvill.ru/mcp \
  -X POST -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
# Ожидается: 200
```

При отключении VPN маршрут становится неактивным, но не мешает.

Переменные окружения (или `.env`):
- `VKUSVILL_BOT_TOKEN` — токен Telegram бота (обязательно)
- `DEEPSEEK_API_KEY` — ключ DeepSeek API для поиска рецептов (опционально)
- `ALLOWED_USERS` — Telegram ID через запятую (опционально)

## Команды бота

```
/start                     — приветствие и справка
/cart                      — ссылка на корзину
/myid                      — узнать свой Telegram ID
/allow <id>                — добавить пользователя в белый список
/deny <id>                 — удалить из белого списка
блюдо борщ                 — блюдо → ингредиенты → корзина
продукты молоко, хлеб      — товары → поиск → корзина
```

Свободный ввод:
- `борщ` — разложит блюдо на ингредиенты (сначала локальная база, потом LLM)
- `молоко, хлеб, яйца` — найдёт каждый товар и создаст корзину

## CLI-интерфейс

```bash
python3 bot.py search "молоко 3.2%"      # поиск товара
python3 bot.py multy '["молоко","хлеб"]' # несколько товаров + корзина
python3 bot.py resolve "борщ"            # ингредиенты блюда
python3 bot.py cart                      # ссылка на корзину
```

## Тесты

```bash
python3 -m pytest tests/ -v
```

Все тесты мокированные — ни одного реального запроса к сети или файловой системе.

## Структура проекта

```
vkusvill_bot/
├── telegram_bot.py    # Telegram бот — только aiogram-хэндлеры
├── service.py         # Бизнес-логика (доступ, поиск, корзина, LLM fallback)
├── bot.py             # CLI-точка входа
├── vkusvill.py        # Клиент MCP API ВкусВилл
├── resolver.py        # Резолвер блюд → продукты (локальная база)
├── llm_resolver.py    # Резолвер через DeepSeek API (fallback)
├── recipes.yaml       # База рецептов (40+ блюд)
├── requirements.txt   # Зависимости
├── tests/
│   ├── test_bot.py    # 15 мокированных тестов
│   └── conftest.py    # Конфигурация тестов
└── README.md
```

## Как это работает

1. Пользователь пишет `блюдо борщ` или просто `борщ`
2. `resolver.py` ищет рецепт в `recipes.yaml`
3. Если не нашёл — `llm_resolver.py` отправляет запрос к DeepSeek API
4. Результаты LLM кешируются в `llm_cache.json` (повторные запросы бесплатные)
5. `vkusvill.py` ищет каждый товар через MCP API ВкусВилла
6. Для всех найденных товаров создаётся share-ссылка на корзину
7. Бот возвращает результаты и ссылку

## MCP API

Используется официальный MCP API ВкусВилла (`https://mcp001.vkusvill.ru/mcp`) через библиотеку [vv_mcp](https://github.com/Elzehorn/vv_mcp).

Методы:
- `vkusvill_products_search` — поиск товаров
- `vkusvill_product_details` — детальная информация
- `vkusvill_cart_link_create` — создание корзины
