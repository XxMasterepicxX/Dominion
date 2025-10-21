"""
Comprehensive Scraper - Pre-AWS Migration

Runs ALL scrapers with backfill to ensure fresh, complete data:
- Backfills last 14 days (covers 1-2 weeks gap)
- Full refresh of all data sources
- Automatic deduplication (via DataIngestionService)
- Progress tracking
- Error handling

ONE COMMAND: python scripts/run_comprehensive_scrape.py
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


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_progress(current, total, prefix="Progress"):
    """Print progress bar"""
    if total == 0:
        return
    percent = (current / total) * 100
    bar_length = 50
    filled = int(bar_length * current / total)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r{prefix}: |{bar}| {current}/{total} ({percent:.1f}%)", end='', flush=True)
    if current == total:
        print()  # New line when complete


async def scrape_city_permits_backfill(market_config, days_back=14):
    """Scrape city permits with backfill"""
    print_header("1. CITY PERMITS (14-day backfill)")

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        print(f"Fetching last {days_back} days of permits...")
        permits = await scraper.fetch_recent_permits(days_back=days_back)

        if not permits:
            print("[OK] No permits found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(permits)} permits")

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
                    if errors <= 3:
                        print(f"\nError on permit {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 50 == 0:
                    print_progress(i, len(permits), "City Permits")

            print_progress(len(permits), len(permits), "City Permits")
            await db_session.commit()

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}, Errors: {errors}")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_county_permits_backfill(market_config, days_back=14):
    """Scrape county permits with backfill"""
    print_header("2. COUNTY PERMITS (14-day backfill)")

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        print(f"Fetching last {days_back} days of permits...")
        permits = await scraper.fetch_recent_permits(days_back=days_back)

        if not permits:
            print("[OK] No permits found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(permits)} permits")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, permit_dict in enumerate(permits, 1):
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

                if i % 50 == 0:
                    print_progress(i, len(permits), "County Permits")

            print_progress(len(permits), len(permits), "County Permits")
            await db_session.commit()

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_crime_backfill(market_config, days_back=14):
    """Scrape crime data with backfill"""
    print_header("3. CRIME DATA (14-day backfill)")

    try:
        from src.scrapers.data_sources.crime_data_socrata import CrimeDataScraper

        scraper = CrimeDataScraper(market_config)
        ingestion_service = DataIngestionService()

        print(f"Fetching last {days_back} days of crime reports...")
        crime_reports = scraper.fetch_recent_crimes(days_back=days_back)

        if not crime_reports:
            print("[OK] No crime reports found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(crime_reports)} crime reports")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, report in enumerate(crime_reports, 1):
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

                if i % 50 == 0:
                    print_progress(i, len(crime_reports), "Crime Data")

            print_progress(len(crime_reports), len(crime_reports), "Crime Data")
            await db_session.commit()

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}")
        return {'total': len(crime_reports), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_news(market_config):
    """Scrape news RSS feeds"""
    print_header("4. NEWS RSS FEEDS")

    try:
        from src.scrapers.business.news_rss_extractor import NewsRSSScraper

        scraper = NewsRSSScraper(market_config)
        ingestion_service = DataIngestionService()

        print("Fetching latest news articles...")
        articles = scraper.fetch_recent_news()

        if not articles:
            print("[OK] No articles found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(articles)} articles")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, article in enumerate(articles, 1):
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

                if i % 20 == 0:
                    print_progress(i, len(articles), "News Articles")

            print_progress(len(articles), len(articles), "News Articles")
            await db_session.commit()

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}")
        return {'total': len(articles), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_council(market_config):
    """Scrape city council meetings"""
    print_header("5. CITY COUNCIL MEETINGS")

    try:
        from src.scrapers.government.city_council_scraper import CouncilScraper

        scraper = CouncilScraper(market_config)
        ingestion_service = DataIngestionService()

        print("Fetching last 3 months of council meetings...")
        meetings = scraper.fetch_recent_meetings(months_back=3)

        if not meetings:
            print("[OK] No meetings found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(meetings)} meetings")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, meeting in enumerate(meetings, 1):
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

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}")
        return {'total': len(meetings), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def scrape_census(market_config):
    """Scrape census demographics"""
    print_header("6. CENSUS DEMOGRAPHICS")

    try:
        from src.scrapers.demographics.census_demographics import CensusScraper
        from sqlalchemy import text
        import json

        scraper = CensusScraper(market_config)

        print("Fetching census data...")
        census_data = scraper.fetch_county_data()

        if not census_data:
            print("[ERROR] Failed to fetch census data")
            return {'total': 0, 'stored': 0, 'error': 'Fetch failed'}

        population = int(census_data.get('B01003_001E', 0))
        median_income = int(census_data.get('B19013_001E', 0))
        median_home_value = int(census_data.get('B25077_001E', 0))

        print(f"Population: {population:,}")
        print(f"Median Income: ${median_income:,}")
        print(f"Median Home Value: ${median_home_value:,}")

        async with db_manager.get_session() as session:
            result = await session.execute(
                text("SELECT id FROM markets WHERE market_code = :code"),
                {'code': 'gainesville_fl'}
            )
            row = result.fetchone()
            if not row:
                print("[ERROR] Market not found")
                return {'total': 0, 'stored': 0, 'error': 'Market not found'}

            market_uuid = str(row[0])

            query = text("""
                INSERT INTO market_demographics (
                    market_id, total_population, median_household_income,
                    median_home_value, census_variables, data_year, census_dataset
                ) VALUES (
                    :market_id, :population, :income, :home_value,
                    :census_vars, 2022, 'acs5'
                )
                ON CONFLICT (market_id, data_year)
                DO UPDATE SET
                    total_population = EXCLUDED.total_population,
                    median_household_income = EXCLUDED.median_household_income,
                    median_home_value = EXCLUDED.median_home_value,
                    census_variables = EXCLUDED.census_variables,
                    scraped_at = NOW()
                RETURNING id
            """)

            result = await session.execute(query, {
                'market_id': market_uuid,
                'population': population,
                'income': median_income,
                'home_value': median_home_value,
                'census_vars': json.dumps(census_data)
            })

            await session.commit()

        print("[OK] Census data stored")
        return {'total': 1, 'stored': 1}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'stored': 0, 'error': str(e)}


async def scrape_sunbiz(market_config):
    """Scrape Sunbiz business entities"""
    print_header("7. SUNBIZ (Florida Business Entities)")

    try:
        from src.scrapers.data_sources.sunbiz import SunbizScraper

        scraper = SunbizScraper()
        ingestion_service = DataIngestionService()

        print("Fetching yesterday's business formations...")
        yesterday = datetime.now() - timedelta(days=1)
        all_data = scraper.scrape_all(date=yesterday)

        formations = all_data.get('formations', [])

        if not formations:
            print("[OK] No formations found")
            return {'total': 0, 'ingested': 0, 'duplicates': 0}

        print(f"Found {len(formations)} business entities")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, entity in enumerate(formations, 1):
                result = await ingestion_service.ingest(
                    fact_type='llc_formation',
                    source_url='https://dos.myflorida.com/sunbiz/',
                    raw_content=entity,
                    parser_version='v1.0',
                    db_session=db_session
                )

                if result['is_duplicate']:
                    duplicates += 1
                else:
                    ingested += 1

                if i % 20 == 0:
                    print_progress(i, len(formations), "Sunbiz Entities")

            print_progress(len(formations), len(formations), "Sunbiz Entities")
            await db_session.commit()

        print(f"[OK] Ingested: {ingested}, Duplicates: {duplicates}")
        return {'total': len(formations), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_entity_resolution():
    """Run entity resolution to link contractors"""
    print_header("8. ENTITY RESOLUTION")

    try:
        print("Running entity resolution...")
        print("(This links contractors to LLCs and builds relationships)")

        # Import and run entity resolution
        from scripts.run_entity_resolution import main as entity_resolution_main

        # Run entity resolution (it's async)
        result = await entity_resolution_main()

        print("[OK] Entity resolution complete")
        return {'success': True}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {'success': False, 'error': str(e)}


async def show_database_stats():
    """Show final database statistics"""
    print_header("DATABASE STATISTICS")

    async with db_manager.get_session() as db_session:
        from sqlalchemy import text

        tables = [
            ('bulk_property_records', 'Properties (CAMA)'),
            ('entities', 'Entities'),
            ('permits', 'Permits (Total)'),
            ('crime_reports', 'Crime Reports'),
            ('news_articles', 'News Articles'),
            ('council_meetings', 'Council Meetings'),
            ('llc_formations', 'LLC Formations'),
            ('ordinance_embeddings', 'Ordinance Chunks'),
            ('entity_market_properties', 'Entity-Property Links'),
            ('market_demographics', 'Demographics')
        ]

        for table, label in tables:
            try:
                count = await db_session.scalar(text(f"SELECT COUNT(*) FROM {table}"))
                print(f"{label:.<45} {count:>10,}")
            except:
                print(f"{label:.<45} {'(not found)':>10}")


async def main():
    """Run comprehensive scraping with backfill"""

    print("=" * 80)
    print(" COMPREHENSIVE SCRAPER - PRE-AWS MIGRATION")
    print("=" * 80)
    print(f" Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Market: Gainesville, FL")
    print(f" Backfill: Last 14 days (permits + crime)")
    print("=" * 80)
    print("\nDuplication Prevention: ✓ Automatic via DataIngestionService")
    print("Safe to run multiple times - duplicates will be skipped\n")

    start_time = datetime.now()

    # Initialize
    await db_manager.initialize()
    market_config = load_market_config("gainesville_fl")
    await CurrentMarket.initialize(market_code='gainesville_fl')

    results = {}

    # Run all scrapers with backfill
    results['city_permits'] = await scrape_city_permits_backfill(market_config, days_back=14)
    results['county_permits'] = await scrape_county_permits_backfill(market_config, days_back=14)
    results['crime'] = await scrape_crime_backfill(market_config, days_back=14)
    results['news'] = await scrape_news(market_config)
    results['council'] = await scrape_council(market_config)
    results['census'] = await scrape_census(market_config)
    results['sunbiz'] = await scrape_sunbiz(market_config)

    # Run entity resolution
    results['entity_resolution'] = await run_entity_resolution()

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print_header("SCRAPING COMPLETE - SUMMARY")

    total_new = 0
    total_duplicates = 0

    for source, stats in results.items():
        ingested = stats.get('ingested', stats.get('stored', 0))
        duplicates = stats.get('duplicates', 0)
        errors = stats.get('errors', 0)

        if ingested > 0:
            print(f"\n{source.upper().replace('_', ' ')}:")
            print(f"  New records: {ingested}")
            if duplicates > 0:
                print(f"  Duplicates skipped: {duplicates}")
            if errors > 0:
                print(f"  Errors: {errors}")

        total_new += ingested
        total_duplicates += duplicates

    print(f"\nTOTAL NEW RECORDS: {total_new:,}")
    print(f"TOTAL DUPLICATES SKIPPED: {total_duplicates:,}")
    print(f"Duration: {duration}")

    # Show database stats
    await show_database_stats()

    print_header("READY FOR AWS MIGRATION")
    print("Database is now up-to-date with fresh data!")
    print("\nNext steps:")
    print("  1. Export database: pg_dump dominion > dominion_fresh.sql")
    print("  2. Import to Aurora: psql -h aurora-endpoint < dominion_fresh.sql")
    print("  3. Test agent on AWS")

    await db_manager.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
