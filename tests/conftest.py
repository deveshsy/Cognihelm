import os
import pytest

# Inject mock environment variables before importing app to prevent pydantic-settings
# validation crashes and to mock settings dynamically.
os.environ["SLACK_SIGNING_SECRET"] = "test_secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_token"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_telegram_token"
os.environ["DISCORD_PUBLIC_KEY"] = "test_discord_key"
os.environ["DYNAMODB_TABLE_NAME"] = "CogniHelm-Test"
os.environ["PORT"] = "8000"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    """FastAPI TestClient instance fixture."""
    with TestClient(app) as c:
        yield c
