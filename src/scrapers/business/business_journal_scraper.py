"""
Business Journal/News RSS Scraper

Scrapes business news from RSS feeds.
Portable - works with any business news RSS feed URLs.
"""
import sys
import feedparser
import structlog
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from ...config import load_market_config, MarketConfig

logger = structlog.get_logger(__name__)


class BusinessArticle:
    """Business news article model."""

    def __init__(self, data: Dict):
        self.source = data.get('source', '')
        self.title = data.get('title', '')
        self.link = data.get('link', '')
        self.published = data.get('published', '')
        self.summary = data.get('summary', '')
        self.content = data.get('content', self.summary)

    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'title': self.title,
            'link': self.link,
            'published': self.published,
            'summary': self.summary[:200] if self.summary else '',
        }


class BusinessNewsScraper:
    """Business news scraper using RSS feeds."""

    def __init__(self, market_config: MarketConfig):
        self.config = market_config
        self.business_config = market_config.scrapers.business

        if not self.business_config or not self.business_config.enabled:
            raise ValueError("Business scraper not enabled in config")

        logger.info("business_scraper_initialized",
                   market=market_config.market.name,
                   feeds_count=len(self.business_config.feeds))

    def fetch_recent_news(self, max_articles_per_feed: int = 10) -> List[BusinessArticle]:
        """Fetch recent business news from all configured feeds."""
        all_articles = []

        for feed_name, feed_url in self.business_config.feeds.items():
            articles = self._fetch_feed(feed_url, feed_name, max_articles_per_feed)
            if articles:
                all_articles.extend(articles)
                logger.info("feed_fetched", feed=feed_name, articles_count=len(articles))
            else:
                logger.warning("feed_empty", feed=feed_name)

        logger.info("fetch_news_completed", total_articles=len(all_articles))
        return all_articles

    def _fetch_feed(self, feed_url: str, source: str, max_articles: int = 10) -> List[BusinessArticle]:
        """Fetch and parse a single RSS feed."""
        articles = []

        try:
            feed = feedparser.parse(feed_url)

            if not feed.entries:
                return []

            for entry in feed.entries[:max_articles]:
                try:
                    summary = ''
                    if hasattr(entry, 'summary'):
                        summary = entry.summary
                    elif hasattr(entry, 'description'):
                        summary = entry.description
                    elif hasattr(entry, 'content'):
                        summary = entry.content[0].value if entry.content else ''

                    published = ''
                    if hasattr(entry, 'published'):
                        published = entry.published
                    elif hasattr(entry, 'updated'):
                        published = entry.updated

                    article = BusinessArticle({
                        'source': source,
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link', ''),
                        'published': published,
                        'summary': summary,
                    })
                    articles.append(article)

                except Exception as e:
                    logger.warning("entry_parse_failed", source=source, error=str(e))
                    continue

        except Exception as e:
            logger.error("feed_fetch_failed", source=source, error=str(e))

        return articles


def test_scraper():
    """Test the business news scraper."""
    print("\n=== Testing Business News Scraper ===\n")

    try:
        config = load_market_config('gainesville_fl')
        print(f"[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"[FAIL] Failed to load config: {e}")
        return

    try:
        scraper = BusinessNewsScraper(config)
        print(f"[OK] Business scraper initialized")
        print(f"     Feeds: {len(scraper.business_config.feeds)}")
        for name in scraper.business_config.feeds.keys():
            print(f"       - {name}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize scraper: {e}")
        return

    print(f"\n[TEST] Fetching recent business news...")
    articles = scraper.fetch_recent_news(max_articles_per_feed=5)

    if articles:
        print(f"\n[SUCCESS] Fetched {len(articles)} business articles!")

        for i, article in enumerate(articles[:3]):
            print(f"\n--- Article {i+1} ---")
            print(f"Source: {article.source}")
            print(f"Title: {article.title}")
            print(f"Link: {article.link}")
            if article.published:
                print(f"Published: {article.published}")
            if article.summary:
                print(f"Summary: {article.summary[:150]}...")

        # Summary by source
        sources = {}
        for article in articles:
            sources[article.source] = sources.get(article.source, 0) + 1

        print(f"\n--- Summary ---")
        print(f"Total Articles: {len(articles)}")
        print(f"By Source:")
        for source, count in sources.items():
            print(f"  {source}: {count}")

    else:
        print(f"\n[WARN] No articles found")
        print(f"[INFO] This may be normal if:")
        print(f"       - RSS feeds have changed URLs")
        print(f"       - Feeds are temporarily down")
        print(f"       - Network issues")

    print(f"\n[INFO] Business scraper test complete")


if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    test_scraper()
