"""
City of Gainesville Permits API scraper.
Fetches permit data from the city's public API endpoint.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class PermitRecord(BaseModel):
    """Model for city permit data."""
    permit_number: str = Field(..., min_length=1)
    permit_type: str
    status: str
    application_date: datetime
    issue_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    description: str
    address: str
    parcel_id: Optional[str] = None
    applicant_name: str
    contractor_name: Optional[str] = None
    estimated_value: Optional[float] = None
    square_footage: Optional[float] = None
    fees_paid: Optional[float] = None

    @validator('application_date', 'issue_date', 'expiration_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle multiple date formats from API
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('estimated_value', 'square_footage', 'fees_paid', pre=True)
    def parse_numbers(cls, v):
        if v is None or v == "" or v == "N/A":
            return None
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = v.replace('$', '').replace(',', '')
            try:
                return float(v)
            except ValueError:
                return None
        return float(v) if v else None


class CityPermitsScraper(ResilientScraper):
    """
    Scraper for City of Gainesville building permits.

    API Endpoint: https://data.cityofgainesville.org/api/explore/v2.1/catalog/datasets/building-permits
    Data Format: JSON via Socrata API
    Update Frequency: Daily (new permits added continuously)
    """

    BASE_URL = "https://data.cityofgainesville.org/api/explore/v2.1/catalog/datasets/building-permits/records"

    def __init__(self, db_manager: DatabaseManager, change_detector: ChangeDetector, **kwargs):
        super().__init__(
            scraper_id="city_permits_gainesville",
            scraper_type=ScraperType.API,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.session_timeout = 60

    async def scrape_permits(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[PermitRecord]:
        """
        Scrape permits with date range filtering.

        Args:
            start_date: Start date for permit search (defaults to yesterday)
            end_date: End date for permit search (defaults to today)
            limit: Maximum records per request (API max is 10000)
            offset: Starting offset for pagination
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=1)
        if not end_date:
            end_date = datetime.now()

        # Build API query parameters
        params = {
            "limit": min(limit, 10000),  # API maximum
            "offset": offset,
            "timezone": "America/New_York",
            "format": "json"
        }

        # Add date filter
        date_filter = f"application_date >= '{start_date.strftime('%Y-%m-%d')}' AND application_date <= '{end_date.strftime('%Y-%m-%d')}'"
        params["where"] = date_filter

        # Add ordering
        params["order_by"] = "application_date DESC"

        # Execute request
        result = await self.scrape(self.BASE_URL, params=params)

        if not result.success:
            self.logger.error(f"Failed to fetch permits: {result.error}")
            return []

        return await self._parse_permits_response(result.data)

    async def scrape_all_recent_permits(self, days_back: int = 7) -> List[PermitRecord]:
        """
        Scrape all permits from the last N days using pagination.

        Args:
            days_back: Number of days to look back for permits
        """
        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        all_permits = []
        offset = 0
        page_size = 1000

        while True:
            permits = await self.scrape_permits(
                start_date=start_date,
                end_date=end_date,
                limit=page_size,
                offset=offset
            )

            if not permits:
                break

            all_permits.extend(permits)

            # Check if we got less than page_size (last page)
            if len(permits) < page_size:
                break

            offset += page_size

            # Safety check to prevent infinite loops
            if len(all_permits) > 50000:
                self.logger.warning("Reached safety limit of 50k permits")
                break

        self.logger.info(f"Scraped {len(all_permits)} permits from last {days_back} days")
        return all_permits

    async def monitor_new_permits(self) -> List[PermitRecord]:
        """
        Monitor for new permits since last successful scrape.
        Uses change detection to identify when new permits are available.
        """
        # Check for changes in the API response
        test_url = f"{self.BASE_URL}?limit=1&order_by=application_date DESC"

        change_result = await self.change_detector.track_content_change(
            url=test_url,
            content=b"",  # Will be filled by the scraper
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        # If no changes detected, return empty list
        if change_result.change_type.value == "unchanged":
            self.logger.debug("No new permits detected")
            return []

        # Get permits from last 24 hours to catch any new ones
        return await self.scrape_all_recent_permits(days_back=1)

    async def store_permits(self, permits: List[PermitRecord]) -> int:
        """
        Store permits in database as raw facts.

        Returns:
            Number of new permits stored
        """
        if not permits:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for permit in permits:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "permit_data": permit.dict(),
                        "scraped_from": "city_permits_api",
                        "scraper_version": "1.0",
                        "processing_notes": {
                            "data_quality": "structured_json",
                            "confidence": 1.0
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
                        "permit_filing",
                        f"{self.BASE_URL}?permit={permit.permit_number}",
                        datetime.utcnow(),
                        "city_permits_v1.0",
                        json.dumps(fact_data),
                        content_hash,
                        datetime.utcnow()
                    )

                    if result.rowcount > 0:
                        stored_count += 1

                        # Also create structured fact
                        raw_fact_id = (await result.fetchone())['id']

                        structured_query = """
                            INSERT INTO structured_facts (
                                raw_fact_id, entity_type, structured_data, extraction_confidence
                            ) VALUES ($1, $2, $3, $4)
                        """

                        await session.execute(
                            structured_query,
                            raw_fact_id,
                            "permit",
                            json.dumps(permit.dict(), default=str),
                            1.0  # High confidence for structured API data
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store permit {permit.permit_number}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new permits")
        return stored_count

    async def get_recent_permits_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics of recent permits."""
        async with self.db_manager.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            query = """
                SELECT
                    COUNT(*) as total_permits,
                    COUNT(DISTINCT (structured_data->>'permit_type')::text) as unique_types,
                    AVG((structured_data->>'estimated_value')::numeric) as avg_value,
                    SUM((structured_data->>'estimated_value')::numeric) as total_value,
                    COUNT(*) FILTER (WHERE (structured_data->>'status')::text = 'Issued') as issued_count,
                    COUNT(*) FILTER (WHERE (structured_data->>'status')::text = 'Pending') as pending_count
                FROM structured_facts sf
                JOIN raw_facts rf ON sf.raw_fact_id = rf.id
                WHERE sf.entity_type = 'permit'
                AND rf.fact_type = 'permit_filing'
                AND rf.scraped_at >= $1
            """

            result = await session.execute(query, cutoff_date)
            row = await result.fetchone()

            return {
                'total_permits': row['total_permits'] or 0,
                'unique_types': row['unique_types'] or 0,
                'average_value': float(row['avg_value']) if row['avg_value'] else 0.0,
                'total_value': float(row['total_value']) if row['total_value'] else 0.0,
                'issued_count': row['issued_count'] or 0,
                'pending_count': row['pending_count'] or 0,
                'period_days': days
            }

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process API response and extract permit records."""
        try:
            data = json.loads(content.decode('utf-8'))

            # Gainesville API returns data in 'records' field
            if 'records' not in data:
                self.logger.error(f"Unexpected API response format: {list(data.keys())}")
                return []

            records = data['records']
            self.logger.info(f"Received {len(records)} permit records from API")

            return records

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing response: {e}")
            return []

    async def _parse_permits_response(self, api_records: List[Dict[str, Any]]) -> List[PermitRecord]:
        """Parse API records into PermitRecord objects."""
        permits = []

        for record in api_records:
            try:
                # Extract fields from nested structure
                fields = record.get('record', {}).get('fields', {})

                # Map API fields to our model
                permit_data = {
                    'permit_number': fields.get('permit_number', ''),
                    'permit_type': fields.get('permit_type', ''),
                    'status': fields.get('status', ''),
                    'application_date': fields.get('application_date'),
                    'issue_date': fields.get('issue_date'),
                    'expiration_date': fields.get('expiration_date'),
                    'description': fields.get('description', ''),
                    'address': fields.get('address', ''),
                    'parcel_id': fields.get('parcel_id'),
                    'applicant_name': fields.get('applicant_name', ''),
                    'contractor_name': fields.get('contractor_name'),
                    'estimated_value': fields.get('estimated_value'),
                    'square_footage': fields.get('square_footage'),
                    'fees_paid': fields.get('fees_paid')
                }

                # Create and validate permit record
                permit = PermitRecord(**permit_data)
                permits.append(permit)

            except Exception as e:
                self.logger.warning(f"Failed to parse permit record: {e}")
                self.logger.debug(f"Problem record: {record}")
                continue

        self.logger.info(f"Successfully parsed {len(permits)} valid permits")
        return permits


async def create_city_permits_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    **kwargs
) -> CityPermitsScraper:
    """Factory function to create configured city permits scraper."""
    scraper = CityPermitsScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        **kwargs
    )
    await scraper.initialize()
    return scraper