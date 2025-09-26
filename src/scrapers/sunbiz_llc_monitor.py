"""
Florida Sunbiz LLC Formation Monitor

Tracks new LLC formations through the Florida Division of Corporations website.
Uses Patchright stealth automation to bypass CloudFlare protection.

Focus: Real estate and development related entities for intelligence gathering.
Target: Property developers, investment LLCs, construction companies.
"""
import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from patchright.async_api import Page, BrowserContext, TimeoutError as PatchrightTimeoutError
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class LLCStatus(Enum):
    """LLC status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISSOLVED = "dissolved"
    WITHDRAWN = "withdrawn"
    MERGED = "merged"
    UNKNOWN = "unknown"


class BusinessType(Enum):
    """Business entity types."""
    LLC = "llc"
    CORPORATION = "corporation"
    LIMITED_PARTNERSHIP = "limited_partnership"
    PARTNERSHIP = "partnership"
    NONPROFIT = "nonprofit"
    OTHER = "other"


class RealEstateRelevance(Enum):
    """Relevance to real estate development."""
    HIGHLY_RELEVANT = "highly_relevant"      # Clear real estate focus
    MODERATELY_RELEVANT = "moderately_relevant"  # Potential real estate connection
    SOMEWHAT_RELEVANT = "somewhat_relevant"  # Indirect connection
    NOT_RELEVANT = "not_relevant"           # No apparent connection


class LLCRecord(BaseModel):
    """Model for LLC formation data from Sunbiz."""
    document_number: str = Field(..., min_length=1)
    entity_name: str = Field(..., min_length=1)
    business_type: BusinessType = BusinessType.LLC
    status: LLCStatus = LLCStatus.UNKNOWN

    # Formation details
    filing_date: datetime
    effective_date: Optional[datetime] = None
    state_of_formation: str = Field(default="FL")

    # Address information
    principal_address: Optional[str] = None
    principal_city: Optional[str] = None
    principal_state: Optional[str] = None
    principal_zip: Optional[str] = None

    mailing_address: Optional[str] = None
    mailing_city: Optional[str] = None
    mailing_state: Optional[str] = None
    mailing_zip: Optional[str] = None

    # Key personnel
    registered_agent_name: Optional[str] = None
    registered_agent_address: Optional[str] = None
    authorized_persons: Optional[List[str]] = None
    officers: Optional[List[Dict[str, str]]] = None

    # Business details
    purpose: Optional[str] = None
    naics_code: Optional[str] = None
    business_classification: Optional[str] = None
    annual_report_due: Optional[datetime] = None

    # Intelligence analysis
    real_estate_relevance: RealEstateRelevance = RealEstateRelevance.NOT_RELEVANT
    relevance_keywords: Optional[List[str]] = None
    potential_development_entity: bool = False

    # Data source
    source_url: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('filing_date', 'effective_date', 'annual_report_due', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
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

    @validator('authorized_persons', 'officers', pre=True)
    def parse_personnel_lists(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle comma-separated lists
            return [person.strip() for person in v.split(',') if person.strip()]
        return v

    def analyze_real_estate_relevance(self) -> RealEstateRelevance:
        """Analyze entity for real estate development relevance."""
        # Combine searchable text
        searchable_text = " ".join([
            self.entity_name.lower(),
            self.purpose.lower() if self.purpose else "",
            self.business_classification.lower() if self.business_classification else "",
            " ".join(self.authorized_persons or []).lower(),
            " ".join([officer.get('name', '') for officer in (self.officers or [])]).lower()
        ])

        # High relevance keywords
        high_relevance_keywords = [
            'real estate', 'realty', 'development', 'developer', 'construction',
            'building', 'property', 'land', 'investment', 'holdings',
            'commercial property', 'residential development', 'construction company',
            'property management', 'real estate investment', 'land development',
            'home builder', 'homebuilder', 'apartment', 'condo', 'condominium',
            'shopping center', 'plaza', 'office building', 'warehouse development'
        ]

        # Moderate relevance keywords
        moderate_relevance_keywords = [
            'equity', 'capital', 'ventures', 'group', 'partners', 'holdings',
            'acquisition', 'asset', 'finance', 'funding', 'mortgage',
            'title company', 'closing', 'escrow', 'appraisal',
            'contracting', 'engineering', 'architecture', 'planning'
        ]

        # Some relevance keywords
        some_relevance_keywords = [
            'llc', 'company', 'corp', 'inc', 'enterprises', 'solutions',
            'services', 'management', 'consulting', 'advisory'
        ]

        found_keywords = []

        # Check for high relevance keywords
        high_matches = sum(1 for keyword in high_relevance_keywords
                          if keyword in searchable_text)
        if high_matches > 0:
            found_keywords.extend([kw for kw in high_relevance_keywords if kw in searchable_text])

        # Check for moderate relevance keywords
        moderate_matches = sum(1 for keyword in moderate_relevance_keywords
                              if keyword in searchable_text)
        if moderate_matches > 0:
            found_keywords.extend([kw for kw in moderate_relevance_keywords if kw in searchable_text])

        # Check for some relevance keywords
        some_matches = sum(1 for keyword in some_relevance_keywords
                          if keyword in searchable_text)

        # Store found keywords
        self.relevance_keywords = list(set(found_keywords)) if found_keywords else None

        # Determine relevance level
        if high_matches >= 2 or (high_matches >= 1 and moderate_matches >= 1):
            self.potential_development_entity = True
            return RealEstateRelevance.HIGHLY_RELEVANT
        elif high_matches >= 1 or moderate_matches >= 2:
            return RealEstateRelevance.MODERATELY_RELEVANT
        elif moderate_matches >= 1 or some_matches >= 2:
            return RealEstateRelevance.SOMEWHAT_RELEVANT
        else:
            return RealEstateRelevance.NOT_RELEVANT

    def classify_business_type(self, entity_type_text: str) -> BusinessType:
        """Classify business type from entity type text."""
        entity_type_lower = entity_type_text.lower()

        if 'llc' in entity_type_lower or 'limited liability' in entity_type_lower:
            return BusinessType.LLC
        elif any(word in entity_type_lower for word in ['corp', 'corporation', 'inc']):
            return BusinessType.CORPORATION
        elif 'limited partnership' in entity_type_lower or 'lp' in entity_type_lower:
            return BusinessType.LIMITED_PARTNERSHIP
        elif 'partnership' in entity_type_lower:
            return BusinessType.PARTNERSHIP
        elif 'nonprofit' in entity_type_lower or 'non-profit' in entity_type_lower:
            return BusinessType.NONPROFIT
        else:
            return BusinessType.OTHER

    def classify_status(self, status_text: str) -> LLCStatus:
        """Classify LLC status from text."""
        status_lower = status_text.lower()

        if 'active' in status_lower:
            return LLCStatus.ACTIVE
        elif 'inactive' in status_lower:
            return LLCStatus.INACTIVE
        elif 'dissolved' in status_lower or 'dissolution' in status_lower:
            return LLCStatus.DISSOLVED
        elif 'withdrawn' in status_lower:
            return LLCStatus.WITHDRAWN
        elif 'merged' in status_lower or 'merger' in status_lower:
            return LLCStatus.MERGED
        else:
            return LLCStatus.UNKNOWN


class SunbizSearchConfig(BaseModel):
    """Configuration for Sunbiz LLC searches."""
    base_url: str = Field(..., min_length=1)

    # Search parameters
    entity_types: List[str] = Field(default=["LLC", "CORP"])
    search_by_date: bool = Field(default=True)
    max_results_per_search: int = Field(default=500)

    # Browser automation settings
    headless: bool = Field(default=True)
    timeout_ms: int = Field(default=30000, ge=5000, le=120000)
    page_load_delay_ms: int = Field(default=3000, ge=1000, le=10000)
    between_searches_delay_ms: int = Field(default=2000, ge=500, le=10000)

    # Relevance filtering
    min_relevance_level: RealEstateRelevance = RealEstateRelevance.SOMEWHAT_RELEVANT
    focus_on_new_formations: bool = Field(default=True)
    max_days_back: int = Field(default=30, ge=1, le=365)

    # Portal-specific selectors (configurable, not hardcoded)
    search_form_selector: Optional[str] = None
    entity_name_input_selector: Optional[str] = None
    filing_date_from_selector: Optional[str] = None
    filing_date_to_selector: Optional[str] = None
    entity_type_selector: Optional[str] = None
    search_button_selector: Optional[str] = None
    results_table_selector: Optional[str] = None
    detail_link_selector: Optional[str] = None
    next_page_selector: Optional[str] = None


class SunbizLLCMonitor(ResilientScraper):
    """
    Monitor for new LLC formations in Florida through the Sunbiz portal.

    Focuses on entities relevant to real estate development and investment.
    Uses browser automation to handle the complex search interface.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        search_config: SunbizSearchConfig,
        **kwargs
    ):
        super().__init__(
            scraper_id="sunbiz_llc_monitor",
            scraper_type=ScraperType.WEB,
            enable_js=True,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.config = search_config

        # Default selectors (can be overridden by config)
        self.default_selectors = {
            'search_form_selector': 'form[name="searchForm"], #searchForm, .search-form',
            'entity_name_input_selector': 'input[name*="name"], input[id*="name"], #EntityName',
            'filing_date_from_selector': 'input[name*="from"], input[name*="start"], #FilingDateFrom',
            'filing_date_to_selector': 'input[name*="to"], input[name*="end"], #FilingDateTo',
            'entity_type_selector': 'select[name*="type"], select[id*="type"], #EntityType',
            'search_button_selector': 'input[type="submit"], button[type="submit"], #searchButton',
            'results_table_selector': 'table, .results-table, #searchResults',
            'detail_link_selector': 'a[href*="detail"], a[href*="entity"], .entity-link',
            'next_page_selector': 'a[href*="next"], .next, .pagination-next'
        }

        # Apply default selectors where not configured
        for key, default_value in self.default_selectors.items():
            if not getattr(self.config, key):
                setattr(self.config, key, default_value)

        self.context: Optional[BrowserContext] = None

    async def monitor_new_llc_formations(
        self,
        days_back: int = 7
    ) -> List[LLCRecord]:
        """
        Monitor for new LLC formations in the specified time period.

        Args:
            days_back: Number of days to look back for new formations
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.search_llc_formations(
            start_date=start_date,
            end_date=end_date
        )

    async def search_llc_formations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entity_name_keywords: Optional[List[str]] = None
    ) -> List[LLCRecord]:
        """
        Search for LLC formations with specified criteria.

        Args:
            start_date: Start date for filing date search
            end_date: End date for filing date search
            entity_name_keywords: Keywords to search in entity names
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=self.config.max_days_back)
        if not end_date:
            end_date = datetime.now()

        llc_records = []

        try:
            # Create browser context
            self.context = await self.browser.new_context(
                user_agent=self.user_agent.random,
                viewport={'width': 1920, 'height': 1080}
            )

            page = await self.context.new_page()

            self.logger.info(f"Navigating to Sunbiz portal: {self.config.base_url}")

            # Navigate to search page
            await page.goto(self.config.base_url,
                           wait_until='networkidle',
                           timeout=self.config.timeout_ms)

            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            # Perform searches for each entity type
            for entity_type in self.config.entity_types:
                try:
                    records = await self._search_by_entity_type(
                        page, entity_type, start_date, end_date, entity_name_keywords
                    )
                    llc_records.extend(records)

                    # Rate limiting between searches
                    await asyncio.sleep(self.config.between_searches_delay_ms / 1000)

                except Exception as e:
                    self.logger.error(f"Failed to search for {entity_type}: {e}")
                    continue

            # Filter by relevance
            relevant_records = []
            for record in llc_records:
                record.real_estate_relevance = record.analyze_real_estate_relevance()

                # Only keep records above minimum relevance threshold
                relevance_levels = [
                    RealEstateRelevance.NOT_RELEVANT,
                    RealEstateRelevance.SOMEWHAT_RELEVANT,
                    RealEstateRelevance.MODERATELY_RELEVANT,
                    RealEstateRelevance.HIGHLY_RELEVANT
                ]

                min_index = relevance_levels.index(self.config.min_relevance_level)
                record_index = relevance_levels.index(record.real_estate_relevance)

                if record_index >= min_index:
                    relevant_records.append(record)

            self.logger.info(f"Found {len(relevant_records)} relevant LLC formations out of {len(llc_records)} total")

        except Exception as e:
            self.logger.error(f"Failed to search LLC formations: {e}")

        finally:
            if self.context:
                await self.context.close()
                self.context = None

        return relevant_records

    async def check_for_new_formations(self) -> List[LLCRecord]:
        """Check for new formations since last scrape using change detection."""
        # Check for changes in the portal
        change_result = await self.change_detector.track_content_change(
            url=self.config.base_url,
            content=b"",
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        if change_result.change_type.value == "unchanged":
            self.logger.debug("No changes detected in Sunbiz portal")
            return []

        # Get formations from last 24 hours
        return await self.monitor_new_llc_formations(days_back=1)

    async def store_llc_records(self, records: List[LLCRecord]) -> int:
        """Store LLC records in database."""
        if not records:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for record in records:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "llc_data": record.dict(),
                        "scraped_from": "florida_sunbiz_portal",
                        "scraper_version": "1.0",
                        "processing_notes": {
                            "data_quality": "official_state_corporation_data",
                            "confidence": 0.95,
                            "source_type": "llc_formation",
                            "business_type": record.business_type.value,
                            "real_estate_relevance": record.real_estate_relevance.value,
                            "potential_development_entity": record.potential_development_entity,
                            "relevance_keywords_count": len(record.relevance_keywords or [])
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
                        "llc_formation",
                        record.source_url,
                        datetime.utcnow(),
                        "sunbiz_llc_v1.0",
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
                            "llc_formation",
                            json.dumps(record.dict(), default=str),
                            0.95  # High confidence for official state data
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store LLC record {record.document_number}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new LLC formation records")
        return stored_count

    async def get_llc_formation_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics about recent LLC formations."""
        async with self.db_manager.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Formations by relevance and business type
            query = """
                SELECT
                    (structured_data->>'real_estate_relevance')::text as relevance,
                    (structured_data->>'business_type')::text as business_type,
                    COUNT(*) as count,
                    COUNT(*) FILTER (WHERE (structured_data->>'potential_development_entity')::boolean = true) as development_entities
                FROM structured_facts sf
                JOIN raw_facts rf ON sf.raw_fact_id = rf.id
                WHERE sf.entity_type = 'llc_formation'
                AND rf.fact_type = 'llc_formation'
                AND rf.scraped_at >= $1
                GROUP BY relevance, business_type
                ORDER BY count DESC
            """

            result = await session.execute(query, cutoff_date)
            formation_stats = {}

            total_formations = 0
            development_entities = 0

            for row in await result.fetchall():
                relevance = row['relevance']
                business_type = row['business_type']
                count = row['count']
                dev_count = row['development_entities']

                if relevance not in formation_stats:
                    formation_stats[relevance] = {}

                formation_stats[relevance][business_type] = {
                    'count': count,
                    'development_entities': dev_count
                }

                total_formations += count
                development_entities += dev_count

            return {
                'formation_breakdown': formation_stats,
                'total_formations': total_formations,
                'total_development_entities': development_entities,
                'period_days': days
            }

    async def _search_by_entity_type(
        self,
        page: Page,
        entity_type: str,
        start_date: datetime,
        end_date: datetime,
        entity_name_keywords: Optional[List[str]] = None
    ) -> List[LLCRecord]:
        """Perform search for specific entity type."""
        records = []

        try:
            self.logger.info(f"Searching for {entity_type} formations from {start_date.date()} to {end_date.date()}")

            # Fill search form
            await self._fill_search_form(page, entity_type, start_date, end_date, entity_name_keywords)

            # Submit search and process results
            search_results = await self._submit_search_and_get_results(page)

            if search_results:
                records = await self._extract_llc_records_from_results(page, search_results)

        except Exception as e:
            self.logger.error(f"Failed to search for {entity_type}: {e}")

        return records

    async def _fill_search_form(
        self,
        page: Page,
        entity_type: str,
        start_date: datetime,
        end_date: datetime,
        entity_name_keywords: Optional[List[str]] = None
    ) -> None:
        """Fill out the search form."""
        try:
            # Wait for search form
            await page.wait_for_selector(
                self.config.search_form_selector,
                timeout=self.config.timeout_ms
            )

            # Fill entity type if selector available
            if self.config.entity_type_selector:
                try:
                    await page.select_option(self.config.entity_type_selector, entity_type)
                except Exception as e:
                    self.logger.debug(f"Could not select entity type: {e}")

            # Fill date range if selectors available
            if self.config.filing_date_from_selector:
                try:
                    from_input = await page.query_selector(self.config.filing_date_from_selector)
                    if from_input:
                        await from_input.fill(start_date.strftime("%m/%d/%Y"))
                except Exception as e:
                    self.logger.debug(f"Could not fill start date: {e}")

            if self.config.filing_date_to_selector:
                try:
                    to_input = await page.query_selector(self.config.filing_date_to_selector)
                    if to_input:
                        await to_input.fill(end_date.strftime("%m/%d/%Y"))
                except Exception as e:
                    self.logger.debug(f"Could not fill end date: {e}")

            # Fill entity name keywords if provided and selector available
            if entity_name_keywords and self.config.entity_name_input_selector:
                try:
                    name_input = await page.query_selector(self.config.entity_name_input_selector)
                    if name_input:
                        # Use first keyword for search
                        await name_input.fill(entity_name_keywords[0])
                except Exception as e:
                    self.logger.debug(f"Could not fill entity name: {e}")

        except Exception as e:
            self.logger.error(f"Failed to fill search form: {e}")

    async def _submit_search_and_get_results(self, page: Page) -> Optional[str]:
        """Submit search form and return results HTML."""
        try:
            # Submit search
            search_button = await page.query_selector(self.config.search_button_selector)
            if search_button:
                await search_button.click()
            else:
                # Try submitting form directly
                form = await page.query_selector(self.config.search_form_selector)
                if form:
                    await form.evaluate("form => form.submit()")

            # Wait for results
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            return await page.content()

        except PatchrightTimeoutError as e:
            self.logger.error(f"Timeout waiting for search results: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error submitting search: {e}")
            return None

    async def _extract_llc_records_from_results(
        self,
        page: Page,
        results_html: str
    ) -> List[LLCRecord]:
        """Extract LLC records from search results."""
        records = []

        try:
            soup = BeautifulSoup(results_html, 'html.parser')

            # Find results table
            results_table = soup.select_one(self.config.results_table_selector)
            if not results_table:
                self.logger.warning("Could not find results table")
                return records

            # Extract data from table rows
            rows = results_table.select("tr")[1:]  # Skip header row

            for i, row in enumerate(rows[:self.config.max_results_per_search]):
                try:
                    record = await self._extract_llc_from_row(page, row, i)
                    if record:
                        records.append(record)

                except Exception as e:
                    self.logger.debug(f"Failed to extract LLC from row {i}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting LLC records: {e}")

        return records

    async def _extract_llc_from_row(
        self,
        page: Page,
        row,
        row_index: int
    ) -> Optional[LLCRecord]:
        """Extract LLC data from a table row."""
        try:
            cells = row.select("td")
            if len(cells) < 3:
                return None

            # Extract basic data from table cells (adjust indices based on actual table structure)
            document_number = self._extract_cell_text(cells, 0)
            entity_name = self._extract_cell_text(cells, 1)
            status_text = self._extract_cell_text(cells, 2)
            filing_date_text = self._extract_cell_text(cells, 3) if len(cells) > 3 else ""

            if not document_number or not entity_name:
                return None

            # Parse filing date
            filing_date = self._parse_date_from_text(filing_date_text) or datetime.now()

            # Check for detail link
            detail_link = row.select_one(self.config.detail_link_selector)
            additional_data = {}

            if detail_link and detail_link.get('href'):
                additional_data = await self._scrape_entity_details(page, detail_link.get('href'))

            # Create LLC record
            llc_data = {
                'document_number': document_number,
                'entity_name': entity_name,
                'filing_date': filing_date,
                'source_url': self.config.base_url,
                **additional_data
            }

            # Create and classify LLC record
            llc_record = LLCRecord(**llc_data)
            llc_record.status = llc_record.classify_status(status_text)

            # Determine business type from entity name
            llc_record.business_type = llc_record.classify_business_type(entity_name)

            return llc_record

        except Exception as e:
            self.logger.debug(f"Failed to extract LLC from row {row_index}: {e}")
            return None

    async def _scrape_entity_details(self, page: Page, detail_url: str) -> Dict[str, Any]:
        """Scrape additional details from entity detail page."""
        additional_data = {}

        try:
            # Navigate to detail page
            full_url = urljoin(self.config.base_url, detail_url)
            await page.goto(full_url, timeout=self.config.timeout_ms)
            await asyncio.sleep(self.config.page_load_delay_ms / 1000)

            # Extract additional details from page
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract common fields (adapt selectors based on actual site structure)
            field_selectors = {
                'principal_address': '.address, .principal-address, td:contains("Principal Address") + td',
                'registered_agent_name': '.agent, .registered-agent, td:contains("Registered Agent") + td',
                'purpose': '.purpose, .business-purpose, td:contains("Purpose") + td',
                'effective_date': '.effective-date, td:contains("Effective Date") + td'
            }

            for field_name, selector in field_selectors.items():
                try:
                    element = soup.select_one(selector)
                    if element:
                        text = element.get_text().strip()
                        if text:
                            additional_data[field_name] = text
                except Exception:
                    continue

            # Go back to search results
            await page.go_back()
            await asyncio.sleep(self.config.between_searches_delay_ms / 1000)

        except Exception as e:
            self.logger.debug(f"Failed to scrape entity details from {detail_url}: {e}")

        return additional_data

    def _extract_cell_text(self, cells, index: int) -> str:
        """Extract text from table cell safely."""
        if index < len(cells):
            return cells[index].get_text().strip()
        return ""

    def _parse_date_from_text(self, date_text: str) -> Optional[datetime]:
        """Parse date from text."""
        if not date_text or date_text.strip() == "":
            return None

        date_text = date_text.strip()

        formats = [
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%Y-%m-%d",
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


async def create_sunbiz_llc_monitor(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    sunbiz_base_url: str,
    entity_types: Optional[List[str]] = None,
    min_relevance_level: RealEstateRelevance = RealEstateRelevance.SOMEWHAT_RELEVANT,
    **config_kwargs
) -> SunbizLLCMonitor:
    """Factory function to create configured Sunbiz LLC monitor."""

    search_config = SunbizSearchConfig(
        base_url=sunbiz_base_url,
        entity_types=entity_types or ["LLC", "CORP"],
        min_relevance_level=min_relevance_level,
        **config_kwargs
    )

    scraper = SunbizLLCMonitor(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        search_config=search_config,
        **config_kwargs
    )

    await scraper.initialize()
    return scraper