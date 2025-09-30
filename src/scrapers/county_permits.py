"""
Alachua County Permits Scraper (via CitizenServe Portal)

Provides real-time permit data for Alachua County (outside Gainesville city limits).
Uses CitizenServe portal with browser automation to bypass reCAPTCHA v3.

Coverage: Building, Electrical, Plumbing, Mechanical, Zoning, Subdivision permits
Jurisdiction: Alachua County (outside Gainesville city limits)

Report Types:
- Applied (ID 359): Permits applied for during date range
- Issued (ID 360): Permits issued during date range
- Closed (ID 379): Permits closed/completed during date range
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

import pandas as pd
import structlog
from pydantic import BaseModel, Field, validator

# Patchright for undetected browser automation
from patchright.async_api import async_playwright

# Add BypassV3 to path for reCAPTCHA bypassing
sys.path.append(str(Path(__file__).parent / "BypassV3"))
from bypass import ReCaptchaV3Bypass

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector

logger = structlog.get_logger("dominion.scrapers.county_permits")


class CountyReportType(Enum):
    """Available county permit report types."""
    APPLIED = {"id": 359, "name": "Permits Applied For", "description": "Applications submitted"}
    ISSUED = {"id": 360, "name": "Permits Issued", "description": "Permits approved and active"}
    CLOSED = {"id": 379, "name": "Permits Closed", "description": "Permits completed/closed"}


class CountyPermitRecord(BaseModel):
    """Model for CitizenServe county permit data."""
    permit_number: str = Field(..., min_length=1)
    permit_type: str
    sub_type: Optional[str] = None
    address: str
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    parcel_number: Optional[str] = None
    jurisdiction: Optional[str] = None
    description: str
    classification: Optional[str] = None
    status: Optional[str] = None
    applicant: Optional[str] = None
    contractor: Optional[str] = None
    contractor_address: Optional[str] = None
    contractor_phone: Optional[str] = None
    application_date: datetime
    issue_date: Optional[datetime] = None
    approval_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    construction_cost: Optional[float] = None
    valuation: Optional[float] = None
    report_type: str  # applied, issued, or closed

    @validator('application_date', 'issue_date', 'approval_date', 'expiration_date', 'close_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "" or pd.isna(v):
            return None
        if isinstance(v, str):
            # Handle multiple date formats from CitizenServe
            for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('construction_cost', 'valuation', pre=True)
    def parse_cost(cls, v):
        if v is None or v == "" or pd.isna(v):
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class CountyPermitsScraper(ResilientScraper):
    """
    Alachua County permits scraper using CitizenServe portal.
    Provides real-time permit data with stealth automation via Patchright.
    Handles 3 report types: Applied, Issued, and Closed permits.
    """

    def __init__(self,
                 download_dir: Optional[str] = None,
                 db_manager: Optional[DatabaseManager] = None,
                 change_detector: Optional[ChangeDetector] = None):
        super().__init__(
            scraper_type=ScraperType.WEB,
            name="county_permits",
            base_url="https://www6.citizenserve.com"
        )

        self.download_dir = Path(download_dir or os.getenv('DOWNLOAD_DIR', './downloads'))
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Configuration from environment
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        self.timeout = int(os.getenv('TIMEOUT', '30000'))

        # County-specific reCAPTCHA anchor URL (www6 instead of www4)
        self.recaptcha_anchor_url = (
            'https://www.google.com/recaptcha/api2/anchor?ar=1&k='
            '6LeKdrMZAAAAAHhaf46zpFeRsB-VLv8kRAqKVrEW&co=aHR0cHM6Ly93d3c2'
            'LmNpdGl6ZW5zZXJ2ZS5jb206NDQz&hl=en&v=1aEzDFnIBfL6Zd_MU9G3Luhj'
            '&size=invisible&cb=123456789'
        )

        self.db_manager = db_manager
        self.change_detector = change_detector or ChangeDetector("county_permits")

        logger.info("County permits scraper initialized", download_dir=str(self.download_dir))

    async def _get_recaptcha_token(self) -> str:
        """Generate reCAPTCHA v3 token using BypassV3."""
        try:
            logger.info("Generating reCAPTCHA token...")
            # Run in executor since BypassV3 is synchronous
            loop = asyncio.get_event_loop()
            bypass = ReCaptchaV3Bypass(self.recaptcha_anchor_url)
            token = await loop.run_in_executor(None, bypass.bypass)

            if not token:
                raise ValueError("Failed to generate reCAPTCHA token")

            logger.info("reCAPTCHA token generated successfully")
            return token

        except Exception as e:
            logger.error("reCAPTCHA token generation failed", error=str(e))
            raise

    async def scrape_permits_data(
        self,
        start_date: str,
        end_date: str,
        report_type: CountyReportType = CountyReportType.ISSUED
    ) -> ScrapingResult:
        """
        Scrape county permits for date range using Playwright stealth automation.

        Args:
            start_date: Start date in MM/DD/YYYY format
            end_date: End date in MM/DD/YYYY format
            report_type: Which report to scrape (APPLIED, ISSUED, or CLOSED)

        Returns:
            ScrapingResult with permit data or error information
        """
        start_time = datetime.utcnow()
        report_id = report_type.value["id"]
        report_name = report_type.value["name"]

        try:
            logger.info(
                "Starting county permit scrape",
                start_date=start_date,
                end_date=end_date,
                report_type=report_name
            )

            # Get reCAPTCHA token
            token = await self._get_recaptcha_token()

            # Use patchright for stealth scraping
            async with async_playwright() as playwright:
                # Launch browser with stealth configuration
                browser = await playwright.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )

                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    accept_downloads=True
                )

                context.set_default_timeout(self.timeout)

                try:
                    page = await context.new_page()

                    # Navigate to county reports page (Installation ID 318 for county)
                    logger.info("Navigating to CitizenServe reports page...")
                    await page.goto(
                        "https://www6.citizenserve.com/Portal/PortalController?"
                        "Action=showPortalReports&ctzPagePrefix=Portal_&installationID=318"
                        "&original_iid=0&original_contactID=0"
                    )
                    await page.wait_for_load_state("networkidle")

                    # Click report using XPath (text selector would match wrong report)
                    # Cannot use "Permits Issued" text because it matches "Permits Issued Map" (767)
                    logger.info(f"Selecting report: {report_name} (ID {report_id})...")
                    report_link = await page.wait_for_selector(
                        f"xpath=//a[contains(@href, 'getQuery({report_id}')]",
                        timeout=10000
                    )
                    await report_link.click()
                    logger.info(f"Clicked {report_name} link")

                    # Wait for form to load
                    await page.wait_for_load_state("networkidle")

                    # Verify form is present
                    form = await page.wait_for_selector("#Frm_QueryTool", timeout=10000)
                    if not form:
                        raise Exception("Could not find permit query form")

                    logger.info("Form loaded successfully with valid session")

                    # Fill form fields
                    logger.info("Filling form fields...")

                    # From Date (Param_0 for county, different from city which uses Param_1)
                    param0 = await page.wait_for_selector("input[name='Param_0']")
                    await param0.fill("")
                    await param0.fill(start_date)
                    logger.info(f"Set From Date: {start_date}")

                    # To Date (Param_1 for county, different from city which uses Param_2)
                    param1 = await page.wait_for_selector("input[name='Param_1']")
                    await param1.fill("")
                    await param1.fill(end_date)
                    logger.info(f"Set To Date: {end_date}")

                    # Permit Type is optional (Param_2) - leave blank for all types

                    # Handle human verification checkbox
                    try:
                        human_checkbox = await page.wait_for_selector("#noparam-checkbox", timeout=5000)
                        if not await human_checkbox.is_checked():
                            await human_checkbox.check()
                            logger.info("Checked 'I am human' checkbox")
                    except:
                        logger.info("Human checkbox not found - may not be required")

                    # Set reCAPTCHA token as fallback
                    try:
                        recaptcha_field = await page.wait_for_selector(
                            "input[name='g-recaptcha-response']",
                            timeout=5000
                        )
                        await page.evaluate(f"arguments[0].value = '{token}';", recaptcha_field)
                        logger.info("reCAPTCHA token set (fallback)")
                    except:
                        logger.info("reCAPTCHA field not found - using human checkbox instead")

                    # Submit form
                    logger.info("Submitting permit query...")
                    try:
                        submit_link = await page.wait_for_selector("#submitLink", timeout=5000)
                        await submit_link.click()
                        logger.info("Clicked Submit link")
                    except:
                        try:
                            await page.evaluate("runQuery();")
                            logger.info("Used JavaScript runQuery() function")
                        except:
                            form = await page.wait_for_selector("#Frm_QueryTool")
                            await form.evaluate("form => form.submit()")
                            logger.info("Used form.submit() as last resort")

                    # Wait for results
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(2000)  # Small delay for dynamic content

                    # Check if results loaded (county permit patterns)
                    page_text = await page.text_content("body")
                    has_permits = any(pattern in page_text for pattern in [
                        'BLD', 'ELE', 'PLU', 'MEC',  # County permit prefixes
                        'Permit', 'Application'       # Generic indicators
                    ])

                    if not has_permits:
                        logger.warning("No permit data found for date range")
                        return ScrapingResult(
                            success=True,
                            data=[],
                            response_time=(datetime.utcnow() - start_time).total_seconds()
                        )

                    logger.info("SUCCESS! Permit data found in results!")

                    # Wait for export button and download
                    logger.info("Waiting for export button...")
                    export_icon = await page.wait_for_selector(
                        "i.icon-external-link[title='Export']",
                        timeout=self.timeout
                    )

                    if not export_icon:
                        raise Exception("Export button not found")

                    # Download Excel file
                    async with page.expect_download() as download_info:
                        logger.info("Clicking export button...")
                        await export_icon.click()

                    download = await download_info.value
                    report_type_str = report_type.name.lower()
                    excel_filename = f"county_permits_{report_type_str}_{start_date.replace('/', '')}_{end_date.replace('/', '')}.xlsx"
                    excel_path = self.download_dir / excel_filename

                    await download.save_as(str(excel_path))
                    logger.info("Excel file downloaded", filename=excel_filename)

                    # Process Excel data
                    logger.info("Processing Excel data...")
                    df = pd.read_excel(str(excel_path))

                    # Convert to permit records
                    permits = []
                    for _, row in df.iterrows():
                        try:
                            # Map actual Excel column names to model fields
                            permit_data = {
                                'permit_number': str(row.get('Permit#', '')),
                                'permit_type': str(row.get('Permit Type', '')),
                                'sub_type': str(row.get('Sub Type', '')) if pd.notna(row.get('Sub Type')) else None,
                                'address': str(row.get('Address', '')),
                                'address_city': str(row.get('Address(City)', '')) if pd.notna(row.get('Address(City)')) else None,
                                'address_zip': str(row.get('Address(ZIP)', '')) if pd.notna(row.get('Address(ZIP)')) else None,
                                'parcel_number': str(row.get('Parcel#', '')) if pd.notna(row.get('Parcel#')) else None,
                                'jurisdiction': str(row.get('Jurisdiction', '')) if pd.notna(row.get('Jurisdiction')) else None,
                                'description': str(row.get('Work Description', '')) if pd.notna(row.get('Work Description')) else '',
                                'classification': str(row.get('Classification', '')) if pd.notna(row.get('Classification')) else None,
                                'status': str(row.get('Status', '')) if pd.notna(row.get('Status')) else None,
                                'applicant': str(row.get('Applicant Company Name', '')) if pd.notna(row.get('Applicant Company Name')) else None,
                                'contractor': str(row.get('Contractor Name', '')) if pd.notna(row.get('Contractor Name')) else None,
                                'contractor_address': str(row.get('Contractor Address', '')) if pd.notna(row.get('Contractor Address')) else None,
                                'contractor_phone': str(row.get('Contractor Phone #', '')) if pd.notna(row.get('Contractor Phone #')) else None,
                                'application_date': row.get('Application Date'),
                                'issue_date': row.get('Issue Date'),
                                'approval_date': row.get('Approval Date'),
                                'expiration_date': row.get('Expiration Date'),
                                'close_date': row.get('Close Date'),
                                'construction_cost': row.get('Estimated cost of construction'),
                                'valuation': row.get('Valuation'),
                                'report_type': report_type_str
                            }

                            permit = CountyPermitRecord(**permit_data)
                            permits.append(permit.dict())
                        except Exception as e:
                            logger.warning(f"Failed to parse permit row: {e}", row_data=row.to_dict())
                            continue

                    # Calculate content hash for change detection
                    content_hash = self.change_detector.calculate_hash(permits)

                    response_time = (datetime.utcnow() - start_time).total_seconds()

                    logger.info(
                        "Scraping completed successfully",
                        total_permits=len(permits),
                        report_type=report_name,
                        response_time=response_time
                    )

                    return ScrapingResult(
                        success=True,
                        data=permits,
                        content_hash=content_hash,
                        response_time=response_time
                    )

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            logger.error("County permit scraping failed", error=str(e), exc_info=True)
            return ScrapingResult(
                success=False,
                error=str(e),
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )

    async def scrape_all_reports(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, ScrapingResult]:
        """
        Scrape all 3 report types for comprehensive permit intelligence.

        Returns:
            Dictionary with keys: 'applied', 'issued', 'closed'
        """
        logger.info("Scraping all county report types...")

        results = {}

        # Scrape each report type
        for report_type in CountyReportType:
            logger.info(f"Scraping {report_type.name} report...")
            result = await self.scrape_permits_data(start_date, end_date, report_type)
            results[report_type.name.lower()] = result

            # Small delay between reports to avoid rate limiting
            await asyncio.sleep(2)

        total_permits = sum(
            len(result.data) if result.success else 0
            for result in results.values()
        )

        logger.info(
            "All county reports scraped",
            total_permits=total_permits,
            applied=len(results['applied'].data) if results['applied'].success else 0,
            issued=len(results['issued'].data) if results['issued'].success else 0,
            closed=len(results['closed'].data) if results['closed'].success else 0
        )

        return results

    async def scrape_all_reports_deduplicated(
        self,
        start_date: str,
        end_date: str
    ) -> ScrapingResult:
        """
        Scrape all 3 report types and return deduplicated unique permits.

        Deduplication strategy:
        - Permits can appear in multiple reports as they move through lifecycle
        - Keep the record with most advanced status: Closed > Issued > Applied
        - This gives the current status of each unique permit

        Returns:
            Single ScrapingResult with deduplicated data
        """
        logger.info("Scraping all county reports with deduplication...")

        # Scrape all reports
        results = await self.scrape_all_reports(start_date, end_date)

        # Combine all data
        all_permits = []
        for report_name, result in results.items():
            if result.success:
                all_permits.extend(result.data)

        if not all_permits:
            return ScrapingResult(
                success=False,
                data=[],
                error="No permits found in any report",
                response_time=0.0
            )

        # Convert to DataFrame for deduplication
        df = pd.DataFrame(all_permits)

        raw_count = len(df)
        logger.info(f"Combined raw permits: {raw_count}")

        # Add priority for deduplication (Closed > Issued > Applied)
        status_priority = {'closed': 3, 'issued': 2, 'applied': 1}
        df['_priority'] = df['report_type'].map(status_priority)

        # Keep record with highest priority (most advanced status)
        df_deduplicated = df.sort_values('_priority', ascending=False).drop_duplicates(
            subset=['permit_number'],
            keep='first'
        )

        # Remove priority column
        df_deduplicated = df_deduplicated.drop(columns=['_priority'])

        unique_count = len(df_deduplicated)
        duplicates_removed = raw_count - unique_count

        logger.info(
            "Deduplication complete",
            raw_count=raw_count,
            unique_count=unique_count,
            duplicates_removed=duplicates_removed
        )

        # Convert back to dict list
        deduplicated_permits = df_deduplicated.to_dict('records')

        return ScrapingResult(
            success=True,
            data=deduplicated_permits,
            response_time=sum(r.response_time for r in results.values())
        )

    async def scrape_today(self, report_type: CountyReportType = CountyReportType.ISSUED) -> ScrapingResult:
        """Convenience method to scrape today's permits."""
        today = datetime.now().strftime("%m/%d/%Y")
        return await self.scrape_permits_data(today, today, report_type)

    async def scrape_date_range(
        self,
        days_back: int = 7,
        report_type: CountyReportType = CountyReportType.ISSUED
    ) -> ScrapingResult:
        """Convenience method to scrape permits for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.scrape_permits_data(
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y"),
            report_type
        )

    async def run_continuous_monitoring(self) -> None:
        """Run continuous monitoring for new county permits."""
        logger.info("Starting continuous county permit monitoring...")

        while True:
            try:
                # Scrape issued permits (most important for tracking active projects)
                result = await self.scrape_today(CountyReportType.ISSUED)

                if result.success and result.data:
                    # Check for changes
                    has_changes = await self.change_detector.has_changes(result.content_hash)

                    if has_changes:
                        logger.info("New county permits detected!", count=len(result.data))

                        # Store in database if available
                        if self.db_manager:
                            await self._store_permits(result.data)

                        # Update change detector
                        await self.change_detector.update_hash(result.content_hash)
                    else:
                        logger.info("No new county permits since last check")
                else:
                    logger.warning("Failed to scrape county permits or no data found")

                # Wait 2 hours before next check
                await asyncio.sleep(2 * 60 * 60)

            except Exception as e:
                logger.error("Error in continuous monitoring", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _store_permits(self, permits: List[Dict[str, Any]]) -> None:
        """Store permits in database."""
        if not self.db_manager:
            return

        try:
            logger.info("Storing county permits in database", count=len(permits))
            # Implementation depends on database schema
            # await self.db_manager.store_permits(permits)
        except Exception as e:
            logger.error("Failed to store county permits in database", error=str(e))


async def create_county_permits_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    download_dir: Optional[str] = None,
    **kwargs
) -> CountyPermitsScraper:
    """Factory function to create configured county permits scraper."""
    scraper = CountyPermitsScraper(
        download_dir=download_dir,
        db_manager=db_manager,
        change_detector=change_detector,
        **kwargs
    )
    return scraper