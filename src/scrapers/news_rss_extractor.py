"""
Gainesville News Monitor (RSS + Web Scraping)

Comprehensive local news collection for knowledge graph building.
Collects ALL local news to find hidden patterns and relationships.

Coverage: Local news, government, crime, weather, sports, business, education
Data Sources: WUFT News, Alachua Chronicle, Mainstreet Daily, Gainesville Sun, The Alligator
Update Frequency: Daily at 6:00 AM
Intelligence Value: Complete local knowledge graph for pattern detection
"""
import hashlib
import json
import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum

import aiohttp
import feedparser
from bs4 import BeautifulSoup, Comment
from dateutil import parser as date_parser
from pydantic import BaseModel, Field, validator
from readability.readability import Document

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class ArticleCategory(Enum):
    """Article categories for real estate intelligence."""
    BUSINESS = "business"
    DEVELOPMENT = "development"
    REAL_ESTATE = "real_estate"
    LOCAL_NEWS = "local_news"
    POLITICS = "politics"
    CONSTRUCTION = "construction"
    ZONING = "zoning"
    PERMITS = "permits"
    GENERAL = "general"


class NewsArticle(BaseModel):
    """Model for news article data."""
    article_id: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    published_date: datetime
    updated_date: Optional[datetime] = None
    source_name: str
    section: Optional[str] = None
    tags: Optional[List[str]] = None
    category: ArticleCategory = ArticleCategory.GENERAL
    word_count: int = 0
    reading_time_minutes: int = 0
    image_url: Optional[str] = None
    rss_feed_url: str

    @validator('published_date', 'updated_date', pre=True)
    def parse_dates(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                # Use dateutil parser for flexible date parsing
                return date_parser.parse(v)
            except (ValueError, TypeError):
                # Fallback to manual parsing
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
                    "%a, %d %b %Y %H:%M:%S %Z"
                ]:
                    try:
                        return datetime.strptime(v, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Unable to parse date: {v}")
        return v

    @validator('tags', pre=True)
    def parse_tags(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            # Handle comma-separated tags
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v

    @validator('word_count', 'reading_time_minutes', pre=True)
    def calculate_reading_metrics(cls, v, values, field):
        if field.name == 'word_count':
            content = values.get('content', '')
            return len(content.split()) if content else 0
        elif field.name == 'reading_time_minutes':
            word_count = values.get('word_count', 0)
            return max(1, round(word_count / 200))  # Average 200 words per minute
        return v

    def categorize_from_content(self) -> ArticleCategory:
        """Automatically categorize article based on title and content."""
        text = f"{self.title.lower()} {self.content.lower()}"

        # Keywords for different categories
        category_keywords = {
            ArticleCategory.DEVELOPMENT: [
                'development', 'developer', 'construction', 'building project',
                'new development', 'residential development', 'commercial development'
            ],
            ArticleCategory.REAL_ESTATE: [
                'real estate', 'property', 'housing market', 'home sales',
                'property values', 'mortgage', 'rental', 'apartment'
            ],
            ArticleCategory.CONSTRUCTION: [
                'construction', 'contractor', 'building', 'renovation',
                'infrastructure', 'road construction', 'bridge'
            ],
            ArticleCategory.ZONING: [
                'zoning', 'rezoning', 'land use', 'comprehensive plan',
                'zoning board', 'variance', 'special use permit'
            ],
            ArticleCategory.PERMITS: [
                'building permit', 'permit', 'planning commission',
                'site plan', 'subdivision', 'development order'
            ],
            ArticleCategory.BUSINESS: [
                'business', 'economy', 'economic development', 'jobs',
                'employment', 'industry', 'commercial', 'retail'
            ],
            ArticleCategory.POLITICS: [
                'city commission', 'county commission', 'mayor',
                'council', 'politics', 'election', 'government'
            ]
        }

        # Score each category
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score

        # Return category with highest score
        if category_scores:
            return max(category_scores, key=category_scores.get)

        return ArticleCategory.GENERAL


class RSSFeedConfig(BaseModel):
    """Configuration for RSS feed processing."""
    url: str = Field(..., min_length=1)
    source_name: str = Field(..., min_length=1)
    section: Optional[str] = None
    update_frequency_hours: int = Field(default=6, ge=1, le=24)
    max_articles_per_fetch: int = Field(default=50, ge=1, le=500)
    content_selectors: Optional[Dict[str, str]] = None  # CSS selectors for content extraction
    remove_selectors: Optional[List[str]] = None  # Elements to remove before extraction
    author_selectors: Optional[List[str]] = None
    date_selectors: Optional[List[str]] = None
    category_keywords: Optional[Dict[str, List[str]]] = None


class NewsRSSExtractor(ResilientScraper):
    """
    Comprehensive RSS news scraper with full article content extraction.

    Supports multiple news sources with configurable extraction rules.
    Uses RSS feeds to discover articles, then extracts full content from individual pages.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        rss_feeds: List[RSSFeedConfig],
        **kwargs
    ):
        super().__init__(
            scraper_id="news_rss_extractor",
            scraper_type=ScraperType.RSS,
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.rss_feeds = {feed.url: feed for feed in rss_feeds}

        # Default content extraction selectors
        self.default_content_selectors = [
            'article',
            '.article-content',
            '.entry-content',
            '.post-content',
            '.content',
            '[itemprop="articleBody"]',
            '.story-body',
            '.article-body'
        ]

        # Elements to remove (ads, navigation, etc.)
        self.default_remove_selectors = [
            '.advertisement', '.ad', '.ads',
            '.social-share', '.share-buttons',
            '.newsletter-signup',
            '.related-articles', '.recommended',
            '.comments', '.comment-form',
            'script', 'style', 'iframe',
            '.header', '.footer', '.nav', '.navigation'
        ]

        # Author selectors
        self.default_author_selectors = [
            '[itemprop="author"]',
            '.author', '.byline', '.by-author',
            '.article-author', '.story-author',
            '[rel="author"]'
        ]

        # Date selectors
        self.default_date_selectors = [
            '[itemprop="datePublished"]',
            '[itemprop="dateModified"]',
            '.published-date', '.publish-date',
            '.article-date', '.story-date',
            'time[datetime]', '.timestamp'
        ]

    async def scrape_all_feeds(self, max_articles_per_feed: Optional[int] = None) -> List[NewsArticle]:
        """
        Scrape all configured RSS feeds and extract article content.

        Args:
            max_articles_per_feed: Override max articles per feed limit
        """
        all_articles = []

        for rss_url, feed_config in self.rss_feeds.items():
            try:
                self.logger.info(f"Processing RSS feed: {rss_url}")

                articles = await self.scrape_rss_feed(
                    feed_config,
                    max_articles=max_articles_per_feed or feed_config.max_articles_per_fetch
                )

                all_articles.extend(articles)

                # Rate limiting between feeds
                await self.rate_limiter.acquire(self.scraper_id)

            except Exception as e:
                self.logger.error(f"Failed to process RSS feed {rss_url}: {e}")
                continue

        self.logger.info(f"Scraped {len(all_articles)} articles from {len(self.rss_feeds)} RSS feeds")
        return all_articles

    async def scrape_rss_feed(self, feed_config: RSSFeedConfig, max_articles: int = 50) -> List[NewsArticle]:
        """
        Scrape articles from a single RSS feed.

        Args:
            feed_config: RSS feed configuration
            max_articles: Maximum articles to process from this feed
        """
        # Fetch RSS feed
        rss_result = await self.scrape(feed_config.url)
        if not rss_result.success:
            self.logger.error(f"Failed to fetch RSS feed {feed_config.url}: {rss_result.error}")
            return []

        # Parse RSS feed
        try:
            feed_data = feedparser.parse(rss_result.data)
        except Exception as e:
            self.logger.error(f"Failed to parse RSS feed {feed_config.url}: {e}")
            return []

        if not feed_data.entries:
            self.logger.warning(f"No entries found in RSS feed {feed_config.url}")
            return []

        # Extract articles from RSS entries
        articles = []
        entries_to_process = feed_data.entries[:max_articles]

        self.logger.info(f"Processing {len(entries_to_process)} entries from {feed_config.source_name}")

        for entry in entries_to_process:
            try:
                article = await self.extract_article_from_entry(entry, feed_config)
                if article:
                    articles.append(article)

                # Rate limiting between articles
                await self.rate_limiter.acquire(self.scraper_id)

            except Exception as e:
                self.logger.warning(f"Failed to extract article from entry {entry.get('link', 'unknown')}: {e}")
                continue

        return articles

    async def extract_article_from_entry(self, entry: Dict[str, Any], feed_config: RSSFeedConfig) -> Optional[NewsArticle]:
        """
        Extract full article content from RSS entry.

        Args:
            entry: RSS feed entry
            feed_config: Configuration for this feed
        """
        # Get article URL
        article_url = entry.get('link')
        if not article_url:
            return None

        # Check if we've already processed this article recently
        article_id = self._generate_article_id(article_url)
        if await self._is_article_recently_processed(article_id):
            return None

        # Fetch full article content
        article_result = await self.scrape(article_url)
        if not article_result.success:
            self.logger.warning(f"Failed to fetch article content: {article_url}")
            return None

        # Extract article metadata and content
        try:
            article_data = await self._extract_article_data(
                article_result.data, entry, feed_config, article_url
            )

            if not article_data:
                return None

            # Auto-categorize article
            article = NewsArticle(**article_data)
            article.category = article.categorize_from_content()

            return article

        except Exception as e:
            self.logger.error(f"Failed to extract article data from {article_url}: {e}")
            return None

    async def _extract_article_data(
        self,
        html_content: str,
        rss_entry: Dict[str, Any],
        feed_config: RSSFeedConfig,
        article_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract structured data from article HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove unwanted elements
        remove_selectors = feed_config.remove_selectors or self.default_remove_selectors
        for selector in remove_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Extract title
        title = self._extract_title(soup, rss_entry)
        if not title:
            return None

        # Extract content
        content = self._extract_content(soup, feed_config)
        if not content or len(content.strip()) < 100:  # Skip articles that are too short
            return None

        # Extract metadata
        author = self._extract_author(soup, feed_config)
        published_date = self._extract_date(soup, rss_entry, feed_config)
        image_url = self._extract_image(soup, rss_entry)
        summary = self._extract_summary(rss_entry, content)

        return {
            'article_id': self._generate_article_id(article_url),
            'url': article_url,
            'title': title,
            'content': content,
            'summary': summary,
            'author': author,
            'published_date': published_date or datetime.utcnow(),
            'source_name': feed_config.source_name,
            'section': feed_config.section,
            'tags': self._extract_tags(rss_entry),
            'image_url': image_url,
            'rss_feed_url': feed_config.url
        }

    def _extract_title(self, soup: BeautifulSoup, rss_entry: Dict[str, Any]) -> Optional[str]:
        """Extract article title."""
        # Try RSS entry title first
        if 'title' in rss_entry and rss_entry['title'].strip():
            return rss_entry['title'].strip()

        # Try HTML meta tags and headers
        selectors = [
            'h1',
            '[itemprop="headline"]',
            '.article-title', '.story-title',
            'title'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()

        return None

    def _extract_content(self, soup: BeautifulSoup, feed_config: RSSFeedConfig) -> Optional[str]:
        """Extract main article content."""
        # Try configured selectors first
        if feed_config.content_selectors:
            for selector_name, selector in feed_config.content_selectors.items():
                elements = soup.select(selector)
                if elements:
                    content_parts = []
                    for element in elements:
                        text = element.get_text(separator=' ', strip=True)
                        if text:
                            content_parts.append(text)
                    if content_parts:
                        return '\n\n'.join(content_parts)

        # Try default selectors
        for selector in self.default_content_selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator=' ', strip=True)
                if len(content) > 200:  # Ensure we have substantial content
                    return content

        # Fallback: Use readability library
        try:
            doc = Document(str(soup))
            readable_content = BeautifulSoup(doc.summary(), 'html.parser')
            content = readable_content.get_text(separator=' ', strip=True)
            if len(content) > 200:
                return content
        except Exception as e:
            self.logger.debug(f"Readability extraction failed: {e}")

        return None

    def _extract_author(self, soup: BeautifulSoup, feed_config: RSSFeedConfig) -> Optional[str]:
        """Extract article author."""
        # Try configured selectors
        author_selectors = feed_config.author_selectors or self.default_author_selectors

        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                author = element.get_text().strip()
                if author and not any(skip in author.lower() for skip in ['staff', 'editor', 'by ']):
                    # Clean author name
                    author = re.sub(r'^by\s+', '', author, flags=re.IGNORECASE)
                    return author

        return None

    def _extract_date(
        self,
        soup: BeautifulSoup,
        rss_entry: Dict[str, Any],
        feed_config: RSSFeedConfig
    ) -> Optional[datetime]:
        """Extract article publication date."""
        # Try RSS entry date first
        for date_field in ['published', 'updated', 'published_parsed']:
            if date_field in rss_entry and rss_entry[date_field]:
                try:
                    if hasattr(rss_entry[date_field], 'timetuple'):
                        return datetime(*rss_entry[date_field][:6])
                    else:
                        return date_parser.parse(str(rss_entry[date_field]))
                except (ValueError, TypeError):
                    continue

        # Try HTML selectors
        date_selectors = feed_config.date_selectors or self.default_date_selectors

        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                # Try datetime attribute first
                date_str = element.get('datetime') or element.get('content') or element.get_text()
                if date_str:
                    try:
                        return date_parser.parse(date_str)
                    except (ValueError, TypeError):
                        continue

        return None

    def _extract_image(self, soup: BeautifulSoup, rss_entry: Dict[str, Any]) -> Optional[str]:
        """Extract main article image."""
        # Try RSS entry media
        if hasattr(rss_entry, 'media_content') and rss_entry.media_content:
            return rss_entry.media_content[0].get('url')

        # Try HTML selectors
        selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.article-image img', '.story-image img',
            'img[itemprop="image"]',
            'article img:first-of-type'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                img_url = element.get('content') or element.get('src')
                if img_url:
                    # Convert relative URLs to absolute
                    return urllib.parse.urljoin(rss_entry.get('link', ''), img_url)

        return None

    def _extract_summary(self, rss_entry: Dict[str, Any], content: str) -> Optional[str]:
        """Extract or generate article summary."""
        # Try RSS summary/description first
        if 'summary' in rss_entry and rss_entry['summary'].strip():
            return BeautifulSoup(rss_entry['summary'], 'html.parser').get_text().strip()

        # Generate summary from first paragraph of content
        if content:
            sentences = content.split('. ')
            if len(sentences) >= 2:
                summary = '. '.join(sentences[:2]) + '.'
                if len(summary) < 300:
                    return summary

        return None

    def _extract_tags(self, rss_entry: Dict[str, Any]) -> Optional[List[str]]:
        """Extract article tags from RSS entry."""
        tags = []

        # Try RSS tags
        if hasattr(rss_entry, 'tags') and rss_entry.tags:
            tags.extend([tag.term for tag in rss_entry.tags if hasattr(tag, 'term')])

        # Try categories
        if hasattr(rss_entry, 'categories') and rss_entry.categories:
            tags.extend(rss_entry.categories)

        return tags if tags else None

    def _generate_article_id(self, url: str) -> str:
        """Generate unique article ID from URL."""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    async def _is_article_recently_processed(self, article_id: str, hours: int = 24) -> bool:
        """Check if article was processed recently to avoid duplicates."""
        try:
            cache_key = f"article_processed:{article_id}"
            cached = await self.redis.get(cache_key)
            return cached is not None
        except Exception:
            return False

    async def monitor_new_articles(self) -> List[NewsArticle]:
        """Monitor for new articles across all RSS feeds."""
        all_new_articles = []

        for feed_config in self.rss_feeds.values():
            try:
                # Check for changes in RSS feed
                change_result = await self.change_detector.track_content_change(
                    url=feed_config.url,
                    content=b"",  # Will be filled by scraper
                    metadata={"scraper": self.scraper_id, "check_type": "monitor", "feed": feed_config.source_name}
                )

                # If changes detected, scrape recent articles
                if change_result.change_type.value != "unchanged":
                    new_articles = await self.scrape_rss_feed(feed_config, max_articles=10)
                    all_new_articles.extend(new_articles)

            except Exception as e:
                self.logger.error(f"Failed to monitor feed {feed_config.url}: {e}")
                continue

        return all_new_articles

    async def store_articles(self, articles: List[NewsArticle]) -> int:
        """Store articles in database as raw facts."""
        if not articles:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for article in articles:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "article_data": article.dict(),
                        "scraped_from": "rss_news_feed",
                        "scraper_version": "1.0",
                        "processing_notes": {
                            "data_quality": "extracted_from_rss_and_html",
                            "confidence": 0.95,
                            "source_type": "news_article",
                            "category": article.category.value,
                            "word_count": article.word_count
                        }
                    }

                    # Calculate content hash for deduplication
                    content_str = json.dumps(fact_data, sort_keys=True, default=str)
                    content_hash = hashlib.md5(content_str.encode()).hexdigest()

                    # Insert raw fact
                    query = """
                        INSERT INTO raw_facts (
                            fact_type, source_url, scraped_at, parser_version,
                            raw_content, content_hash, processed_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (content_hash) DO NOTHING
                        RETURNING id
                    """

                    result = await session.execute(
                        query,
                        "news_article",
                        article.url,
                        datetime.utcnow(),
                        "rss_news_v1.0",
                        json.dumps(fact_data),
                        content_hash,
                        datetime.utcnow()
                    )

                    if result.rowcount > 0:
                        stored_count += 1

                        # Create structured fact
                        raw_fact_id = (await result.fetchone())['id']

                        structured_query = """
                            INSERT INTO structured_facts (
                                raw_fact_id, entity_type, structured_data, extraction_confidence
                            ) VALUES ($1, $2, $3, $4)
                        """

                        await session.execute(
                            structured_query,
                            raw_fact_id,
                            "news_article",
                            json.dumps(article.dict(), default=str),
                            0.95  # High confidence for extracted news articles
                        )

                        # Cache that we've processed this article
                        cache_key = f"article_processed:{article.article_id}"
                        try:
                            await self.redis.setex(cache_key, 86400, "1")  # 24 hour cache
                        except Exception:
                            pass  # Non-critical cache operation

                except Exception as e:
                    self.logger.error(f"Failed to store article {article.url}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new articles")
        return stored_count

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process RSS feed or HTML response."""
        content_type = response.headers.get('Content-Type', '').lower()

        if 'xml' in content_type or 'rss' in content_type:
            # RSS feed content - return raw bytes for feedparser
            return content
        else:
            # HTML content - return as string
            return content.decode('utf-8', errors='ignore')


async def create_news_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    rss_feeds: List[RSSFeedConfig],
    **kwargs
) -> NewsRSSExtractor:
    """Factory function to create configured news RSS scraper."""
    scraper = NewsRSSExtractor(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        rss_feeds=rss_feeds,
        **kwargs
    )
    await scraper.initialize()
    return scraper


# Pre-configured Gainesville news feeds
DEFAULT_NEWS_FEEDS = [
    RSSFeedConfig(
        url="https://www.wuft.org/news/feed/",
        source_name="WUFT News",
        section="local_news",
        update_frequency_hours=6,
        max_articles_per_fetch=30,
        content_selectors={"article": [".entry-content", ".post-content", "article"]},
        remove_selectors=[".social-share", ".advertisement", ".newsletter-signup"]
    ),
    RSSFeedConfig(
        url="https://alachuachronicle.com/feed/",
        source_name="Alachua Chronicle",
        section="county_news",
        update_frequency_hours=12,
        max_articles_per_fetch=25,
        content_selectors={"article": [".entry-content", ".post-content", "article"]},
        remove_selectors=[".social-share", ".advertisement", ".newsletter-signup"]
    ),
    RSSFeedConfig(
        url="https://mainstreetdailynews.com/feed/",
        source_name="Mainstreet Daily News",
        section="local_news",
        update_frequency_hours=8,
        max_articles_per_fetch=20,
        content_selectors={"article": [".entry-content", ".post-content", "article"]},
        remove_selectors=[".social-share", ".advertisement", ".newsletter-signup"]
    )
]

# HTML scraping sources (no RSS feeds)
DEFAULT_HTML_SOURCES = [
    {
        "url": "https://www.gainesville.com/news/",
        "source_name": "Gainesville Sun",
        "section": "local_news",
        "article_selectors": [".story-card a", ".headline a", "h3 a"],
        "content_selectors": [".story-body", ".article-content", ".entry-content"],
        "max_articles": 15
    },
    {
        "url": "https://alligator.org/section/news/",
        "source_name": "The Alligator",
        "section": "university_news",
        "article_selectors": [".story-headline a", ".article-title a", "h2 a"],
        "content_selectors": [".story-content", ".article-content", ".entry-content"],
        "max_articles": 10
    }
]