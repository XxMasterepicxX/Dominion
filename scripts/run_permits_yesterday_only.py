"""
Run permit scrapers for YESTERDAY ONLY (10/6/2025)
Testing fresh data collection and field mapping
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
from sqlalchemy import text


async def run_city_permits_single_day(market_config, target_date):
    """Run city permits scraper for a single day"""
    print("\n" + "=" * 80)
    print(f"CITY PERMITS - {target_date.strftime('%Y-%m-%d')}")
    print("=" * 80)

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Fetch permits for single day (1 day back from target)
        permits = await scraper.fetch_recent_permits(days_back=1)

        if not permits:
            print("[WARNING] No permits found")
            return {'scraped': 0, 'ingested': 0, 'samples': []}

        print(f"\nScraped {len(permits)} permits from CitizenServe")

        # Show first 3 raw permits
        print("\nSample raw permits:")
        print("-" * 80)
        for i, permit in enumerate(permits[:3], 1):
            permit_dict = permit.dict() if hasattr(permit, 'dict') else permit
            print(f"\nPermit #{i}:")
            for key, value in permit_dict.items():
                if value is not None:
                    print(f"  {key}: {value}")

        print("-" * 80)

        # Ingest to database
        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0
            samples = []

            for i, permit in enumerate(permits, 1):
                try:
                    permit_dict = permit.dict() if hasattr(permit, 'dict') else permit

                    result = await ingestion_service.ingest(
                        fact_type='city_permit',
                        source_url=f'https://www4.citizenserve.com/{scraper.jurisdiction}',
                        raw_content=permit_dict,
                        parser_version='v2.0_test',
                        db_session=db_session
                    )

                    if result['is_duplicate']:
                        duplicates += 1
                    else:
                        ingested += 1
                        if len(samples) < 3:
                            samples.append(permit_dict)

                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [ERROR] Permit {i}: {str(e)[:150]}")
                    await db_session.rollback()

            await db_session.commit()

        print(f"\n[OK] Scraped: {len(permits)}, Ingested: {ingested}, Duplicates: {duplicates}, Errors: {errors}")
        return {
            'scraped': len(permits),
            'ingested': ingested,
            'duplicates': duplicates,
            'errors': errors,
            'samples': samples
        }

    except Exception as e:
        print(f"[ERROR] City permits failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'scraped': 0, 'ingested': 0, 'error': str(e)}


async def run_county_permits_single_day(market_config, target_date):
    """Run county permits scraper for a single day"""
    print("\n" + "=" * 80)
    print(f"COUNTY PERMITS - {target_date.strftime('%Y-%m-%d')}")
    print("=" * 80)

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Fetch permits for single day
        permits = await scraper.fetch_recent_permits(days_back=1)

        if not permits:
            print("[WARNING] No permits found")
            return {'scraped': 0, 'ingested': 0, 'samples': []}

        print(f"\nScraped {len(permits)} permits from CitizenServe")

        # Show first 3 raw permits
        print("\nSample raw permits:")
        print("-" * 80)
        for i, permit_dict in enumerate(permits[:3], 1):
            print(f"\nPermit #{i}:")
            for key, value in permit_dict.items():
                if value is not None:
                    print(f"  {key}: {value}")

        print("-" * 80)

        # Ingest to database
        async with db_manager.get_session() as db_session:
            ingested = 0
            duplicates = 0
            errors = 0
            samples = []

            for i, permit_dict in enumerate(permits, 1):
                try:
                    # Convert pandas Timestamp and NaN values
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
                        parser_version='v2.0_test',
                        db_session=db_session
                    )

                    if result['is_duplicate']:
                        duplicates += 1
                    else:
                        ingested += 1
                        if len(samples) < 3:
                            samples.append(cleaned_permit)

                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [ERROR] Permit {i}: {str(e)[:150]}")
                    await db_session.rollback()

            await db_session.commit()

        print(f"\n[OK] Scraped: {len(permits)}, Ingested: {ingested}, Duplicates: {duplicates}, Errors: {errors}")
        return {
            'scraped': len(permits),
            'ingested': ingested,
            'duplicates': duplicates,
            'errors': errors,
            'samples': samples
        }

    except Exception as e:
        print(f"[ERROR] County permits failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'scraped': 0, 'ingested': 0, 'error': str(e)}


async def analyze_database_permits(target_date):
    """Analyze what's in the database after scraping"""
    print("\n" + "=" * 80)
    print("DATABASE ANALYSIS - Fresh Permit Data")
    print("=" * 80)

    async with db_manager.get_session() as db_session:
        # Check total permits
        total = await db_session.scalar(text("SELECT COUNT(*) FROM permits"))
        print(f"\nTotal permits in database: {total}")

        # Check permits from our test run (parser_version = v2.0_test)
        test_permits = await db_session.scalar(text("""
            SELECT COUNT(*)
            FROM permits p
            JOIN raw_facts rf ON p.raw_fact_id = rf.id
            WHERE rf.parser_version = 'v2.0_test'
        """))
        print(f"Permits from this test run: {test_permits}")

        # Field population for TEST permits only
        result = await db_session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(p.permit_number) as has_permit_number,
                COUNT(p.application_date) as has_application_date,
                COUNT(p.issued_date) as has_issued_date,
                COUNT(p.final_inspection_date) as has_final_inspection,
                COUNT(p.permit_type) as has_permit_type,
                COUNT(p.work_type) as has_work_type,
                COUNT(p.project_value) as has_project_value,
                COUNT(p.applicant_entity_id) as has_applicant,
                COUNT(p.owner_entity_id) as has_owner,
                COUNT(p.parcel_id) as has_parcel,
                COUNT(p.property_id) as has_property
            FROM permits p
            JOIN raw_facts rf ON p.raw_fact_id = rf.id
            WHERE rf.parser_version = 'v2.0_test'
        """))

        row = result.first()
        if row and row[0] > 0:
            print("\nField Population for NEW permits:")
            print(f"  Total permits: {row[0]}")
            print(f"  permit_number:        {row[1]}/{row[0]} ({row[1]/row[0]*100:.1f}%)")
            print(f"  application_date:     {row[2]}/{row[0]} ({row[2]/row[0]*100:.1f}%)")
            print(f"  issued_date:          {row[3]}/{row[0]} ({row[3]/row[0]*100:.1f}%)")
            print(f"  final_inspection:     {row[4]}/{row[0]} ({row[4]/row[0]*100:.1f}%)")
            print(f"  permit_type:          {row[5]}/{row[0]} ({row[5]/row[0]*100:.1f}%)")
            print(f"  work_type:            {row[6]}/{row[0]} ({row[6]/row[0]*100:.1f}%)")
            print(f"  project_value:        {row[7]}/{row[0]} ({row[7]/row[0]*100:.1f}%)")
            print(f"  applicant_entity_id:  {row[8]}/{row[0]} ({row[8]/row[0]*100:.1f}%)")
            print(f"  owner_entity_id:      {row[9]}/{row[0]} ({row[9]/row[0]*100:.1f}%)")
            print(f"  parcel_id:            {row[10]}/{row[0]} ({row[10]/row[0]*100:.1f}%)")
            print(f"  property_id:          {row[11]}/{row[0]} ({row[11]/row[0]*100:.1f}%)")

        # Show sample permits from database
        result = await db_session.execute(text("""
            SELECT
                p.permit_number,
                p.permit_type,
                p.work_type,
                p.application_date,
                p.issued_date,
                p.project_value,
                p.status,
                p.parcel_id,
                p.applicant_entity_id,
                e.name as applicant_name
            FROM permits p
            JOIN raw_facts rf ON p.raw_fact_id = rf.id
            LEFT JOIN entities e ON p.applicant_entity_id = e.id
            WHERE rf.parser_version = 'v2.0_test'
            LIMIT 5
        """))

        print("\nSample permits in database:")
        print("-" * 80)
        for i, row in enumerate(result, 1):
            print(f"\nPermit #{i}:")
            print(f"  Number: {row[0]}")
            print(f"  Type: {row[1]}")
            print(f"  Work Type: {row[2]}")
            print(f"  Application Date: {row[3]}")
            print(f"  Issued Date: {row[4]}")
            print(f"  Value: ${row[5]:,.0f}" if row[5] else "  Value: None")
            print(f"  Status: {row[6]}")
            print(f"  Parcel ID: {row[7]}")
            print(f"  Applicant Entity: {row[8]}")
            print(f"  Applicant Name: {row[9]}")

        # Check if MarketAnalyzer would find these permits
        recent_90d = await db_session.scalar(text("""
            SELECT COUNT(*)
            FROM permits p
            WHERE p.application_date >= CURRENT_DATE - INTERVAL '90 days'
            OR p.issued_date >= CURRENT_DATE - INTERVAL '90 days'
        """))
        print(f"\nPermits MarketAnalyzer would find (last 90d): {recent_90d}")


async def main():
    """Run permit scrapers for yesterday only"""

    target_date = datetime(2025, 10, 6)  # Yesterday (10/6/2025)

    print("=" * 80)
    print(f"PERMIT SCRAPER TEST - {target_date.strftime('%Y-%m-%d')} ONLY")
    print("=" * 80)
    print("\nTesting:")
    print("  1. City permit scraper")
    print("  2. County permit scraper")
    print("  3. Field mapping and data quality")
    print("  4. Entity linking")
    print("  5. Property/parcel linking")

    # Initialize database
    await db_manager.initialize()

    # Load market config
    market_config = load_market_config("gainesville_fl")
    print(f"\nMarket: {market_config.market.name}")

    # Initialize CurrentMarket
    await CurrentMarket.initialize(market_code='gainesville_fl')
    print(f"CurrentMarket: {CurrentMarket.get_code()} ({CurrentMarket.get_id()})")

    # Run scrapers
    city_results = await run_city_permits_single_day(market_config, target_date)
    county_results = await run_county_permits_single_day(market_config, target_date)

    # Analyze database
    await analyze_database_permits(target_date)

    # Summary
    print("\n" + "=" * 80)
    print("TEST COMPLETE - SUMMARY")
    print("=" * 80)

    print("\nCity Permits:")
    print(f"  Scraped: {city_results.get('scraped', 0)}")
    print(f"  Ingested: {city_results.get('ingested', 0)}")
    print(f"  Duplicates: {city_results.get('duplicates', 0)}")
    if 'error' in city_results:
        print(f"  ERROR: {city_results['error']}")

    print("\nCounty Permits:")
    print(f"  Scraped: {county_results.get('scraped', 0)}")
    print(f"  Ingested: {county_results.get('ingested', 0)}")
    print(f"  Duplicates: {county_results.get('duplicates', 0)}")
    if 'error' in county_results:
        print(f"  ERROR: {county_results['error']}")

    total_scraped = city_results.get('scraped', 0) + county_results.get('scraped', 0)
    total_ingested = city_results.get('ingested', 0) + county_results.get('ingested', 0)

    print(f"\nTOTAL: {total_scraped} scraped, {total_ingested} ingested")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
