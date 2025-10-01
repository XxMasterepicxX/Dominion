"""
Pydantic schemas for market configuration.

Simple, focused schemas for testing portability.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List


class GeographyConfig(BaseModel):
    """Geographic identifiers for a market."""
    fips: Dict[str, str] = Field(..., description="FIPS codes (state, county)")

    @validator('fips')
    def validate_fips(cls, v):
        if 'state' not in v:
            raise ValueError("FIPS must include 'state' code")
        if 'county' not in v:
            raise ValueError("FIPS must include 'county' code")
        return v


class MarketInfo(BaseModel):
    """Basic market information."""
    name: str = Field(..., min_length=1)
    state: str = Field(..., min_length=2, max_length=2)
    county: str = Field(..., min_length=1)
    timezone: str = "America/New_York"


class CensusScraperConfig(BaseModel):
    """Configuration for Census scraper."""
    enabled: bool = True
    api_key: Optional[str] = None  # Census API is free


class SunbizScraperConfig(BaseModel):
    """Configuration for Sunbiz scraper."""
    enabled: bool = True
    # No config needed - uses Florida SFTP constants


class CrimeScraperConfig(BaseModel):
    """Configuration for Crime data scraper."""
    enabled: bool = True
    platform: str = Field(..., description="Platform type: 'socrata' or 'ckan'")
    endpoint: str = Field(..., description="API endpoint or CSV download URL")


class NewsScraperConfig(BaseModel):
    """Configuration for News RSS scraper."""
    enabled: bool = True
    feeds: Dict[str, str] = Field(..., description="Dictionary of feed_name: feed_url")


class CouncilScraperConfig(BaseModel):
    """Configuration for City Council scraper."""
    enabled: bool = True
    platform: str = Field(..., description="Platform type: 'escribe', 'onbase', 'legistar', 'granicus'")
    endpoint: str = Field(..., description="Base URL for council meetings/agendas")


class PropertyScraperConfig(BaseModel):
    """Configuration for Property Appraiser (CAMA) scraper."""
    enabled: bool = True
    portal_base_url: str = Field(..., description="Base URL for property appraiser portal")
    portal_type: str = Field(default="qpublic", description="Portal type: 'qpublic', 'cama', 'custom'")
    county_code: str = Field(..., description="County code (e.g., 'ALA' for Alachua)")
    download_url_pattern: Optional[str] = Field(None, description="Specific download URL if known")


class CityPermitsScraperConfig(BaseModel):
    """Configuration for City Permits scraper."""
    enabled: bool = True
    platform: str = Field(..., description="Platform type: 'citizenserve' or 'accela'")
    base_url: str = Field(..., description="Base URL for permits portal")
    jurisdiction: str = Field(..., description="City/jurisdiction name")
    installation_id: Optional[str] = Field(None, description="CitizenServe installation ID (if applicable)")


class CountyPermitsScraperConfig(BaseModel):
    """Configuration for County Permits scraper."""
    enabled: bool = True
    platform: str = Field(..., description="Platform type: 'citizenserve' or 'accela'")
    base_url: str = Field(..., description="Base URL for permits portal")
    jurisdiction: str = Field(..., description="County/jurisdiction name")
    installation_id: Optional[str] = Field(None, description="CitizenServe installation ID (if applicable)")


class GISScraperConfig(BaseModel):
    """Configuration for GIS Shapefile scraper."""
    enabled: bool = True
    shapefile_urls: Dict[str, str] = Field(..., description="Dictionary of layer_name: shapefile_url")
    county_name: str = Field(..., description="County name for the shapefiles")


class FloridaTrendConfig(BaseModel):
    """Configuration for Florida Trend web scraping."""
    enabled: bool = True
    url_patterns: List[str] = Field(..., description="URL patterns with {date} placeholder (YYYY/MM/DD)")


class BusinessScraperConfig(BaseModel):
    """Configuration for Business Journal/News scraper."""
    enabled: bool = True
    feeds: Dict[str, str] = Field(..., description="Dictionary of source_name: rss_url")
    florida_trend: Optional[FloridaTrendConfig] = None


class ScrapersConfig(BaseModel):
    """All scraper configurations for a market."""
    census: Optional[CensusScraperConfig] = None
    sunbiz: Optional[SunbizScraperConfig] = None
    crime: Optional[CrimeScraperConfig] = None
    news: Optional[NewsScraperConfig] = None
    council: Optional[CouncilScraperConfig] = None
    property: Optional[PropertyScraperConfig] = None
    city_permits: Optional[CityPermitsScraperConfig] = None
    county_permits: Optional[CountyPermitsScraperConfig] = None
    gis: Optional[GISScraperConfig] = None
    business: Optional[BusinessScraperConfig] = None


class MarketConfig(BaseModel):
    """Complete market configuration."""
    market: MarketInfo
    geography: GeographyConfig
    scrapers: ScrapersConfig

    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"


# Example for validation
if __name__ == "__main__":
    # Test Gainesville config
    test_config = MarketConfig(
        market=MarketInfo(
            name="Gainesville, FL",
            state="FL",
            county="Alachua"
        ),
        geography=GeographyConfig(
            fips={"state": "12", "county": "001"}
        ),
        scrapers=ScrapersConfig(
            census=CensusScraperConfig(enabled=True),
            sunbiz=SunbizScraperConfig(enabled=True)
        )
    )

    print("✓ Gainesville config validation passed")
    print(test_config.model_dump_json(indent=2))