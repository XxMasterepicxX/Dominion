"""
Run ALL scrapers for Gainesville, FL - FIXED VERSION

All scrapers properly integrated with correct method signatures
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


async def run_city_permits(market_config, days_back=30):
    """Run city permits scraper"""
    print("\n" + "=" * 80)
    print("1. CITY PERMITS (CitizenServe)")
    print("=" * 80)

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        permits = await scraper.fetch_recent_permits(days_back=days_back)

        if not permits:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits\n")

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
                    if errors <= 5:  # Only print first 5 errors
                        print(f"  Error on permit {i}: {str(e)[:100]}")
                    await db_session.rollback()

                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(permits)}, Errors: {errors}")

            await db_session.commit()
            if errors > 0:
                print(f"  Total errors: {errors}")

        print(f"[OK] City Permits: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_county_permits(market_config, days_back=30):
    """Run county permits scraper"""
    print("\n" + "=" * 80)
    print("2. COUNTY PERMITS (CitizenServe)")
    print("=" * 80)

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # This returns List[Dict] not List[PermitRecord]
        permits = await scraper.fetch_recent_permits(days_back=days_back)

        if not permits:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, permit_dict in enumerate(permits, 1):
                # Convert pandas Timestamp and NaN values for JSON serialization
                import math
                cleaned_permit = {}
                for key, value in permit_dict.items():
                    if hasattr(value, 'isoformat'):  # datetime/Timestamp objects
                        cleaned_permit[key] = value.isoformat() if value else None
                    elif isinstance(value, float) and math.isnan(value):  # NaN values
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

                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(permits)}")

            await db_session.commit()

        print(f"[OK] County Permits: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(permits), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_crime_scraper(market_config, days_back=30):
    """Run crime data scraper (SYNC)"""
    print("\n" + "=" * 80)
    print("3. CRIME DATA (Socrata)")
    print("=" * 80)

    try:
        from src.scrapers.data_sources.crime_data_socrata import CrimeDataScraper

        scraper = CrimeDataScraper(market_config)
        ingestion_service = DataIngestionService()

        # SYNC method!
        crime_reports = scraper.fetch_recent_crimes(days_back=days_back)

        if not crime_reports:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(crime_reports)} crime reports\n")

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

                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(crime_reports)}")

            await db_session.commit()

        print(f"[OK] Crime Data: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(crime_reports), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_news_scraper(market_config):
    """Run news RSS scraper (SYNC)"""
    print("\n" + "=" * 80)
    print("4. NEWS RSS FEEDS")
    print("=" * 80)

    try:
        from src.scrapers.business.news_rss_extractor import NewsRSSScraper

        scraper = NewsRSSScraper(market_config)
        ingestion_service = DataIngestionService()

        # SYNC method!
        articles = scraper.fetch_recent_news()

        if not articles:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(articles)} articles\n")

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
                    print(f"  Progress: {i}/{len(articles)}")

            await db_session.commit()

        print(f"[OK] News: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(articles), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_council_scraper(market_config, months_back=3):
    """Run city council scraper (SYNC)"""
    print("\n" + "=" * 80)
    print("5. CITY COUNCIL MEETINGS (eScribe)")
    print("=" * 80)

    try:
        from src.scrapers.government.city_council_scraper import CouncilScraper

        scraper = CouncilScraper(market_config)
        ingestion_service = DataIngestionService()

        # SYNC method! Uses months_back not days_back
        meetings = scraper.fetch_recent_meetings(months_back=months_back)

        if not meetings:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(meetings)} meetings\n")

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

        print(f"[OK] Council Meetings: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(meetings), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def run_census_scraper(market_config, market_id='gainesville_fl'):
    """Run census demographics scraper"""
    print("\n" + "=" * 80)
    print("6. CENSUS DEMOGRAPHICS (US Census Bureau ACS5)")
    print("=" * 80)

    try:
        from src.scrapers.demographics.census_demographics import CensusScraper
        from sqlalchemy import text
        import json

        scraper = CensusScraper(market_config)

        # Fetch census data
        census_data = scraper.fetch_county_data()

        if not census_data:
            print("[ERROR] Failed to fetch census data")
            return {'total': 0, 'stored': 0, 'error': 'Fetch failed'}

        # Extract variables
        population = int(census_data.get('B01003_001E', 0))
        median_income = int(census_data.get('B19013_001E', 0))
        median_home_value = int(census_data.get('B25077_001E', 0))

        print(f"Found census data:")
        print(f"  Population: {population:,}")
        print(f"  Median Income: ${median_income:,}")
        print(f"  Median Home Value: ${median_home_value:,}\n")

        # Get market UUID and store in database
        async with db_manager.get_session() as session:
            result = await session.execute(
                text("SELECT id FROM markets WHERE market_code = :code"),
                {'code': market_id}
            )
            row = result.fetchone()
            if not row:
                print(f"[ERROR] Market not found: {market_id}")
                return {'total': 0, 'stored': 0, 'error': 'Market not found'}

            market_uuid = str(row[0])

            # Store in database (upsert)
            query = text("""
                INSERT INTO market_demographics (
                    market_id,
                    total_population,
                    median_household_income,
                    median_home_value,
                    census_variables,
                    data_year,
                    census_dataset
                ) VALUES (
                    :market_id,
                    :population,
                    :income,
                    :home_value,
                    :census_vars,
                    2022,
                    'acs5'
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

            demo_id = result.fetchone()[0]

        print(f"[OK] Census: Stored demographics (id: {demo_id})")
        return {'total': 1, 'stored': 1, 'demographics_id': str(demo_id)}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'stored': 0, 'error': str(e)}


