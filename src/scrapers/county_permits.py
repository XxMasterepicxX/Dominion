"""
Alachua County Permits Scraper

Handles permit tracking for Alachua County jurisdiction using browser automation.
Separate from City of Gainesville permits which use the CitizenServe portal.

Coverage: Building, Electrical, Plumbing, Mechanical, Zoning, Subdivision permits
Jurisdiction: Alachua County (outside Gainesville city limits)

Uses Patchright for stealth automation on JavaScript-heavy permit portals.
"""
import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from patchright.async_api import Page, Browser, BrowserContext, TimeoutError as PatchrightTimeoutError
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class PermitStatus(Enum):
    """Permit status values."""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ISSUED = "issued"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"
    PENDING = "pending"
    UNKNOWN = "unknown"


class PermitType(Enum):
    """County permit types."""
    BUILDING = "building"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    MECHANICAL = "mechanical"
    ZONING = "zoning"
    SUBDIVISION = "subdivision"
    SITE_PLAN = "site_plan"
    VARIANCE = "variance"
    SPECIAL_USE = "special_use"
    DEMOLITION = "demolition"
    SIGN = "sign"
    TREE_REMOVAL = "tree_removal"
    SEPTIC = "septic"
    DRIVEWAY = "driveway"
    OTHER = "other"


