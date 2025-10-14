"""Quick check of entities table schema"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import db_manager


async def check_schema():
    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # Get column names
        query = text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'entities'
            ORDER BY ordinal_position
        """)
        result = await session.execute(query)
        rows = result.fetchall()

        print("Entities table columns:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")


asyncio.run(check_schema())
