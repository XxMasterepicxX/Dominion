"""
qPublic Batch Enrichment Script

Enriches properties from bulk_property_records with data from qPublic:
- Coordinates (latitude/longitude)
- Sales history
- Permit history
- Building details

Usage:
    python scripts/enrich_qpublic_batch.py --limit 100 --headless false
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from src.database.models import BulkPropertyRecord
from src.config import CurrentMarket
from src.scrapers.data_sources.qpublic_property_browser_fast import QPublicBrowserScraperFast
from sqlalchemy import select, update, func
import structlog
import argparse
from datetime import datetime
import json
import logging
import math

logger = structlog.get_logger(__name__)


def sanitize_nan(obj):
    """
    Recursively convert NaN values to None in nested dicts/lists.
    PostgreSQL cannot handle NaN in JSONB or numeric fields.
    """
    if isinstance(obj, dict):
        return {key: sanitize_nan(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    else:
        return obj


def setup_logging(log_dir: str = "logs"):
    """
    Set up dual logging:
    - JSON log for structured data
    - TXT log for human-readable output
    """
    from pathlib import Path

    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON log file (structured data)
    json_log_file = log_path / f"qpublic_enrichment_{timestamp}.json"

    # TXT log file (human readable)
    txt_log_file = log_path / f"qpublic_enrichment_{timestamp}.txt"

    # Configure Python's logging for TXT file
    file_handler = logging.FileHandler(txt_log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    return json_log_file, txt_log_file


class EnrichmentLogger:
    """Logs enrichment progress to JSON file"""

    def __init__(self, json_log_file: str):
        self.json_log_file = json_log_file
        self.entries = []

        # Write initial header
        self.log_event({
            'event': 'enrichment_started',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0'
        })

    def log_event(self, event_data: dict):
        """Log an event to JSON file"""
        event_data['timestamp'] = datetime.now().isoformat()
        self.entries.append(event_data)

        # Append to JSON file (newline-delimited JSON)
        with open(self.json_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event_data) + '\n')

    def log_property_success(self, parcel_id: str, data: dict, duration_seconds: float):
        """Log successful property enrichment"""
        coords = data.get('coordinates', {})
        self.log_event({
            'event': 'property_success',
            'parcel_id': parcel_id,
            'duration_seconds': duration_seconds,
            'has_coordinates': coords.get('latitude') is not None and coords.get('longitude') is not None,
            'has_market_value': data.get('market_value') is not None,
            'has_year_built': data.get('year_built') is not None,
            'has_square_footage': data.get('square_footage') is not None
        })

    def log_property_failure(self, parcel_id: str, error_type: str, error_msg: str, attempts: int):
        """Log failed property enrichment"""
        self.log_event({
            'event': 'property_failure',
            'parcel_id': parcel_id,
            'error_type': error_type,
            'error_message': error_msg,
            'attempts': attempts
        })

    def log_bot_detection(self, parcel_id: str, attempt: int, wait_time: int):
        """Log bot detection event"""
        self.log_event({
            'event': 'bot_detection',
            'parcel_id': parcel_id,
            'attempt': attempt,
            'wait_time_seconds': wait_time
        })

    def log_summary(self, stats: dict):
        """Log final summary"""
        self.log_event({
            'event': 'enrichment_complete',
            'total': stats['total'],
            'success': stats['success'],
            'failed': stats['failed'],
            'success_rate': stats['success'] / stats['total'] if stats['total'] > 0 else 0,
            'duration_seconds': (datetime.now() - stats['start_time']).total_seconds(),
            'rate_per_second': stats['success'] / (datetime.now() - stats['start_time']).total_seconds() if (datetime.now() - stats['start_time']).total_seconds() > 0 else 0
        })


async def enrich_qpublic_batch(limit: int = 100, headless: bool = False, parallel: int = 10):
    """
    Enrich batch of properties with qPublic data

    Args:
        limit: Number of properties to enrich
        headless: Run browsers in headless mode (NOT recommended for qPublic)
        parallel: Number of parallel browser instances
    """

    # Set up logging
    json_log_file, txt_log_file = setup_logging()
    enrichment_logger = EnrichmentLogger(json_log_file)

    print(f"\nLogging to:")
    print(f"   JSON: {json_log_file}")
    print(f"   TXT:  {txt_log_file}\n")

    logging.info(f"Starting qPublic enrichment: limit={limit}, headless={headless}, parallel={parallel}")

    # Initialize database and market
    await db_manager.initialize()
    await CurrentMarket.initialize()

    enrichment_logger.log_event({
        'event': 'config',
        'limit': limit,
        'headless': headless,
        'parallel': parallel
    })

    logger.info(
        "starting_qpublic_enrichment",
        limit=limit,
        headless=headless,
        parallel=parallel
    )

    # Get properties that need enrichment (missing coordinates)
    async with db_manager.get_session() as session:
        # Find properties without qPublic enrichment
        result = await session.execute(
            select(BulkPropertyRecord.parcel_id)
            .where(BulkPropertyRecord.qpublic_enriched_at.is_(None))
            .limit(limit)
        )
        properties_to_enrich = result.all()

        if not properties_to_enrich:
            logger.info("no_properties_need_enrichment")
            print("\nAll properties already enriched!")
            return

        logger.info(
            "found_properties_needing_enrichment",
            count=len(properties_to_enrich)
        )
        print(f"\nFound {len(properties_to_enrich)} properties needing enrichment")

    # Create browser scrapers (multiple instances for parallel)
    scrapers = []
    for i in range(parallel):
        scraper = QPublicBrowserScraperFast(headless=headless)
        await scraper.start_browser()
        scrapers.append(scraper)
        logger.info(f"browser_{i+1}_started")

    print(f"Started {len(scrapers)} browser instances\n")

    # Track stats
    stats = {
        'total': len(properties_to_enrich),
        'success': 0,
        'failed': 0,
        'start_time': datetime.now()
    }

    # Scrape properties
    semaphore = asyncio.Semaphore(parallel)

    async def scrape_and_save(parcel_id: str, idx: int):
        """Scrape property and save to database with retry logic"""
        async with semaphore:
            scraper = scrapers[idx % len(scrapers)]
            max_retries = 3
            retry_delay = 5  # seconds
            property_start_time = datetime.now()

            for attempt in range(max_retries):
                try:
                    logger.info(
                        "scraping_property",
                        parcel_id=parcel_id,
                        progress=f"{idx+1}/{stats['total']}",
                        attempt=attempt+1
                    )

                    # Scrape qPublic
                    qpublic_data = await scraper.scrape_property_fast(parcel_id)

                    # Sanitize NaN values to None (PostgreSQL cannot handle NaN)
                    if qpublic_data:
                        qpublic_data = sanitize_nan(qpublic_data)

                    if not qpublic_data:
                        logger.warning("no_data_returned", parcel_id=parcel_id, attempt=attempt+1)

                        # If last attempt, mark as failed
                        if attempt == max_retries - 1:
                            # Mark as failed in database (so we can retry later)
                            async with db_manager.get_session() as session:
                                await session.execute(
                                    update(BulkPropertyRecord)
                                    .where(BulkPropertyRecord.parcel_id == parcel_id)
                                    .values(
                                        qpublic_enrichment_status='failed_no_data',
                                        qpublic_enriched_at=datetime.now()
                                    )
                                )
                                await session.commit()
                            stats['failed'] += 1
                        else:
                            # Retry with delay
                            await asyncio.sleep(retry_delay)
                            continue
                        return

                    # Update database
                    async with db_manager.get_session() as session:
                        # Extract coordinates from nested dict
                        coords = qpublic_data.get('coordinates', {})

                        # Build update values
                        update_values = {
                            'latitude': coords.get('latitude'),
                            'longitude': coords.get('longitude'),
                            'raw_data': qpublic_data,  # Store complete response
                            'qpublic_enriched_at': datetime.now(),
                            'qpublic_enrichment_status': 'success'
                        }

                        # Add optional fields from qpublic_data if they exist
                        if 'year_built' in qpublic_data and qpublic_data['year_built']:
                            update_values['year_built'] = qpublic_data['year_built']
                        if 'square_footage' in qpublic_data and qpublic_data['square_footage']:
                            update_values['square_feet'] = qpublic_data['square_footage']
                        if 'bedrooms' in qpublic_data and qpublic_data['bedrooms']:
                            update_values['bedrooms'] = qpublic_data['bedrooms']
                        if 'bathrooms' in qpublic_data and qpublic_data['bathrooms']:
                            update_values['bathrooms'] = qpublic_data['bathrooms']
                        if 'use_code' in qpublic_data and qpublic_data['use_code']:
                            update_values['use_code'] = qpublic_data['use_code']
                        if 'market_value' in qpublic_data and qpublic_data['market_value']:
                            update_values['market_value'] = qpublic_data['market_value']
                        if 'assessed_value' in qpublic_data and qpublic_data['assessed_value']:
                            update_values['assessed_value'] = qpublic_data['assessed_value']

                        await session.execute(
                            update(BulkPropertyRecord)
                            .where(BulkPropertyRecord.parcel_id == parcel_id)
                            .values(**update_values)
                        )
                        await session.commit()

                    stats['success'] += 1

                    # Log success
                    property_duration = (datetime.now() - property_start_time).total_seconds()
                    enrichment_logger.log_property_success(parcel_id, qpublic_data, property_duration)
                    logging.info(f"SUCCESS: {parcel_id} - {property_duration:.2f}s")

                    # Progress update
                    elapsed = (datetime.now() - stats['start_time']).total_seconds()
                    rate = stats['success'] / elapsed if elapsed > 0 else 0
                    remaining = (stats['total'] - stats['success']) / rate if rate > 0 else 0

                    print(
                        f"SUCCESS {parcel_id}: {stats['success']}/{stats['total']} "
                        f"({rate:.2f} props/sec, ~{remaining/60:.1f} min remaining)"
                    )

                    # Success - break retry loop
                    break

                except Exception as e:
                    error_msg = str(e)

                    # Check for bot detection errors
                    if 'cloudflare' in error_msg.lower() or 'captcha' in error_msg.lower() or '403' in error_msg:
                        logger.error(
                            "bot_detection_error",
                            parcel_id=parcel_id,
                            error=error_msg,
                            attempt=attempt+1
                        )
                        print(f"WARNING {parcel_id}: BOT DETECTION - {error_msg}")

                        # If we hit bot detection, wait longer before retry
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (attempt + 2)  # Exponential backoff
                            enrichment_logger.log_bot_detection(parcel_id, attempt + 1, wait_time)
                            logging.warning(f"BOT DETECTION: {parcel_id} - waiting {wait_time}s (attempt {attempt+1})")
                            print(f"   Waiting {wait_time}s before retry...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Last attempt failed - mark in database
                            enrichment_logger.log_property_failure(parcel_id, 'bot_detection', error_msg, max_retries)
                            logging.error(f"FAILED (bot detection): {parcel_id} - {error_msg}")
                            async with db_manager.get_session() as session:
                                await session.execute(
                                    update(BulkPropertyRecord)
                                    .where(BulkPropertyRecord.parcel_id == parcel_id)
                                    .values(
                                        qpublic_enrichment_status='failed_bot_detection',
                                        qpublic_enriched_at=datetime.now()
                                    )
                                )
                                await session.commit()
                            stats['failed'] += 1
                    else:
                        logger.error(
                            "scrape_failed",
                            parcel_id=parcel_id,
                            error=error_msg,
                            error_type=type(e).__name__,
                            attempt=attempt+1
                        )

                        # General error - retry with shorter delay
                        if attempt < max_retries - 1:
                            logging.warning(f"RETRY: {parcel_id} - {error_msg} (attempt {attempt+1})")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            # Mark as failed after all retries
                            enrichment_logger.log_property_failure(parcel_id, type(e).__name__, error_msg, max_retries)
                            logging.error(f"FAILED ({type(e).__name__}): {parcel_id} - {error_msg}")
                            async with db_manager.get_session() as session:
                                await session.execute(
                                    update(BulkPropertyRecord)
                                    .where(BulkPropertyRecord.parcel_id == parcel_id)
                                    .values(
                                        qpublic_enrichment_status=f'failed_{type(e).__name__}',
                                        qpublic_enriched_at=datetime.now()
                                    )
                                )
                                await session.commit()
                            stats['failed'] += 1
                            print(f"FAILED {parcel_id}: {error_msg} (after {max_retries} attempts)")

    # Run all scrapes in parallel
    tasks = [
        scrape_and_save(parcel_id, idx)
        for idx, (parcel_id,) in enumerate(properties_to_enrich)
    ]

    await asyncio.gather(*tasks)

    # Close browsers
    for scraper in scrapers:
        await scraper.close_browser()

    # Final stats
    elapsed = (datetime.now() - stats['start_time']).total_seconds()

    # Log summary
    enrichment_logger.log_summary(stats)
    logging.info(f"COMPLETE: {stats['success']}/{stats['total']} success ({stats['success']/stats['total']*100:.1f}%), {elapsed/60:.1f} min, {stats['success']/elapsed:.2f} props/sec")

    print("\n" + "="*60)
    print("ENRICHMENT COMPLETE")
    print("="*60)
    print(f"Success: {stats['success']}/{stats['total']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"Failed: {stats['failed']}/{stats['total']} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Rate: {stats['success']/elapsed:.2f} properties/second")
    print("="*60)
    print(f"\nFull logs saved to:")
    print(f"   JSON: {json_log_file}")
    print(f"   TXT:  {txt_log_file}")

    # Show failure breakdown
    if stats['failed'] > 0:
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(
                    BulkPropertyRecord.qpublic_enrichment_status,
                    func.count(BulkPropertyRecord.id).label('count')
                )
                .where(BulkPropertyRecord.qpublic_enrichment_status.like('failed%'))
                .group_by(BulkPropertyRecord.qpublic_enrichment_status)
            )
            failures = result.all()

            if failures:
                print("\nFailure Breakdown:")
                for status, count in failures:
                    print(f"   {status}: {count}")

                print("\nTo retry failed properties, run:")
                print("   venv_src/Scripts/python.exe scripts/enrich_qpublic_batch.py --limit 100 --retry-failed")

    logger.info(
        "enrichment_complete",
        success=stats['success'],
        failed=stats['failed'],
        total=stats['total'],
        duration_seconds=elapsed,
        rate_per_second=stats['success']/elapsed
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich properties with qPublic data")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of properties to enrich (default: 100)"
    )
    parser.add_argument(
        "--headless",
        type=str,
        default="false",
        choices=["true", "false"],
        help="Run browsers in headless mode (default: false, NOT recommended for qPublic)"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=10,
        help="Number of parallel browser instances (default: 10)"
    )

    args = parser.parse_args()

    headless_bool = args.headless.lower() == "true"

    print("\n" + "="*60)
    print("qPublic Batch Enrichment")
    print("="*60)
    print(f"Limit: {args.limit} properties")
    print(f"Parallel browsers: {args.parallel}")
    print(f"Headless: {headless_bool} ({'NOT RECOMMENDED' if not headless_bool else ''})")
    print("="*60 + "\n")

    asyncio.run(enrich_qpublic_batch(
        limit=args.limit,
        headless=headless_bool,
        parallel=args.parallel
    ))
