"""
Populate entity_market_properties table

This script aggregates entity ownership data from bulk_property_records
to populate the entity_market_properties table used by EntityAnalyzer.

Run this after:
1. Running migration 009_add_entity_market_properties.sql
2. Loading property data (bulk_data_sync.py)
3. Whenever entity-property relationships change significantly
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from sqlalchemy import text
import structlog

logger = structlog.get_logger(__name__)


async def populate_entity_market_properties():
    """
    Populate entity_market_properties from bulk_property_records

    Aggregates:
    - Total properties owned by each entity in each market
    - Total market value of properties
    - Array of property IDs
    - First and last activity dates (from sales history)
    """

    print("=" * 80)
    print("POPULATING entity_market_properties TABLE")
    print("=" * 80)

    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # First, ensure table exists (run migration)
        print("\n0. Ensuring entity_market_properties table exists...")
        migration_sql = """
            CREATE TABLE IF NOT EXISTS entity_market_properties (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID REFERENCES entities(id) NOT NULL,
                market_id UUID REFERENCES markets(id) NOT NULL,

                -- Portfolio stats in this market
                total_properties INTEGER DEFAULT 0,
                total_value DECIMAL(15, 2) DEFAULT 0,
                property_ids UUID[] DEFAULT ARRAY[]::UUID[],

                -- Activity tracking
                first_activity_date DATE,
                last_activity_date DATE,

                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                UNIQUE (entity_id, market_id)
            );
        """
        await session.execute(text(migration_sql))

        # Create indexes
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_entity_market_properties_entity_id ON entity_market_properties(entity_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_entity_market_properties_market_id ON entity_market_properties(market_id)
        """))

        await session.commit()
        print("   [OK] Table created/verified")
        # First, clear existing data
        print("\n1. Clearing existing entity_market_properties data...")
        await session.execute(text("DELETE FROM entity_market_properties"))
        await session.commit()
        print("   [OK] Cleared")

        # Get current count
        result = await session.execute(text("""
            SELECT COUNT(*)
            FROM bulk_property_records bpr
            JOIN entities e ON e.name = bpr.owner_name
        """))
        total_props = result.scalar()
        print(f"\n2. Found {total_props:,} properties with matched entities")

        # Aggregate entity ownership by market
        print("\n3. Aggregating entity ownership by market...")
        print("   (This links properties to entities via owner_name match)")

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
                bpr.market_id,
                COUNT(*)::INTEGER as total_properties,
                SUM(bpr.market_value)::DECIMAL(15,2) as total_value,
                ARRAY_AGG(bpr.id) as property_ids,
                MIN(bpr.last_sale_date) as first_activity_date,
                MAX(bpr.last_sale_date) as last_activity_date
            FROM bulk_property_records bpr
            JOIN entities e ON e.name = bpr.owner_name
            WHERE bpr.market_id IS NOT NULL
            GROUP BY e.id, bpr.market_id
            ON CONFLICT (entity_id, market_id)
            DO UPDATE SET
                total_properties = EXCLUDED.total_properties,
                total_value = EXCLUDED.total_value,
                property_ids = EXCLUDED.property_ids,
                first_activity_date = EXCLUDED.first_activity_date,
                last_activity_date = EXCLUDED.last_activity_date,
                updated_at = NOW()
        """)

        result = await session.execute(query)
        await session.commit()

        print("   [OK] Aggregation complete")

        # Show results
        print("\n4. Results:")

        # Total entities with properties
        result = await session.execute(text("""
            SELECT COUNT(DISTINCT entity_id) FROM entity_market_properties
        """))
        total_entities = result.scalar()
        print(f"   - Total entities with properties: {total_entities:,}")

        # Total entity-market combinations
        result = await session.execute(text("""
            SELECT COUNT(*) FROM entity_market_properties
        """))
        total_combos = result.scalar()
        print(f"   - Total entity-market combinations: {total_combos:,}")

        # Show top 10 entities by property count
        print("\n5. Top 10 Entities by Property Count:")
        query = text("""
            SELECT
                e.canonical_name,
                emp.total_properties,
                emp.total_value,
                m.market_name
            FROM entity_market_properties emp
            JOIN entities e ON e.id = emp.entity_id
            JOIN markets m ON m.id = emp.market_id
            ORDER BY emp.total_properties DESC
            LIMIT 10
        """)

        result = await session.execute(query)
        print()
        print(f"   {'Entity':<40} {'Properties':>12} {'Total Value':>18} {'Market':<20}")
        print(f"   {'-'*40} {'-'*12} {'-'*18} {'-'*20}")

        for row in result:
            entity_name = row[0][:38] if row[0] else "Unknown"
            props = row[1]
            value = row[2] if row[2] else 0
            market = row[3]
            print(f"   {entity_name:<40} {props:>12,} ${value:>16,.0f} {market:<20}")

        # Check D.R. Horton specifically
        print("\n6. D.R. Horton Verification:")
        query = text("""
            SELECT
                e.canonical_name,
                emp.total_properties,
                emp.total_value,
                emp.first_activity_date,
                emp.last_activity_date,
                m.market_name
            FROM entity_market_properties emp
            JOIN entities e ON e.id = emp.entity_id
            JOIN markets m ON m.id = emp.market_id
            WHERE e.canonical_name = 'D R HORTON INC'
        """)

        result = await session.execute(query)
        row = result.fetchone()

        if row:
            print(f"   [OK] D.R. Horton found in entity_market_properties:")
            print(f"      Entity: {row[0]}")
            print(f"      Total Properties: {row[1]:,}")
            print(f"      Total Value: ${row[2]:,.0f}")
            print(f"      First Activity: {row[3]}")
            print(f"      Last Activity: {row[4]}")
            print(f"      Market: {row[5]}")
        else:
            print(f"   [WARN]  D.R. Horton NOT found in entity_market_properties")
            print(f"      Checking if D.R. Horton exists in entities...")

            result = await session.execute(text("""
                SELECT id, canonical_name FROM entities
                WHERE canonical_name LIKE '%HORTON%'
            """))
            rows = result.fetchall()
            if rows:
                print(f"      Found {len(rows)} HORTON entities:")
                for r in rows:
                    print(f"        - {r[1]} (ID: {r[0]})")

                    # Check if they own properties
                    result2 = await session.execute(text("""
                        SELECT COUNT(*) FROM bulk_property_records
                        WHERE owner_entity_id = :entity_id
                    """), {'entity_id': str(r[0])})
                    prop_count = result2.scalar()
                    print(f"          Properties owned: {prop_count}")
            else:
                print(f"      [ERROR] No HORTON entities found in database")

    await db_manager.close()

    print("\n" + "=" * 80)
    print("POPULATION COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Test entity analysis with: python scripts/test_agent_and_save.py")
    print("  2. Query should include 'analyze D.R. Horton' or similar entity")
    print("  3. Check that entity activity data is populated (not NULL)")


if __name__ == "__main__":
    asyncio.run(populate_entity_market_properties())
