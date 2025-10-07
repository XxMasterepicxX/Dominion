#!/usr/bin/env python3
"""
Entity Resolution Script - Link Property Owners to Entities

This script runs entity resolution on bulk_property_records to:
1. Match all property owners to entities in the entities table
2. Populate entity_market_properties with portfolio data
3. Enable all intelligence queries (assemblages, portfolios, etc.)

Usage:
    python scripts/run_entity_resolution.py --market gainesville_fl
    python scripts/run_entity_resolution.py --market gainesville_fl --limit 1000  # Test run
"""
import asyncio
import sys
import os
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import text, select, func
from collections import defaultdict

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.database.connection import db_manager
from src.database.models import Entity
import structlog

logger = structlog.get_logger(__name__)


class EntityResolutionRunner:
    """Orchestrates bulk entity resolution on property records"""

    def __init__(self, market_code: str, limit: Optional[int] = None):
        self.market_code = market_code
        self.limit = limit

        # Stats
        self.stats = {
            'total_owners': 0,
            'entities_created': 0,
            'entities_matched': 0,
            'properties_processed': 0,
            'properties_linked': 0,
            'errors': 0,
            'start_time': datetime.now()
        }

    async def run(self):
        """Main execution flow"""
        print("=" * 80)
        print("DOMINION ENTITY RESOLUTION")
        print("=" * 80)
        print(f"Market: {self.market_code}")
        print(f"Limit: {self.limit or 'All properties'}")
        print(f"Started: {self.stats['start_time']}")
        print()

        try:
            await db_manager.initialize()

            # Step 1: Get market ID
            market_id = await self._get_market_id()
            if not market_id:
                print(f"ERROR: Market '{self.market_code}' not found")
                return

            # Step 2: Get unique owners
            print("Step 1: Gathering unique property owners...")
            owners = await self._get_unique_owners(market_id)
            self.stats['total_owners'] = len(owners)
            print(f"Found {len(owners)} unique property owners\n")

            # Step 3: Process each owner
            print("Step 2: Resolving entities...")
            await self._process_owners(owners, market_id)

            # Step 4: Populate entity_market_properties
            print("\nStep 3: Populating entity_market_properties...")
            await self._populate_entity_market_properties(market_id)

            # Step 5: Show results
            await self._print_results()

        except Exception as e:
            logger.error("entity_resolution_failed", error=str(e))
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await db_manager.close()

    async def _get_market_id(self) -> Optional[str]:
        """Get market UUID from code"""
        async with db_manager.get_session() as session:
            result = await session.execute(
                text("SELECT id, market_name FROM markets WHERE market_code = :code"),
                {'code': self.market_code}
            )
            row = result.fetchone()
            if row:
                print(f"Market: {row[1]} ({row[0]})\n")
                return str(row[0])
            return None

    async def _get_unique_owners(self, market_id: str) -> List[Dict]:
        """Get all unique property owners with sample addresses"""
        async with db_manager.get_session() as session:
            # Get unique owners with property counts and sample data
            query = text("""
                SELECT
                    owner_name,
                    COUNT(*) as property_count,
                    MAX(mailing_address) as sample_address,
                    MAX(city) as sample_city,
                    STRING_AGG(DISTINCT parcel_id, ',') as sample_parcels
                FROM bulk_property_records
                WHERE market_id = :market_id
                  AND owner_name IS NOT NULL
                  AND TRIM(owner_name) != ''
                GROUP BY owner_name
                ORDER BY property_count DESC
                """ + (f" LIMIT {self.limit}" if self.limit else ""))

            result = await session.execute(query, {'market_id': market_id})

            owners = []
            for row in result:
                owners.append({
                    'name': row[0],
                    'property_count': row[1],
                    'sample_address': row[2],
                    'sample_city': row[3],
                    'sample_parcels': row[4].split(',')[:3] if row[4] else []
                })

            return owners

    async def _process_owners(self, owners: List[Dict], market_id: str):
        """Process each owner - create or find entities"""
        batch_size = 100
        processed = 0

        for i in range(0, len(owners), batch_size):
            batch = owners[i:i + batch_size]

            async with db_manager.get_session() as session:
                for owner_data in batch:
                    try:
                        owner_name = owner_data['name']

                        # Check if entity already exists by name
                        result = await session.execute(
                            text("SELECT id FROM entities WHERE name = :name LIMIT 1"),
                            {'name': owner_name}
                        )
                        existing = result.fetchone()

                        if existing:
                            # Entity already exists
                            entity_id = existing[0]
                            self.stats['entities_matched'] += 1
                        else:
                            # Create new entity
                            entity_type = self._infer_entity_type(owner_name)
                            canonical_name = owner_name.upper().strip()

                            result = await session.execute(
                                text("""
                                    INSERT INTO entities (
                                        entity_type,
                                        name,
                                        canonical_name,
                                        primary_address,
                                        confidence_score,
                                        verification_source
                                    ) VALUES (
                                        :entity_type,
                                        :name,
                                        :canonical_name,
                                        :primary_address,
                                        0.95,
                                        'property_appraiser'
                                    ) RETURNING id
                                """),
                                {
                                    'entity_type': entity_type,
                                    'name': owner_name,
                                    'canonical_name': canonical_name,
                                    'primary_address': owner_data.get('sample_address')
                                }
                            )
                            entity_id = result.scalar()
                            self.stats['entities_created'] += 1

                        # Store entity_id for later linking
                        owner_data['entity_id'] = str(entity_id)

                        processed += 1

                        # Progress update
                        if processed % 100 == 0:
                            pct = (processed / len(owners)) * 100
                            print(f"  Progress: {processed}/{len(owners)} owners ({pct:.1f}%) "
                                  f"[Created: {self.stats['entities_created']}, "
                                  f"Matched: {self.stats['entities_matched']}]")

                    except Exception as e:
                        self.stats['errors'] += 1
                        logger.error("owner_resolution_failed",
                                   owner=owner_data['name'],
                                   error=str(e))
                        continue

                # Commit batch
                await session.commit()

        print(f"  Completed: {processed}/{len(owners)} owners processed")

    def _infer_entity_type(self, name: str) -> str:
        """Infer entity type from name"""
        name_upper = name.upper()

        if any(x in name_upper for x in [' LLC', 'LLC ', ' L.L.C', 'LIMITED LIABILITY']):
            return 'llc'
        elif any(x in name_upper for x in [' INC', 'INC ', ' CORP', 'CORPORATION', 'INCORPORATED']):
            return 'corporation'
        elif any(x in name_upper for x in ['CITY OF', 'COUNTY', 'STATE OF', 'SCHOOL', 'GOVERNMENT']):
            return 'government'
        elif any(x in name_upper for x in [' LP', ' LLP', 'PARTNERSHIP', 'PARTNERS']):
            return 'partnership'
        elif '&' in name_upper and name_upper.count(' ') <= 4:  # Names like "SMITH JOHN & MARY"
            return 'person'
        elif any(x in name_upper for x in ['TRUST', 'TRUSTEE', 'ESTATE']):
            return 'person'
        else:
            return 'unknown'

    async def _populate_entity_market_properties(self, market_id: str):
        """Populate entity_market_properties table with aggregated data"""
        async with db_manager.get_session() as session:
            # For each entity with properties in this market, calculate stats
            query = text("""
                INSERT INTO entity_market_properties (
                    entity_id,
                    market_id,
                    total_properties,
                    total_value,
                    property_ids,
                    first_activity_date,
                    last_activity_date
                )
                SELECT
                    e.id as entity_id,
                    :market_id as market_id,
                    COUNT(DISTINCT bp.id) as total_properties,
                    SUM(COALESCE(bp.market_value, 0)) as total_value,
                    ARRAY_AGG(DISTINCT bp.id) as property_ids,
                    MIN(bp.last_sale_date) as first_activity_date,
                    MAX(bp.last_sale_date) as last_activity_date
                FROM entities e
                JOIN bulk_property_records bp ON bp.owner_name = e.name
                WHERE bp.market_id = :market_id
                GROUP BY e.id
                ON CONFLICT (entity_id, market_id)
                DO UPDATE SET
                    total_properties = EXCLUDED.total_properties,
                    total_value = EXCLUDED.total_value,
                    property_ids = EXCLUDED.property_ids,
                    first_activity_date = EXCLUDED.first_activity_date,
                    last_activity_date = EXCLUDED.last_activity_date,
                    updated_at = NOW()
            """)

            result = await session.execute(query, {'market_id': market_id})
            await session.commit()

            # Get count of records created
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM entity_market_properties WHERE market_id = :market_id"),
                {'market_id': market_id}
            )
            count = count_result.scalar()

            print(f"  Created/updated {count} entity_market_properties records")
            self.stats['properties_linked'] = count

    async def _print_results(self):
        """Print final statistics"""
        duration = datetime.now() - self.stats['start_time']

        print("\n" + "=" * 80)
        print("ENTITY RESOLUTION COMPLETE")
        print("=" * 80)
        print(f"Duration: {duration}")
        print()
        print("RESULTS:")
        print(f"  Total unique owners:        {self.stats['total_owners']:>8,}")
        print(f"  Entities created (new):     {self.stats['entities_created']:>8,}")
        print(f"  Entities matched (existing):{self.stats['entities_matched']:>8,}")
        print(f"  Entity portfolios created:  {self.stats['properties_linked']:>8,}")
        print(f"  Errors:                     {self.stats['errors']:>8,}")
        print()

        # Show sample results
        print("SAMPLE RESULTS (Top 10 Property Owners):")
        async with db_manager.get_session() as session:
            results = await session.execute(text("""
                SELECT
                    e.name,
                    e.entity_type,
                    emp.total_properties,
                    emp.total_value
                FROM entities e
                JOIN entity_market_properties emp ON emp.entity_id = e.id
                JOIN markets m ON m.id = emp.market_id
                WHERE m.market_code = :market_code
                ORDER BY emp.total_properties DESC
                LIMIT 10
            """), {'market_code': self.market_code})

            print(f"{'Entity Name':<50} {'Type':<15} {'Properties':>12} {'Total Value':>15}")
            print("-" * 95)
            for row in results:
                name = row[0][:48] if row[0] else 'Unknown'
                entity_type = row[1] or 'unknown'
                props = row[2] or 0
                value = row[3] or 0
                print(f"{name:<50} {entity_type:<15} {props:>12,} ${value:>14,.0f}")

        print()
        print("NEXT STEPS:")
        print("1. Verify results with test queries")
        print("2. Build intelligence layer (assemblage detector, etc.)")
        print("3. Create AI Property Analysis Agent")
        print()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Run entity resolution on bulk property records'
    )
    parser.add_argument(
        '--market',
        type=str,
        default='gainesville_fl',
        help='Market code (e.g., gainesville_fl)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of owners to process (for testing)'
    )

    args = parser.parse_args()

    runner = EntityResolutionRunner(
        market_code=args.market,
        limit=args.limit
    )

    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
