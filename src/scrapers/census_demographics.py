"""
US Census Demographics Scraper

Fetches demographic, economic, and housing data from the US Census Bureau API.
Provides population, income, housing, and economic indicators for market analysis.

Coverage: Population, housing units, income, demographics for Gainesville area
Data Source: US Census Bureau American Community Survey (ACS)
Update Frequency: Monthly (when new Census data released)
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import aiohttp
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class CensusAPI(Enum):
    """Supported Census Bureau APIs."""
    ACS5 = "acs/acs5"  # American Community Survey 5-year
    ACS1 = "acs/acs1"  # American Community Survey 1-year
    POPULATION_ESTIMATES = "pep/population"
    ECONOMIC_CENSUS = "ecnbasic"
    HOUSING = "dec/dhc"  # Decennial Housing Characteristics


class GeographyLevel(Enum):
    """Geographic levels for Census data."""
    STATE = "state"
    COUNTY = "county"
    TRACT = "tract"
    BLOCK_GROUP = "block group"
    PLACE = "place"
    ZIP = "zip code tabulation area"
    MSA = "metropolitan statistical area/micropolitan statistical area"


class CensusDataRequest(BaseModel):
    """Configuration for a Census API request."""
    api_type: CensusAPI
    year: int = Field(..., ge=2010, le=2030)
    variables: List[str] = Field(..., min_items=1)
    geography_level: GeographyLevel
    geography_filter: Optional[Dict[str, str]] = None  # e.g., {"state": "12", "county": "001"}
    dataset_name: Optional[str] = None

    @validator('year')
    def validate_year(cls, v, values):
        """Validate year based on API type."""
        api_type = values.get('api_type')
        if api_type == CensusAPI.ACS5 and v < 2009:
            raise ValueError("ACS 5-year data starts from 2009")
        if api_type == CensusAPI.ACS1 and v < 2005:
            raise ValueError("ACS 1-year data starts from 2005")
        return v


class CensusDataPoint(BaseModel):
    """Individual Census data observation."""
    geography_id: str
    geography_name: str
    geography_level: str
    variables: Dict[str, Any]
    year: int
    dataset: str
    margin_of_error: Optional[Dict[str, float]] = None


class CensusBureauScraper(ResilientScraper):
    """
    Scraper for US Census Bureau APIs.

    Supports multiple APIs and geography levels with configurable variables.
    Handles rate limiting and provides comprehensive demographic data for real estate intelligence.
    """

    BASE_URL = "https://api.census.gov/data"

    # Common variable groups for real estate analysis
    DEMOGRAPHIC_VARIABLES = [
        "B01003_001E",  # Total population
        "B25001_001E",  # Total housing units
        "B25003_002E",  # Owner occupied housing
        "B25003_003E",  # Renter occupied housing
        "B19013_001E",  # Median household income
        "B25077_001E",  # Median home value
        "B08301_001E",  # Total commuters
        "B08301_010E",  # Public transportation commuters
        "B15003_022E",  # Bachelor's degree holders
        "B01002_001E"   # Median age
    ]

    ECONOMIC_VARIABLES = [
        "B08303_001E",  # Total travel time to work
        "B19001_001E",  # Household income distribution
        "B25064_001E",  # Median gross rent
        "B25075_001E",  # Home value distribution
        "C24010_001E",  # Employment by occupation
        "B23025_002E"   # Labor force
    ]

    HOUSING_VARIABLES = [
        "B25024_001E",  # Units in structure
        "B25034_001E",  # Year structure built
        "B25040_001E",  # House heating fuel
        "B25016_001E",  # Household size by tenure
        "B25002_002E",  # Occupied housing units
        "B25002_003E"   # Vacant housing units
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        census_api_key: str,
        default_geography: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(
            scraper_id="census_demographics",
            scraper_type=ScraperType.API,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.api_key = census_api_key
        self.default_geography = default_geography or {"state": "12", "county": "001"}  # Alachua County, FL as default

    async def scrape_demographics(
        self,
        requests: List[CensusDataRequest]
    ) -> List[CensusDataPoint]:
        """
        Scrape demographic data for multiple requests.

        Args:
            requests: List of Census API requests to execute
        """
        all_data = []

        for request in requests:
            try:
                data_points = await self._execute_census_request(request)
                all_data.extend(data_points)

                # Rate limiting - Census API allows 500 requests per day
                await self.rate_limiter.acquire(self.scraper_id)

            except Exception as e:
                self.logger.error(f"Failed to execute Census request {request.dict()}: {e}")
                continue

        return all_data

    async def scrape_area_profile(
        self,
        geography_filter: Dict[str, str],
        year: int = 2022,
        include_housing: bool = True,
        include_economics: bool = True
    ) -> List[CensusDataPoint]:
        """
        Create comprehensive demographic profile for a geographic area.

        Args:
            geography_filter: Geographic identifiers (e.g., {"state": "12", "county": "001"})
            year: Data year to retrieve
            include_housing: Include housing-related variables
            include_economics: Include economic variables
        """
        requests = []

        # Base demographics (always included)
        requests.append(CensusDataRequest(
            api_type=CensusAPI.ACS5,
            year=year,
            variables=self.DEMOGRAPHIC_VARIABLES,
            geography_level=self._determine_geography_level(geography_filter),
            geography_filter=geography_filter,
            dataset_name="demographics_base"
        ))

        # Housing data
        if include_housing:
            requests.append(CensusDataRequest(
                api_type=CensusAPI.ACS5,
                year=year,
                variables=self.HOUSING_VARIABLES,
                geography_level=self._determine_geography_level(geography_filter),
                geography_filter=geography_filter,
                dataset_name="housing_characteristics"
            ))

        # Economic data
        if include_economics:
            requests.append(CensusDataRequest(
                api_type=CensusAPI.ACS5,
                year=year,
                variables=self.ECONOMIC_VARIABLES,
                geography_level=self._determine_geography_level(geography_filter),
                geography_filter=geography_filter,
                dataset_name="economic_indicators"
            ))

        return await self.scrape_demographics(requests)

    async def scrape_time_series(
        self,
        variables: List[str],
        geography_filter: Dict[str, str],
        start_year: int,
        end_year: int,
        api_type: CensusAPI = CensusAPI.ACS5
    ) -> List[CensusDataPoint]:
        """
        Scrape time series data for trend analysis.

        Args:
            variables: Census variables to track over time
            geography_filter: Geographic area to analyze
            start_year: Starting year for time series
            end_year: Ending year for time series
            api_type: Which Census API to use
        """
        requests = []

        for year in range(start_year, end_year + 1):
            requests.append(CensusDataRequest(
                api_type=api_type,
                year=year,
                variables=variables,
                geography_level=self._determine_geography_level(geography_filter),
                geography_filter=geography_filter,
                dataset_name=f"time_series_{year}"
            ))

        return await self.scrape_demographics(requests)

    async def monitor_new_releases(self) -> List[CensusDataPoint]:
        """
        Monitor for new Census data releases.
        Checks if new data is available for recent years.
        """
        current_year = datetime.now().year

        # Check for new ACS 5-year data (typically released in December)
        test_requests = [
            CensusDataRequest(
                api_type=CensusAPI.ACS5,
                year=current_year - 1,  # Most recent likely available year
                variables=["B01003_001E"],  # Just total population for testing
                geography_level=GeographyLevel.STATE,
                geography_filter={"state": "12"},  # Florida
                dataset_name="availability_check"
            )
        ]

        # Use change detection to see if new data is available
        test_url = self._build_api_url(test_requests[0])

        change_result = await self.change_detector.track_content_change(
            url=test_url,
            content=b"",
            metadata={"scraper": self.scraper_id, "check_type": "new_release_monitor"}
        )

        if change_result.change_type.value == "unchanged":
            self.logger.debug("No new Census data releases detected")
            return []

        # If changes detected, scrape the new data
        return await self.scrape_demographics(test_requests)

    async def store_census_data(self, data_points: List[CensusDataPoint]) -> int:
        """
        Store Census data in database as raw facts.

        Returns:
            Number of new data points stored
        """
        if not data_points:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for data_point in data_points:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "census_data": data_point.dict(),
                        "scraped_from": "census_api",
                        "scraper_version": "1.0",
                        "api_endpoint": f"{self.BASE_URL}/{data_point.dataset}",
                        "processing_notes": {
                            "data_quality": "official_government_api",
                            "confidence": 1.0,
                            "geography_level": data_point.geography_level,
                            "survey_year": data_point.year
                        }
                    }

                    # Calculate content hash for deduplication
                    content_str = json.dumps(fact_data, sort_keys=True, default=str)
                    import hashlib
                    content_hash = hashlib.md5(content_str.encode()).hexdigest()

                    # Insert raw fact
                    query = """
                        INSERT INTO raw_facts (
                            fact_type, source_url, scraped_at, parser_version,
                            raw_content, content_hash, processed_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (content_hash) DO NOTHING
                        RETURNING id
                    """

                    result = await session.execute(
                        query,
                        "census_data",
                        f"census_api/{data_point.dataset}/{data_point.year}/{data_point.geography_id}",
                        datetime.utcnow(),
                        "census_demographics_v1.0",
                        json.dumps(fact_data),
                        content_hash,
                        datetime.utcnow()
                    )

                    if result.rowcount > 0:
                        stored_count += 1

                        # Create structured fact
                        raw_fact_id = (await result.fetchone())['id']

                        structured_query = """
                            INSERT INTO structured_facts (
                                raw_fact_id, entity_type, structured_data, extraction_confidence
                            ) VALUES ($1, $2, $3, $4)
                        """

                        await session.execute(
                            structured_query,
                            raw_fact_id,
                            "demographic_data",
                            json.dumps(data_point.dict(), default=str),
                            1.0  # High confidence for official government data
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store census data point {data_point.geography_id}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new Census data points")
        return stored_count

    async def get_variable_metadata(self, api_type: CensusAPI, year: int) -> Dict[str, Any]:
        """
        Fetch variable definitions and metadata from Census API.

        Args:
            api_type: Census API to query
            year: Data year
        """
        metadata_url = f"{self.BASE_URL}/{year}/{api_type.value}/variables.json"

        result = await self.scrape(metadata_url)

        if not result.success:
            self.logger.error(f"Failed to fetch variable metadata: {result.error}")
            return {}

        return result.data

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process Census API response."""
        try:
            data = json.loads(content.decode('utf-8'))

            # Census API returns array format: first row is headers, rest are data
            if not isinstance(data, list) or len(data) < 2:
                self.logger.error(f"Unexpected Census API response format")
                return []

            headers = data[0]
            rows = data[1:]

            self.logger.info(f"Received {len(rows)} records from Census API")

            # Convert to list of dictionaries
            result = []
            for row in rows:
                if len(row) != len(headers):
                    self.logger.warning(f"Row length mismatch: {len(row)} vs {len(headers)}")
                    continue
                result.append(dict(zip(headers, row)))

            return result

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing Census response: {e}")
            return []

    async def _execute_census_request(self, request: CensusDataRequest) -> List[CensusDataPoint]:
        """Execute a single Census API request."""
        url = self._build_api_url(request)

        result = await self.scrape(url)

        if not result.success:
            self.logger.error(f"Census API request failed: {result.error}")
            return []

        return self._parse_census_response(result.data, request)

    def _build_api_url(self, request: CensusDataRequest) -> str:
        """Build Census API URL from request configuration."""
        base = f"{self.BASE_URL}/{request.year}/{request.api_type.value}"

        # Build query parameters
        params = {
            "get": ",".join(request.variables + ["NAME"]),
            "key": self.api_key
        }

        # Add geography
        if request.geography_filter:
            for_clause = f"for={request.geography_level.value}:*"
            in_clause_parts = []

            for geo_level, geo_code in request.geography_filter.items():
                if geo_level != request.geography_level.value:
                    in_clause_parts.append(f"{geo_level}:{geo_code}")

            if in_clause_parts:
                params["for"] = for_clause
                params["in"] = ",".join(in_clause_parts)
            else:
                params["for"] = f"{request.geography_level.value}:{request.geography_filter[request.geography_level.value]}"
        else:
            params["for"] = f"{request.geography_level.value}:*"

        # Build query string
        query_params = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query_params}"

    def _parse_census_response(self, api_data: List[Dict], request: CensusDataRequest) -> List[CensusDataPoint]:
        """Parse Census API response into CensusDataPoint objects."""
        data_points = []

        for record in api_data:
            try:
                # Extract geography information
                geography_name = record.get("NAME", "Unknown")
                geography_id = self._build_geography_id(record, request)

                # Extract variable data
                variables = {}
                for var in request.variables:
                    value = record.get(var)
                    if value is not None and value != "-666666666":  # Census null value
                        try:
                            # Try to convert to numeric if possible
                            variables[var] = float(value) if "." in str(value) else int(value)
                        except (ValueError, TypeError):
                            variables[var] = value
                    else:
                        variables[var] = None

                # Create data point
                data_point = CensusDataPoint(
                    geography_id=geography_id,
                    geography_name=geography_name,
                    geography_level=request.geography_level.value,
                    variables=variables,
                    year=request.year,
                    dataset=request.dataset_name or request.api_type.value
                )

                data_points.append(data_point)

            except Exception as e:
                self.logger.warning(f"Failed to parse Census record: {e}")
                self.logger.debug(f"Problem record: {record}")
                continue

        self.logger.info(f"Successfully parsed {len(data_points)} Census data points")
        return data_points

    def _build_geography_id(self, record: Dict, request: CensusDataRequest) -> str:
        """Build unique geography identifier from API response."""
        id_parts = []

        # Add geography codes in hierarchical order
        geo_levels = ["state", "county", "tract", "block group"]

        for level in geo_levels:
            if level in record and level != "NAME":
                id_parts.append(f"{level}:{record[level]}")

        return "|".join(id_parts) if id_parts else "unknown"

    def _determine_geography_level(self, geography_filter: Dict[str, str]) -> GeographyLevel:
        """Determine appropriate geography level from filter."""
        if "block group" in geography_filter:
            return GeographyLevel.BLOCK_GROUP
        elif "tract" in geography_filter:
            return GeographyLevel.TRACT
        elif "county" in geography_filter:
            return GeographyLevel.COUNTY
        elif "state" in geography_filter:
            return GeographyLevel.STATE
        else:
            return GeographyLevel.COUNTY  # Default fallback


async def create_census_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    census_api_key: str,
    default_geography: Optional[Dict[str, str]] = None,
    **kwargs
) -> CensusBureauScraper:
    """Factory function to create configured Census Bureau scraper."""
    scraper = CensusBureauScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        census_api_key=census_api_key,
        default_geography=default_geography,
        **kwargs
    )
    await scraper.initialize()
    return scraper