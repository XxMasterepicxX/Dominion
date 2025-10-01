"""
County Permits Scraper

Config-driven scraper for county building permits via CitizenServe portal.
Uses Patchright (stealth browser) to bypass bot detection.

Design: Multi-report scraping (Applied, Issued, Closed) with deduplication.
Portability: Works across counties by reading config (base_url, installation_id, report_ids).
"""

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field, validator
import structlog

from patchright.async_api import async_playwright

from ...config.schemas import MarketConfig
from BypassV3.bypass import ReCaptchaV3Bypass

logger = structlog.get_logger(__name__)


class CountyReportType(Enum):
    """
    County permit report types with IDs.

    Default IDs are for Alachua County, but can be overridden in config.
    """
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


class CountyPermitsScraper:
    """
    PORTABLE County Permits Scraper using CitizenServe portal.

    Config-driven scraper that works across different counties by reading
    configuration from MarketConfig (base_url, installation_id, report_ids).

    Uses Patchright (stealth browser) to bypass bot detection.
    Handles 3 report types: Applied, Issued, and Closed permits.
    """

    def __init__(self, market_config: MarketConfig, headless: bool = True):
        """
        Initialize county permits scraper from market config.

        Args:
            market_config: Market configuration with county_permits settings
            headless: Run browser in headless mode (default: True)
        """
        self.config = market_config
        self.permits_config = market_config.scrapers.county_permits

        if not self.permits_config or not self.permits_config.enabled:
            raise ValueError("County permits scraper not enabled in config")

        # Config-driven values (PORTABLE!)
        self.platform = self.permits_config.platform.lower()
        self.base_url = self.permits_config.base_url
        self.jurisdiction = self.permits_config.jurisdiction
        self.installation_id = getattr(self.permits_config, 'installation_id', None)

        if not self.installation_id:
            raise ValueError(f"installation_id required for {self.jurisdiction}")

        # Report IDs with defaults (can be overridden in config for different counties)
        self.report_ids = {
            'applied': getattr(self.permits_config, 'applied_report_id', 359),
            'issued': getattr(self.permits_config, 'issued_report_id', 360),
            'closed': getattr(self.permits_config, 'closed_report_id', 379),
        }

        # Browser settings
        self.headless = headless
        self.timeout = 30000

        # Build reCAPTCHA URL dynamically based on base_url
        self.recaptcha_anchor_url = self._build_recaptcha_url()

        # Download directory
        self.download_dir = Path(tempfile.mkdtemp(prefix="permits_"))

        logger.info("county_permits_initialized",
                   jurisdiction=self.jurisdiction,
                   platform=self.platform,
                   installation_id=self.installation_id,
                   report_ids=self.report_ids)

    def _build_recaptcha_url(self) -> str:
        """
        Build reCAPTCHA anchor URL dynamically based on base_url.

        Different CitizenServe installations use different URLs:
        - www4.citizenserve.com → encoded as aHR0cHM6Ly93d3c0...
        - www6.citizenserve.com → encoded as aHR0cHM6Ly93d3c2...
        """
        import base64

        # Extract subdomain (www4, www6, etc.)
        if 'www4' in self.base_url:
            encoded_origin = base64.b64encode(b'https://www4.citizenserve.com:443').decode()
        elif 'www6' in self.base_url:
            encoded_origin = base64.b64encode(b'https://www6.citizenserve.com:443').decode()
        else:
            # Default to www6
            encoded_origin = base64.b64encode(b'https://www6.citizenserve.com:443').decode()

        return (
            f'https://www.google.com/recaptcha/api2/anchor?ar=1&k='
            f'6LeKdrMZAAAAAHhaf46zpFeRsB-VLv8kRAqKVrEW&co={encoded_origin}'
            f'&hl=en&v=1aEzDFnIBfL6Zd_MU9G3Luhj&size=invisible&cb=123456789'
        )

    async def _get_recaptcha_token(self) -> str:
        """Generate reCAPTCHA v3 token using BypassV3."""
        try:
            loop = asyncio.get_event_loop()
            bypass = ReCaptchaV3Bypass(self.recaptcha_anchor_url)
            token = await loop.run_in_executor(None, bypass.bypass)

            if not token:
                raise ValueError("Failed to generate reCAPTCHA token")

            logger.info("recaptcha_token_generated", token_length=len(token))
            return token

        except Exception as e:
            logger.error("recaptcha_token_failed", error=str(e))
            raise

    async def scrape_permits_data(
        self,
        start_date: str,
        end_date: str,
        report_type: CountyReportType = CountyReportType.ISSUED
    ) -> Dict[str, Any]:
        """
        Scrape county permits for date range using Playwright stealth automation.

        Args:
            start_date: Start date in MM/DD/YYYY format
            end_date: End date in MM/DD/YYYY format
            report_type: Which report to scrape (APPLIED, ISSUED, or CLOSED)

        Returns:
            Dict with 'success', 'data', 'error' keys
        """
        start_time = datetime.now()
        report_id = report_type.value["id"]
        report_name = report_type.value["name"]

        try:
            logger.info("scrape_permits_started",
                       jurisdiction=self.jurisdiction,
                       report=report_name,
                       date_range=f"{start_date} to {end_date}")

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

                    url = (
                        f"{self.base_url}/Portal/PortalController?"
                        f"Action=showPortalReports&ctzPagePrefix=Portal_"
                        f"&installationID={self.installation_id}"
                        f"&original_iid=0&original_contactID=0"
                    )
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")

                    report_link = await page.wait_for_selector(
                        f"xpath=//a[contains(@href, 'getQuery({report_id}')]",
                        timeout=10000
                    )
                    await report_link.click()
                    await page.wait_for_load_state("networkidle")

                    form = await page.wait_for_selector("#Frm_QueryTool", timeout=10000)
                    if not form:
                        raise Exception("Could not find permit query form")

                    param0 = await page.wait_for_selector("input[name='Param_0']")
                    await param0.fill("")
                    await param0.fill(start_date)

                    param1 = await page.wait_for_selector("input[name='Param_1']")
                    await param1.fill("")
                    await param1.fill(end_date)

                    try:
                        human_checkbox = await page.wait_for_selector("#noparam-checkbox", timeout=5000)
                        if not await human_checkbox.is_checked():
                            await human_checkbox.check()
                    except:
                        pass

                    try:
                        recaptcha_field = await page.wait_for_selector(
                            "input[name='g-recaptcha-response']",
                            timeout=5000
                        )
                        await page.evaluate(f"arguments[0].value = '{token}';", recaptcha_field)
                    except:
                        pass

                    try:
                        submit_link = await page.wait_for_selector("#submitLink", timeout=5000)
                        await submit_link.click()
                    except:
                        try:
                            await page.evaluate("runQuery();")
                        except:
                            form = await page.wait_for_selector("#Frm_QueryTool")
                            await form.evaluate("form => form.submit()")

                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(2000)

                    page_text = await page.text_content("body")
                    has_permits = any(pattern in page_text for pattern in [
                        'BLD', 'ELE', 'PLU', 'MEC', 'Permit', 'Application'
                    ])

                    if not has_permits:
                        logger.warning("no_permits_found",
                                     jurisdiction=self.jurisdiction,
                                     report=report_name)
                        return {
                            'success': True,
                            'data': [],
                            'response_time': (datetime.now() - start_time).total_seconds()
                        }

                    export_icon = await page.wait_for_selector(
                        "i.icon-external-link[title='Export']",
                        timeout=self.timeout
                    )

                    if not export_icon:
                        raise Exception("Export button not found")

                    async with page.expect_download() as download_info:
                        await export_icon.click()

                    download = await download_info.value
                    report_type_str = report_type.name.lower()
                    excel_filename = f"county_permits_{report_type_str}_{start_date.replace('/', '')}_{end_date.replace('/', '')}.xlsx"
                    excel_path = self.download_dir / excel_filename

                    await download.save_as(str(excel_path))
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
                            logger.warning("permit_parse_failed", error=str(e))
                            continue

                    response_time = (datetime.now() - start_time).total_seconds()

                    logger.info("scrape_permits_completed",
                               jurisdiction=self.jurisdiction,
                               report=report_name,
                               permits_count=len(permits),
                               response_time=response_time)

                    return {
                        'success': True,
                        'data': permits,
                        'report_type': report_type.name.lower(),
                        'response_time': response_time
                    }

                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            logger.error("scrape_permits_failed",
                        jurisdiction=self.jurisdiction,
                        error=str(e))
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'data': [],
                'error': str(e),
                'response_time': (datetime.now() - start_time).total_seconds()
            }

    async def scrape_all_reports(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Scrape all 3 report types for comprehensive permit intelligence.

        Returns:
            Dictionary with keys: 'applied', 'issued', 'closed'
        """
        logger.info("scrape_all_reports_started",
                   jurisdiction=self.jurisdiction,
                   date_range=f"{start_date} to {end_date}")

        results = {}

        for report_type in CountyReportType:
            result = await self.scrape_permits_data(start_date, end_date, report_type)
            results[report_type.name.lower()] = result
            await asyncio.sleep(2)

        total_permits = sum(
            len(result['data']) if result['success'] else 0
            for result in results.values()
        )

        logger.info("scrape_all_reports_completed",
                   total_permits=total_permits,
                   applied=len(results['applied']['data']) if results['applied']['success'] else 0,
                   issued=len(results['issued']['data']) if results['issued']['success'] else 0,
                   closed=len(results['closed']['data']) if results['closed']['success'] else 0)

        return results

    async def scrape_all_reports_deduplicated(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Scrape all 3 report types and return deduplicated unique permits.

        Deduplication strategy:
        - Permits can appear in multiple reports as they move through lifecycle
        - Keep the record with most advanced status: Closed > Issued > Applied
        - This gives the current status of each unique permit

        Returns:
            Dict with deduplicated data
        """
        results = await self.scrape_all_reports(start_date, end_date)

        all_permits = []
        for report_name, result in results.items():
            if result['success']:
                all_permits.extend(result['data'])

        if not all_permits:
            return {
                'success': False,
                'data': [],
                'error': "No permits found in any report",
                'response_time': 0.0
            }

        df = pd.DataFrame(all_permits)
        raw_count = len(df)

        status_priority = {'closed': 3, 'issued': 2, 'applied': 1}
        df['_priority'] = df['report_type'].map(status_priority)

        df_deduplicated = df.sort_values('_priority', ascending=False).drop_duplicates(
            subset=['permit_number'],
            keep='first'
        )

        df_deduplicated = df_deduplicated.drop(columns=['_priority'])

        unique_count = len(df_deduplicated)
        duplicates_removed = raw_count - unique_count

        logger.info("deduplication_completed",
                   raw_count=raw_count,
                   unique_count=unique_count,
                   duplicates_removed=duplicates_removed)

        deduplicated_permits = df_deduplicated.to_dict('records')

        return {
            'success': True,
            'data': deduplicated_permits,
            'response_time': sum(r['response_time'] for r in results.values())
        }

    async def scrape_today(self, report_type: CountyReportType = CountyReportType.ISSUED) -> Dict[str, Any]:
        """Convenience method to scrape today's permits."""
        today = datetime.now().strftime("%m/%d/%Y")
        return await self.scrape_permits_data(today, today, report_type)

    async def scrape_date_range(
        self,
        days_back: int = 7,
        report_type: CountyReportType = CountyReportType.ISSUED
    ) -> Dict[str, Any]:
        """Convenience method to scrape permits for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.scrape_permits_data(
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y"),
            report_type
        )

    async def fetch_recent_permits(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch recent county permits with deduplication.

        Portable version - returns list of permit dicts instead of database models.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        result = await self.scrape_all_reports_deduplicated(
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y")
        )

        if result['success']:
            return result['data']
        else:
            logger.error("fetch_permits_failed", error=result.get('error'))
            return []


# Test function
async def test_county_permits():
    """Test the county permits scraper with Gainesville config."""
    import sys
    from ...config.loader import load_market_config

    config = load_market_config('gainesville_fl')
    scraper = CountyPermitsScraper(config, headless=False)

    # Test fetching recent permits (30 days)
    permits = await scraper.fetch_recent_permits(days_back=30)

    print(f"\n[RESULT] County permits found: {len(permits)}")
    if permits:
        print(f"Sample: {permits[0]}")

    return permits


if __name__ == "__main__":
    asyncio.run(test_county_permits())