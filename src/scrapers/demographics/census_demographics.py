"""
Census Demographics Scraper

Fetches county-level census data using US Census Bureau API.
Portable across markets via FIPS codes in config.
"""
import sys
import requests
import structlog
from pathlib import Path
from typing import Dict, Optional

from ...config import load_market_config, MarketConfig

logger = structlog.get_logger(__name__)


class CensusScraper:
    """Census scraper that fetches county demographics via Census API."""

    BASE_URL = "https://api.census.gov/data/2022/acs/acs5"

    TEST_VARIABLES = [
        "B01003_001E",  # Total population
        "B19013_001E",  # Median household income
        "B25077_001E",  # Median home value
    ]

    def __init__(self, market_config: MarketConfig):
        """Initialize with market config."""
        self.config = market_config
        self.fips = market_config.geography.fips
        self.api_key = market_config.scrapers.census.api_key if market_config.scrapers.census else None

        logger.info("census_scraper_initialized",
                   market=market_config.market.name,
                   state_fips=self.fips['state'],
                   county_fips=self.fips['county'])

    def fetch_county_data(self) -> Optional[Dict]:
        """
        Fetch basic county-level census data.

        Returns:
            Dict with census data or None if failed
        """
        params = {
            "get": ",".join(self.TEST_VARIABLES),
            "for": f"county:{self.fips['county']}",
            "in": f"state:{self.fips['state']}"
        }

        if self.api_key:
            params["key"] = self.api_key

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if len(data) >= 2:
                headers = data[0]
                values = data[1]
                result = dict(zip(headers, values))

                logger.info("census_data_fetched",
                           population=result.get('B01003_001E'),
                           median_income=result.get('B19013_001E'),
                           median_home_value=result.get('B25077_001E'))

                return result
            else:
                logger.warning("unexpected_response_format")
                return None

        except requests.RequestException as e:
            logger.error("census_request_failed", error=str(e))
            return None
        except Exception as e:
            logger.error("census_fetch_failed", error=str(e))
            return None


def test_scraper(market_id: str):
    """Test the scraper with a specific market."""
    print("=" * 80)
    print(f"TESTING CENSUS SCRAPER WITH {market_id.upper()}")
    print("=" * 80)

    # Load market config
    try:
        config = load_market_config(market_id)
        print(f"\n[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"\n[FAIL] Could not load config: {e}")
        return False

    # Create scraper
    scraper = CensusScraper(config)

    # Fetch data
    result = scraper.fetch_county_data()

    if result:
        print(f"\n[OK] Scraper works for {config.market.name}!")
        return True
    else:
        print(f"\n[FAIL] Scraper failed for {config.market.name}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Census scraper portability")
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
        # Test all markets
        from ...config import get_available_markets

        markets = get_available_markets()
        print(f"\nTesting {len(markets)} markets...\n")

        results = {}
        for market_id in markets:
            success = test_scraper(market_id)
            results[market_id] = success
            print()

        # Summary
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
        # Test single market
        success = test_scraper(args.market)
        sys.exit(0 if success else 1)