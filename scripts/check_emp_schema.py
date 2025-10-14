"""Check entity_market_properties schema"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import db_manager


async def check():
    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # Get schema
        query = text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'entity_market_properties'
            ORDER BY ordinal_position
        """)
        result = await session.execute(query)
        rows = result.fetchall()

        print("entity_market_properties schema:")
        for col, dtype in rows:
            print(f"  {col}: {dtype}")

        # Check sample data
        print("\nSample data:")
        query2 = text("SELECT * FROM entity_market_properties LIMIT 3")
        result2 = await session.execute(query2)
        rows2 = result2.fetchall()

        for i, row in enumerate(rows2, 1):
            print(f"\nRow {i}:")
            for j, col in enumerate(rows[0:len(row)]):
                col_name = col[0]
                value = row[j]
                print(f"  {col_name}: {value}")


asyncio.run(check())
