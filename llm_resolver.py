import json
import os
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).parent
CACHE_FILE = BASE_DIR / "llm_cache.json"
MODEL = "deepseek-chat"

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = (
    "Ты — помощник по русской кухне. "
    "По названию блюда верни JSON-массив ингредиентов, "
    "которые нужны для его приготовления (для покупки в магазине). "
    "Каждый элемент: {\"name\": \"имя продукта\", \"quantity\": количество}.\n\n"
    "Правила:\n"
    "- quantity — число (по умолчанию 1)\n"
    "- name — название продукта как для поиска в магазине (без брендов)\n"
    "- Не добавляй соль, перец, воду, масло для жарки, если они не ключевые\n"
    "- Ответ должен быть ТОЛЬКО JSON без пояснений\n"
    "- Пример: [{\"name\": \"сметана 20%\", \"quantity\": 1}, {\"name\": \"творог 5%\", \"quantity\": 2}]"
)


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def resolve_via_llm(dish: str) -> list[dict] | None:
    key = dish.strip().lower()
    cache = load_cache()
    if key in cache:
        return cache[key]

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": dish},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
        result = json.loads(content)
        if not isinstance(result, list):
            return None
        cache[key] = result
        save_cache(cache)
        return result
    except Exception as e:
        print(f"LLM error: {e}")
        return None
