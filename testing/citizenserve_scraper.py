#!/usr/bin/env python3
"""
CitizenServe Permit Scraper - Production Version
Uses Patchright for Docker/VPS deployment with stealth capabilities
"""

import sys
import os
import json
import pandas as pd
import structlog
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Patchright - undetected Playwright replacement
from patchright.sync_api import sync_playwright

# reCAPTCHA bypass
sys.path.append('BypassV3')
from bypass import ReCaptchaV3Bypass

# Configure structured logging for production
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("dominion.scrapers.citizenserve")


class CitizenServePermitScraper:
    """
    Production CitizenServe permit scraper using Patchright for stealth.
    Designed for Docker deployment on VPS infrastructure.
    """

    def __init__(self, download_dir: str = None):
        """
        Initialize scraper with Docker-friendly configuration.

        Args:
            download_dir: Directory for Excel file downloads (uses env var DOWNLOAD_DIR or ./downloads)
        """
        self.download_dir = Path(download_dir or os.getenv('DOWNLOAD_DIR', './downloads'))
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Configuration from environment
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        self.timeout = int(os.getenv('TIMEOUT', '30000'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        self.recaptcha_anchor_url = (
            'https://www.google.com/recaptcha/api2/anchor?ar=1&k='
            '6LeKdrMZAAAAAHhaf46zpFeRsB-VLv8kRAqKVrEW&co=aHR0cHM6Ly93d3c0'
            'LmNpdGl6ZW5zZXJ2ZS5jb206NDQz&hl=en&v=1aEzDFnIBfL6Zd_MU9G3Luhj'
            '&size=invisible&cb=123456789'
        )

        self.playwright = None
        self.browser = None
        self.context = None

        logger.info("CitizenServe scraper initialized", download_dir=str(self.download_dir))

    def _setup_browser(self) -> None:
        """Initialize Patchright browser with stealth configuration."""
        try:
            logger.info("Initializing Patchright browser...")

            self.playwright = sync_playwright().start()

            # Better stealth: Use Chromium with configurable headless mode
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )

            # Configure download behavior with stealth settings
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                accept_downloads=True,
            )

            # Set timeout from configuration
            self.context.set_default_timeout(self.timeout)

            logger.info("Browser initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize browser", error=str(e))
            raise

    def _get_recaptcha_token(self) -> str:
        """Generate reCAPTCHA v3 token using BypassV3."""
        try:
            logger.info("Generating reCAPTCHA token...")
            bypass = ReCaptchaV3Bypass(self.recaptcha_anchor_url)
            token = bypass.bypass()

            if not token:
                raise ValueError("Failed to generate reCAPTCHA token")

            logger.info("reCAPTCHA token generated successfully")
            return token

        except Exception as e:
            logger.error("reCAPTCHA token generation failed", error=str(e))
            raise

    def scrape_permits(self, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """
        Scrape permits for date range and download Excel file.

        Args:
            start_date: Start date in MM/DD/YYYY format
            end_date: End date in MM/DD/YYYY format

        Returns:
            Dictionary with scraping results and permit data, or None if failed
        """
        logger.info("Starting permit scrape", start_date=start_date, end_date=end_date)

        try:
            # Initialize browser
            if not self.browser:
                self._setup_browser()

            # Get reCAPTCHA token
            token = self._get_recaptcha_token()

            # Navigate and scrape
            page = self.context.new_page()

            logger.info("Navigating to CitizenServe reports page...")

            # Step 1: Go to the reports page first (to get valid session)
            page.goto("https://www4.citizenserve.com/Portal/PortalController?"
                     "Action=showPortalReports&ctzPagePrefix=Portal_&installationID=308")
            page.wait_for_load_state("networkidle")

            logger.info("Reports page loaded")

            # Step 2: Click "Permits by date range" link to load form with valid session
            logger.info("Clicking 'Permits by date range' link...")
            try:
                # Try clicking the link text first
                permits_link = page.wait_for_selector("a:has-text('Permits by date range')", timeout=10000)
                permits_link.click()
                logger.info("Clicked permits link successfully")
            except:
                # Fallback: execute the JavaScript directly
                logger.info("Fallback: executing getQuery JavaScript")
                page.evaluate("getQuery(269, 'Permits by date range');")

            # Wait for form to load
            page.wait_for_load_state("networkidle")


            # Verify form is present with valid session
            form = page.wait_for_selector("#Frm_QueryTool", timeout=10000)
            if not form:
                raise Exception("Could not find permit query form after clicking link")

            logger.info("Form loaded successfully with valid session")

            logger.info("Filling permit search form...")


            # Fill all form fields properly
            logger.info("Filling form fields...")

            # Param_0: Permits status (keep default "- All -")
            # No need to change this unless user wants specific status

            # Param_1: From Date
            param1 = page.wait_for_selector("input[name='Param_1']")
            param1.fill("")  # Clear first
            param1.fill(start_date)
            logger.info(f"Set From Date: {start_date}")

            # Param_2: To Date
            param2 = page.wait_for_selector("input[name='Param_2']")
            param2.fill("")  # Clear first
            param2.fill(end_date)
            logger.info(f"Set To Date: {end_date}")

            # Param_3: Permit Type (keep default "All Permit Types")
            # No need to change this unless user wants specific type

            # Handle human verification checkbox (new system)
            try:
                human_checkbox = page.wait_for_selector("#noparam-checkbox", timeout=5000)
                if not human_checkbox.is_checked():
                    human_checkbox.check()
                    logger.info("Checked 'I am human' checkbox")
                else:
                    logger.info("'I am human' checkbox already checked")
            except:
                logger.info("Human checkbox not found - may not be required")

            # Set reCAPTCHA token as fallback (in case some forms still use it)
            try:
                recaptcha_field = page.wait_for_selector("input[name='g-recaptcha-response']", timeout=5000)
                page.evaluate(f"arguments[0].value = '{token}';", recaptcha_field)
                logger.info("reCAPTCHA token set (fallback)")
            except:
                logger.info("reCAPTCHA field not found - using human checkbox instead")

            logger.info("Submitting permit query...")

            # Submit using the correct method from HTML analysis
            try:
                # Try clicking the Submit link first (ID: submitLink)
                submit_link = page.wait_for_selector("#submitLink", timeout=5000)
                submit_link.click()
                logger.info("Clicked Submit link")
            except:
                # Fallback: Call runQuery() JavaScript function directly
                try:
                    page.evaluate("runQuery();")
                    logger.info("Used JavaScript runQuery() function")
                except:
                    # Last resort: traditional form submit
                    form = page.wait_for_selector("#Frm_QueryTool")
                    form.evaluate("form => form.submit()")
                    logger.info("Used form.submit() as last resort")

            # Wait for results to load with smart wait
            page.wait_for_load_state("networkidle")
            # Small delay for dynamic content
            page.wait_for_timeout(2000)


            # Check if results loaded - look for permit data directly
            page_text = page.text_content("body")
            has_permits = any(permit_pattern in page_text for permit_pattern in ['B25-', 'E25-', 'M25-', 'P25-'])

            if has_permits:
                logger.info("SUCCESS! Permit data found in results!")
                # Find all tables to get the right one with data
                all_tables = page.query_selector_all("table")
                logger.info(f"Found {len(all_tables)} tables on page")
            else:
                logger.warning("No permit data found for date range")
                return None

            # Wait for export functionality - look for the correct export icon
            logger.info("Waiting for export button...")
            export_icon = page.wait_for_selector(
                "i.icon-external-link[title='Export']",
                timeout=self.timeout
            )

            if not export_icon:
                raise Exception("Export button not found")


            # Setup download handler
            with page.expect_download() as download_info:
                logger.info("Clicking export button...")
                export_icon.click()

            # Wait for download
            try:
                download = download_info.value
                excel_filename = f"permits_{start_date.replace('/', '')}_{end_date.replace('/', '')}.xlsx"
                excel_path = self.download_dir / excel_filename

                # Save download
                download.save_as(str(excel_path))
                logger.info("Excel file downloaded", filename=excel_filename)

            except Exception as e:
                logger.error("Download failed", error=str(e))
                return None

            # Process Excel file
            logger.info("Processing Excel data...")
            df = pd.read_excel(str(excel_path))

            # Create result structure
            result = {
                "extraction_date": datetime.now().isoformat(),
                "source": "citizenserve_patchright_scraper",
                "date_range": {"start": start_date, "end": end_date},
                "total_permits": len(df),
                "excel_file": excel_filename,
                "permits": df.to_dict('records')
            }

            # Save JSON
            json_filename = f"permits_{start_date.replace('/', '')}_{end_date.replace('/', '')}.json"
            json_path = self.download_dir / json_filename

            with open(json_path, "w") as f:
                json.dump(result, f, indent=2, default=str)

            logger.info("Scraping completed successfully",
                       total_permits=len(df),
                       excel_file=excel_filename,
                       json_file=json_filename)

            return result

        except Exception as e:
            logger.error("Permit scraping failed", error=str(e), exc_info=True)
            return None

        finally:
            # Cleanup
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()

    def scrape_today(self) -> Optional[Dict[str, Any]]:
        """Convenience method to scrape today's permits."""
        today = datetime.now().strftime("%m/%d/%Y")
        return self.scrape_permits(today, today)

    def scrape_date_range(self, days_back: int = 7) -> Optional[Dict[str, Any]]:
        """Convenience method to scrape permits for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return self.scrape_permits(
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y")
        )


def main():
    """Test the scraper with a known date."""
    scraper = CitizenServePermitScraper()

    # Test with known working date
    result = scraper.scrape_permits("09/25/2025", "09/25/2025")

    if result:
        print(f"Success: {result['total_permits']} permits scraped")
        print(f"Files: {result['excel_file']}")
    else:
        print("Failed to scrape permits")


if __name__ == "__main__":
    main()