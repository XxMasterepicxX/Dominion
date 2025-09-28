"""Florida business intelligence scraper for Gainesville area."""

import json
import asyncio
import aiohttp
import feedparser
import re
from datetime import datetime, timedelta
from typing import List
from bs4 import BeautifulSoup

from .news_rss_extractor import NewsRSSExtractor, NewsArticle, RSSFeedConfig, ArticleCategory
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class BusinessJournalScraper(NewsRSSExtractor):
    """Business journal scraper optimized for Florida real estate intelligence."""

    def __init__(self, db_manager: DatabaseManager, change_detector: ChangeDetector,
                 business_journal_feeds: List[RSSFeedConfig], **kwargs):
        super().__init__(
            db_manager=db_manager,
            change_detector=change_detector,
            rss_feeds=business_journal_feeds,
            **kwargs
        )
        self.scraper_id = "business_journal_scraper"

    async def scrape_business_articles(self, max_articles_per_feed: int = 25) -> List[NewsArticle]:
        """Scrape business articles from RSS and Florida Trend."""
        rss_articles = await self._scrape_rss_summaries_only(max_articles_per_feed)
        trend_articles = await self._scrape_florida_trend_weekly()

        all_articles = rss_articles + trend_articles
        for article in all_articles:
            article.tags = self._find_keywords(article.content)

        self.logger.info(f"Scraped {len(all_articles)} total articles ({len(rss_articles)} RSS + {len(trend_articles)} Florida Trend)")
        return all_articles

    async def _scrape_rss_summaries_only(self, max_articles_per_feed: int) -> List[NewsArticle]:
        """Scrape RSS feeds using summaries only."""
        all_articles = []

        for rss_url, feed_config in self.rss_feeds.items():
            try:
                feed = feedparser.parse(rss_url)
                if not feed.entries:
                    continue

                for entry in feed.entries[:max_articles_per_feed]:
                    try:
                        article = NewsArticle(
                            article_id=self._generate_article_id(entry.link),
                            url=entry.link,
                            title=entry.title,
                            content=getattr(entry, 'summary', ''),
                            summary=getattr(entry, 'summary', ''),
                            published_date=entry.get('published', datetime.utcnow()),
                            source_name=feed_config.source_name,
                            section=feed_config.section,
                            category=ArticleCategory.REAL_ESTATE,
                            rss_feed_url=rss_url
                        )
                        all_articles.append(article)
                    except Exception as e:
                        self.logger.warning(f"Failed to process RSS entry: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Failed to process RSS feed {rss_url}: {e}")
                continue

        return all_articles

    async def _scrape_florida_trend_weekly(self) -> List[NewsArticle]:
        """Scrape Florida Trend weekly using Monday-only discovery."""
        articles = []
        article_urls = await self._discover_florida_trend_articles()

        if not article_urls:
            return articles

        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(article_urls[:3]):
                try:
                    if i > 0:
                        await asyncio.sleep(3)

                    async with session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}) as response:
                        if response.status == 200:
                            html = await response.text()
                            date_match = re.search(r'/(\d{4}/\d{2}/\d{2})/', url)
                            date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y/%m/%d")
                            briefs = self._parse_florida_trend_briefs(html, url, date_str)
                            articles.extend(briefs)
                        elif response.status == 429:
                            break
                except Exception:
                    continue

        return articles

    async def _discover_florida_trend_articles(self) -> List[str]:
        """Discover Florida Trend articles using Monday-only pattern."""
        article_urls = []
        base_date = datetime.now()
        days_since_monday = (base_date.weekday() - 0) % 7
        last_monday = base_date - timedelta(days=days_since_monday)

        for week in range(8):
            monday = last_monday - timedelta(weeks=week)
            date_str = monday.strftime("%Y/%m/%d")
            patterns = [
                f"https://www.floridatrend.com/realestate/{date_str}/florida-trend-real-estate/",
                f"https://www.floridatrend.com/realestate/{date_str}/florida-real-estate/"
            ]
            article_urls.extend(patterns)

        found_urls = []
        try:
            async with aiohttp.ClientSession() as session:
                for url in article_urls:
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                found_urls.append(url)
                            elif response.status == 429:
                                break
                            await asyncio.sleep(1)
                    except:
                        continue
            return found_urls
        except:
            return []

    def _parse_florida_trend_briefs(self, html: str, source_url: str, date_str: str) -> List[NewsArticle]:
        """Parse briefs from Florida Trend weekly roundup."""
        soup = BeautifulSoup(html, 'html.parser')
        full_text = soup.get_text()
        source_pattern = r'\[Source: ([^\]]+)\]'
        parts = re.split(source_pattern, full_text)
        articles = []

        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                try:
                    text = parts[i].strip()
                    source = parts[i + 1].strip()

                    if len(text) < 50 or not any(word in text.lower() for word in ['florida', 'real estate', 'property', 'housing']):
                        continue

                    lines = text.split('\n')
                    title_line = lines[0] if lines else text
                    title = title_line.split('.')[0] if '.' in title_line else title_line[:100]
                    title = title.strip()

                    if len(title) < 10:
                        continue

                    article = NewsArticle(
                        article_id=self._generate_article_id(source_url + str(i)),
                        url=source_url,
                        title=title,
                        content=text,
                        summary=text[:200],
                        published_date=datetime.strptime(date_str, "%Y/%m/%d"),
                        source_name=f"Florida Trend via {source}",
                        section="development",
                        category=ArticleCategory.REAL_ESTATE,
                        rss_feed_url=""
                    )
                    articles.append(article)
                except:
                    continue

        return articles

    def _find_keywords(self, text: str) -> List[str]:
        """Find relevant keywords in text."""
        content_lower = text.lower()
        keywords = [
            'real estate development', 'commercial development', 'residential development',
            'construction project', 'building permit', 'development agreement',
            'zoning change', 'land acquisition', 'property investment',
            'gainesville', 'alachua county', 'north central florida',
            'property tax', 'homestead exemption', 'impact fees',
            'live local act', 'florida housing', 'property insurance',
            'manufactured homes', 'build-to-rent', 'affordable housing',
            'foreclosure', 'mortgage rates', 'home sales', 'market trends',
            'rental rates', 'housing inventory', 'construction costs',
            'property values', 'housing demand', 'development permits'
        ]
        return [kw for kw in keywords if kw in content_lower]

    def _generate_article_id(self, url: str) -> str:
        """Generate unique article ID from URL."""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]

    async def store_business_articles(self, articles: List[NewsArticle]) -> int:
        """Store business articles in database."""
        if not articles:
            return 0

        stored_count = 0
        async with self.db_manager.get_session() as session:
            for article in articles:
                try:
                    fact_data = {
                        "article_data": article.dict(),
                        "scraped_from": "business_journal_rss",
                        "scraper_version": "2.0_optimized"
                    }

                    content_str = json.dumps(fact_data, sort_keys=True, default=str)
                    import hashlib
                    content_hash = hashlib.md5(content_str.encode()).hexdigest()

                    query = """
                        INSERT INTO raw_facts (
                            fact_type, source_url, scraped_at, parser_version,
                            raw_content, content_hash, processed_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (content_hash) DO NOTHING
                        RETURNING id
                    """

                    result = await session.execute(
                        query, "business_news_article", article.url, datetime.utcnow(),
                        "business_journal_v2.0", json.dumps(fact_data), content_hash, datetime.utcnow()
                    )

                    if result.rowcount > 0:
                        stored_count += 1

                except Exception as e:
                    self.logger.error(f"Failed to store article {article.url}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new business articles")
        return stored_count


# Pre-configured Florida business feeds
DEFAULT_BUSINESS_FEEDS = [
    RSSFeedConfig(
        url="https://www.floridarealtors.org/news-media/rss.xml",
        source_name="Florida Realtors",
        section="market_data",
        update_frequency_hours=12,
        max_articles_per_fetch=20,
        content_selectors={"article": [".entry-content", ".post-content", "article"]},
        remove_selectors=[".social-share", ".advertisement", ".newsletter-signup"]
    )
]