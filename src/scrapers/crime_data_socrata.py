"""
Gainesville Crime Data Scraper (via Socrata API)

Fetches crime incident data from Gainesville Police Department's open data portal.
Uses the standardized Socrata Open Data API (SODA) for reliable data access.

Coverage: Crime incidents, locations, types, dates for safety analysis
Data Source: City of Gainesville open data portal
Update Frequency: Daily
"""
import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import aiohttp
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class SocrataDataFormat(Enum):
    """Supported Socrata data formats."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    RDF = "rdf"
    RSS = "rss"


class SocrataOrderDirection(Enum):
    """Sort order directions."""
    ASC = "ASC"
    DESC = "DESC"


class CrimeIncident(BaseModel):
    """Model for crime incident data."""
    incident_id: str = Field(..., min_length=1)
    incident_date: datetime
    incident_type: str
    incident_category: Optional[str] = None
    description: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    beat: Optional[str] = None
    district: Optional[str] = None
    disposition: Optional[str] = None
    case_number: Optional[str] = None
    reported_date: Optional[datetime] = None
    cleared_date: Optional[datetime] = None

    @validator('incident_date', 'reported_date', 'cleared_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle various Socrata date formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
                "%Y-%m-%dT%H:%M:%S",     # ISO format
                "%Y-%m-%d %H:%M:%S",     # Standard datetime
                "%Y-%m-%d",              # Date only
                "%m/%d/%Y %H:%M:%S %p",  # US format with AM/PM
                "%m/%d/%Y"               # US date only
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('latitude', 'longitude', pre=True)
    def parse_coordinates(cls, v):
        if v is None or v == "" or v == "0":
            return None
        try:
            coord = float(v)
            return coord if coord != 0.0 else None
        except (ValueError, TypeError):
            return None


class SocrataQuery(BaseModel):
    """Configuration for Socrata API queries."""
    endpoint_url: str
    data_format: SocrataDataFormat = SocrataDataFormat.JSON
    limit: Optional[int] = 1000
    offset: Optional[int] = 0
    where_clause: Optional[str] = None
    order_by: Optional[str] = None
    order_direction: SocrataOrderDirection = SocrataOrderDirection.DESC
    select_fields: Optional[List[str]] = None
    group_by: Optional[List[str]] = None
    app_token: Optional[str] = None

    @validator('limit')
    def validate_limit(cls, v):
        if v is not None and (v < 1 or v > 50000):
            raise ValueError("Limit must be between 1 and 50000")
        return v

    def to_query_params(self) -> Dict[str, str]:
        """Convert query configuration to Socrata API parameters."""
        params = {}

        if self.data_format != SocrataDataFormat.JSON:
            params["$format"] = self.data_format.value

        if self.limit:
            params["$limit"] = str(self.limit)

        if self.offset:
            params["$offset"] = str(self.offset)

        if self.where_clause:
            params["$where"] = self.where_clause

        if self.order_by:
            order_clause = self.order_by
            if self.order_direction:
                order_clause += f" {self.order_direction.value}"
            params["$order"] = order_clause

        if self.select_fields:
            params["$select"] = ",".join(self.select_fields)

        if self.group_by:
            params["$group"] = ",".join(self.group_by)

        return params


class SocrataCrimeDataScraper(ResilientScraper):
    """
    Scraper for crime data via Socrata Open Data API.

    Supports flexible querying, date range filtering, and geographic analysis.
    Works with any Socrata-based government data portal.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        base_endpoint_url: str,
        app_token: Optional[str] = None,
        default_field_mapping: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(
            scraper_id="crime_data_socrata",
            scraper_type=ScraperType.API,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.base_endpoint_url = base_endpoint_url.rstrip('/')
        self.app_token = app_token

        # Default field mapping for common Socrata crime data schemas
        self.field_mapping = default_field_mapping or {
            'incident_id': ['incident_number', 'case_id', 'id', 'incident_id'],
            'incident_date': ['incident_date', 'date_occurred', 'occurrence_date', 'date'],
            'incident_type': ['incident_type', 'crime_type', 'offense_type', 'type'],
            'incident_category': ['category', 'crime_category', 'classification'],
            'description': ['description', 'offense_description', 'details'],
            'address': ['address', 'location', 'incident_address'],
            'latitude': ['latitude', 'lat', 'y_coordinate'],
            'longitude': ['longitude', 'lng', 'lon', 'x_coordinate'],
            'beat': ['beat', 'police_beat', 'patrol_beat'],
            'district': ['district', 'police_district', 'zone'],
            'disposition': ['disposition', 'status', 'clearance_status'],
            'case_number': ['case_number', 'case_id', 'report_number'],
            'reported_date': ['reported_date', 'date_reported'],
            'cleared_date': ['cleared_date', 'date_cleared']
        }

    async def scrape_crime_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        crime_types: Optional[List[str]] = None,
        geographic_bounds: Optional[Dict[str, float]] = None,
        limit: int = 1000
    ) -> List[CrimeIncident]:
        """
        Scrape crime data with flexible filtering.

        Args:
            start_date: Start date for incident search (defaults to yesterday)
            end_date: End date for incident search (defaults to today)
            crime_types: List of specific crime types to filter by
            geographic_bounds: Dict with 'north', 'south', 'east', 'west' coordinates
            limit: Maximum records per request
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=1)
        if not end_date:
            end_date = datetime.now()

        # Build where clause for filtering
        where_conditions = []

        # Date filtering
        date_field = self._get_mapped_field('incident_date')
        if date_field:
            where_conditions.append(
                f"{date_field} >= '{start_date.strftime('%Y-%m-%dT%H:%M:%S')}' AND "
                f"{date_field} <= '{end_date.strftime('%Y-%m-%dT%H:%M:%S')}'"
            )

        # Crime type filtering
        if crime_types:
            type_field = self._get_mapped_field('incident_type')
            if type_field:
                type_conditions = [f"{type_field} = '{crime_type}'" for crime_type in crime_types]
                where_conditions.append(f"({' OR '.join(type_conditions)})")

        # Geographic bounds filtering
        if geographic_bounds:
            lat_field = self._get_mapped_field('latitude')
            lon_field = self._get_mapped_field('longitude')

            if lat_field and lon_field:
                bounds_conditions = []
                if 'north' in geographic_bounds:
                    bounds_conditions.append(f"{lat_field} <= {geographic_bounds['north']}")
                if 'south' in geographic_bounds:
                    bounds_conditions.append(f"{lat_field} >= {geographic_bounds['south']}")
                if 'east' in geographic_bounds:
                    bounds_conditions.append(f"{lon_field} <= {geographic_bounds['east']}")
                if 'west' in geographic_bounds:
                    bounds_conditions.append(f"{lon_field} >= {geographic_bounds['west']}")

                if bounds_conditions:
                    where_conditions.append(' AND '.join(bounds_conditions))

        # Build query
        query = SocrataQuery(
            endpoint_url=self.base_endpoint_url,
            limit=limit,
            where_clause=' AND '.join(where_conditions) if where_conditions else None,
            order_by=self._get_mapped_field('incident_date'),
            order_direction=SocrataOrderDirection.DESC,
            app_token=self.app_token
        )

        # Execute request
        result = await self._execute_socrata_query(query)
        if not result.success:
            self.logger.error(f"Failed to fetch crime data: {result.error}")
            return []

        return await self._parse_crime_data(result.data)

    async def scrape_all_recent_crimes(self, days_back: int = 7) -> List[CrimeIncident]:
        """
        Scrape all crime incidents from the last N days using pagination.

        Args:
            days_back: Number of days to look back for incidents
        """
        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        all_incidents = []
        offset = 0
        page_size = 1000

        while True:
            # Build paginated query
            where_clause = None
            date_field = self._get_mapped_field('incident_date')
            if date_field:
                where_clause = (
                    f"{date_field} >= '{start_date.strftime('%Y-%m-%dT%H:%M:%S')}' AND "
                    f"{date_field} <= '{end_date.strftime('%Y-%m-%dT%H:%M:%S')}'"
                )

            query = SocrataQuery(
                endpoint_url=self.base_endpoint_url,
                limit=page_size,
                offset=offset,
                where_clause=where_clause,
                order_by=date_field,
                order_direction=SocrataOrderDirection.DESC,
                app_token=self.app_token
            )

            result = await self._execute_socrata_query(query)
            if not result.success:
                self.logger.error(f"Failed to fetch paginated crime data: {result.error}")
                break

            incidents = await self._parse_crime_data(result.data)
            if not incidents:
                break

            all_incidents.extend(incidents)

            # Check if we got less than page_size (last page)
            if len(incidents) < page_size:
                break

            offset += page_size

            # Safety check to prevent infinite loops
            if len(all_incidents) > 100000:
                self.logger.warning("Reached safety limit of 100k crime records")
                break

        self.logger.info(f"Scraped {len(all_incidents)} crime incidents from last {days_back} days")
        return all_incidents

    async def get_crime_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated crime statistics using Socrata's $group functionality.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        stats = {}

        # Total incidents by type
        type_field = self._get_mapped_field('incident_type')
        date_field = self._get_mapped_field('incident_date')

        if type_field and date_field:
            where_clause = (
                f"{date_field} >= '{start_date.strftime('%Y-%m-%dT%H:%M:%S')}' AND "
                f"{date_field} <= '{end_date.strftime('%Y-%m-%dT%H:%M:%S')}'"
            )

            query = SocrataQuery(
                endpoint_url=self.base_endpoint_url,
                select_fields=[type_field, f"COUNT(*) as count"],
                group_by=[type_field],
                where_clause=where_clause,
                order_by="count",
                order_direction=SocrataOrderDirection.DESC,
                limit=50,
                app_token=self.app_token
            )

            result = await self._execute_socrata_query(query)
            if result.success:
                stats['incidents_by_type'] = result.data

        return stats

    async def monitor_new_incidents(self) -> List[CrimeIncident]:
        """
        Monitor for new crime incidents since last successful scrape.
        Uses change detection to identify when new incidents are available.
        """
        # Check for changes in the most recent incidents
        test_query = SocrataQuery(
            endpoint_url=self.base_endpoint_url,
            limit=1,
            order_by=self._get_mapped_field('incident_date'),
            order_direction=SocrataOrderDirection.DESC,
            app_token=self.app_token
        )

        test_url = self._build_query_url(test_query)

        change_result = await self.change_detector.track_content_change(
            url=test_url,
            content=b"",  # Will be filled by the scraper
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        # If no changes detected, return empty list
        if change_result.change_type.value == "unchanged":
            self.logger.debug("No new crime incidents detected")
            return []

        # Get incidents from last 24 hours to catch any new ones
        return await self.scrape_all_recent_crimes(days_back=1)

    async def store_crime_data(self, incidents: List[CrimeIncident]) -> int:
        """
        Store crime incidents in database as raw facts.

        Returns:
            Number of new incidents stored
        """
        if not incidents:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for incident in incidents:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "crime_data": incident.dict(),
                        "scraped_from": "socrata_crime_api",
                        "scraper_version": "1.0",
                        "api_endpoint": self.base_endpoint_url,
                        "processing_notes": {
                            "data_quality": "structured_government_api",
                            "confidence": 1.0,
                            "source_type": "socrata_api"
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
                        "crime_incident",
                        f"{self.base_endpoint_url}?incident={incident.incident_id}",
                        datetime.utcnow(),
                        "socrata_crime_v1.0",
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
                            "crime_incident",
                            json.dumps(incident.dict(), default=str),
                            1.0  # High confidence for structured government API data
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store crime incident {incident.incident_id}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new crime incidents")
        return stored_count

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process Socrata API response."""
        try:
            data = json.loads(content.decode('utf-8'))

            # Socrata returns array of objects for JSON format
            if not isinstance(data, list):
                self.logger.error(f"Unexpected Socrata API response format: {type(data)}")
                return []

            self.logger.info(f"Received {len(data)} records from Socrata API")
            return data

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing Socrata response: {e}")
            return []

    async def _execute_socrata_query(self, query: SocrataQuery) -> ScrapingResult:
        """Execute a Socrata API query."""
        url = self._build_query_url(query)

        headers = {}
        if query.app_token:
            headers['X-App-Token'] = query.app_token

        return await self.scrape(url, headers=headers)

    def _build_query_url(self, query: SocrataQuery) -> str:
        """Build Socrata API URL from query configuration."""
        # Ensure endpoint ends with .json for JSON format
        endpoint = query.endpoint_url
        if not endpoint.endswith('.json') and query.data_format == SocrataDataFormat.JSON:
            endpoint += '.json'

        # Add query parameters
        params = query.to_query_params()

        if params:
            query_string = urllib.parse.urlencode(params)
            return f"{endpoint}?{query_string}"

        return endpoint

    async def _parse_crime_data(self, api_data: List[Dict[str, Any]]) -> List[CrimeIncident]:
        """Parse Socrata API response into CrimeIncident objects."""
        incidents = []

        for record in api_data:
            try:
                # Map API fields to our model using field mapping
                mapped_data = {}

                for model_field, api_field_options in self.field_mapping.items():
                    value = None

                    # Try each possible field name until we find one with data
                    for api_field in api_field_options:
                        if api_field in record and record[api_field]:
                            value = record[api_field]
                            break

                    mapped_data[model_field] = value

                # Ensure required fields are present
                if not mapped_data.get('incident_id'):
                    # Try to generate ID from other fields
                    case_num = mapped_data.get('case_number')
                    date_str = str(mapped_data.get('incident_date', ''))
                    if case_num:
                        mapped_data['incident_id'] = case_num
                    elif date_str:
                        mapped_data['incident_id'] = f"incident_{date_str}_{hash(str(record)) % 10000}"
                    else:
                        continue  # Skip records without identifiable ID

                if not mapped_data.get('incident_date'):
                    continue  # Skip records without date

                if not mapped_data.get('incident_type'):
                    mapped_data['incident_type'] = "Unknown"

                if not mapped_data.get('description'):
                    mapped_data['description'] = "No description available"

                # Create and validate incident record
                incident = CrimeIncident(**{k: v for k, v in mapped_data.items() if v is not None})
                incidents.append(incident)

            except Exception as e:
                self.logger.warning(f"Failed to parse crime record: {e}")
                self.logger.debug(f"Problem record: {record}")
                continue

        self.logger.info(f"Successfully parsed {len(incidents)} valid crime incidents")
        return incidents

    def _get_mapped_field(self, model_field: str) -> Optional[str]:
        """Get the first available API field name for a model field."""
        if model_field not in self.field_mapping:
            return None

        # Return first field name as default
        return self.field_mapping[model_field][0]


async def create_crime_data_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    endpoint_url: str,
    app_token: Optional[str] = None,
    field_mapping: Optional[Dict[str, str]] = None,
    **kwargs
) -> SocrataCrimeDataScraper:
    """Factory function to create configured Socrata crime data scraper."""
    scraper = SocrataCrimeDataScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        base_endpoint_url=endpoint_url,
        app_token=app_token,
        default_field_mapping=field_mapping,
        **kwargs
    )
    await scraper.initialize()
    return scraper