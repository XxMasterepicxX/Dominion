"""
Daily Scraper Runner - TODAY ONLY MODE

This script is designed to run daily and only fetch today's new data.
Run backfill_3_months.py FIRST to populate historical data.

Recommended: Run this via cron/Task Scheduler at 11 PM daily.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_market_config
from src.config.current_market import CurrentMarket
from src.services.data_ingestion import DataIngestionService
from src.database.connection import db_manager


async def scrape_city_permits_today(market_config):
    """Scrape city permits from TODAY only"""
    print("\n" + "=" * 80)
    print("DAILY: CITY PERMITS (today only)")
    print("=" * 80)

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Get only today's permits (1 day back to ensure we catch everything)
        permits = await scraper.fetch_recent_permits(days_back=1)

        if not permits:
            print("[OK] No new permits today")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from today\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for permit in permits:
                result = await ingestion_service.ingest(
                    fact_type='city_permit',
                    source_url=f'https://www4.citizenserve.com/{scraper.jurisdiction}',
                    raw_content=permit.to_dict(),
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

            await db_session.commit()

        print(f"[OK] City Permits: {ingested} new, {duplicates} duplicates")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_county_permits_today(market_config):
    """Scrape county permits from TODAY only"""
    print("\n" + "=" * 80)
    print("DAILY: COUNTY PERMITS (today only)")
    print("=" * 80)

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        permits = await scraper.fetch_recent_permits(days_back=1)

        if not permits:
            print("[OK] No new permits today")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from today\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for permit_dict in permits:
                import math
                cleaned_permit = {}
                for key, value in permit_dict.items():
                    if hasattr(value, 'isoformat'):
                        cleaned_permit[key] = value.isoformat() if value else None
                    elif isinstance(value, float) and math.isnan(value):
                        cleaned_permit[key] = None
                    else:
                        cleaned_permit[key] = value

                result = await ingestion_service.ingest(
                    fact_type='county_permit',
                    source_url=f'https://www6.citizenserve.com/{scraper.jurisdiction}',
                    raw_content=cleaned_permit,
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

            await db_session.commit()

        print(f"[OK] County Permits: {ingested} new, {duplicates} duplicates")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_crime_today(market_config):
    """Scrape crime data from TODAY only"""
    print("\n" + "=" * 80)
    print("DAILY: CRIME DATA (today only)")
    print("=" * 80)

    try:
        from src.scrapers.data_sources.crime_data_socrata import CrimeDataScraper

        scraper = CrimeDataScraper(market_config)
        ingestion_service = DataIngestionService()

        # Get only today's crime reports
        crime_reports = scraper.fetch_recent_crimes(days_back=1)

        if not crime_reports:
            print("[OK] No new crime reports today")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(crime_reports)} crime reports from today\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for report in crime_reports:
                result = await ingestion_service.ingest(
                    fact_type='crime_report',
                    source_url=market_config.scrapers.crime.endpoint,
                    raw_content=report,
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

            await db_session.commit()

        print(f"[OK] Crime Data: {ingested} new, {duplicates} duplicates")
        return {'total': len(crime_reports), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_news_today(market_config):
    """Scrape news - RSS feeds don't have 'today only' mode, just get latest"""
    print("\n" + "=" * 80)
    print("DAILY: NEWS RSS FEEDS (latest)")
    print("=" * 80)

    try:
        from src.scrapers.business.news_rss_extractor import NewsRSSScraper

        scraper = NewsRSSScraper(market_config)
        ingestion_service = DataIngestionService()

        # RSS feeds show latest ~100 articles, system will dedupe
        articles = scraper.fetch_recent_news()

        if not articles:
            print("[OK] No new news articles")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(articles)} articles from RSS feeds\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for article in articles:
                result = await ingestion_service.ingest(
                    fact_type='news_article',
                    source_url=article.get('link', ''),
                    raw_content=article,
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

            await db_session.commit()

        print(f"[OK] News: {ingested} new, {duplicates} duplicates")
        return {'total': len(articles), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_council_today(market_config):
    """Scrape council meetings - check for today's meetings"""
    print("\n" + "=" * 80)
    print("DAILY: CITY COUNCIL MEETINGS (recent)")
    print("=" * 80)

    try:
        from src.scrapers.government.city_council_scraper import CouncilScraper

        scraper = CouncilScraper(market_config)
        ingestion_service = DataIngestionService()

        # Check last week for new meetings (they might be posted with delay)
        meetings = scraper.fetch_recent_meetings(months_back=0.25)  # ~1 week

        if not meetings:
            print("[OK] No new council meetings")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(meetings)} council meetings\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for meeting in meetings:
                result = await ingestion_service.ingest(
                    fact_type='council_meeting',
                    source_url=market_config.scrapers.council.endpoint,
                    raw_content=meeting.to_dict(),
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

            await db_session.commit()

        print(f"[OK] Council Meetings: {ingested} new, {duplicates} duplicates")
        return {'total': len(meetings), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def main():
    """Run daily scrapers (today only)"""

    print("=" * 80)
    print("DAILY SCRAPER RUN - TODAY ONLY MODE")
    print("=" * 80)
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nFetching only today's new data...\n")

    # Initialize database
    await db_manager.initialize()

    # Load market config
    market_config = load_market_config("gainesville_fl")
    print(f"Market: {market_config.market.name}\n")

    # Initialize CurrentMarket
    await CurrentMarket.initialize(market_code='gainesville_fl')

    results = {}
    start_time = datetime.now()

    # Run all daily scrapers
    results['city_permits'] = await scrape_city_permits_today(market_config)
    results['county_permits'] = await scrape_county_permits_today(market_config)
    results['crime'] = await scrape_crime_today(market_config)
    results['news'] = await scrape_news_today(market_config)
    results['council'] = await scrape_council_today(market_config)

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("DAILY SCRAPING COMPLETE - SUMMARY")
    print("=" * 80)

    total_ingested = 0
    total_duplicates = 0

    for scraper, result in results.items():
        ingested = result.get('ingested', 0)
        duplicates = result.get('duplicates', 0)

        total_ingested += ingested
        total_duplicates += duplicates

        if ingested > 0:
            print(f"{scraper.upper()}: {ingested} new records")

    print("\n" + "=" * 80)
    print(f"TOTAL NEW RECORDS TODAY: {total_ingested}")
    print(f"Duration: {duration}")
    print("=" * 80)

    if total_ingested > 0:
        print("\n[RECOMMENDATION] Run entity resolution to link new contractors:")
        print("  python scripts/run_entity_resolution.py")

    await db_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
