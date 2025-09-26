"""
City of Gainesville Permits Scraper (via CitizenServe Portal)

Provides real-time permit data for Gainesville city limits.
Replaces the stale 2023 city API with live CitizenServe portal scraping.

Coverage: Building, Electrical, Fire, Gas, Mechanical, Plumbing, Roofing, Site Work permits
Jurisdiction: City of Gainesville only (Alachua County permits in separate scraper)
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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

logger = structlog.get_logger("dominion.scrapers.city_permits")


class PermitRecord(BaseModel):
    """Model for CitizenServe permit data."""
    permit_number: str = Field(..., min_length=1)
    permit_type: str
    sub_type: Optional[str] = None
    address: str
    parcel_number: Optional[str] = None
    description: str
    classification: Optional[str] = None
    contractor: Optional[str] = None
    application_date: datetime
    issue_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    construction_cost: Optional[float] = None

    @validator('application_date', 'issue_date', 'expiration_date', 'close_date', pre=True)
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

    @validator('construction_cost', pre=True)
    def parse_cost(cls, v):
        if v is None or v == "" or pd.isna(v):
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class CityPermitsScraper(ResilientScraper):
    """
    City of Gainesville permits scraper using CitizenServe portal.
    Provides real-time permit data with stealth automation via Patchright.
    Replaces stale city API with comprehensive permit intelligence.
    """

    def __init__(self,
                 download_dir: Optional[str] = None,
                 db_manager: Optional[DatabaseManager] = None,
                 change_detector: Optional[ChangeDetector] = None):
        super().__init__(
            scraper_type=ScraperType.WEB,
            name="city_permits",
            base_url="https://www4.citizenserve.com"
        )

        self.download_dir = Path(download_dir or os.getenv('DOWNLOAD_DIR', './downloads'))
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Configuration from environment
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        self.timeout = int(os.getenv('TIMEOUT', '30000'))

        self.recaptcha_anchor_url = (
            'https://www.google.com/recaptcha/api2/anchor?ar=1&k='
            '6LeKdrMZAAAAAHhaf46zpFeRsB-VLv8kRAqKVrEW&co=aHR0cHM6Ly93d3c0'
            'LmNpdGl6ZW5zZXJ2ZS5jb206NDQz&hl=en&v=1aEzDFnIBfL6Zd_MU9G3Luhj'
            '&size=invisible&cb=123456789'
        )

        self.db_manager = db_manager
        self.change_detector = change_detector or ChangeDetector("city_permits")

        logger.info("City permits scraper initialized", download_dir=str(self.download_dir))

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

    async def scrape_permits_data(self, start_date: str, end_date: str) -> ScrapingResult:
        """
        Scrape permits for date range using Playwright stealth automation.

        Args:
            start_date: Start date in MM/DD/YYYY format
            end_date: End date in MM/DD/YYYY format

        Returns:
            ScrapingResult with permit data or error information
        """
        start_time = datetime.utcnow()

        try:
            logger.info("Starting permit scrape", start_date=start_date, end_date=end_date)

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

                    # Navigate to reports page
                    logger.info("Navigating to CitizenServe reports page...")
                    await page.goto(
                        "https://www4.citizenserve.com/Portal/PortalController?"
                        "Action=showPortalReports&ctzPagePrefix=Portal_&installationID=308"
                    )
                    await page.wait_for_load_state("networkidle")

                    # Click permits by date range link
                    logger.info("Clicking 'Permits by date range' link...")
                    try:
                        permits_link = await page.wait_for_selector("a:has-text('Permits by date range')", timeout=10000)
                        await permits_link.click()
                        logger.info("Clicked permits link successfully")
                    except:
                        logger.info("Fallback: executing getQuery JavaScript")
                        await page.evaluate("getQuery(269, 'Permits by date range');")

                    # Wait for form to load
                    await page.wait_for_load_state("networkidle")

                    # Verify form is present
                    form = await page.wait_for_selector("#Frm_QueryTool", timeout=10000)
                    if not form:
                        raise Exception("Could not find permit query form")

                    logger.info("Form loaded successfully with valid session")

                    # Fill form fields
                    logger.info("Filling form fields...")

                    # From Date
                    param1 = await page.wait_for_selector("input[name='Param_1']")
                    await param1.fill("")
                    await param1.fill(start_date)
                    logger.info(f"Set From Date: {start_date}")

                    # To Date
                    param2 = await page.wait_for_selector("input[name='Param_2']")
                    await param2.fill("")
                    await param2.fill(end_date)
                    logger.info(f"Set To Date: {end_date}")

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
                        recaptcha_field = await page.wait_for_selector("input[name='g-recaptcha-response']", timeout=5000)
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

                    # Check if results loaded
                    page_text = await page.text_content("body")
                    has_permits = any(pattern in page_text for pattern in ['B25-', 'E25-', 'M25-', 'P25-'])

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
                    excel_filename = f"permits_{start_date.replace('/', '')}_{end_date.replace('/', '')}.xlsx"
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
                            permit = PermitRecord(
                                permit_number=str(row.get('Permit#', '')),
                                permit_type=str(row.get('PermitType', '')),
                                sub_type=str(row.get('SubType', '')) if pd.notna(row.get('SubType')) else None,
                                address=str(row.get('Address', '')),
                                parcel_number=str(row.get('Parcel#', '')) if pd.notna(row.get('Parcel#')) else None,
                                description=str(row.get('Description', '')),
                                classification=str(row.get('Classification', '')) if pd.notna(row.get('Classification')) else None,
                                contractor=str(row.get('Contractor', '')) if pd.notna(row.get('Contractor')) else None,
                                application_date=row.get('ApplicationDate'),
                                issue_date=row.get('IssueDate'),
                                expiration_date=row.get('ExpirationDate'),
                                close_date=row.get('CloseDate'),
                                construction_cost=row.get('Construction Cost')
                            )
                            permits.append(permit.dict())
                        except Exception as e:
                            logger.warning(f"Failed to parse permit row: {e}", row_data=row.to_dict())
                            continue

                    # Calculate content hash for change detection
                    content_hash = self.change_detector.calculate_hash(permits)

                    response_time = (datetime.utcnow() - start_time).total_seconds()

                    logger.info("Scraping completed successfully",
                               total_permits=len(permits),
                               response_time=response_time)

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
            logger.error("Permit scraping failed", error=str(e), exc_info=True)
            return ScrapingResult(
                success=False,
                error=str(e),
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )

    async def scrape_today(self) -> ScrapingResult:
        """Convenience method to scrape today's permits."""
        today = datetime.now().strftime("%m/%d/%Y")
        return await self.scrape_permits_data(today, today)

    async def scrape_date_range(self, days_back: int = 7) -> ScrapingResult:
        """Convenience method to scrape permits for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.scrape_permits_data(
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y")
        )

    async def run_continuous_monitoring(self) -> None:
        """Run continuous monitoring for new permits."""
        logger.info("Starting continuous city permit monitoring...")

        while True:
            try:
                # Scrape today's permits
                result = await self.scrape_today()

                if result.success and result.data:
                    # Check for changes
                    has_changes = await self.change_detector.has_changes(result.content_hash)

                    if has_changes:
                        logger.info("New permits detected!", count=len(result.data))

                        # Store in database if available
                        if self.db_manager:
                            await self._store_permits(result.data)

                        # Update change detector
                        await self.change_detector.update_hash(result.content_hash)
                    else:
                        logger.info("No new permits since last check")
                else:
                    logger.warning("Failed to scrape permits or no data found")

                # Wait 2 hours before next check (real-time data per mmm.txt)
                await asyncio.sleep(2 * 60 * 60)

            except Exception as e:
                logger.error("Error in continuous monitoring", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _store_permits(self, permits: List[Dict[str, Any]]) -> None:
        """Store permits in database."""
        if not self.db_manager:
            return

        try:
            # Implementation depends on database schema
            # This would be implemented based on the actual database models
            logger.info("Storing permits in database", count=len(permits))
            # await self.db_manager.store_permits(permits)
        except Exception as e:
            logger.error("Failed to store permits in database", error=str(e))