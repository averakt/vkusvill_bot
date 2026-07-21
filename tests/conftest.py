"""Test configuration — sets env vars before any test imports."""

import os

os.environ.setdefault("VKUSVILL_BOT_TOKEN", "test:fake_token_for_tests")