class CountyPermitRecord(BaseModel):
    """Model for county permit data."""
    permit_number: str = Field(..., min_length=1)
    permit_type: PermitType = PermitType.OTHER
    permit_subtype: Optional[str] = None
    status: PermitStatus = PermitStatus.UNKNOWN
    application_date: datetime
    issued_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None

    # Project details
    project_description: str = Field(..., min_length=1)
    project_address: str = Field(..., min_length=1)
    parcel_number: Optional[str] = None
    estimated_value: Optional[float] = None
    square_footage: Optional[float] = None

    # Applicant information
    applicant_name: str = Field(..., min_length=1)
    applicant_address: Optional[str] = None
    applicant_phone: Optional[str] = None
    contractor_name: Optional[str] = None
    contractor_license: Optional[str] = None

    # Review details
    plan_reviewer: Optional[str] = None
    inspector: Optional[str] = None
    review_comments: Optional[str] = None
    conditions: Optional[List[str]] = None

    # Geographic data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    district: Optional[str] = None
    zone: Optional[str] = None

    # Fees
    permit_fee: Optional[float] = None
    impact_fee: Optional[float] = None
    total_fees: Optional[float] = None
    fees_paid: Optional[float] = None

    # Data source
    portal_url: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('application_date', 'issued_date', 'expiration_date', 'completed_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle multiple date formats
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y",
                "%m-%d-%Y",
                "%B %d, %Y",
                "%b %d, %Y"
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('estimated_value', 'square_footage', 'permit_fee', 'impact_fee',
              'total_fees', 'fees_paid', 'latitude', 'longitude', pre=True)
    def parse_numbers(cls, v):
        if v is None or v == "" or v == "N/A":
            return None
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = v.replace('$', '').replace(',', '').replace('(', '').replace(')', '')
            try:
                return float(v) if v else None
            except ValueError:
                return None
        return float(v) if v else None

    @validator('conditions', pre=True)
    def parse_conditions(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Split by common separators
            conditions = re.split(r'[;\n\|]', v)
            return [condition.strip() for condition in conditions if condition.strip()]
        return v

    def classify_permit_type(self) -> PermitType:
        """Classify permit type from permit number or description."""
        text = f"{self.permit_number} {self.project_description}".lower()

        # Classification patterns
        if any(word in text for word in ['building', 'construction', 'residential', 'commercial']):
            return PermitType.BUILDING
        elif any(word in text for word in ['electrical', 'electric']):
            return PermitType.ELECTRICAL
        elif any(word in text for word in ['plumbing', 'plumb']):
            return PermitType.PLUMBING
        elif any(word in text for word in ['mechanical', 'hvac', 'air conditioning']):
            return PermitType.MECHANICAL
        elif any(word in text for word in ['zoning', 'variance', 'rezoning']):
            return PermitType.ZONING
        elif any(word in text for word in ['subdivision', 'plat', 'subdivide']):
            return PermitType.SUBDIVISION
        elif any(word in text for word in ['site plan', 'site development']):
            return PermitType.SITE_PLAN
        elif any(word in text for word in ['demolition', 'demolish', 'demo']):
            return PermitType.DEMOLITION
        elif any(word in text for word in ['sign', 'signage']):
            return PermitType.SIGN
        elif any(word in text for word in ['tree', 'removal', 'clearing']):
            return PermitType.TREE_REMOVAL
        elif any(word in text for word in ['septic', 'sewage', 'waste']):
            return PermitType.SEPTIC
        elif any(word in text for word in ['driveway', 'access', 'approach']):
            return PermitType.DRIVEWAY
        else:
            return PermitType.OTHER

    def classify_status(self, status_text: str) -> PermitStatus:
        """Classify permit status from text."""
        status_lower = status_text.lower()

        if any(word in status_lower for word in ['issued', 'active']):
            return PermitStatus.ISSUED
        elif any(word in status_lower for word in ['approved', 'accept']):
            return PermitStatus.APPROVED
        elif any(word in status_lower for word in ['submitted', 'received', 'intake']):
            return PermitStatus.SUBMITTED
        elif any(word in status_lower for word in ['review', 'processing', 'examining']):
            return PermitStatus.UNDER_REVIEW
        elif any(word in status_lower for word in ['denied', 'rejected']):
            return PermitStatus.DENIED
        elif any(word in status_lower for word in ['expired', 'expire']):
            return PermitStatus.EXPIRED
        elif any(word in status_lower for word in ['cancelled', 'withdrawn', 'void']):
            return PermitStatus.CANCELLED
        elif any(word in status_lower for word in ['hold', 'suspended']):
            return PermitStatus.ON_HOLD
        elif any(word in status_lower for word in ['pending']):
            return PermitStatus.PENDING
        else:
            return PermitStatus.UNKNOWN


class PermitPortalConfig(BaseModel):
    """Configuration for permit portal interactions."""
    portal_url: str = Field(..., min_length=1)
    portal_type: str = Field(default="generic")  # alachua, generic, tyler, etc.

    # Navigation selectors
    search_form_selector: Optional[str] = None
    date_from_selector: Optional[str] = None
    date_to_selector: Optional[str] = None
    search_button_selector: Optional[str] = None
    results_table_selector: Optional[str] = None
    next_page_selector: Optional[str] = None
    permit_detail_link_selector: Optional[str] = None

    # Data extraction selectors
    field_selectors: Optional[Dict[str, str]] = None

    # Interaction settings
    wait_timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    page_load_delay_ms: int = Field(default=2000, ge=0, le=10000)
    between_requests_delay_ms: int = Field(default=1000, ge=100, le=10000)

    # Browser settings
    headless: bool = Field(default=True)
    user_agent: Optional[str] = None
    viewport_width: int = Field(default=1920, ge=800, le=3840)
    viewport_height: int = Field(default=1080, ge=600, le=2160)


class CountyPermitsScraper(ResilientScraper):
    """
    Alachua County permits scraper using Patchright for stealth automation.

    Handles county permit portals that require browser automation with anti-detection.
    Covers permits outside Gainesville city limits with stealth capabilities.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        portal_config: PermitPortalConfig,
        **kwargs
    ):
        super().__init__(
            scraper_id="county_permits_playwright",
            scraper_type=ScraperType.WEB,
            enable_js=True,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.config = portal_config

        # Portal-specific configurations
        self.portal_configs = {
            "alachua": {
                "search_form_selector": "#searchForm",
                "date_from_selector": "input[name='dateFrom']",
                "date_to_selector": "input[name='dateTo']",
                "search_button_selector": "button[type='submit'], input[type='submit']",
                "results_table_selector": ".results-table, #resultsTable, table",
                "permit_detail_link_selector": "a[href*='permit'], a[href*='detail']",
                "field_selectors": {
                    "permit_number": ".permit-number, .permit-id",
                    "status": ".status, .permit-status",
                    "project_description": ".description, .project-desc",
                    "project_address": ".address, .location",
                    "applicant_name": ".applicant, .owner",
                    "application_date": ".app-date, .date-submitted"
                }
            },
            "tyler": {
                "search_form_selector": "form[name='searchForm']",
                "date_from_selector": "#fromDate",
                "date_to_selector": "#toDate",
                "search_button_selector": "#searchButton",
                "results_table_selector": "#searchResults table",
                "permit_detail_link_selector": "a.permit-link"
            },
            "generic": {
                "search_form_selector": "form, #searchForm, .search-form",
                "date_from_selector": "input[type='date'], input[name*='from'], input[name*='start']",
                "date_to_selector": "input[type='date'], input[name*='to'], input[name*='end']",
                "search_button_selector": "button[type='submit'], input[type='submit'], .search-btn",
                "results_table_selector": "table, .results, .permits-table",
                "permit_detail_link_selector": "a[href*='permit'], a[href*='detail'], .permit-link"
            }
        }

        # Merge portal-specific config with provided config
        portal_defaults = self.portal_configs.get(self.config.portal_type, self.portal_configs["generic"])

        if not self.config.search_form_selector:
            self.config.search_form_selector = portal_defaults.get("search_form_selector")
        if not self.config.field_selectors:
            self.config.field_selectors = portal_defaults.get("field_selectors", {})

        # Browser context will be managed per scraping session
        self.context: Optional[BrowserContext] = None

    async def scrape_permits(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        permit_types: Optional[List[str]] = None,
        max_permits: int = 1000
    ) -> List[CountyPermitRecord]:
        """
        Scrape county permits using browser automation.

        Args:
            start_date: Start date for permit search
            end_date: End date for permit search
            permit_types: Specific permit types to filter
            max_permits: Maximum permits to retrieve
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)  # Last week
        if not end_date:
            end_date = datetime.now()

        permits = []

        try:
            # Create browser context
            self.context = await self.browser.new_context(
                user_agent=self.config.user_agent or self.user_agent.random,
                viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height}
            )

            # Create new page
            page = await self.context.new_page()

            self.logger.info(f"Navigating to permit portal: {self.config.portal_url}")

            # Navigate to portal
            await page.goto(self.config.portal_url,
                           wait_until='networkidle',
                           timeout=self.config.wait_timeout_ms)

            # Wait for page to fully load
            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            # Perform search
            search_results = await self._perform_permit_search(page, start_date, end_date)

            if not search_results:
                self.logger.warning("No search results found")
                return permits

            # Extract permits from search results
            permits = await self._extract_permits_from_results(page, search_results, max_permits)

            self.logger.info(f"Successfully scraped {len(permits)} permits")

        except Exception as e:
            self.logger.error(f"Failed to scrape permits: {e}")

        finally:
            # Clean up browser context
            if self.context:
                await self.context.close()
                self.context = None

        return permits

    async def scrape_recent_permits(self, days_back: int = 7) -> List[CountyPermitRecord]:
        """
        Scrape recent permits from the last N days.

        Args:
            days_back: Number of days to look back
        """
        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        return await self.scrape_permits(start_date=start_date, end_date=end_date)

    async def monitor_new_permits(self) -> List[CountyPermitRecord]:
        """Monitor for new permits since last check."""
        # Check for changes in the portal
        change_result = await self.change_detector.track_content_change(
            url=self.config.portal_url,
            content=b"",  # Will be filled by change detector
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        if change_result.change_type.value == "unchanged":
            self.logger.debug("No changes detected in permit portal")
            return []

        # Get permits from last 24 hours
        return await self.scrape_recent_permits(days_back=1)

    async def store_permits(self, permits: List[CountyPermitRecord]) -> int:
        """Store county permits in database."""
        if not permits:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for permit in permits:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "permit_data": permit.dict(),
                        "scraped_from": "county_permits",
                        "scraper_version": "1.0",
                        "portal_type": self.config.portal_type,
                        "processing_notes": {
                            "data_quality": "browser_automated_extraction",
                            "confidence": 0.90,  # Slightly lower due to complex extraction
                            "source_type": "county_permit_portal",
                            "permit_type": permit.permit_type.value,
                            "permit_status": permit.status.value,
                            "has_financial_data": any([permit.permit_fee, permit.total_fees]),
                            "has_geographic_data": all([permit.latitude, permit.longitude])
                        }
                    }

                    # Calculate content hash
                    content_str = json.dumps(fact_data, sort_keys=True, default=str)
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
                        "county_permit_filing",
                        f"{self.config.portal_url}?permit={permit.permit_number}",
                        datetime.utcnow(),
                        "county_permits_playwright_v1.0",
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
                            "county_permit",
                            json.dumps(permit.dict(), default=str),
                            0.90  # Browser automation confidence
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store permit {permit.permit_number}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new county permits")
        return stored_count

    async def get_permit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics about recent county permits."""
        async with self.db_manager.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Permits by type and status
            query = """
                SELECT
                    (structured_data->>'permit_type')::text as permit_type,
                    (structured_data->>'status')::text as status,
                    COUNT(*) as count,
                    AVG((structured_data->>'estimated_value')::numeric) as avg_value
                FROM structured_facts sf
                JOIN raw_facts rf ON sf.raw_fact_id = rf.id
                WHERE sf.entity_type = 'county_permit'
                AND rf.fact_type = 'county_permit_filing'
                AND rf.scraped_at >= $1
                GROUP BY permit_type, status
                ORDER BY count DESC
            """

            result = await session.execute(query, cutoff_date)
            permit_stats = {}

            for row in await result.fetchall():
                permit_type = row['permit_type']
                status = row['status']

                if permit_type not in permit_stats:
                    permit_stats[permit_type] = {}

                permit_stats[permit_type][status] = {
                    'count': row['count'],
                    'avg_value': float(row['avg_value']) if row['avg_value'] else 0
                }

            return {
                'permit_breakdown': permit_stats,
                'period_days': days,
                'total_permits': sum(
                    sum(statuses.values(), {}).get('count', 0)
                    for statuses in permit_stats.values()
                )
            }

    async def _perform_permit_search(
        self,
        page: Page,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[str]:
        """Perform permit search on the portal."""
        try:
            # Look for search form
            search_form = await page.wait_for_selector(
                self.config.search_form_selector or "form",
                timeout=self.config.wait_timeout_ms
            )

            if not search_form:
                self.logger.error("Could not find search form")
                return None

            # Fill date fields if available
            if self.config.date_from_selector:
                date_from_input = await page.query_selector(self.config.date_from_selector)
                if date_from_input:
                    await date_from_input.fill(start_date.strftime("%m/%d/%Y"))

            if self.config.date_to_selector:
                date_to_input = await page.query_selector(self.config.date_to_selector)
                if date_to_input:
                    await date_to_input.fill(end_date.strftime("%m/%d/%Y"))

            # Submit search
            search_button = await page.query_selector(
                self.config.search_button_selector or "button[type='submit']"
            )

            if search_button:
                await search_button.click()
            else:
                # Try submitting the form directly
                await search_form.evaluate("form => form.submit()")

            # Wait for results
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            # Return page content for processing
            return await page.content()

        except PatchrightTimeoutError as e:
            self.logger.error(f"Timeout during permit search: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error performing permit search: {e}")
            return None

    async def _extract_permits_from_results(
        self,
        page: Page,
        results_html: str,
        max_permits: int
    ) -> List[CountyPermitRecord]:
        """Extract permit records from search results."""
        permits = []

        try:
            soup = BeautifulSoup(results_html, 'html.parser')

            # Find results table
            results_table = soup.select_one(
                self.config.results_table_selector or "table"
            )

            if not results_table:
                self.logger.warning("Could not find results table")
                return permits

            # Extract data from table rows
            rows = results_table.select("tr")[1:]  # Skip header row

            for i, row in enumerate(rows[:max_permits]):
                try:
                    permit_data = await self._extract_permit_from_row(page, row, i)
                    if permit_data:
                        permits.append(permit_data)

                    # Rate limiting
                    await asyncio.sleep(self.config.between_requests_delay_ms / 1000)

                except Exception as e:
                    self.logger.warning(f"Failed to extract permit from row {i}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting permits from results: {e}")

        return permits

    async def _extract_permit_from_row(
        self,
        page: Page,
        row,
        row_index: int
    ) -> Optional[CountyPermitRecord]:
        """Extract permit data from a table row."""
        try:
            cells = row.select("td")
            if len(cells) < 3:  # Ensure minimum data available
                return None

            # Extract basic data from table cells (common patterns)
            permit_number = self._extract_cell_text(cells, 0)
            permit_type_text = self._extract_cell_text(cells, 1) if len(cells) > 1 else ""
            status_text = self._extract_cell_text(cells, 2) if len(cells) > 2 else ""
            project_description = self._extract_cell_text(cells, 3) if len(cells) > 3 else "No description"
            project_address = self._extract_cell_text(cells, 4) if len(cells) > 4 else "No address"
            applicant_name = self._extract_cell_text(cells, 5) if len(cells) > 5 else "Unknown"
            date_text = self._extract_cell_text(cells, 6) if len(cells) > 6 else ""

            # Try to parse application date
            application_date = self._parse_date_from_text(date_text) or datetime.now()

            # Check for detail link and get additional data if available
            detail_link = row.select_one(
                self.config.permit_detail_link_selector or "a"
            )

            additional_data = {}
            if detail_link and detail_link.get('href'):
                additional_data = await self._scrape_permit_details(page, detail_link.get('href'))

            # Create permit record
            permit_data = {
                'permit_number': permit_number or f"UNKNOWN_{row_index}",
                'project_description': project_description,
                'project_address': project_address,
                'applicant_name': applicant_name,
                'application_date': application_date,
                'portal_url': self.config.portal_url,
                **additional_data  # Merge additional data from detail page
            }

            # Create and classify permit
            permit = CountyPermitRecord(**permit_data)
            permit.permit_type = permit.classify_permit_type()
            permit.status = permit.classify_status(status_text)

            return permit

        except Exception as e:
            self.logger.debug(f"Failed to extract permit from row {row_index}: {e}")
            return None

    async def _scrape_permit_details(self, page: Page, detail_url: str) -> Dict[str, Any]:
        """Scrape additional details from permit detail page."""
        additional_data = {}

        try:
            # Navigate to detail page
            full_url = urljoin(self.config.portal_url, detail_url)
            await page.goto(full_url, timeout=self.config.wait_timeout_ms)

            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            # Extract additional fields using configured selectors
            if self.config.field_selectors:
                for field_name, selector in self.config.field_selectors.items():
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            if text and text.strip():
                                additional_data[field_name] = text.strip()
                    except Exception:
                        continue

            # Go back to main results
            await page.go_back()
            await asyncio.sleep(self.config.between_requests_delay_ms / 1000)

        except Exception as e:
            self.logger.debug(f"Failed to scrape permit details from {detail_url}: {e}")

        return additional_data

    def _extract_cell_text(self, cells, index: int) -> str:
        """Extract text from table cell safely."""
        if index < len(cells):
            return cells[index].get_text().strip()
        return ""

    def _parse_date_from_text(self, date_text: str) -> Optional[datetime]:
        """Parse date from various text formats."""
        if not date_text or date_text.strip() == "":
            return None

        # Clean date text
        date_text = date_text.strip()

        # Try common date formats
        formats = [
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%Y-%m-%d",
            "%m/%d/%y",
            "%B %d, %Y",
            "%b %d, %Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        return None

    async def process_response(self, content: bytes, response) -> Any:
        """Process response - not used in Playwright scraper."""
        return content.decode('utf-8', errors='ignore')


async def create_county_permits_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    portal_url: str,
    portal_type: str = "generic",
    **config_kwargs
) -> CountyPermitsScraper:
    """Factory function to create configured county permits scraper."""

    portal_config = PermitPortalConfig(
        portal_url=portal_url,
        portal_type=portal_type,
        **config_kwargs
    )

    scraper = CountyPermitsScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        portal_config=portal_config,
        **config_kwargs
    )

    await scraper.initialize()
    return scraper