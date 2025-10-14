"""Check what property types exist in the database"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import db_manager


async def check_property_types():
    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # Check property types
        query = text("""
            SELECT property_type,
                   COUNT(*) as total,
                   COUNT(CASE WHEN last_sale_date IS NOT NULL
                              AND last_sale_price IS NOT NULL
                              AND last_sale_price > 0 THEN 1 END) as with_sales
            FROM bulk_property_records
            GROUP BY property_type
            ORDER BY total DESC
        """)

        result = await session.execute(query)
        rows = result.fetchall()

        print("\n=== PROPERTY TYPES ===")
        print(f"{'Type':<30} | {'Total':>10} | {'With Sales':>12}")
        print("-" * 58)
        for row in rows:
            print(f"{str(row[0]):<30} | {row[1]:>10,} | {row[2]:>12,}")


asyncio.run(check_property_types())
