"""
City Permits Scraper

Scrapes building permits from city permit portals using browser automation.
Config-driven to support multiple platforms and cities.

Platforms:
- CitizenServe: Uses Playwright + reCAPTCHA bypass
- Accela: Uses requests
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from patchright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import structlog

from ...config.schemas import MarketConfig

try:
    from ..BypassV3.bypass import ReCaptchaV3Bypass
except ImportError:
    ReCaptchaV3Bypass = None

logger = structlog.get_logger(__name__)


class PermitRecord:
    """Permit record model."""

    def __init__(self, data: Dict):
        self.permit_number = data.get('permit_number', data.get('Permit Number', data.get('Permit#', '')))
        self.permit_type = data.get('permit_type', data.get('Permit Type', data.get('PermitType', '')))
        self.subtype = data.get('subtype', data.get('SubType', ''))
        self.status = data.get('status', data.get('Status', ''))
        self.address = data.get('address', data.get('Address', ''))
        self.parcel = data.get('parcel', data.get('Parcel#', ''))
        self.applicant = data.get('applicant', data.get('Applicant', ''))
        self.contractor = data.get('contractor', data.get('Contractor', ''))
        self.application_date = data.get('application_date', data.get('ApplicationDate', ''))
        self.issue_date = data.get('issue_date', data.get('Issue Date', data.get('IssueDate', '')))
        self.expiration_date = data.get('expiration_date', data.get('ExpirationDate', ''))
        self.close_date = data.get('close_date', data.get('CloseDate', ''))
        self.valuation = self._parse_float(data.get('valuation', data.get('Valuation', data.get('Value', data.get('Construction Cost', '')))))
        self.description = data.get('description', data.get('Description', ''))

    def _parse_float(self, value):
        """Parse float from string."""
        if not value or value in ['', 'N/A', None]:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.replace('$', '').replace(',', '').strip()
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> Dict:
        """Convert to dictionary, handling NaN values."""
        import math

        def clean_value(v):
            """Convert NaN to None for JSON compatibility."""
            if isinstance(v, float) and math.isnan(v):
                return None
            return v

        return {
            'permit_number': clean_value(self.permit_number),
            'permit_type': clean_value(self.permit_type),
            'status': clean_value(self.status),
            'address': clean_value(self.address),
            'applicant': clean_value(self.applicant),
            'contractor': clean_value(self.contractor),
            'application_date': clean_value(self.application_date),  # FIXED - was missing!
            'issue_date': clean_value(self.issue_date),
            'valuation': clean_value(self.valuation),
            'description': clean_value(self.description),
        }


class CityPermitsScraper:
    """City building permits scraper with browser automation."""

    def __init__(self, market_config: MarketConfig, headless: bool = True):
        """Initialize with market config."""
        self.config = market_config
        self.permits_config = market_config.scrapers.city_permits

        if not self.permits_config or not self.permits_config.enabled:
            raise ValueError("City permits scraper not enabled in config")

        self.platform = self.permits_config.platform.lower()
        self.base_url = self.permits_config.base_url
        self.jurisdiction = self.permits_config.jurisdiction
        self.installation_id = getattr(self.permits_config, 'installation_id', None)
        self.headless = headless
        self.download_dir = Path(tempfile.mkdtemp(prefix="permits_"))

        logger.info("city_permits_initialized",
                   jurisdiction=self.jurisdiction,
                   platform=self.platform,
                   download_dir=str(self.download_dir))

    async def fetch_recent_permits(self, days_back: int = 7) -> List[PermitRecord]:
        """
        Fetch permits from the last N days.

        Args:
            days_back: Number of days to look back

        Returns:
            List of PermitRecord objects
        """
        logger.info("fetch_permits_started",
                   jurisdiction=self.jurisdiction,
                   platform=self.platform,
                   days_back=days_back)

        if self.platform == "citizenserve":
            permits = await self._fetch_citizenserve(days_back)
        elif self.platform == "accela":
            permits = await self._fetch_accela(days_back)
        else:
            logger.error("unknown_platform", platform=self.platform)
            return []

        logger.info("fetch_permits_completed",
                   permits_found=len(permits),
                   jurisdiction=self.jurisdiction)

        return permits

    async def _fetch_citizenserve(self, days_back: int) -> List[PermitRecord]:
        """Fetch permits from CitizenServe using Patchright."""

        if not self.installation_id:
            logger.error("missing_installation_id", platform="citizenserve")
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        start_str = start_date.strftime("%m/%d/%Y")
        end_str = end_date.strftime("%m/%d/%Y")

        logger.info("citizenserve_fetch_started",
                   date_range=f"{start_str} to {end_str}",
                   installation_id=self.installation_id)

        recaptcha_anchor_url = (
            'https://www.google.com/recaptcha/api2/anchor?ar=1&k='
            '6LeKdrMZAAAAAHhaf46zpFeRsB-VLv8kRAqKVrEW&co=aHR0cHM6Ly93d3c0'
            'LmNpdGl6ZW5zZXJ2ZS5jb206NDQz&hl=en&v=1aEzDFnIBfL6Zd_MU9G3Luhj'
            '&size=invisible&cb=123456789'
        )

        token = ""
        try:
            bypass = ReCaptchaV3Bypass(recaptcha_anchor_url)
            token = bypass.bypass()
            if token:
                logger.info("recaptcha_token_generated", token_length=len(token))
        except Exception as e:
            logger.warning("recaptcha_bypass_failed", error=str(e))

        permits = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(accept_downloads=True)
                page = await context.new_page()

                reports_url = (
                    f"{self.base_url}/Portal/PortalController?"
                    f"Action=showPortalReports&ctzPagePrefix=Portal_"
                    f"&installationID={self.installation_id}"
                )

                await page.goto(reports_url, wait_until="networkidle")

                try:
                    permits_link = await page.wait_for_selector("a:has-text('Permits by date range')", timeout=10000)
                    await permits_link.click()
                except Exception:
                    await page.evaluate("getQuery(269, 'Permits by date range');")

                await page.wait_for_load_state("networkidle")

                form = await page.wait_for_selector("#Frm_QueryTool", timeout=10000)
                if not form:
                    raise Exception("Form not found")

                param1 = await page.wait_for_selector("input[name='Param_1']")
                await param1.fill(start_str)

                param2 = await page.wait_for_selector("input[name='Param_2']")
                await param2.fill(end_str)

                try:
                    human_checkbox = await page.wait_for_selector("#noparam-checkbox", timeout=5000)
                    if not await human_checkbox.is_checked():
                        await human_checkbox.check()
                except (PlaywrightTimeout, Exception) as e:
                    logger.debug("human_checkbox_not_found", error=str(e))

                if token:
                    try:
                        await page.evaluate(f"document.querySelector('input[name=\"g-recaptcha-response\"]').value = '{token}';")
                    except Exception as e:
                        logger.debug("recaptcha_injection_failed", error=str(e))

                try:
                    submit_link = await page.wait_for_selector("#submitLink", timeout=5000)
                    await submit_link.click()
                except (PlaywrightTimeout, Exception):
                    try:
                        await page.evaluate("runQuery();")
                    except Exception:
                        await form.evaluate("form => form.submit()")

                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                page_text = await page.text_content("body")
                has_permits = any(pattern in page_text for pattern in ['B25-', 'E25-', 'M25-', 'P25-', 'B24-'])

                if not has_permits:
                    logger.warning("no_permits_found_in_results")
                    await browser.close()
                    return []

                try:
                    export_icon = await page.wait_for_selector("i.icon-external-link[title='Export']", timeout=10000)

                    async with page.expect_download() as download_info:
                        await export_icon.click()

                    download = await download_info.value
                    excel_path = self.download_dir / f"permits_{start_str.replace('/', '')}_{end_str.replace('/', '')}.xlsx"
                    await download.save_as(str(excel_path))

                    logger.info("excel_downloaded", file=excel_path.name)

                    try:
                        import pandas as pd

                        # Add timeout for Excel parsing (30 seconds max)
                        import signal
                        from contextlib import contextmanager

                        @contextmanager
                        def timeout_context(seconds):
                            def timeout_handler(signum, frame):
                                raise TimeoutError(f"Excel parsing exceeded {seconds} seconds")

                            # Set alarm (Unix only)
                            if hasattr(signal, 'SIGALRM'):
                                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                                signal.alarm(seconds)
                                try:
                                    yield
                                finally:
                                    signal.alarm(0)
                                    signal.signal(signal.SIGALRM, old_handler)
                            else:
                                # Windows fallback - no timeout
                                yield

                        with timeout_context(30):
                            df = pd.read_excel(str(excel_path))

                            for _, row in df.iterrows():
                                permit = PermitRecord(row.to_dict())
                                permits.append(permit)

                            logger.info("excel_parsed", permits_count=len(permits))

                    except TimeoutError as e:
                        logger.error("excel_parsing_timeout", error=str(e), file=excel_path.name)
                    except Exception as e:
                        logger.error("excel_parsing_failed", error=str(e))

                except Exception as e:
                    logger.warning("export_failed", error=str(e))
                    permits = await self._parse_html_results(page)

                await browser.close()

        except Exception as e:
            logger.error("citizenserve_scraping_failed", error=str(e))

        return permits

    async def _parse_html_results(self, page) -> List[PermitRecord]:
        """Fallback: parse permits from HTML table if Excel download fails."""
        permits = []

        try:
            table = await page.query_selector("table")
            if not table:
                return []

            rows = await table.query_selector_all("tr")

            for row in rows[1:]:
                cells = await row.query_selector_all("td")
                if len(cells) >= 3:
                    permit = PermitRecord({
                        'permit_number': (await cells[0].text_content()).strip() if len(cells) > 0 else '',
                        'permit_type': (await cells[1].text_content()).strip() if len(cells) > 1 else '',
                        'address': (await cells[2].text_content()).strip() if len(cells) > 2 else '',
                    })
                    permits.append(permit)

            logger.info("html_parsed", permits_count=len(permits))

        except Exception as e:
            logger.error("html_parsing_failed", error=str(e))

        return permits

    async def _fetch_accela(self, days_back: int) -> List[PermitRecord]:
        """Fetch permits from Accela."""
        logger.warning("accela_not_implemented")
        return []


async def test_scraper():
    """Test the permits scraper."""
    from ...config.loader import load_market_config

    print("\n=== Testing City Permits Scraper ===\n")

    try:
        config = load_market_config('gainesville_fl')
        print(f"[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"[FAIL] Failed to load config: {e}")
        return

    try:
        scraper = CityPermitsScraper(config, headless=False)
        print(f"[OK] Initialized scraper for {scraper.jurisdiction}")
        print(f"     Platform: {scraper.platform}")
        print(f"     Installation ID: {scraper.installation_id}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize scraper: {e}")
        return

    print(f"\n[TEST] Fetching permit data (last 7 days)...")
    permits = await scraper.fetch_recent_permits(days_back=7)

    if permits:
        print(f"\n[SUCCESS] Fetched {len(permits)} permits!")

        first = permits[0]
        print(f"\n--- Sample Permit ---")
        print(f"Permit Number: {first.permit_number}")
        print(f"Type: {first.permit_type}")
        print(f"Status: {first.status}")
        print(f"Address: {first.address}")
        print(f"Applicant: {first.applicant}")
        print(f"Contractor: {first.contractor}")
        print(f"Issue Date: {first.issue_date}")
        if first.valuation:
            print(f"Valuation: ${first.valuation:,.2f}")
        print(f"Description: {first.description[:100] if first.description else 'N/A'}")

        print(f"\n--- Summary ---")
        print(f"Total Permits: {len(permits)}")
        permit_types = {}
        for p in permits:
            permit_types[p.permit_type] = permit_types.get(p.permit_type, 0) + 1
        print(f"Permit Types:")
        for ptype, count in sorted(permit_types.items(), key=lambda x: -x[1])[:5]:
            print(f"  - {ptype}: {count}")

    else:
        print(f"\n[WARN] No permits found")


if __name__ == "__main__":
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    asyncio.run(test_scraper())
