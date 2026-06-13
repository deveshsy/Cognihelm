from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    CogniHelm Centralized Configuration settings.
    Enforces type safety and loads overrides from local .env files.
    """
    environment: str = "dev"
    port: int = 8000
    dynamodb_table_name: str = "CogniHelm_Ledger"
    slack_signing_secret: str
    log_level: str = "INFO"

    # AWS Credentials
    aws_region: str = "eu-north-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Slack bot credentials
    slack_bot_token: Optional[str] = None

    # Microsoft Bot Framework Credentials
    microsoft_app_id: Optional[str] = None
    microsoft_app_password: Optional[str] = None

    # Omni-Channel Credentials
    whatsapp_verify_token: Optional[str] = None
    whatsapp_phone_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    discord_public_key: Optional[str] = None

    # Pydantic v2 config configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Returns a cached Settings instance to prevent re-reading the env file."""
    return Settings()
