"""
Application settings and configuration.

Loads environment variables for database, Redis, API keys, and other settings.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://dominion:dominion@localhost:5432/dominion",
        env="DATABASE_URL"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )

    # API Keys
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")

    # Scraper Settings
    SUNBIZ_SFTP_USER: str = Field(default="Public", env="SUNBIZ_SFTP_USER")
    SUNBIZ_SFTP_PASS: str = Field(default="PubAccess1845!", env="SUNBIZ_SFTP_PASS")

    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = Field(default="gemini", env="DEFAULT_LLM_PROVIDER")
    DEFAULT_LLM_MODEL: str = Field(default="gemini-2.0-flash", env="DEFAULT_LLM_MODEL")
    DEFAULT_LLM_TEMPERATURE: float = Field(default=0.0, env="DEFAULT_LLM_TEMPERATURE")

    # Confidence Thresholds
    CONFIDENCE_THRESHOLD_FACTUAL: float = Field(default=0.90, env="CONFIDENCE_THRESHOLD_FACTUAL")
    CONFIDENCE_THRESHOLD_PREDICTION: float = Field(default=0.70, env="CONFIDENCE_THRESHOLD_PREDICTION")
    CONFIDENCE_THRESHOLD_RELATIONSHIP: float = Field(default=0.80, env="CONFIDENCE_THRESHOLD_RELATIONSHIP")
    CONFIDENCE_THRESHOLD_PATTERN: float = Field(default=0.75, env="CONFIDENCE_THRESHOLD_PATTERN")

    # Data Directories
    DATA_DIR: Path = Field(default=Path("./data"), env="DATA_DIR")
    CACHE_DIR: Path = Field(default=Path("./data/cache"), env="CACHE_DIR")

    # Security
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    API_KEY_SALT: str = Field(default="dev-api-key-salt", env="API_KEY_SALT")

    # Performance
    MAX_WORKERS: int = Field(default=4, env="MAX_WORKERS")
    SCRAPER_TIMEOUT: int = Field(default=300, env="SCRAPER_TIMEOUT")
    LLM_CACHE_TTL: int = Field(default=2592000, env="LLM_CACHE_TTL")  # 30 days

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
