"""
US Census Demographics Scraper - Complete Multi-Level Geographic Coverage

Fetches comprehensive demographic, economic, and housing data from Census Bureau API
for real estate intelligence and property investment analysis.

GEOGRAPHIC LEVELS COLLECTED:
├─ County (1): Alachua County market overview
├─ Census Tracts (58): Neighborhoods - PRIMARY for comparisons
├─ Block Groups (160): Street-level precision for property assignment
├─ Places (5): Cities - Gainesville, Alachua, High Springs, Archer, etc.
└─ ZIP Codes (10+): User-facing searches (32601, 32606, 32608, etc.)

DATA COLLECTED (45 variables per geography):
├─ Demographics (10): Population, age, gender, education, households
├─ Economics (10): Income distribution, poverty, unemployment, labor force
├─ Housing (19): Vacancy, rent burden, building age, values, unit types
└─ Commute (6): Transportation modes, work from home, commute times

DATA SOURCES:
├─ ACS 5-Year (2023): Most comprehensive, available to block group level
├─ ACS 1-Year (2024): Most current, county level only (65k+ population)
└─ No API key required - Census API is free and open

UPDATE SCHEDULE:
├─ ACS 5-Year: Released December annually (covers 2019-2023, etc.)
├─ ACS 1-Year: Released September annually (covers 2024, etc.)
└─ Run scraper: September (for current data) + December (for comprehensive data)

REAL ESTATE USE CASES:
├─ Link properties to demographics via spatial join (block group/tract)
├─ Compare neighborhoods for investment opportunities (tract analysis)
├─ Detect gentrification patterns (income trends over time)
├─ Assess rental market demand (age, household composition)
├─ Calculate affordability metrics (income vs rent/values)
├─ Target specific demographics (students, young professionals, families)
└─ User-facing market reports by city or ZIP code
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from urllib.parse import urlencode, quote

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

    # Comprehensive variable groups for real estate intelligence
    # ALL USEFUL CENSUS DATA FOR NEIGHBORHOOD ANALYSIS

    DEMOGRAPHIC_VARIABLES = [
        "B01003_001E",  # Total population
        "B01002_001E",  # Median age
        "B01001_002E",  # Male population
        "B01001_026E",  # Female population
        "B11001_001E",  # Total households
        "B11001_003E",  # Family households (married couple)
        "B11001_005E",  # Nonfamily households
        "B15003_022E",  # Bachelor's degree holders
        "B15003_023E",  # Master's degree holders
        "B15003_025E",  # Doctorate degree holders
    ]

    ECONOMIC_VARIABLES = [
        "B19013_001E",  # Median household income
        "B19025_001E",  # Aggregate household income
        "B19001_002E",  # Households earning <$10k
        "B19001_013E",  # Households earning $100k-$124k
        "B19001_014E",  # Households earning $125k-$149k
        "B19001_017E",  # Households earning $200k+
        "B17001_002E",  # Population below poverty level
        "B23025_002E",  # Labor force
        "B23025_005E",  # Unemployed
        "C24010_001E",  # Employment by occupation
    ]

    HOUSING_VARIABLES = [
        "B25001_001E",  # Total housing units
        "B25002_002E",  # Occupied housing units
        "B25002_003E",  # Vacant housing units
        "B25004_001E",  # Vacancy status (for rent, for sale, etc)
        "B25003_002E",  # Owner occupied units
        "B25003_003E",  # Renter occupied units
        "B25077_001E",  # Median home value (owner-occupied)
        "B25064_001E",  # Median gross rent
        "B25070_010E",  # Rent burden (paying 50%+ of income)
        "B25035_001E",  # Median year structure built
        "B25034_002E",  # Built 2020 or later
        "B25034_010E",  # Built 1970-1979
        "B25034_011E",  # Built 1939 or earlier
        "B25024_002E",  # 1-unit detached
        "B25024_003E",  # 1-unit attached
        "B25024_007E",  # 5-9 unit buildings
        "B25024_008E",  # 10-19 unit buildings
        "B25024_009E",  # 20-49 unit buildings
        "B25024_010E",  # 50+ unit buildings
    ]

    COMMUTE_VARIABLES = [
        "B08301_001E",  # Total commuters
        "B08301_010E",  # Public transportation commuters
        "B08301_019E",  # Walked to work
        "B08301_021E",  # Work from home
        "B08303_001E",  # Total travel time to work
        "B08303_013E",  # Commute 60+ minutes
    ]

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        census_api_key: Optional[str] = None,
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
        self.api_key = census_api_key  # Optional - Census API is free and open
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
        year: Optional[int] = None,
        include_housing: bool = True,
        include_economics: bool = True,
        include_commute: bool = True
    ) -> List[CensusDataPoint]:
        """
        Create comprehensive demographic profile for a geographic area.

        Args:
            geography_filter: Geographic identifiers (e.g., {"state": "12", "county": "001"})
            year: Data year to retrieve (None = auto-detect current year)
            include_housing: Include housing-related variables
            include_economics: Include economic variables
            include_commute: Include commute-related variables
        """
        # Auto-detect year if not provided
        if year is None:
            year = DEFAULT_ACS5_YEAR

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

        # Commute data
        if include_commute:
            requests.append(CensusDataRequest(
                api_type=CensusAPI.ACS5,
                year=year,
                variables=self.COMMUTE_VARIABLES,
                geography_level=self._determine_geography_level(geography_filter),
                geography_filter=geography_filter,
                dataset_name="commute_patterns"
            ))

        return await self.scrape_demographics(requests)

    async def scrape_all_county_tracts(
        self,
        state: str = "12",
        county: str = "001",
        year: Optional[int] = None
    ) -> List[CensusDataPoint]:
        """
        Scrape ALL census tracts in a county for detailed neighborhood analysis.

        Tracts represent neighborhoods (~4,000 people). PRIMARY geographic level
        for comparing neighborhoods and detecting investment opportunities.

        Args:
            state: State FIPS code (default: "12" = Florida)
            county: County FIPS code (default: "001" = Alachua)
            year: Data year (None = auto-detect current ACS 5-Year)

        Returns:
            List of CensusDataPoint objects, one for each tract (58 for Alachua)
        """
        # Auto-detect year if not provided
        if year is None:
            year = DEFAULT_ACS5_YEAR

        self.logger.info(f"Scraping all census tracts for state={state}, county={county}, year={year}")

        all_variables = (
            self.DEMOGRAPHIC_VARIABLES +
            self.ECONOMIC_VARIABLES +
            self.HOUSING_VARIABLES +
            self.COMMUTE_VARIABLES
        )

        request = CensusDataRequest(
            api_type=CensusAPI.ACS5,
            year=year,
            variables=all_variables,
            geography_level=GeographyLevel.TRACT,
            geography_filter={"state": state, "county": county},
            dataset_name="all_county_tracts"
        )

        data_points = await self._execute_census_request(request)
        self.logger.info(f"Retrieved data for {len(data_points)} census tracts")

        return data_points

    async def scrape_all_block_groups(
        self,
        state: str = "12",
        county: str = "001",
        year: Optional[int] = None
    ) -> List[CensusDataPoint]:
        """
        Scrape ALL block groups in a county for street-level demographic detail.

        Block groups are subdivisions of tracts (~600-3,000 people). Use for
        PRECISE property-level demographic assignment when you need street-by-street
        granularity. Higher margin of error than tracts due to smaller sample sizes.

        Args:
            state: State FIPS code (default: "12" = Florida)
            county: County FIPS code (default: "001" = Alachua)
            year: Data year (default: 2023 for ACS 5-Year)

        Returns:
            List of CensusDataPoint objects, one for each block group (160 for Alachua)
        """

        # Auto-detect year if not provided
        if year is None:
            year = DEFAULT_ACS5_YEAR

        self.logger.info(f"Scraping all block groups for state={state}, county={county}, year={year}")

        all_variables = (
            self.DEMOGRAPHIC_VARIABLES +
            self.ECONOMIC_VARIABLES +
            self.HOUSING_VARIABLES +
            self.COMMUTE_VARIABLES
        )

        request = CensusDataRequest(
            api_type=CensusAPI.ACS5,
            year=year,
            variables=all_variables,
            geography_level=GeographyLevel.BLOCK_GROUP,
            geography_filter={"state": state, "county": county},
            dataset_name="all_county_block_groups"
        )

        data_points = await self._execute_census_request(request)
        self.logger.info(f"Retrieved data for {len(data_points)} block groups")

        return data_points

    async def scrape_all_places(
        self,
        state: str = "12",
        year: Optional[int] = None
    ) -> List[CensusDataPoint]:
        """
        Scrape ALL incorporated places (cities/towns) in a state.

        Places represent municipalities (cities, towns). Use for CITY-LEVEL comparisons
        like Gainesville vs Alachua vs High Springs.

        Args:
            state: State FIPS code (default: "12" = Florida)
            year: Data year (default: 2023 for ACS 5-Year)

        Returns:
            List of CensusDataPoint objects, one for each place/city
        """

        # Auto-detect year if not provided
        if year is None:
            year = DEFAULT_ACS5_YEAR

        self.logger.info(f"Scraping all places for state={state}, year={year}")

        all_variables = (
            self.DEMOGRAPHIC_VARIABLES +
            self.ECONOMIC_VARIABLES +
            self.HOUSING_VARIABLES +
            self.COMMUTE_VARIABLES
        )

        request = CensusDataRequest(
            api_type=CensusAPI.ACS5,
            year=year,
            variables=all_variables,
            geography_level=GeographyLevel.PLACE,
            geography_filter={"state": state},
            dataset_name="all_state_places"
        )

        data_points = await self._execute_census_request(request)
        self.logger.info(f"Retrieved data for {len(data_points)} places")

        return data_points

    async def get_zip_codes_for_county(
        self,
        state: str = "12",
        county: str = "001"
    ) -> List[str]:
        """
        Get all ZIP codes (ZCTAs) for a specific county.

        Downloads Census Bureau's ZCTA-to-County relationship file and extracts
        ZIP codes that intersect with the specified county. This allows DYNAMIC
        ZIP code discovery for ANY county instead of hardcoding them.

        Args:
            state: State FIPS code (default: "12" = Florida)
            county: County FIPS code (default: "001" = Alachua)

        Returns:
            List of ZIP codes (as strings) for the county
        """
        county_fips = f"{state}{county}"  # e.g., "12001" for Alachua
        self.logger.info(f"Fetching ZIP codes for county FIPS: {county_fips}")

        try:
            # Download relationship file
            result = await self.scrape(ZCTA_COUNTY_RELATIONSHIP_URL)

            if not result.success:
                self.logger.error(f"Failed to download ZCTA relationship file: {result.error}")
                return []

            # Parse pipe-delimited file
            # Format: OID_ZCTA5_20|GEOID_ZCTA5_20|...|GEOID_COUNTY_20|...
            # Column 2 = ZIP code, Column 10 = County FIPS
            content = result.data.decode('utf-8')
            lines = content.strip().split('\n')

            zip_codes = set()
            for line in lines[1:]:  # Skip header
                fields = line.split('|')
                if len(fields) >= 10:
                    zcta = fields[1]  # ZIP code
                    county_id = fields[9]  # County FIPS

                    if county_id == county_fips and zcta:
                        zip_codes.add(zcta)

            zip_list = sorted(list(zip_codes))
            self.logger.info(f"Found {len(zip_list)} ZIP codes for county {county_fips}")

            return zip_list

        except Exception as e:
            self.logger.error(f"Error fetching ZIP codes for county: {e}")
            return []

    async def scrape_zip_codes(
        self,
        zip_codes: Optional[List[str]] = None,
        state: str = "12",
        county: str = "001",
        year: Optional[int] = None
    ) -> List[CensusDataPoint]:
        """
        Scrape ZIP Code Tabulation Areas (ZCTAs).

        If zip_codes not provided, automatically fetches ALL ZIPs for the county.
        This makes it work for ANY county (Gainesville, Tampa, Miami, Orlando, etc.)
        without hardcoding ZIP codes.

        ZCTAs approximate ZIP codes. Use for USER-FACING searches since people
        think in ZIP codes. Note: ZCTAs cross tract boundaries so they don't
        align perfectly with neighborhoods.

        Args:
            zip_codes: List of specific ZIP codes to query (optional)
            state: State FIPS code (default: "12" = Florida)
            county: County FIPS code (default: "001" = Alachua)
            year: Data year (default: 2023 for ACS 5-Year)

        Returns:
            List of CensusDataPoint objects, one for each ZIP code
        """

        # If no ZIP codes provided, get all ZIPs for county
        if zip_codes is None:
            self.logger.info(f"No ZIP codes provided, fetching all for county {state}{county}")
            zip_codes = await self.get_zip_codes_for_county(state, county)

            if not zip_codes:
                self.logger.warning("No ZIP codes found for county")
                return []

        # Auto-detect year if not provided
        if year is None:
            year = DEFAULT_ACS5_YEAR

        self.logger.info(f"Scraping {len(zip_codes)} ZIP codes, year={year}")

        all_variables = (
            self.DEMOGRAPHIC_VARIABLES +
            self.ECONOMIC_VARIABLES +
            self.HOUSING_VARIABLES +
            self.COMMUTE_VARIABLES
        )

        request = CensusDataRequest(
            api_type=CensusAPI.ACS5,
            year=year,
            variables=all_variables,
            geography_level=GeographyLevel.ZIP,
            geography_filter={"zip code tabulation area": ",".join(zip_codes)},
            dataset_name="zip_codes"
        )

        data_points = await self._execute_census_request(request)
        self.logger.info(f"Retrieved data for {len(data_points)} ZIP codes")

        return data_points

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
            "get": ",".join(request.variables + ["NAME"])
        }

        # Only add API key if provided (Census API doesn't require it)
        if self.api_key:
            params["key"] = self.api_key

        # Add geography
        if request.geography_filter:
            in_clause_parts = []

            for geo_level, geo_code in request.geography_filter.items():
                if geo_level != request.geography_level.value:
                    in_clause_parts.append(f"in={geo_level}:{geo_code}")

            if in_clause_parts:
                params["for"] = f"{request.geography_level.value}:*"
                # Don't include 'in' in params dict, add it separately to avoid encoding issues
            else:
                # Geography level matches filter - requesting specific geographies
                params["for"] = f"{request.geography_level.value}:{request.geography_filter[request.geography_level.value]}"
        else:
            params["for"] = f"{request.geography_level.value}:*"

        # Use urlencode for proper URL encoding of all parameters
        query_string = urlencode(params, safe=':,*')

        # Add 'in' clauses separately (they can appear multiple times)
        if request.geography_filter:
            for geo_level, geo_code in request.geography_filter.items():
                if geo_level != request.geography_level.value:
                    query_string += f"&in={quote(geo_level, safe='')}:{geo_code}"

        return f"{base}?{query_string}"

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


# Default configuration for Alachua County, Florida
DEFAULT_GEOGRAPHY = {
    "state": "12",    # Florida
    "county": "001"   # Alachua County
}

# Census Bureau ZCTA to County relationship file (2020)
ZCTA_COUNTY_RELATIONSHIP_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"

# County FIPS codes for common areas (for quick reference)
COUNTY_FIPS = {
    "alachua_fl": "12001",      # Gainesville area
    "hillsborough_fl": "12057",  # Tampa area
    "miami_dade_fl": "12086",    # Miami area
    "orange_fl": "12095",        # Orlando area
    "duval_fl": "12031",         # Jacksonville area
}

# Auto-calculate current Census data years
# ACS 1-Year: Released in September, covers previous year (Sept 2025 = 2024 data)
# ACS 5-Year: Released in December, covers 5-year period ending 2 years ago (Dec 2025 = 2019-2023)
def get_current_acs_years():
    """
    Automatically determine most recent available Census data years.

    ACS 1-Year: Released September of year Y with data from year Y-1
                (e.g., September 2025 releases 2024 data)
    ACS 5-Year: Released December of year Y with data from (Y-6) to (Y-2)
                (e.g., December 2025 releases 2019-2023 data)

    Returns: (acs1_year, acs5_year)
    """
    from datetime import datetime
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # ACS 1-Year: Available after September, covers previous year
    if current_month >= 9:
        acs1_year = current_year - 1  # Sept 2025+ uses 2024 data
    else:
        acs1_year = current_year - 2  # Before Sept 2025 uses 2023 data

    # ACS 5-Year: Available after December, ends 2 years prior
    if current_month >= 12:
        acs5_year = current_year - 2  # Dec 2025+ uses 2023 data (2019-2023)
    else:
        acs5_year = current_year - 3  # Before Dec 2025 uses 2022 data (2018-2022)

    return acs1_year, acs5_year

# Get current years automatically
DEFAULT_CENSUS_YEAR, DEFAULT_ACS5_YEAR = get_current_acs_years()

# For debugging/logging
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"Auto-detected Census data years: ACS 1-Year={DEFAULT_CENSUS_YEAR}, ACS 5-Year={DEFAULT_ACS5_YEAR}")


async def create_census_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    census_api_key: Optional[str] = None,
    default_geography: Optional[Dict[str, str]] = None,
    **kwargs
) -> CensusBureauScraper:
    """
    Factory function to create configured Census Bureau scraper.

    Args:
        db_manager: Database connection manager
        change_detector: Change detection system
        redis_client: Redis client for caching/rate limiting
        census_api_key: Optional Census API key (not required - API is free)
        default_geography: Default geographic area (defaults to Alachua County, FL)
        **kwargs: Additional arguments passed to ResilientScraper
    """
    scraper = CensusBureauScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        census_api_key=census_api_key,
        default_geography=default_geography or DEFAULT_GEOGRAPHY,
        **kwargs
    )
    await scraper.initialize()
    return scraper