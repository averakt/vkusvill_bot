import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
RECIPES_FILE = BASE_DIR / "recipes.yaml"
VKUSVILL_URL = "https://www.vkusvill.ru"
