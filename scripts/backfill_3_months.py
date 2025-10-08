"""
Backfill 3 months of historical data from all scrapers

This is a ONE-TIME script to populate historical data.
After this runs, daily scrapers should use today-only mode.
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


async def backfill_city_permits(market_config):
    """Backfill city permits - 90 days"""
    print("\n" + "=" * 80)
    print("BACKFILL: CITY PERMITS (90 days)")
    print("=" * 80)

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Get 90 days of data
        permits = await scraper.fetch_recent_permits(days_back=90)

        if not permits:
            print("[WARN] No permits found")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from last 90 days\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0

            for i, permit in enumerate(permits, 1):
                try:
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

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on permit {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(permits)} ({ingested} new, {duplicates} duplicates, {errors} errors)")

            await db_session.commit()

        print(f"\n[OK] City Permits: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def backfill_county_permits(market_config):
    """Backfill county permits - 90 days"""
    print("\n" + "=" * 80)
    print("BACKFILL: COUNTY PERMITS (90 days)")
    print("=" * 80)

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        permits = await scraper.fetch_recent_permits(days_back=90)

        if not permits:
            print("[WARN] No permits found")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from last 90 days\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0

            for i, permit_dict in enumerate(permits, 1):
                try:
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

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on permit {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(permits)} ({ingested} new, {duplicates} duplicates, {errors} errors)")

            await db_session.commit()

        print(f"\n[OK] County Permits: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def backfill_crime(market_config):
    """Backfill crime data - 90 days"""
    print("\n" + "=" * 80)
    print("BACKFILL: CRIME DATA (90 days)")
    print("=" * 80)

    try:
        from src.scrapers.data_sources.crime_data_socrata import CrimeDataScraper

        scraper = CrimeDataScraper(market_config)
        ingestion_service = DataIngestionService()

        # Get 90 days of data (with coordinate extraction!)
        crime_reports = scraper.fetch_recent_crimes(days_back=90)

        if not crime_reports:
            print("[WARN] No crime data found")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(crime_reports)} crime reports from last 90 days\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0

            for i, report in enumerate(crime_reports, 1):
                try:
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

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on report {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 500 == 0:
                    print(f"  Progress: {i}/{len(crime_reports)} ({ingested} new, {duplicates} duplicates, {errors} errors)")

            await db_session.commit()

        print(f"\n[OK] Crime Data: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(crime_reports), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def backfill_news(market_config):
    """Backfill news - get all available from RSS"""
    print("\n" + "=" * 80)
    print("BACKFILL: NEWS RSS FEEDS")
    print("=" * 80)

    try:
        from src.scrapers.business.news_rss_extractor import NewsRSSScraper

        scraper = NewsRSSScraper(market_config)
        ingestion_service = DataIngestionService()

        # RSS feeds typically have last 20-100 articles available
        articles = scraper.fetch_recent_news()

        if not articles:
            print("[WARN] No news articles found")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(articles)} news articles from RSS feeds\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0

            for i, article in enumerate(articles, 1):
                try:
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

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on article {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 50 == 0:
                    print(f"  Progress: {i}/{len(articles)} ({ingested} new, {duplicates} duplicates, {errors} errors)")

            await db_session.commit()

        print(f"\n[OK] News: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(articles), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def backfill_council(market_config):
    """Backfill council meetings - 6 months"""
    print("\n" + "=" * 80)
    print("BACKFILL: CITY COUNCIL MEETINGS (6 months)")
    print("=" * 80)

    try:
        from src.scrapers.government.city_council_scraper import CouncilScraper

        scraper = CouncilScraper(market_config)
        ingestion_service = DataIngestionService()

        # Get 6 months of meeting data
        meetings = scraper.fetch_recent_meetings(months_back=6)

        if not meetings:
            print("[WARN] No council meetings found")
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(meetings)} council meetings from last 6 months\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0

            for i, meeting in enumerate(meetings, 1):
                try:
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

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on meeting {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 20 == 0:
                    print(f"  Progress: {i}/{len(meetings)} ({ingested} new, {duplicates} duplicates, {errors} errors)")

            await db_session.commit()

        print(f"\n[OK] Council Meetings: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(meetings), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def main():
    """Run backfill for all scrapers"""

    print("=" * 80)
    print("3-MONTH HISTORICAL DATA BACKFILL")
    print("=" * 80)
    print("\nThis will populate 3 months of historical data from all sources.")
    print("After this completes, daily scrapers should run in 'today-only' mode.\n")

    # Initialize database
    await db_manager.initialize()

    # Load market config
    market_config = load_market_config("gainesville_fl")
    print(f"Market: {market_config.market.name}\n")

    # Initialize CurrentMarket
    await CurrentMarket.initialize(market_code='gainesville_fl')

    results = {}
    start_time = datetime.now()

    # Run all backfills
    results['city_permits'] = await backfill_city_permits(market_config)
    results['county_permits'] = await backfill_county_permits(market_config)
    results['crime'] = await backfill_crime(market_config)
    results['news'] = await backfill_news(market_config)
    results['council'] = await backfill_council(market_config)

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("BACKFILL COMPLETE - SUMMARY")
    print("=" * 80)

    total_ingested = 0
    total_duplicates = 0
    total_errors = 0

    for scraper, result in results.items():
        total = result.get('total', 0)
        ingested = result.get('ingested', 0)
        duplicates = result.get('duplicates', 0)
        errors = result.get('errors', 0)

        total_ingested += ingested
        total_duplicates += duplicates
        total_errors += errors

        print(f"\n{scraper.upper()}:")
        print(f"  Total found: {total}")
        print(f"  New records: {ingested}")
        print(f"  Duplicates: {duplicates}")
        if errors:
            print(f"  Errors: {errors}")

    print("\n" + "=" * 80)
    print(f"TOTAL NEW RECORDS: {total_ingested}")
    print(f"TOTAL DUPLICATES: {total_duplicates}")
    if total_errors:
        print(f"TOTAL ERRORS: {total_errors}")
    print(f"\nDuration: {duration}")
    print("=" * 80)

    print("\n[NEXT STEP] Run entity resolution to link contractors to entities:")
    print("  python scripts/run_entity_resolution.py")

    print("\n[NEXT STEP] Run daily scrapers in today-only mode:")
    print("  python scripts/run_daily_scrapers.py")

    await db_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
