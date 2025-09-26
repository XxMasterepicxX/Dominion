"""
Business Journal News Scraper

Tracks business news focusing on real estate development, commercial property,
construction industry, and economic development in Gainesville area.

Coverage: Commercial real estate, development projects, business partnerships
Data Source: Local business journals, trade publications
Update Frequency: Daily
Intelligence Value: Commercial development intelligence and business relationship mapping
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from pydantic import BaseModel, Field, validator

from .news_rss_extractor import NewsRSSExtractor, NewsArticle, RSSFeedConfig, ArticleCategory
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class BusinessTopicRelevance(Enum):
    """Relevance levels for business articles to real estate intelligence."""
    HIGHLY_RELEVANT = "highly_relevant"      # Direct real estate/development content
    MODERATELY_RELEVANT = "moderately_relevant"  # Business/economic content that affects RE
    SOMEWHAT_RELEVANT = "somewhat_relevant"  # General business news
    NOT_RELEVANT = "not_relevant"           # Unrelated content


class BusinessJournalArticle(NewsArticle):
    """Extended model for business journal articles with real estate intelligence scoring."""
    business_relevance: BusinessTopicRelevance = BusinessTopicRelevance.NOT_RELEVANT
    development_keywords_found: List[str] = Field(default_factory=list)
    commercial_property_mentioned: bool = False
    financial_figures_extracted: Optional[Dict[str, float]] = None
    company_names_mentioned: List[str] = Field(default_factory=list)
    location_mentioned: Optional[str] = None
    project_name: Optional[str] = None

    def analyze_business_relevance(self) -> BusinessTopicRelevance:
        """Analyze article content to determine relevance to real estate intelligence."""
        title_content = f"{self.title.lower()} {self.content.lower()}"

        # High relevance keywords
        high_relevance_keywords = [
            'real estate development', 'commercial development', 'residential development',
            'construction project', 'building permit', 'development agreement',
            'zoning change', 'land acquisition', 'property investment',
            'commercial real estate', 'office building', 'retail development',
            'mixed-use development', 'apartment complex', 'shopping center',
            'industrial park', 'warehouse development', 'hotel development'
        ]

        # Moderate relevance keywords
        moderate_relevance_keywords = [
            'economic development', 'job creation', 'business expansion',
            'corporate headquarters', 'manufacturing facility', 'distribution center',
            'infrastructure project', 'public-private partnership',
            'tax incentives', 'development authority', 'enterprise zone',
            'chamber of commerce', 'business park', 'technology corridor'
        ]

        # Some relevance keywords
        some_relevance_keywords = [
            'business growth', 'company expansion', 'new business',
            'employment', 'workforce', 'startup', 'venture capital',
            'merger', 'acquisition', 'investment', 'funding'
        ]

        # Count keyword matches
        high_score = sum(1 for keyword in high_relevance_keywords if keyword in title_content)
        moderate_score = sum(1 for keyword in moderate_relevance_keywords if keyword in title_content)
        some_score = sum(1 for keyword in some_relevance_keywords if keyword in title_content)

        # Store found keywords for analysis
        found_keywords = []
        for keyword in high_relevance_keywords + moderate_relevance_keywords + some_relevance_keywords:
            if keyword in title_content:
                found_keywords.append(keyword)

        self.development_keywords_found = found_keywords

        # Determine relevance score
        if high_score >= 2 or (high_score >= 1 and moderate_score >= 1):
            return BusinessTopicRelevance.HIGHLY_RELEVANT
        elif high_score >= 1 or moderate_score >= 2:
            return BusinessTopicRelevance.MODERATELY_RELEVANT
        elif moderate_score >= 1 or some_score >= 2:
            return BusinessTopicRelevance.SOMEWHAT_RELEVANT
        else:
            return BusinessTopicRelevance.NOT_RELEVANT

    def extract_financial_figures(self) -> Dict[str, float]:
        """Extract financial figures mentioned in the article."""
        figures = {}
        content = f"{self.title} {self.content}"

        # Patterns for financial figures
        patterns = {
            'investment_amount': r'\$([0-9,]+(?:\.[0-9]+)?)\s*(?:million|billion|M|B)?\s*(?:investment|funding|capital|raised)',
            'project_cost': r'\$([0-9,]+(?:\.[0-9]+)?)\s*(?:million|billion|M|B)?\s*(?:project|cost|budget)',
            'square_footage': r'([0-9,]+)\s*(?:square\s*feet|sq\s*ft|sf)',
            'acreage': r'([0-9,]+(?:\.[0-9]+)?)\s*acres?',
            'units': r'([0-9,]+)\s*(?:units|apartments|homes|condos)',
            'jobs': r'([0-9,]+)\s*(?:jobs|positions|employees)'
        }

        for figure_type, pattern in patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    value_str = match.group(1).replace(',', '')
                    value = float(value_str)

                    # Convert millions/billions
                    if 'million' in match.group(0).lower() or 'M' in match.group(0):
                        value *= 1_000_000
                    elif 'billion' in match.group(0).lower() or 'B' in match.group(0):
                        value *= 1_000_000_000

                    figures[figure_type] = value
                    break  # Take first match of each type
                except (ValueError, IndexError):
                    continue

        return figures if figures else None

    def extract_company_names(self) -> List[str]:
        """Extract company names mentioned in the article."""
        content = f"{self.title} {self.content}"

        # Common business entity suffixes
        entity_patterns = [
            r'([A-Z][a-zA-Z\s&]+(?:Inc\.?|LLC|Corp\.?|Corporation|Company|Co\.?|Ltd\.?))',
            r'([A-Z][a-zA-Z\s&]+ (?:Group|Holdings|Enterprises|Partners|Development|Construction|Properties|Realty))',
            r'([A-Z][a-zA-Z\s&]+ (?:Real Estate|Developers?|Builders?))'
        ]

        companies = set()
        for pattern in entity_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                company_name = match.group(1).strip()
                if len(company_name) > 3 and len(company_name) < 100:  # Reasonable length
                    companies.add(company_name)

        return list(companies)

    def detect_commercial_property_mention(self) -> bool:
        """Detect if commercial property types are mentioned."""
        content = f"{self.title.lower()} {self.content.lower()}"

        commercial_keywords = [
            'office building', 'retail space', 'shopping center', 'mall',
            'warehouse', 'industrial', 'commercial property', 'business park',
            'hotel', 'restaurant', 'store', 'plaza', 'strip center',
            'medical office', 'flex space', 'data center', 'logistics center'
        ]

        return any(keyword in content for keyword in commercial_keywords)

    def extract_location_and_project(self) -> tuple[Optional[str], Optional[str]]:
        """Extract location and project name if mentioned."""
        content = f"{self.title} {self.content}"

        # Look for project names (often in quotes or capitalized)
        project_patterns = [
            r'"([A-Z][^"]*(?:Plaza|Center|Park|Commons|Square|Place|Point|Grove|Village|District|Quarter))"',
            r'([A-Z][a-zA-Z\s]*(?:Plaza|Center|Park|Commons|Square|Place|Point|Grove|Village|District|Quarter))',
        ]

        project_name = None
        for pattern in project_patterns:
            match = re.search(pattern, content)
            if match:
                project_name = match.group(1).strip()
                break

        # Look for locations (cities, neighborhoods)
        location_patterns = [
            r'in ([A-Z][a-zA-Z\s]+(?:, FL|, Florida))',
            r'([A-Z][a-zA-Z\s]+) area',
            r'downtown ([A-Z][a-zA-Z]+)',
            r'([A-Z][a-zA-Z]+) market'
        ]

        location = None
        for pattern in location_patterns:
            match = re.search(pattern, content)
            if match:
                location = match.group(1).strip()
                break

        return location, project_name


class BusinessJournalScraper(NewsRSSExtractor):
    """
    Specialized scraper for business journals focusing on real estate and development news.

    Extends the RSS news scraper with business intelligence analysis and
    real estate relevance scoring.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        business_journal_feeds: List[RSSFeedConfig],
        min_relevance_threshold: BusinessTopicRelevance = BusinessTopicRelevance.SOMEWHAT_RELEVANT,
        **kwargs
    ):
        super().__init__(
            db_manager=db_manager,
            change_detector=change_detector,
            rss_feeds=business_journal_feeds,
            **kwargs
        )
        self.scraper_id = "business_journal_scraper"
        self.min_relevance_threshold = min_relevance_threshold

        # Business-specific content selectors
        self.business_content_selectors = [
            '.article-content', '.story-content', '.entry-content',
            '[itemprop="articleBody"]', '.post-body', '.article-body',
            '.content-body', '.article-text', '.story-text'
        ]

        # Business journal specific elements to remove
        self.business_remove_selectors = [
            '.sidebar', '.related-content', '.newsletter-signup',
            '.subscription-wall', '.paywall', '.premium-content',
            '.social-sharing', '.comment-section', '.author-bio-long',
            '.advertisement', '.sponsored-content', '.native-ad'
        ]

    async def scrape_business_articles(
        self,
        focus_topics: Optional[List[str]] = None,
        max_articles_per_feed: int = 25
    ) -> List[BusinessJournalArticle]:
        """
        Scrape business journal articles with focus on real estate development topics.

        Args:
            focus_topics: List of specific topics to prioritize
            max_articles_per_feed: Maximum articles per RSS feed
        """
        # Update content selectors for business journals
        self.default_content_selectors = self.business_content_selectors
        self.default_remove_selectors.extend(self.business_remove_selectors)

        # Scrape articles using parent class
        raw_articles = await self.scrape_all_feeds(max_articles_per_feed)

        # Convert to business journal articles with analysis
        business_articles = []
        for article in raw_articles:
            try:
                # Convert to business journal article
                business_article = BusinessJournalArticle(
                    **article.dict(),
                    business_relevance=BusinessTopicRelevance.NOT_RELEVANT,
                    development_keywords_found=[],
                    commercial_property_mentioned=False,
                    financial_figures_extracted=None,
                    company_names_mentioned=[],
                    location_mentioned=None,
                    project_name=None
                )

                # Analyze business relevance
                business_article.business_relevance = business_article.analyze_business_relevance()

                # Skip articles below relevance threshold
                if self._is_below_threshold(business_article.business_relevance):
                    continue

                # Extract business intelligence
                business_article.financial_figures_extracted = business_article.extract_financial_figures()
                business_article.company_names_mentioned = business_article.extract_company_names()
                business_article.commercial_property_mentioned = business_article.detect_commercial_property_mention()

                location, project = business_article.extract_location_and_project()
                business_article.location_mentioned = location
                business_article.project_name = project

                # Focus on specified topics if provided
                if focus_topics and not self._matches_focus_topics(business_article, focus_topics):
                    continue

                business_articles.append(business_article)

            except Exception as e:
                self.logger.warning(f"Failed to analyze business article {article.url}: {e}")
                continue

        self.logger.info(f"Processed {len(business_articles)} relevant business articles from {len(raw_articles)} total")
        return business_articles

    async def get_development_news_summary(self, days_back: int = 7) -> Dict[str, Any]:
        """Get summary of recent development-related business news."""

        # Get articles from recent period
        articles = await self.scrape_business_articles(max_articles_per_feed=50)

        # Filter to recent articles
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_articles = [
            article for article in articles
            if article.published_date >= cutoff_date
        ]

        # Analyze trends
        summary = {
            'total_articles': len(recent_articles),
            'by_relevance': {},
            'by_category': {},
            'financial_highlights': {},
            'top_companies': {},
            'locations_mentioned': {},
            'development_keywords': {},
            'period_days': days_back
        }

        # Count by relevance
        for article in recent_articles:
            relevance = article.business_relevance.value
            summary['by_relevance'][relevance] = summary['by_relevance'].get(relevance, 0) + 1

            # Count by category
            category = article.category.value
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1

            # Aggregate financial figures
            if article.financial_figures_extracted:
                for figure_type, value in article.financial_figures_extracted.items():
                    if figure_type not in summary['financial_highlights']:
                        summary['financial_highlights'][figure_type] = []
                    summary['financial_highlights'][figure_type].append(value)

            # Count company mentions
            for company in article.company_names_mentioned:
                summary['top_companies'][company] = summary['top_companies'].get(company, 0) + 1

            # Count location mentions
            if article.location_mentioned:
                location = article.location_mentioned
                summary['locations_mentioned'][location] = summary['locations_mentioned'].get(location, 0) + 1

            # Count development keywords
            for keyword in article.development_keywords_found:
                summary['development_keywords'][keyword] = summary['development_keywords'].get(keyword, 0) + 1

        # Calculate financial summaries
        for figure_type, values in summary['financial_highlights'].items():
            summary['financial_highlights'][figure_type] = {
                'total': sum(values),
                'average': sum(values) / len(values) if values else 0,
                'count': len(values),
                'max': max(values) if values else 0
            }

        return summary

    async def monitor_development_alerts(
        self,
        alert_keywords: Optional[List[str]] = None,
        min_investment_amount: Optional[float] = None
    ) -> List[BusinessJournalArticle]:
        """
        Monitor for high-priority development alerts based on criteria.

        Args:
            alert_keywords: Keywords that trigger alerts
            min_investment_amount: Minimum investment amount to trigger alert
        """
        # Default alert keywords
        if not alert_keywords:
            alert_keywords = [
                'major development', 'billion dollar', 'mega project',
                'downtown development', 'mixed-use development',
                'rezoning approved', 'development agreement signed',
                'groundbreaking', 'construction begins'
            ]

        # Get recent articles
        articles = await self.scrape_business_articles(max_articles_per_feed=20)

        alert_articles = []
        for article in articles:
            # Check for high relevance
            if article.business_relevance != BusinessTopicRelevance.HIGHLY_RELEVANT:
                continue

            # Check alert keywords
            content_text = f"{article.title.lower()} {article.content.lower()}"
            keyword_match = any(keyword.lower() in content_text for keyword in alert_keywords)

            # Check investment amount
            investment_match = False
            if article.financial_figures_extracted and min_investment_amount:
                for figure_type, amount in article.financial_figures_extracted.items():
                    if figure_type in ['investment_amount', 'project_cost'] and amount >= min_investment_amount:
                        investment_match = True
                        break

            # Add to alerts if criteria met
            if keyword_match or investment_match:
                alert_articles.append(article)

        return alert_articles

    async def store_business_articles(self, articles: List[BusinessJournalArticle]) -> int:
        """Store business articles with enhanced metadata."""
        if not articles:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for article in articles:
                try:
                    # Create enhanced fact data
                    fact_data = {
                        "article_data": article.dict(),
                        "scraped_from": "business_journal_rss",
                        "scraper_version": "1.0",
                        "processing_notes": {
                            "data_quality": "business_intelligence_analyzed",
                            "confidence": 0.90,
                            "source_type": "business_journal",
                            "business_relevance": article.business_relevance.value,
                            "commercial_property_mentioned": article.commercial_property_mentioned,
                            "companies_mentioned_count": len(article.company_names_mentioned),
                            "financial_figures_count": len(article.financial_figures_extracted or {}),
                            "development_keywords_count": len(article.development_keywords_found)
                        }
                    }

                    # Calculate content hash for deduplication
                    content_str = json.dumps(fact_data, sort_keys=True, default=str)
                    import hashlib
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
                        "business_news_article",
                        article.url,
                        datetime.utcnow(),
                        "business_journal_v1.0",
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
                            "business_news_article",
                            json.dumps(article.dict(), default=str),
                            0.90  # High confidence for analyzed business articles
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store business article {article.url}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new business articles")
        return stored_count

    def _is_below_threshold(self, relevance: BusinessTopicRelevance) -> bool:
        """Check if article relevance is below configured threshold."""
        relevance_order = [
            BusinessTopicRelevance.NOT_RELEVANT,
            BusinessTopicRelevance.SOMEWHAT_RELEVANT,
            BusinessTopicRelevance.MODERATELY_RELEVANT,
            BusinessTopicRelevance.HIGHLY_RELEVANT
        ]

        current_index = relevance_order.index(relevance)
        threshold_index = relevance_order.index(self.min_relevance_threshold)

        return current_index < threshold_index

    def _matches_focus_topics(self, article: BusinessJournalArticle, focus_topics: List[str]) -> bool:
        """Check if article matches any of the focus topics."""
        content_text = f"{article.title.lower()} {article.content.lower()}"
        return any(topic.lower() in content_text for topic in focus_topics)


