#!/usr/bin/env python3
"""
Bulk Data Sync Script

Downloads and syncs bulk data sources with MD5 change detection.

Usage:
    # Initial bulk load (run once)
    python scripts/bulk_data_sync.py --initial

    # Daily sync (checks MD5, only updates if changed)
    python scripts/bulk_data_sync.py --daily

    # Force update (ignore MD5check)
    python scripts/bulk_data_sync.py --force

    # Sync specific source
    python scripts/bulk_data_sync.py --source sunbiz
    python scripts/bulk_data_sync.py --source property
    python scripts/bulk_data_sync.py --source gis
    python scripts/bulk_data_sync.py --source zoning

Schedule:
    - Sunbiz: Daily (cron: 0 2 * * *)
    - Property Appraiser: Weekly (cron: 0 3 * * 0)
    - GIS: Monthly (cron: 0 4 1 * *)
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.loader import load_market_config
from src.config.current_market import CurrentMarket
from src.database import DatabaseManager
from src.services.bulk_data_manager import BulkDataManager
import structlog

logger = structlog.get_logger(__name__)


async def run_initial_load(market_name: str = 'gainesville_fl'):
    """
    Initial bulk load - downloads all data for the first time.

    This should be run ONCE when setting up the system.
    """
    logger.info("=== INITIAL BULK LOAD STARTED ===", market=market_name)

    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()

    # Initialize CurrentMarket (required for multi-market schema v2)
    await CurrentMarket.initialize(market_code=market_name)
    logger.info("CurrentMarket initialized", market_code=CurrentMarket.get_code(), market_id=CurrentMarket.get_id())

    # Load config (still needed for BulkDataManager)
    config = load_market_config(market_name)

    # Initialize bulk data manager
    bulk_manager = BulkDataManager(config, db_manager)

    # Download and process all sources
    logger.info("Syncing Sunbiz SFTP (all historical data)...")
    sunbiz_snapshot = await bulk_manager.sync_sunbiz(force_update=True)

    logger.info("Syncing Property Appraiser (all parcels)...")
    property_snapshot = await bulk_manager.sync_property_appraiser(force_update=True)

    logger.info("Syncing GIS (parcel geometries) - DISABLED in schema v2...")
    gis_snapshot = await bulk_manager.sync_gis(layer_name='parcels', force_update=True)

    # Close database
    await db_manager.close()

    logger.info("=== INITIAL BULK LOAD COMPLETED ===")
    logger.info("Summary:",
               sunbiz_id=sunbiz_snapshot['id'] if sunbiz_snapshot else None,
               property_id=property_snapshot['id'] if property_snapshot else None,
               gis_id=gis_snapshot['id'] if gis_snapshot else None)


async def run_daily_sync(market_name: str = 'gainesville_fl', force: bool = False):
    """
    Daily sync - checks MD5, only updates if changed.

    This should run daily via cron.
    """
    logger.info("=== DAILY SYNC STARTED ===", market=market_name, force=force)

    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()

    # Initialize CurrentMarket (required for multi-market schema v2)
    await CurrentMarket.initialize(market_code=market_name)
    logger.info("CurrentMarket initialized", market_code=CurrentMarket.get_code(), market_id=CurrentMarket.get_id())

    # Load config (still needed for BulkDataManager)
    config = load_market_config(market_name)

    # Initialize bulk data manager
    bulk_manager = BulkDataManager(config, db_manager)

    # Sync all sources (with MD5 check)
    await bulk_manager.sync_all_bulk_data(force_update=force)

    # Close database
    await db_manager.close()

    logger.info("=== DAILY SYNC COMPLETED ===")


async def run_single_source(source: str, market_name: str = 'gainesville_fl', force: bool = False):
    """Sync a single data source"""
    logger.info(f"=== SYNCING {source.upper()} ===", market=market_name)

    # Initialize database FIRST
    from src.database.connection import db_manager
    await db_manager.initialize()

    # THEN initialize CurrentMarket (requires db connection)
    await CurrentMarket.initialize(market_code=market_name)
    logger.info("CurrentMarket initialized", market_code=CurrentMarket.get_code(), market_id=CurrentMarket.get_id())

    # Load config (still needed for BulkDataManager)
    config = load_market_config(market_name)

    # Initialize bulk data manager
    bulk_manager = BulkDataManager(config, db_manager)

    # Sync specific source
    if source == 'sunbiz':
        await bulk_manager.sync_sunbiz(force_update=force)
    elif source == 'property':
        await bulk_manager.sync_property_appraiser(force_update=force)
    elif source == 'gis':
        logger.warning("GIS sync disabled in schema v2 - will be added in Phase 3")
        await bulk_manager.sync_gis(layer_name='parcels', force_update=force)
    elif source == 'zoning':
        logger.warning("Zoning sync disabled in schema v2 - will be added in Phase 3")
        await bulk_manager.sync_zoning(layer_name='zoning', force_update=force)
    else:
        logger.error("unknown_source", source=source)
        sys.exit(1)

    # Close database
    await db_manager.close()

    logger.info(f"=== {source.upper()} SYNC COMPLETED ===")


async def enrich_existing_properties(market_name: str = 'gainesville_fl'):
    """
    Enrich existing properties with bulk data.

    Matches properties to bulk_property_records and fills in missing data.
    DISABLED in schema v2 - GIS tables not yet implemented.
    """
    logger.info("=== ENRICHING EXISTING PROPERTIES ===", market=market_name)

    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()

    # Initialize CurrentMarket (required for multi-market schema v2)
    await CurrentMarket.initialize(market_code=market_name)
    logger.info("CurrentMarket initialized", market_code=CurrentMarket.get_code(), market_id=CurrentMarket.get_id())

    # Load config (still needed for BulkDataManager)
    config = load_market_config(market_name)

    # Initialize bulk data manager
    bulk_manager = BulkDataManager(config, db_manager)

    # Run enrichment (will return 0s in schema v2 until GIS implemented)
    stats = await bulk_manager.enrich_properties_from_bulk(similarity_threshold=0.7)

    logger.info("=== ENRICHMENT COMPLETED ===",
               matched=stats['matched'],
               updated=stats['updated'],
               skipped=stats['skipped'])

    await db_manager.close()


def main():
    parser = argparse.ArgumentParser(description='Bulk data sync manager')

    # Operation mode
    parser.add_argument('--initial', action='store_true',
                       help='Initial bulk load (downloads all data)')
    parser.add_argument('--daily', action='store_true',
                       help='Daily sync with MD5 check')
    parser.add_argument('--enrich', action='store_true',
                       help='Enrich existing properties from bulk data')

    # Source selection
    parser.add_argument('--source', choices=['sunbiz', 'property', 'gis', 'zoning'],
                       help='Sync specific source only')

    # Options
    parser.add_argument('--market', default='gainesville_fl',
                       help='Market name (default: gainesville_fl)')
    parser.add_argument('--force', action='store_true',
                       help='Force update even if MD5 unchanged')

    args = parser.parse_args()

    # Run appropriate operation
    if args.initial:
        asyncio.run(run_initial_load(args.market))
    elif args.daily:
        asyncio.run(run_daily_sync(args.market, force=args.force))
    elif args.source:
        asyncio.run(run_single_source(args.source, args.market, force=args.force))
    elif args.enrich:
        asyncio.run(enrich_existing_properties(args.market))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
