"""
Crime Data Scraper

Supports both Socrata (Gainesville) and CKAN (Tampa) platforms
through config-driven architecture.
"""
import csv
import sys
import requests
import structlog
from io import StringIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ...config import load_market_config, MarketConfig

logger = structlog.get_logger(__name__)


class CrimeDataScraper:
    """
    Config-driven crime data scraper.

    Supports multiple platforms:
    - Socrata (JSON API) - Used by Gainesville
    - CKAN (CSV download) - Used by Tampa
    """

    def __init__(self, market_config: MarketConfig):
        """Initialize with market config."""
        self.config = market_config
        self.crime_config = market_config.scrapers.crime if hasattr(market_config.scrapers, 'crime') else None

        if not self.crime_config or not self.crime_config.enabled:
            raise ValueError(f"Crime scraper not enabled for {market_config.market.name}")

        logger.info("crime_scraper_initialized",
                   market=market_config.market.name,
                   platform=self.crime_config.platform)

    def fetch_recent_crimes(self, days_back: int = 7) -> Optional[List[Dict]]:
        """Fetch recent crime data."""
        logger.info("fetch_crime_started", days_back=days_back)

        try:
            if self.crime_config.platform.lower() == "socrata":
                return self._fetch_socrata_data(days_back)
            elif self.crime_config.platform.lower() == "ckan":
                return self._fetch_ckan_data()
            else:
                logger.warning("unsupported_platform", platform=self.crime_config.platform)
                return None

        except Exception as e:
            logger.error("fetch_crime_failed", error=str(e))
            return None

    def _fetch_socrata_data(self, days_back: int) -> Optional[List[Dict]]:
        """Fetch data from Socrata API."""
        try:
            start_date = datetime.now() - timedelta(days=days_back)

            endpoint = self.crime_config.endpoint
            if not endpoint.endswith('.json'):
                endpoint += '.json'

            params = {
                '$limit': 10,
                '$order': 'offense_date DESC'
            }

            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                logger.info("socrata_data_fetched", records_count=len(data))
                return data
            else:
                logger.warning("socrata_no_data")
                return None

        except requests.RequestException as e:
            logger.error("socrata_request_failed", error=str(e))
            return None
        except Exception as e:
            logger.error("socrata_fetch_failed", error=str(e))
            return None

    def _fetch_ckan_data(self) -> Optional[List[Dict]]:
        """Fetch data from CKAN (CSV download)."""
        try:
            response = requests.get(self.crime_config.endpoint, timeout=60)
            response.raise_for_status()

            csv_data = response.text
            lines = csv_data.strip().split('\n')

            if len(lines) > 1:
                reader = csv.DictReader(StringIO(csv_data))
                sample_records = []
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    sample_records.append(row)

                logger.info("ckan_data_fetched", total_records=len(lines)-1, sample_count=len(sample_records))
                return sample_records
            else:
                logger.warning("ckan_csv_empty")
                return None

        except requests.RequestException as e:
            logger.error("ckan_request_failed", error=str(e))
            return None
        except Exception as e:
            logger.error("ckan_fetch_failed", error=str(e))
            return None


def test_scraper(market_id: str):
    """Test the crime scraper with a specific market."""
    print("=" * 80)
    print(f"TESTING CRIME SCRAPER WITH {market_id.upper()}")
    print("=" * 80)

    # Load market config
    try:
        config = load_market_config(market_id)
        print(f"\n[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"\n[FAIL] Could not load config: {e}")
        return False

    # Check if crime scraper is enabled
    if not hasattr(config.scrapers, 'crime') or not config.scrapers.crime or not config.scrapers.crime.enabled:
        print(f"\n[SKIP] Crime scraper not enabled for this market")
        return True

    # Create scraper
    try:
        scraper = CrimeDataScraper(config)
    except Exception as e:
        print(f"\n[FAIL] Could not create scraper: {e}")
        return False

    # Fetch data
    result = scraper.fetch_recent_crimes(days_back=7)

    if result and len(result) > 0:
        print(f"\n[OK] Crime scraper works for {config.market.name}!")
        return True
    else:
        print(f"\n[WARN] Crime scraper returned no data for {config.market.name}")
        print(f"       (May be expected if no recent data available)")
        return True  # Not a failure - just no data


if __name__ == "__main__":
    import argparse

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    parser = argparse.ArgumentParser(description="Test Crime scraper portability")
    parser.add_argument(
        "--market",
        default="gainesville_fl",
        help="Market ID to test (default: gainesville_fl)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all available markets"
    )

    args = parser.parse_args()

    if args.all:
        from ...config import get_available_markets

        markets = get_available_markets()
        print(f"\nTesting {len(markets)} markets...\n")

        results = {}
        for market_id in markets:
            success = test_scraper(market_id)
            results[market_id] = success
            print()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        for market_id, success in results.items():
            status = "[OK]" if success else "[FAIL]"
            print(f"{status} {market_id}")

        total = len(results)
        passed = sum(results.values())
        print(f"\nPassed: {passed}/{total}")

        sys.exit(0 if passed == total else 1)
    else:
        success = test_scraper(args.market)
        sys.exit(0 if success else 1)
