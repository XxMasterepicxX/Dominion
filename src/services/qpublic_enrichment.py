"""
qPublic Property Enrichment Service

Uses qPublic scraper to fill gaps in CAMA bulk data:
- Missing property addresses (CAMA has 0%)
- Missing financial data (CAMA missing 0.8% of parcels)
- Multiple improvements per parcel (CAMA only captures one)

Strategy:
1. Identify properties with NULL/missing critical fields
2. Scrape qPublic for authoritative data
3. Update bulk_property_records with complete data
"""
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from database import DatabaseManager
from database.models import BulkPropertyRecord, BulkDataSnapshot
from scrapers.data_sources.qpublic_scraper import QPublicBrowserScraperFast

logger = structlog.get_logger(__name__)


class QPublicEnrichmentService:
    """
    Service to enrich property data using qPublic browser scraper (Patchright).

    Uses browser automation to bypass 403 Forbidden errors.
    """

    def __init__(self, db_manager: DatabaseManager, headless: bool = True):
        """
        Initialize enrichment service.

        Args:
            db_manager: Database manager instance
            headless: Run browser in headless mode (default: True)
        """
        self.db = db_manager
        self.scraper = None  # Will be initialized in async context
        self.headless = headless

    async def find_properties_needing_enrichment(
        self,
        snapshot_id: Optional[int] = None,
        limit: int = 100
    ) -> List[str]:
        """
        Find parcel IDs that need enrichment from qPublic.

        Criteria for needing enrichment:
        - Missing market_value (NULL or 0)
        - Missing property_address (NULL)
        - Missing year_built (NULL)
        - Missing square_footage (NULL)

        Args:
            snapshot_id: Specific snapshot to check (None = latest)
            limit: Maximum parcels to return

        Returns:
            List of parcel IDs needing enrichment
        """
        async with self.db.async_session_maker() as session:
            # Get latest snapshot if not specified
            if snapshot_id is None:
                snapshot_result = await session.execute(
                    select(BulkDataSnapshot.id)
                    .filter(BulkDataSnapshot.data_source.like('property_appraiser%'))
                    .order_by(BulkDataSnapshot.snapshot_date.desc())
                    .limit(1)
                )
                snapshot_row = snapshot_result.first()
                if not snapshot_row:
                    logger.error("No property appraiser snapshots found")
                    return []
                snapshot_id = snapshot_row[0]

            # Find properties with missing critical data
            query = (
                select(BulkPropertyRecord.parcel_id)
                .filter(
                    and_(
                        BulkPropertyRecord.snapshot_id == snapshot_id,
                        or_(
                            BulkPropertyRecord.market_value.is_(None),
                            BulkPropertyRecord.market_value == 0,
                            BulkPropertyRecord.site_address.is_(None),      # FIXED: was property_address
                            BulkPropertyRecord.year_built.is_(None),
                            BulkPropertyRecord.square_feet.is_(None)        # FIXED: was square_footage
                        )
                    )
                )
                .limit(limit)
            )

            result = await session.execute(query)
            parcel_ids = [row[0] for row in result.all()]

            logger.info("Found properties needing enrichment",
                       count=len(parcel_ids),
                       snapshot_id=snapshot_id,
                       limit=limit)

            return parcel_ids

    async def enrich_property(
        self,
        parcel_id: str,
        snapshot_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Enrich a single property from qPublic using browser automation.

        Args:
            parcel_id: Parcel ID to enrich
            snapshot_id: Snapshot ID to update
            session: Database session

        Returns:
            True if successful, False otherwise
        """
        logger.info("Enriching property from qPublic (browser)", parcel_id=parcel_id)

        # Initialize browser scraper if needed
        if self.scraper is None:
            self.scraper = QPublicBrowserScraperFast(headless=self.headless)
            await self.scraper.start_browser()

        # Scrape qPublic (ASYNC with browser automation)
        qpublic_data = await self.scraper.scrape_property_fast(parcel_id)
        if not qpublic_data:
            logger.warning("Failed to scrape qPublic", parcel_id=parcel_id)
            return False

        # Build update dict with non-None values from qPublic
        update_data = {}

        # Map qPublic fields to database columns
        # Fixed field names to match actual schema (site_address not property_address, etc.)
        field_mappings = {
            # Direct fields that exist in schema
            'property_address': 'site_address',      # FIXED: was property_address
            'owner_name': 'owner_name',
            'owner_address': 'mailing_address',      # FIXED: was owner_address
            'market_value': 'market_value',
            'assessed_value': 'assessed_value',
            'taxable_value': 'taxable_value',
            'year_built': 'year_built',
            'square_footage': 'square_feet',         # FIXED: was square_footage
            'bedrooms': 'bedrooms',                  # NEW: added in migration
            'bathrooms': 'bathrooms',                # NEW: added in migration
            'lot_size_acres': 'lot_size_acres',
            'last_sale_date': 'last_sale_date',      # NEW: added in migration
            'last_sale_price': 'last_sale_price',    # NEW: added in migration
            'use_code': 'use_code',                  # NEW: added in migration
            'city': 'city',                          # NEW: added in migration
        }

        for qpublic_field, db_field in field_mappings.items():
            value = qpublic_data.get(qpublic_field)
            if value is not None:  # Only update non-NULL values
                update_data[db_field] = value

        # Store building details in JSONB column
        # These fields don't have dedicated columns, so store in building_details JSONB
        building_details_fields = [
            'exterior_walls', 'interior_walls', 'roofing', 'roof_type',
            'frame', 'floor_cover', 'heat', 'hvac', 'stories',
            'total_area', 'effective_year_built', 'improvement_value',
            'land_value', 'land_agricultural_value', 'agricultural_market_value',
            'exempt_value', 'max_soh_portability'
        ]

        building_details_data = {}
        for field in building_details_fields:
            value = qpublic_data.get(field)
            if value is not None:
                building_details_data[field] = value

        if building_details_data:
            update_data['building_details'] = building_details_data

        # Extract coordinates
        coords = qpublic_data.get('coordinates', {})
        if coords:
            update_data['latitude'] = coords.get('latitude')
            update_data['longitude'] = coords.get('longitude')
            # Note: state_plane coordinates stored in raw_data JSONB

        # Store JSON arrays in existing JSONB columns
        if qpublic_data.get('sales_history'):
            update_data['sales_history'] = qpublic_data['sales_history']

        # Map permits to permit_history (correct column name)
        if qpublic_data.get('permits'):
            update_data['permit_history'] = qpublic_data['permits']

        # Map trim_notices to trim_notice (correct column name)
        if qpublic_data.get('trim_notices'):
            update_data['trim_notice'] = qpublic_data['trim_notices']

        # Add qPublic enrichment metadata
        update_data['qpublic_enriched_at'] = datetime.utcnow()

        # Always update raw_data and last updated timestamp
        # raw_data contains everything including source_url, land_info, sub_areas, links, etc.
        update_data['raw_data'] = qpublic_data
        update_data['updated_at'] = datetime.utcnow()

        # Execute update
        stmt = (
            update(BulkPropertyRecord)
            .where(
                and_(
                    BulkPropertyRecord.parcel_id == parcel_id,
                    BulkPropertyRecord.snapshot_id == snapshot_id
                )
            )
            .values(**update_data)
        )

        result = await session.execute(stmt)
        await session.commit()

        if result.rowcount > 0:
            logger.info("Successfully enriched property",
                       parcel_id=parcel_id,
                       fields_updated=len(update_data))
            return True
        else:
            logger.warning("Property not found in database",
                          parcel_id=parcel_id,
                          snapshot_id=snapshot_id)
            return False

    async def enrich_batch(
        self,
        parcel_ids: List[str],
        snapshot_id: Optional[int] = None,
        batch_size: int = 50
    ) -> Dict[str, int]:
        """
        Enrich multiple properties from qPublic.

        Args:
            parcel_ids: List of parcel IDs to enrich
            snapshot_id: Snapshot ID to update (None = latest)
            batch_size: Number of properties to process in parallel

        Returns:
            Dict with success/failure counts
        """
        # Get snapshot ID if not provided
        if snapshot_id is None:
            async with self.db.async_session_maker() as session:
                snapshot_result = await session.execute(
                    select(BulkDataSnapshot.id)
                    .filter(BulkDataSnapshot.data_source.like('property_appraiser%'))
                    .order_by(BulkDataSnapshot.snapshot_date.desc())
                    .limit(1)
                )
                snapshot_row = snapshot_result.first()
                if not snapshot_row:
                    logger.error("No property appraiser snapshots found")
                    return {"success": 0, "failed": 0, "total": 0}
                snapshot_id = snapshot_row[0]

        logger.info("Starting qPublic batch enrichment",
                   parcel_count=len(parcel_ids),
                   snapshot_id=snapshot_id)

        success_count = 0
        failed_count = 0

        # Process in batches to avoid overwhelming database
        for i in range(0, len(parcel_ids), batch_size):
            batch = parcel_ids[i:i + batch_size]

            async with self.db.async_session_maker() as session:
                for parcel_id in batch:
                    try:
                        success = await self.enrich_property(parcel_id, snapshot_id, session)
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error("Failed to enrich property",
                                   parcel_id=parcel_id,
                                   error=str(e))
                        failed_count += 1

            # Progress logging
            logger.info("Batch progress",
                       processed=i + len(batch),
                       total=len(parcel_ids),
                       success=success_count,
                       failed=failed_count)

        logger.info("qPublic enrichment complete",
                   total=len(parcel_ids),
                   success=success_count,
                   failed=failed_count,
                   success_rate=f"{success_count/len(parcel_ids)*100:.1f}%")

        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(parcel_ids)
        }

    async def enrich_missing_addresses(
        self,
        limit: int = 1000
    ) -> Dict[str, int]:
        """
        Specifically target properties with missing addresses.

        CAMA bulk data has 0% property addresses. This fills that gap.

        Args:
            limit: Maximum properties to enrich

        Returns:
            Dict with success/failure counts
        """
        async with self.db.async_session_maker() as session:
            # Get latest snapshot
            snapshot_result = await session.execute(
                select(BulkDataSnapshot.id)
                .filter(BulkDataSnapshot.source_type == 'property_appraiser')
                .order_by(BulkDataSnapshot.created_at.desc())
                .limit(1)
            )
            snapshot_row = snapshot_result.first()
            if not snapshot_row:
                return {"success": 0, "failed": 0, "total": 0}
            snapshot_id = snapshot_row[0]

            # Find properties with NULL addresses
            query = (
                select(BulkPropertyRecord.parcel_id)
                .filter(
                    and_(
                        BulkPropertyRecord.snapshot_id == snapshot_id,
                        BulkPropertyRecord.site_address.is_(None)     # FIXED: was property_address
                    )
                )
                .limit(limit)
            )

            result = await session.execute(query)
            parcel_ids = [row[0] for row in result.all()]

        logger.info("Found properties missing addresses",
                   count=len(parcel_ids))

        return await self.enrich_batch(parcel_ids, snapshot_id)

    async def enrich_missing_values(
        self,
        limit: int = 1000
    ) -> Dict[str, int]:
        """
        Specifically target properties with missing market values.

        CAMA bulk data missing 0.8% (902 parcels). This fills that gap.

        Args:
            limit: Maximum properties to enrich

        Returns:
            Dict with success/failure counts
        """
        async with self.db.async_session_maker() as session:
            # Get latest snapshot
            snapshot_result = await session.execute(
                select(BulkDataSnapshot.id)
                .filter(BulkDataSnapshot.source_type == 'property_appraiser')
                .order_by(BulkDataSnapshot.created_at.desc())
                .limit(1)
            )
            snapshot_row = snapshot_result.first()
            if not snapshot_row:
                return {"success": 0, "failed": 0, "total": 0}
            snapshot_id = snapshot_row[0]

            # Find properties with NULL or $0 market values
            query = (
                select(BulkPropertyRecord.parcel_id)
                .filter(
                    and_(
                        BulkPropertyRecord.snapshot_id == snapshot_id,
                        or_(
                            BulkPropertyRecord.market_value.is_(None),
                            BulkPropertyRecord.market_value == 0
                        )
                    )
                )
                .limit(limit)
            )

            result = await session.execute(query)
            parcel_ids = [row[0] for row in result.all()]

        logger.info("Found properties missing market values",
                   count=len(parcel_ids))

        return await self.enrich_batch(parcel_ids, snapshot_id)

    async def cleanup(self):
        """Close browser and cleanup resources."""
        if self.scraper:
            await self.scraper.close_browser()
            logger.info("Browser closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup browser."""
        await self.cleanup()


async def main():
    """CLI entry point for testing qPublic enrichment with browser automation."""
    import sys

    db = DatabaseManager()
    await db.initialize()

    # Use async context manager to ensure browser cleanup
    async with QPublicEnrichmentService(db, headless=False) as service:
        if len(sys.argv) > 1 and sys.argv[1] == 'test':
            # Test with a single parcel
            test_parcel = "17757-003-004"

            async with db.async_session_maker() as session:
                # Get latest snapshot
                snapshot_result = await session.execute(
                    select(BulkDataSnapshot.id)
                    .filter(BulkDataSnapshot.data_source.like('property_appraiser%'))
                    .order_by(BulkDataSnapshot.snapshot_date.desc())
                    .limit(1)
                )
                snapshot_row = snapshot_result.first()
                if snapshot_row:
                    snapshot_id = snapshot_row[0]
                    success = await service.enrich_property(test_parcel, snapshot_id, session)
                    print(f"Test enrichment: {'SUCCESS' if success else 'FAILED'}")

        else:
            # Run full enrichment
            print("Finding properties needing enrichment...")
            parcel_ids = await service.find_properties_needing_enrichment(limit=10)

            if parcel_ids:
                print(f"Enriching {len(parcel_ids)} properties from qPublic (browser)...")
                results = await service.enrich_batch(parcel_ids)
                print(f"\nResults: {results}")
            else:
                print("No properties need enrichment!")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
