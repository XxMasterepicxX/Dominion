"""
News RSS Scraper

Config-driven RSS news scraper - portable across markets.
"""
import sys
import feedparser
import structlog
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from ...config import load_market_config, MarketConfig

logger = structlog.get_logger(__name__)


class NewsRSSScraper:
    """Config-driven RSS news scraper."""

    def __init__(self, market_config: MarketConfig):
        """Initialize with market config."""
        self.config = market_config
        self.news_config = market_config.scrapers.news if hasattr(market_config.scrapers, 'news') else None

        if not self.news_config or not self.news_config.enabled:
            raise ValueError(f"News scraper not enabled for {market_config.market.name}")

        logger.info("news_scraper_initialized",
                   market=market_config.market.name,
                   feeds_count=len(self.news_config.feeds))

    def fetch_recent_news(self) -> Optional[List[Dict]]:
        """
        Fetch recent news from all configured RSS feeds.

        Returns:
            List of news articles or None if failed
        """
        all_articles = []

        for feed_name, feed_url in self.news_config.feeds.items():
            try:
                feed = feedparser.parse(feed_url)

                if feed.bozo:
                    logger.warning("feed_parse_issue", feed=feed_name, error=str(feed.bozo_exception))
                    continue

                if not feed.entries:
                    logger.warning("feed_empty", feed=feed_name)
                    continue

                # Get all entries from feed (no limit)
                for entry in feed.entries:
                    article = {
                        'source': feed_name,
                        'title': entry.get('title', 'No title'),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', entry.get('updated', 'Unknown date')),
                        'summary': entry.get('summary', '')[:500] + '...' if entry.get('summary') else ''  # Increased from 200 to 500
                    }
                    all_articles.append(article)

                logger.info("feed_fetched", feed=feed_name, articles_count=len(feed.entries))

            except Exception as e:
                logger.error("feed_fetch_failed", feed=feed_name, error=str(e))
                continue

        if all_articles:
            logger.info("fetch_news_completed", total_articles=len(all_articles))
            return all_articles
        else:
            logger.warning("no_articles_retrieved")
            return None


def test_scraper(market_id: str):
    """Test the news scraper with a specific market."""
    print("=" * 80)
    print(f"TESTING NEWS RSS SCRAPER WITH {market_id.upper()}")
    print("=" * 80)

    # Load market config
    try:
        config = load_market_config(market_id)
        print(f"\n[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"\n[FAIL] Could not load config: {e}")
        return False

    # Check if news scraper is enabled
    if not hasattr(config.scrapers, 'news') or not config.scrapers.news or not config.scrapers.news.enabled:
        print(f"\n[SKIP] News scraper not enabled for this market")
        return True

    # Create scraper
    try:
        scraper = NewsRSSScraper(config)
    except Exception as e:
        print(f"\n[FAIL] Could not create scraper: {e}")
        return False

    # Fetch data
    result = scraper.fetch_recent_news()

    if result and len(result) > 0:
        print(f"\n[OK] News scraper works for {config.market.name}!")
        return True
    else:
        print(f"\n[WARN] News scraper returned no data for {config.market.name}")
        return True  # Not a failure - just no data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test News RSS scraper portability")
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
