"""Configuration management for Dominion"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://dominion:dominion_dev_pass@localhost:5432/dominion",
        description="PostgreSQL database URL"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # AI API Configuration
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key"
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for fallback"
    )
    CENSUS_API_KEY: str = Field(
        default="",
        description="US Census Bureau API key"
    )
    SOCRATA_APP_TOKEN: str = Field(
        default="",
        description="Socrata API application token (optional but recommended for higher rate limits)"
    )

    # Security Configuration
    JWT_SECRET_KEY: str = Field(
        default="dev_secret_change_in_production",
        description="JWT signing secret"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        description="JWT access token expiration in minutes"
    )

    # Environment Configuration
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment (development/production)"
    )
    DEBUG: bool = Field(
        default=True,
        description="Enable debug mode"
    )

    # API Configuration
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API host binding"
    )
    API_PORT: int = Field(
        default=8000,
        description="API port"
    )
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://dominion.vercel.app"],
        description="CORS allowed origins"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable API rate limiting"
    )
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        description="Default API rate limit per minute"
    )

    # Scraper Configuration
    SCRAPER_USER_AGENT: str = Field(
        default="Dominion Real Estate Intelligence Bot 1.0",
        description="User agent for web scraping"
    )
    SCRAPER_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retries for failed scrapes"
    )
    SCRAPER_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Request timeout for scrapers"
    )
    SCRAPER_DELAY_SECONDS: float = Field(
        default=1.0,
        description="Delay between scraper requests"
    )

    # Proxy Configuration
    PROXY_ENABLED: bool = Field(
        default=False,
        description="Enable proxy rotation for scraping"
    )
    PROXY_LIST: str = Field(
        default="",
        description="Comma-separated list of proxy URLs"
    )

    # AI Cost Controls
    MONTHLY_AI_BUDGET_CENTS: int = Field(
        default=5000,
        description="Monthly AI API budget in cents ($50)"
    )
    GEMINI_MAX_CENTS: int = Field(
        default=3500,
        description="Maximum Gemini spending in cents ($35)"
    )
    OPENAI_MAX_CENTS: int = Field(
        default=1500,
        description="Maximum OpenAI spending in cents ($15)"
    )

    # AI Cache Configuration
    LLM_CACHE_TTL_HOURS: int = Field(
        default=24,
        description="LLM cache time-to-live in hours"
    )
    EMBEDDING_CACHE_DAYS: int = Field(
        default=30,
        description="Embedding cache duration in days"
    )

    # AI Confidence Thresholds
    MIN_CONFIDENCE_FACTUAL: float = Field(
        default=0.90,
        description="Minimum confidence for factual claims"
    )
    MIN_CONFIDENCE_PREDICTION: float = Field(
        default=0.70,
        description="Minimum confidence for predictions"
    )
    MIN_CONFIDENCE_RELATIONSHIP: float = Field(
        default=0.80,
        description="Minimum confidence for relationships"
    )
    MIN_CONFIDENCE_PATTERN: float = Field(
        default=0.75,
        description="Minimum confidence for pattern detection"
    )

    # Monitoring & Alerting
    ALERT_EMAIL: str = Field(
        default="",
        description="Email address for system alerts"
    )
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname"
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port"
    )
    SMTP_USER: str = Field(
        default="",
        description="SMTP username"
    )
    SMTP_PASSWORD: str = Field(
        default="",
        description="SMTP password"
    )

    # Data Source URLs
    CITY_PERMITS_API: str = Field(
        default="https://data.cityofgainesville.org/Building-Development/Building-Permits/p798-x3nx",
        description="City of Gainesville permits API URL"
    )
    CENSUS_API_BASE: str = Field(
        default="https://api.census.gov/data",
        description="US Census Bureau API base URL"
    )
    CRIME_DATA_API: str = Field(
        default="https://data.cityofgainesville.org/Public-Safety/Crime-Responses/gvua-xt9q",
        description="Crime data API URL"
    )
    ZONING_API: str = Field(
        default="https://data.cityofgainesville.org/resource/2s65-t9he.json",
        description="Zoning data API URL"
    )
    PROPERTY_APPRAISER_URL: str = Field(
        default="https://qpublic.schneidercorp.com/Application.aspx?AppID=1081",
        description="Property appraiser portal URL"
    )
    PROPERTY_PORTAL_TYPE: str = Field(
        default="qpublic",
        description="Property appraiser portal type (qpublic, cama, custom)"
    )
    PROPERTY_DOWNLOAD_FORMAT: str = Field(
        default="csv",
        description="Preferred bulk download format (csv, xml, json, excel)"
    )
    PROPERTY_MAX_FILE_SIZE_MB: int = Field(
        default=500,
        description="Maximum property bulk file size in MB"
    )
    PROPERTY_EXCLUDE_EXEMPT: bool = Field(
        default=True,
        description="Exclude tax-exempt properties from bulk downloads"
    )
    COUNTY_PERMITS_URL: str = Field(
        default="https://growth-management.alachuacounty.us/PermitTracker",
        description="County permits portal URL"
    )
    COUNTY_PORTAL_TYPE: str = Field(
        default="alachua",
        description="County permits portal type (alachua, tyler, generic)"
    )
    COUNTY_PERMITS_HEADLESS: bool = Field(
        default=True,
        description="Run county permits scraper in headless browser mode"
    )
    COUNTY_PERMITS_TIMEOUT_MS: int = Field(
        default=30000,
        description="County permits scraper timeout in milliseconds"
    )
    SUNBIZ_URL: str = Field(
        default="https://dos.myflorida.com/sunbiz/search/",
        description="Florida Division of Corporations URL"
    )
    SUNBIZ_ENTITY_TYPES: str = Field(
        default="LLC,CORP",
        description="Comma-separated list of entity types to monitor (LLC, CORP, LP, etc.)"
    )
    SUNBIZ_MIN_RELEVANCE: str = Field(
        default="somewhat_relevant",
        description="Minimum relevance level for LLC filtering (highly_relevant, moderately_relevant, somewhat_relevant, not_relevant)"
    )
    SUNBIZ_MAX_DAYS_BACK: int = Field(
        default=30,
        description="Maximum days to look back for LLC formations"
    )
    SUNBIZ_HEADLESS: bool = Field(
        default=True,
        description="Run Sunbiz scraper in headless browser mode"
    )
    SUNBIZ_TIMEOUT_MS: int = Field(
        default=30000,
        description="Sunbiz scraper timeout in milliseconds"
    )
    GAINESVILLE_SUN_RSS: str = Field(
        default="https://www.gainesville.com/rss/",
        description="Gainesville Sun RSS feed URL"
    )
    BUSINESS_JOURNAL_FEEDS: str = Field(
        default=(
            "https://feeds.feedburner.com/BiznewsGainesville,"
            "https://www.bizjournals.com/jacksonville/feeds/latest,"
            "https://www.bizjournals.com/orlando/feeds/latest,"
            "https://www.constructiondive.com/feeds/news/,"
            "https://www.realestatefinanceandinvestment.com/feed"
        ),
        description="Comma-separated list of business journal RSS feed URLs"
    )
    CITY_COUNCIL_URL: str = Field(
        default="https://gainesville.legistar.com",
        description="City Council meeting portal URL"
    )

    # File Storage
    DATA_DIRECTORY: str = Field(
        default="./data",
        description="Directory for storing downloaded files"
    )
    LOGS_DIRECTORY: str = Field(
        default="./logs",
        description="Directory for log files"
    )

    # Performance Settings
    MAX_CONCURRENT_SCRAPERS: int = Field(
        default=5,
        description="Maximum concurrent scraper processes"
    )
    MAX_DB_CONNECTIONS: int = Field(
        default=20,
        description="Maximum database connections"
    )
    WORKER_CONCURRENCY: int = Field(
        default=4,
        description="Number of background worker processes"
    )

    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_proxy_list(self) -> List[str]:
        """Parse proxy list from string"""
        if not self.PROXY_LIST:
            return []
        return [proxy.strip() for proxy in self.PROXY_LIST.split(",") if proxy.strip()]

    def get_business_journal_feeds(self) -> List[str]:
        """Parse business journal RSS feeds list from string"""
        if not self.BUSINESS_JOURNAL_FEEDS:
            return []
        return [feed.strip() for feed in self.BUSINESS_JOURNAL_FEEDS.split(",") if feed.strip()]

    def get_sunbiz_entity_types(self) -> List[str]:
        """Parse Sunbiz entity types list from string"""
        if not self.SUNBIZ_ENTITY_TYPES:
            return ["LLC", "CORP"]  # Default entity types
        return [entity_type.strip().upper() for entity_type in self.SUNBIZ_ENTITY_TYPES.split(",") if entity_type.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for migrations"""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


