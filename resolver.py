import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent
RECIPES_FILE = BASE_DIR / "recipes.yaml"


def load_recipes():
    if not RECIPES_FILE.exists():
        return {}
    with open(RECIPES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve(dish_name: str) -> list[str] | None:
    recipes = load_recipes()
    dish = dish_name.strip().lower()
    # exact match
    if dish in recipes:
        return recipes[dish]
    # partial match (e.g. "борщ со сметаной" -> "борщ")
    for name, ingredients in recipes.items():
        if name in dish or dish in name:
            return ingredients
    return None