async def run_sunbiz_scraper(market_config, limit=None):
    """Run Sunbiz scraper (SYNC)"""
    print("\n" + "=" * 80)
    print("7. SUNBIZ (Florida Business Entities)")
    print("=" * 80)

    try:
        from src.scrapers.data_sources.sunbiz import SunbizScraper

        scraper = SunbizScraper()
        ingestion_service = DataIngestionService()

        # SYNC method! scrape_all() returns Dict with 'formations' and 'events' keys
        # Use yesterday's date (today's file might not exist yet)
        yesterday = datetime.now() - timedelta(days=1)
        all_data = scraper.scrape_all(date=yesterday)

        # Get all formations
        formations = all_data.get('formations', [])

        # NO LIMIT - get all entities
        entities = formations[:limit] if limit else formations

        if not entities:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(entities)} business entities\n")

        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0

            for i, entity in enumerate(entities, 1):
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
                    print(f"  Progress: {i}/{len(entities)}")

            await db_session.commit()

        print(f"[OK] Sunbiz: {ingested} ingested, {duplicates} duplicates")
        return {'total': len(entities), 'ingested': ingested, 'duplicates': duplicates}

    except Exception as e:
        print(f"[ERROR] {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def main():
    """Run all scrapers"""

    print("=" * 80)
    print("RUNNING ALL SCRAPERS - GAINESVILLE, FL (MULTI-MARKET)")
    print("=" * 80)

    # Initialize database
    await db_manager.initialize()

    # Load market config
    market_config = load_market_config("gainesville_fl")
    print(f"\nMarket: {market_config.market.name}")

    # Initialize CurrentMarket context (CRITICAL for multi-market support)
    await CurrentMarket.initialize(market_code='gainesville_fl')
    print(f"CurrentMarket initialized: {CurrentMarket.get_code()} ({CurrentMarket.get_id()})")

    results = {}

    # Run all scrapers
    print("\n" + "=" * 80)
    print("STARTING SCRAPERS")
    print("=" * 80)

    results['city_permits'] = await run_city_permits(market_config, days_back=30)
    results['county_permits'] = await run_county_permits(market_config, days_back=30)
    results['crime'] = await run_crime_scraper(market_config, days_back=30)
    results['news'] = await run_news_scraper(market_config)
    results['council'] = await run_council_scraper(market_config, months_back=3)
    results['census'] = await run_census_scraper(market_config, market_id='gainesville_fl')
    results['sunbiz'] = await run_sunbiz_scraper(market_config, limit=None)  # No limit!

    # Final summary
    print("\n" + "=" * 80)
    print("SCRAPING COMPLETE - SUMMARY")
    print("=" * 80)

    total_ingested = 0
    for source, stats in results.items():
        print(f"\n{source.upper().replace('_', ' ')}:")
        print(f"  Total found: {stats.get('total', 0)}")
        # Census uses 'stored' instead of 'ingested'
        ingested = stats.get('ingested', stats.get('stored', 0))
        print(f"  Ingested: {ingested}")
        if 'duplicates' in stats:
            print(f"  Duplicates: {stats['duplicates']}")
        if 'error' in stats:
            print(f"  ERROR: {stats['error'][:100]}")
        total_ingested += ingested

    print(f"\nTOTAL NEW RECORDS INGESTED: {total_ingested}")

    # Show database stats
    print("\n" + "=" * 80)
    print("DATABASE STATISTICS")
    print("=" * 80)

    async with db_manager.get_session() as db_session:
        from sqlalchemy import text

        stats = {}
        tables = [
            ('entities', 'Entities'),
            ('permits', 'Permits (City + County)'),
            ('crime_reports', 'Crime Reports'),
            ('news_articles', 'News Articles'),
            ('council_meetings', 'Council Meetings'),
            ('llc_formations', 'LLC Formations'),
            ('market_demographics', 'Market Demographics (Census)'),
            ('raw_facts', 'Raw Facts (Total)'),
            ('properties', 'Properties'),
            ('bulk_property_records', 'Bulk Property Records (CAMA)'),
            ('bulk_llc_records', 'Bulk LLC Records (Sunbiz)')
        ]

        for table, label in tables:
            try:
                count = await db_session.scalar(text(f"SELECT COUNT(*) FROM {table}"))
                stats[label] = count
            except Exception as e:
                stats[label] = f"Error: {str(e)[:50]}"

        for label, count in stats.items():
            if isinstance(count, int):
                print(f"{label:.<50} {count:>10,}")
            else:
                print(f"{label:.<50} {count}")

    print("\n" + "=" * 80)
    print("ALL SCRAPERS COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("  - Import CAMA bulk data: python scripts/bulk_data_sync.py")
    print("  - Import Sunbiz bulk data: (bulk scraper)")
    print("  - Run entity resolution across markets")


if __name__ == "__main__":
    asyncio.run(main())
