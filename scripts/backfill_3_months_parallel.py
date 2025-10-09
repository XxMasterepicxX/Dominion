"""
3-Month Backfill with PARALLEL Sunbiz Enrichment

This version is 10x faster by:
1. Batching permits into groups of 100
2. Collecting unique contractors from batch
3. Enriching all contractors IN PARALLEL (15 concurrent)
4. Then processing permits with pre-enriched data

Expected time: 30-45 minutes instead of 5 hours!
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_market_config
from src.config.current_market import CurrentMarket
from src.services.data_ingestion import DataIngestionService
from src.services.sunbiz_enrichment import SunbizEnrichmentService
from src.services.parallel_sunbiz_enrichment import ParallelSunbizEnricher
from src.database.connection import db_manager


async def backfill_permits_parallel(market_config):
    """Backfill permits with PARALLEL contractor enrichment"""
    print("\n" + "=" * 80)
    print("BACKFILL: COUNTY PERMITS (90 days) - PARALLEL MODE")
    print("=" * 80)

    try:
        from src.scrapers.permits.county_permits import CountyPermitsScraper

        scraper = CountyPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Scrape all permits
        permits = await scraper.fetch_recent_permits(days_back=90)

        if not permits:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from last 90 days\n")

        # Initialize parallel enricher
        sunbiz_service = SunbizEnrichmentService(headless=True)
        parallel_enricher = ParallelSunbizEnricher(sunbiz_service, max_concurrent=15)

        # Process in batches of 100
        batch_size = 100
        total_ingested = 0
        total_duplicates = 0
        total_errors = 0

        for batch_start in range(0, len(permits), batch_size):
            batch = permits[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(permits) + batch_size - 1) // batch_size

            print(f"\n[Batch {batch_num}/{total_batches}] Processing permits {batch_start+1}-{batch_start+len(batch)}")

            # Step 1: Collect unique contractors from this batch
            contractors = set()
            for permit_dict in batch:
                contractor = permit_dict.get('contractor')
                if contractor and contractor.strip():
                    contractors.add(contractor)

            print(f"  Found {len(contractors)} unique contractors in batch")

            # Step 2: Enrich ALL contractors in PARALLEL
            if contractors:
                print(f"  Enriching contractors in parallel (15 concurrent)...")
                start_time = datetime.now()

                enrichment_map = await parallel_enricher.enrich_batch(list(contractors))

                duration = (datetime.now() - start_time).total_seconds()
                success = sum(1 for v in enrichment_map.values() if v)
                print(f"  ✓ Enriched {success}/{len(contractors)} in {duration:.1f}s ({len(contractors)/duration:.1f} per sec)")
            else:
                enrichment_map = {}

            # Step 3: Process permits (enrichment already done!)
            # IMPORTANT: Uses DataIngestionService which has built-in deduplication via content_hash
            async with db_manager.get_session() as db_session:
                ingested = 0
                duplicates = 0
                errors = 0

                # Temporarily store enrichment in session for fast lookup
                # This is ONLY used to skip web scraping, NOT to skip deduplication!
                db_session.info['enrichment_cache'] = enrichment_map

                for i, permit_dict in enumerate(batch, 1):
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

                        # DataIngestionService handles deduplication automatically:
                        # 1. Generates content_hash from raw_content
                        # 2. Checks if hash exists in raw_facts table
                        # 3. Returns is_duplicate=True if found, skips processing
                        # 4. Only creates new records if hash is unique
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
                        if errors <= 3:
                            print(f"  Error on permit {i}: {str(e)[:100]}")
                        await db_session.rollback()
                        continue

                # Clear cache
                db_session.info.pop('enrichment_cache', None)

                await db_session.commit()

                total_ingested += ingested
                total_duplicates += duplicates
                total_errors += errors

                print(f"  ✓ Batch complete: {ingested} new, {duplicates} duplicates, {errors} errors")

        print(f"\n[OK] County Permits: {total_ingested} new, {total_duplicates} duplicates, {total_errors} errors")
        return {
            'total': len(permits),
            'ingested': total_ingested,
            'duplicates': total_duplicates,
            'errors': total_errors
        }

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def backfill_city_permits_parallel(market_config):
    """Backfill city permits with PARALLEL contractor enrichment"""
    print("\n" + "=" * 80)
    print("BACKFILL: CITY PERMITS (90 days) - PARALLEL MODE")
    print("=" * 80)

    try:
        from src.scrapers.permits.city_permits import CityPermitsScraper

        scraper = CityPermitsScraper(market_config, headless=True)
        ingestion_service = DataIngestionService()

        # Scrape all permits
        permits = await scraper.fetch_recent_permits(days_back=90)

        if not permits:
            return {'total': 0, 'ingested': 0}

        print(f"Found {len(permits)} permits from last 90 days\n")

        # Initialize parallel enricher
        sunbiz_service = SunbizEnrichmentService(headless=True)
        parallel_enricher = ParallelSunbizEnricher(sunbiz_service, max_concurrent=15)

        # Process in batches
        batch_size = 100
        total_ingested = 0
        total_duplicates = 0
        total_errors = 0

        for batch_start in range(0, len(permits), batch_size):
            batch = permits[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(permits) + batch_size - 1) // batch_size

            print(f"\n[Batch {batch_num}/{total_batches}] Processing permits {batch_start+1}-{batch_start+len(batch)}")

            # Collect contractors
            contractors = set()
            for permit in batch:
                contractor = permit.contractor_name if hasattr(permit, 'contractor_name') else None
                if contractor and contractor.strip():
                    contractors.add(contractor)

            # Enrich in parallel
            enrichment_map = {}
            if contractors:
                print(f"  Enriching {len(contractors)} contractors in parallel...")
                start_time = datetime.now()
                enrichment_map = await parallel_enricher.enrich_batch(list(contractors))
                duration = (datetime.now() - start_time).total_seconds()
                success = sum(1 for v in enrichment_map.values() if v)
                print(f"  ✓ Enriched {success}/{len(contractors)} in {duration:.1f}s")

            # Process permits
            async with db_manager.get_session() as db_session:
                db_session.info['enrichment_cache'] = enrichment_map
                ingested = 0
                duplicates = 0
                errors = 0

                for permit in batch:
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
                            print(f"  Error: {str(e)[:100]}")
                        await db_session.rollback()

                db_session.info.pop('enrichment_cache', None)
                await db_session.commit()

                total_ingested += ingested
                total_duplicates += duplicates
                total_errors += errors

                print(f"  ✓ Batch complete: {ingested} new, {duplicates} duplicates, {errors} errors")

        print(f"\n[OK] City Permits: {total_ingested} new, {total_duplicates} duplicates, {total_errors} errors")
        return {'total': len(permits), 'ingested': total_ingested, 'duplicates': total_duplicates, 'errors': total_errors}

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
                    print(f"  Progress: {i}/{len(crime_reports)} ({ingested} new, {duplicates} duplicates)")

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
                    print(f"  Progress: {i}/{len(articles)} ({ingested} new, {duplicates} duplicates)")

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
                        raw_content=meeting,  # Already a dict, no .to_dict() needed
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
                    print(f"  Progress: {i}/{len(meetings)} ({ingested} new, {duplicates} duplicates)")

            await db_session.commit()

        print(f"\n[OK] Council Meetings: {ingested} new, {duplicates} duplicates, {errors} errors")
        return {'total': len(meetings), 'ingested': ingested, 'duplicates': duplicates, 'errors': errors}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {'total': 0, 'ingested': 0, 'error': str(e)}


async def main():
    """Run parallel backfill for ALL data sources"""
    print("=" * 80)
    print("3-MONTH BACKFILL - PARALLEL MODE (10x FASTER)")
    print("=" * 80)
    print("\nUsing parallel Sunbiz enrichment (15 concurrent)")
    print("Expected time: 30-45 minutes\n")

    await db_manager.initialize()

    market_config = load_market_config("gainesville_fl")
    print(f"Market: {market_config.market.name}\n")

    await CurrentMarket.initialize(market_code='gainesville_fl')

    start_time = datetime.now()
    results = {}

    # Run ALL backfills
    results['city_permits'] = await backfill_city_permits_parallel(market_config)
    results['county_permits'] = await backfill_permits_parallel(market_config)
    results['crime'] = await backfill_crime(market_config)
    results['news'] = await backfill_news(market_config)
    results['council'] = await backfill_council(market_config)

    duration = datetime.now() - start_time

    print("\n" + "=" * 80)
    print("BACKFILL COMPLETE - SUMMARY")
    print("=" * 80)

    total_ingested = 0
    for source, result in results.items():
        ingested = result.get('ingested', 0)
        total_ingested += ingested
        print(f"{source}: {ingested} new records")

    print(f"\nTotal ingested: {total_ingested}")
    print(f"Duration: {duration}")
    print("=" * 80)

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