# Global settings instance
settings = Settings()


# Data source configuration for scrapers
class DataSourceConfig:
    """Configuration for data sources"""

    # API endpoints that don't require special handling
    API_SOURCES = {
        "city_permits": {
            "url": settings.CITY_PERMITS_API,
            "format": "json",
            "auth_required": False,
            "rate_limit": 100,  # requests per minute
            "schedule": "daily_09:00"
        },
        "crime_data": {
            "url": settings.CRIME_DATA_API,
            "format": "json",
            "auth_required": False,
            "rate_limit": 100,
            "schedule": "daily_11:00"
        },
        "zoning_data": {
            "url": settings.ZONING_API,
            "format": "json",
            "auth_required": False,
            "rate_limit": 100,
            "schedule": "weekly_sunday_02:00"
        },
        "census_data": {
            "url": settings.CENSUS_API_BASE,
            "format": "json",
            "auth_required": False,
            "rate_limit": 500,
            "schedule": "monthly_01_02:00"
        }
    }

    # Web scraping sources that require browser automation or complex parsing
    SCRAPING_SOURCES = {
        "gainesville_sun": {
            "base_url": "https://www.gainesville.com",
            "rss_url": settings.GAINESVILLE_SUN_RSS,
            "sections": ["business", "local-news", "development"],
            "schedule": "daily_06:00"
        },
        "property_appraiser": {
            "url": "https://s3.amazonaws.com/acpa.cama/ACPA_CAMAData.zip",  # Direct S3 URL
            "method": "direct_download",
            "portal_type": "s3_direct",
            "schedule": "daily_00:30",  # After 11:45 PM nightly updates
            "comment": "CAMA data updates daily at 11:45 PM"
        },
        "county_permits": {
            "url": settings.COUNTY_PERMITS_URL,
            "method": "browser_scraping",
            "schedule": "daily_09:30"
        },
        "sunbiz_llc": {
            "url": settings.SUNBIZ_URL,
            "method": "form_scraping",
            "schedule": "daily_11:00"
        },
        "city_council": {
            "url": "https://pub-cityofgainesville.escribemeetings.com",
            "portal_type": "escribe",
            "method": "ajax_api",
            "schedule": "daily_08:00",
            "comment": "eScribe AJAX endpoints - development boards monitoring"
        }
    }

    # Scraping schedule in cron format
    SCRAPING_SCHEDULE = {
        "daily_00:30": "30 0 * * *",     # Daily at 12:30 AM (after 11:45 PM CAMA updates)
        "daily_06:00": "0 6 * * *",      # Daily at 6 AM
        "daily_09:00": "0 9 * * *",      # Daily at 9 AM
        "daily_09:30": "30 9 * * *",     # Daily at 9:30 AM
        "daily_11:00": "0 11 * * *",     # Daily at 11 AM
        "daily_18:00": "0 18 * * *",     # Daily at 6 PM
        "weekly_sunday_02:00": "0 2 * * 0",   # Weekly on Sunday at 2 AM
        "weekly_tuesday_08:00": "0 8 * * 2",  # Weekly on Tuesday at 8 AM
        "monthly_01_02:00": "0 2 1 * *"       # Monthly on 1st at 2 AM
    }


# Global data source config
data_sources = DataSourceConfig()