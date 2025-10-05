#!/usr/bin/env python3
"""
Re-import CAMA Data with Fixed Address Field Mappings

This script re-imports CAMA data using the corrected field mappings that
properly extract owner_mail_addr2 (99.98% coverage) instead of just
owner_mail_addr1 (4% coverage).

Usage:
    python scripts/reimport_cama_addresses.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.loader import load_market_config
from src.config.current_market import CurrentMarket
from src.database.connection import db_manager  # Use singleton instance
from src.services.bulk_data_manager import BulkDataManager
import structlog
from sqlalchemy import text  # For raw SQL queries

logger = structlog.get_logger(__name__)


async def reimport_cama():
    """Re-import CAMA data with corrected field mappings."""

    print("\n" + "=" * 80)
    print("Re-importing CAMA Data with Fixed Address Mappings")
    print("=" * 80)
    print("\nFixes applied:")
    print("  - owner_mail_addr2 (99.98% coverage) now prioritized")
    print("  - Complete addresses built: 'STREET, CITY, STATE ZIP'")
    print("  - Expected result: 108,366 mailing addresses (vs 4,367 before)")
    print("\n" + "=" * 80)

    # Initialize database using singleton instance
    await db_manager.initialize()

    # Initialize CurrentMarket (uses singleton db_manager)
    await CurrentMarket.initialize(market_code='gainesville_fl')
    logger.info("CurrentMarket initialized",
                market_code=CurrentMarket.get_code(),
                market_id=CurrentMarket.get_id())

    # Load config
    config = load_market_config('gainesville_fl')

    # Initialize bulk data manager
    bulk_manager = BulkDataManager(config, db_manager)

    # Check current address coverage
    print("\nChecking current address coverage in database...")
    async with db_manager.get_session() as session:
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(mailing_address) as with_mailing,
                COUNT(site_address) as with_site
            FROM bulk_property_records
            WHERE market_id = :market_id
        """), {'market_id': CurrentMarket.get_id()})

        row = result.fetchone()
        print(f"\nCurrent coverage:")
        print(f"  Total properties: {row[0]:,}")
        print(f"  With mailing_address: {row[1]:,} ({row[1]/row[0]*100:.2f}%)")
        print(f"  With site_address: {row[2]:,} ({row[2]/row[0]*100:.2f}%)")

    # Re-sync property appraiser data (force update)
    print("\n" + "=" * 80)
    print("Starting CAMA re-import (this may take 5-10 minutes)...")
    print("=" * 80)

    property_snapshot = await bulk_manager.sync_property_appraiser(force_update=True)

    print("\n" + "=" * 80)
    print("Re-import completed!")
    print("=" * 80)

    if property_snapshot:
        print(f"\nSnapshot ID: {property_snapshot.get('id')}")
        print(f"Records imported: {property_snapshot.get('records_imported', 0):,}")

    # Check new address coverage
    print("\nChecking new address coverage...")
    async with db_manager.get_session() as session:
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(mailing_address) as with_mailing,
                COUNT(site_address) as with_site
            FROM bulk_property_records
            WHERE market_id = :market_id
        """), {'market_id': CurrentMarket.get_id()})

        row = result.fetchone()
        print(f"\nNew coverage:")
        print(f"  Total properties: {row[0]:,}")
        print(f"  With mailing_address: {row[1]:,} ({row[1]/row[0]*100:.2f}%)")
        print(f"  With site_address: {row[2]:,} ({row[2]/row[0]*100:.2f}%)")

        # Sample addresses
        print("\nSample mailing addresses:")
        result = await session.execute(text("""
            SELECT parcel_id, mailing_address
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND mailing_address IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 10
        """), {'market_id': CurrentMarket.get_id()})

        for row in result:
            print(f"  {row[0]}: {row[1]}")

    # Close database
    await db_manager.close()

    print("\n" + "=" * 80)
    print("SUCCESS! CAMA data re-imported with corrected field mappings")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(reimport_cama())
