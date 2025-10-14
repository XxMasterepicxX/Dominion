"""Quick check of sale data in database"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import db_manager


async def check_sale_data():
    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # Check for any properties with sale data
        query = text("""
            SELECT COUNT(*) as total,
                   COUNT(last_sale_date) as with_sale_date,
                   COUNT(last_sale_price) as with_sale_price,
                   COUNT(CASE WHEN last_sale_date IS NOT NULL
                              AND last_sale_price IS NOT NULL
                              AND last_sale_price > 0 THEN 1 END) as with_both,
                   COUNT(CASE WHEN property_type = 'Vacant'
                              AND last_sale_date IS NOT NULL
                              AND last_sale_price IS NOT NULL
                              AND last_sale_price > 0 THEN 1 END) as vacant_with_sales
            FROM bulk_property_records
        """)

        result = await session.execute(query)
        row = result.fetchone()

        print("\n=== SALE DATA STATISTICS ===")
        print(f"Total properties: {row[0]:,}")
        print(f"Properties with last_sale_date: {row[1]:,}")
        print(f"Properties with last_sale_price: {row[2]:,}")
        print(f"Properties with both (and price > 0): {row[3]:,}")
        print(f"Vacant properties with sales: {row[4]:,}")

        # Sample a few properties with sale data
        query2 = text("""
            SELECT site_address, property_type, last_sale_date, last_sale_price, lot_size_acres
            FROM bulk_property_records
            WHERE last_sale_date IS NOT NULL
              AND last_sale_price IS NOT NULL
              AND last_sale_price > 0
            ORDER BY last_sale_date DESC
            LIMIT 10
        """)

        result2 = await session.execute(query2)
        rows = result2.fetchall()

        print("\n=== SAMPLE PROPERTIES WITH SALE DATA ===")
        for row in rows:
            print(f"{row[0][:40]:40} | {row[1]:15} | {row[2]} | ${row[3]:>10,.0f} | {row[4]:.2f} acres")


asyncio.run(check_sale_data())
