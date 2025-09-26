"""
Zoning and Land Use Data scraper using Socrata API.
Provides comprehensive zoning information for real estate intelligence.
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
from .crime_data_socrata import SocrataQuery, SocrataDataFormat, SocrataOrderDirection


class ZoningClassification(Enum):
    """Common zoning classifications."""
    RESIDENTIAL_SINGLE_FAMILY = "R1"
    RESIDENTIAL_MULTI_FAMILY = "R2"
    COMMERCIAL = "C1"
    INDUSTRIAL = "I1"
    MIXED_USE = "MU"
    AGRICULTURAL = "AG"
    PLANNED_UNIT_DEVELOPMENT = "PUD"
    UNKNOWN = "UNKNOWN"


class ZoningRecord(BaseModel):
    """Model for zoning district data."""
    zoning_id: str = Field(..., min_length=1)
    zoning_code: str
    zoning_description: str
    district_name: Optional[str] = None
    parcel_id: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    acres: Optional[float] = None
    square_feet: Optional[float] = None
    max_building_height: Optional[float] = None
    max_units_per_acre: Optional[float] = None
    max_floor_area_ratio: Optional[float] = None
    setback_front: Optional[float] = None
    setback_rear: Optional[float] = None
    setback_side: Optional[float] = None
    parking_requirements: Optional[str] = None
    permitted_uses: Optional[List[str]] = None
    conditional_uses: Optional[List[str]] = None
    prohibited_uses: Optional[List[str]] = None
    overlay_districts: Optional[List[str]] = None
    last_updated: Optional[datetime] = None
    effective_date: Optional[datetime] = None

    @validator('latitude', 'longitude', 'acres', 'square_feet', 'max_building_height',
              'max_units_per_acre', 'max_floor_area_ratio', 'setback_front',
              'setback_rear', 'setback_side', pre=True)
    def parse_numbers(cls, v):
        if v is None or v == "" or v == "N/A":
            return None
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None

    @validator('last_updated', 'effective_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y"
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('permitted_uses', 'conditional_uses', 'prohibited_uses', 'overlay_districts', pre=True)
    def parse_lists(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle comma-separated values or JSON strings
            try:
                # Try parsing as JSON first
                return json.loads(v) if v.startswith('[') else [item.strip() for item in v.split(',') if item.strip()]
            except json.JSONDecodeError:
                return [item.strip() for item in v.split(',') if item.strip()]
        if isinstance(v, list):
            return v
        return None

    @property
    def classification(self) -> ZoningClassification:
        """Determine zoning classification from code."""
        code_upper = self.zoning_code.upper()

        if code_upper.startswith('R') and ('1' in code_upper or 'SINGLE' in code_upper.upper()):
            return ZoningClassification.RESIDENTIAL_SINGLE_FAMILY
        elif code_upper.startswith('R'):
            return ZoningClassification.RESIDENTIAL_MULTI_FAMILY
        elif code_upper.startswith('C'):
            return ZoningClassification.COMMERCIAL
        elif code_upper.startswith('I'):
            return ZoningClassification.INDUSTRIAL
        elif 'MU' in code_upper or 'MIXED' in code_upper:
            return ZoningClassification.MIXED_USE
        elif code_upper.startswith('AG') or 'AGRIC' in code_upper:
            return ZoningClassification.AGRICULTURAL
        elif 'PUD' in code_upper:
            return ZoningClassification.PLANNED_UNIT_DEVELOPMENT
        else:
            return ZoningClassification.UNKNOWN


class ZoningDataScraper(ResilientScraper):
    """
    Scraper for zoning and land use data via Socrata API.

    Provides comprehensive zoning information including permitted uses,
    building restrictions, and overlay districts for real estate analysis.
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
            scraper_id="zoning_data",
            scraper_type=ScraperType.API,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.base_endpoint_url = base_endpoint_url.rstrip('/')
        self.app_token = app_token

        # Default field mapping for common zoning data schemas
        self.field_mapping = default_field_mapping or {
            'zoning_id': ['id', 'objectid', 'zoning_id', 'zone_id'],
            'zoning_code': ['zoning', 'zone_code', 'zoning_code', 'district'],
            'zoning_description': ['description', 'zoning_desc', 'zone_desc', 'district_name'],
            'district_name': ['district_name', 'zone_name', 'area_name'],
            'parcel_id': ['parcel_id', 'parcel', 'pin', 'apn'],
            'address': ['address', 'location', 'site_address'],
            'latitude': ['latitude', 'lat', 'y', 'point_y'],
            'longitude': ['longitude', 'lng', 'lon', 'x', 'point_x'],
            'acres': ['acres', 'area_acres', 'acreage'],
            'square_feet': ['sq_ft', 'square_feet', 'area_sqft'],
            'max_building_height': ['max_height', 'height_limit', 'building_height'],
            'max_units_per_acre': ['max_density', 'units_per_acre', 'dwelling_units'],
            'max_floor_area_ratio': ['far', 'floor_area_ratio', 'max_far'],
            'setback_front': ['front_setback', 'setback_front'],
            'setback_rear': ['rear_setback', 'setback_rear'],
            'setback_side': ['side_setback', 'setback_side'],
            'parking_requirements': ['parking', 'parking_req', 'parking_requirements'],
            'permitted_uses': ['permitted_uses', 'allowed_uses', 'primary_uses'],
            'conditional_uses': ['conditional_uses', 'special_uses', 'conditional'],
            'prohibited_uses': ['prohibited_uses', 'restricted_uses'],
            'overlay_districts': ['overlay', 'overlay_districts', 'special_districts'],
            'last_updated': ['last_updated', 'modified_date', 'edit_date'],
            'effective_date': ['effective_date', 'created_date', 'adoption_date']
        }

    async def scrape_zoning_data(
        self,
        zoning_codes: Optional[List[str]] = None,
        geographic_bounds: Optional[Dict[str, float]] = None,
        parcel_ids: Optional[List[str]] = None,
        limit: int = 1000
    ) -> List[ZoningRecord]:
        """
        Scrape zoning data with flexible filtering.

        Args:
            zoning_codes: List of specific zoning codes to filter by
            geographic_bounds: Dict with 'north', 'south', 'east', 'west' coordinates
            parcel_ids: List of specific parcel IDs to retrieve
            limit: Maximum records per request
        """
        # Build where clause for filtering
        where_conditions = []

        # Zoning code filtering
        if zoning_codes:
            code_field = self._get_mapped_field('zoning_code')
            if code_field:
                code_conditions = [f"{code_field} = '{code}'" for code in zoning_codes]
                where_conditions.append(f"({' OR '.join(code_conditions)})")

        # Parcel ID filtering
        if parcel_ids:
            parcel_field = self._get_mapped_field('parcel_id')
            if parcel_field:
                parcel_conditions = [f"{parcel_field} = '{parcel_id}'" for parcel_id in parcel_ids]
                where_conditions.append(f"({' OR '.join(parcel_conditions)})")

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
            order_by=self._get_mapped_field('zoning_code'),
            order_direction=SocrataOrderDirection.ASC,
            app_token=self.app_token
        )

        # Execute request
        result = await self._execute_socrata_query(query)
        if not result.success:
            self.logger.error(f"Failed to fetch zoning data: {result.error}")
            return []

        return await self._parse_zoning_data(result.data)

    async def scrape_all_zoning_districts(self) -> List[ZoningRecord]:
        """
        Scrape all zoning districts using pagination.
        """
        all_zones = []
        offset = 0
        page_size = 1000

        while True:
            query = SocrataQuery(
                endpoint_url=self.base_endpoint_url,
                limit=page_size,
                offset=offset,
                order_by=self._get_mapped_field('zoning_id'),
                order_direction=SocrataOrderDirection.ASC,
                app_token=self.app_token
            )

            result = await self._execute_socrata_query(query)
            if not result.success:
                self.logger.error(f"Failed to fetch paginated zoning data: {result.error}")
                break

            zones = await self._parse_zoning_data(result.data)
            if not zones:
                break

            all_zones.extend(zones)

            # Check if we got less than page_size (last page)
            if len(zones) < page_size:
                break

            offset += page_size

            # Safety check
            if len(all_zones) > 50000:
                self.logger.warning("Reached safety limit of 50k zoning records")
                break

        self.logger.info(f"Scraped {len(all_zones)} zoning districts")
        return all_zones

    async def get_zoning_by_address(self, address: str) -> List[ZoningRecord]:
        """
        Get zoning information for a specific address.

        Args:
            address: Address to look up zoning for
        """
        address_field = self._get_mapped_field('address')
        if not address_field:
            self.logger.error("Address field not available in zoning data")
            return []

        query = SocrataQuery(
            endpoint_url=self.base_endpoint_url,
            where_clause=f"upper({address_field}) like upper('%{address}%')",
            limit=10,
            app_token=self.app_token
        )

        result = await self._execute_socrata_query(query)
        if not result.success:
            return []

        return await self._parse_zoning_data(result.data)

    async def get_zoning_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 0.1
    ) -> List[ZoningRecord]:
        """
        Get zoning information near specific coordinates.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius_miles: Search radius in miles (default 0.1 mile)
        """
        lat_field = self._get_mapped_field('latitude')
        lon_field = self._get_mapped_field('longitude')

        if not lat_field or not lon_field:
            self.logger.error("Coordinate fields not available in zoning data")
            return []

        # Convert miles to approximate degrees (rough conversion)
        degree_radius = radius_miles / 69.0  # 1 degree ≈ 69 miles

        query = SocrataQuery(
            endpoint_url=self.base_endpoint_url,
            where_clause=(
                f"{lat_field} BETWEEN {latitude - degree_radius} AND {latitude + degree_radius} AND "
                f"{lon_field} BETWEEN {longitude - degree_radius} AND {longitude + degree_radius}"
            ),
            limit=50,
            app_token=self.app_token
        )

        result = await self._execute_socrata_query(query)
        if not result.success:
            return []

        return await self._parse_zoning_data(result.data)

    async def get_zoning_statistics(self) -> Dict[str, Any]:
        """Get aggregated zoning statistics."""
        stats = {}

        # Total zones by classification
        code_field = self._get_mapped_field('zoning_code')
        if code_field:
            query = SocrataQuery(
                endpoint_url=self.base_endpoint_url,
                select_fields=[code_field, f"COUNT(*) as count"],
                group_by=[code_field],
                order_by="count",
                order_direction=SocrataOrderDirection.DESC,
                limit=100,
                app_token=self.app_token
            )

            result = await self._execute_socrata_query(query)
            if result.success:
                stats['zones_by_code'] = result.data

        return stats

    async def monitor_zoning_changes(self) -> List[ZoningRecord]:
        """
        Monitor for zoning changes since last successful scrape.
        """
        # Check for changes in zoning data
        test_query = SocrataQuery(
            endpoint_url=self.base_endpoint_url,
            limit=1,
            order_by=self._get_mapped_field('last_updated'),
            order_direction=SocrataOrderDirection.DESC,
            app_token=self.app_token
        )

        test_url = self._build_query_url(test_query)

        change_result = await self.change_detector.track_content_change(
            url=test_url,
            content=b"",
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        # If no changes detected, return empty list
        if change_result.change_type.value == "unchanged":
            self.logger.debug("No zoning changes detected")
            return []

        # Get recently updated zones
        last_updated_field = self._get_mapped_field('last_updated')
        if last_updated_field:
            # Get zones updated in last 30 days
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')

            query = SocrataQuery(
                endpoint_url=self.base_endpoint_url,
                where_clause=f"{last_updated_field} >= '{cutoff_date}'",
                order_by=last_updated_field,
                order_direction=SocrataOrderDirection.DESC,
                limit=1000,
                app_token=self.app_token
            )

            result = await self._execute_socrata_query(query)
            if result.success:
                return await self._parse_zoning_data(result.data)

        return []

    async def store_zoning_data(self, zones: List[ZoningRecord]) -> int:
        """
        Store zoning data in database as raw facts.

        Returns:
            Number of new zones stored
        """
        if not zones:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for zone in zones:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "zoning_data": zone.dict(),
                        "scraped_from": "zoning_api",
                        "scraper_version": "1.0",
                        "api_endpoint": self.base_endpoint_url,
                        "processing_notes": {
                            "data_quality": "structured_government_api",
                            "confidence": 1.0,
                            "source_type": "socrata_zoning_api",
                            "classification": zone.classification.value
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
                        "zoning_data",
                        f"{self.base_endpoint_url}?zoning_id={zone.zoning_id}",
                        datetime.utcnow(),
                        "zoning_data_v1.0",
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
                            "zoning_district",
                            json.dumps(zone.dict(), default=str),
                            1.0  # High confidence for structured government API data
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store zoning data {zone.zoning_id}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new zoning districts")
        return stored_count

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process Socrata API response."""
        try:
            data = json.loads(content.decode('utf-8'))

            if not isinstance(data, list):
                self.logger.error(f"Unexpected Socrata API response format: {type(data)}")
                return []

            self.logger.info(f"Received {len(data)} zoning records from Socrata API")
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
        endpoint = query.endpoint_url
        if not endpoint.endswith('.json') and query.data_format == SocrataDataFormat.JSON:
            endpoint += '.json'

        params = query.to_query_params()

        if params:
            query_string = urllib.parse.urlencode(params)
            return f"{endpoint}?{query_string}"

        return endpoint

    async def _parse_zoning_data(self, api_data: List[Dict[str, Any]]) -> List[ZoningRecord]:
        """Parse Socrata API response into ZoningRecord objects."""
        zones = []

        for record in api_data:
            try:
                # Map API fields to our model using field mapping
                mapped_data = {}

                for model_field, api_field_options in self.field_mapping.items():
                    value = None

                    # Try each possible field name until we find one with data
                    for api_field in api_field_options:
                        if api_field in record and record[api_field] is not None:
                            value = record[api_field]
                            break

                    mapped_data[model_field] = value

                # Ensure required fields are present
                if not mapped_data.get('zoning_id'):
                    # Generate ID from other fields if not available
                    parcel_id = mapped_data.get('parcel_id')
                    zoning_code = mapped_data.get('zoning_code', '')
                    if parcel_id:
                        mapped_data['zoning_id'] = f"{parcel_id}_{zoning_code}"
                    else:
                        mapped_data['zoning_id'] = f"zone_{hash(str(record)) % 100000}"

                if not mapped_data.get('zoning_code'):
                    mapped_data['zoning_code'] = "UNKNOWN"

                if not mapped_data.get('zoning_description'):
                    mapped_data['zoning_description'] = f"Zone {mapped_data.get('zoning_code', 'Unknown')}"

                # Create and validate zoning record
                zone = ZoningRecord(**{k: v for k, v in mapped_data.items() if v is not None})
                zones.append(zone)

            except Exception as e:
                self.logger.warning(f"Failed to parse zoning record: {e}")
                self.logger.debug(f"Problem record: {record}")
                continue

        self.logger.info(f"Successfully parsed {len(zones)} valid zoning records")
        return zones

    def _get_mapped_field(self, model_field: str) -> Optional[str]:
        """Get the first available API field name for a model field."""
        if model_field not in self.field_mapping:
            return None
        return self.field_mapping[model_field][0]


async def create_zoning_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    endpoint_url: str,
    app_token: Optional[str] = None,
    field_mapping: Optional[Dict[str, str]] = None,
    **kwargs
) -> ZoningDataScraper:
    """Factory function to create configured zoning data scraper."""
    scraper = ZoningDataScraper(
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