async def create_business_journal_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    business_feeds: List[RSSFeedConfig],
    min_relevance_threshold: BusinessTopicRelevance = BusinessTopicRelevance.SOMEWHAT_RELEVANT,
    **kwargs
) -> BusinessJournalScraper:
    """Factory function to create configured business journal scraper."""
    scraper = BusinessJournalScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        business_journal_feeds=business_feeds,
        min_relevance_threshold=min_relevance_threshold,
        redis_client=redis_client,
        **kwargs
    )
    await scraper.initialize()
    return scraper


# Pre-configured business journal RSS feeds for common sources
DEFAULT_BUSINESS_FEEDS = [
    RSSFeedConfig(
        url="https://feeds.feedburner.com/BiznewsGainesville",
        source_name="Gainesville Business Report",
        section="business",
        update_frequency_hours=6,
        max_articles_per_fetch=25
    ),
    RSSFeedConfig(
        url="https://www.bizjournals.com/jacksonville/feeds/latest",
        source_name="Jacksonville Business Journal",
        section="business",
        update_frequency_hours=4,
        max_articles_per_fetch=30
    ),
    RSSFeedConfig(
        url="https://www.bizjournals.com/orlando/feeds/latest",
        source_name="Orlando Business Journal",
        section="business",
        update_frequency_hours=4,
        max_articles_per_fetch=30
    ),
    RSSFeedConfig(
        url="https://www.constructiondive.com/feeds/news/",
        source_name="Construction Dive",
        section="construction",
        update_frequency_hours=6,
        max_articles_per_fetch=20
    ),
    RSSFeedConfig(
        url="https://www.realestatefinanceandinvestment.com/feed",
        source_name="Real Estate Finance & Investment",
        section="real_estate_finance",
        update_frequency_hours=12,
        max_articles_per_fetch=15
    )
]