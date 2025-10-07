import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_async_engine(os.getenv('DATABASE_URL'))

async def check():
    async with engine.connect() as conn:
        # Check permits saved
        result = await conn.execute(text("SELECT COUNT(*) FROM permits"))
        total = result.scalar()
        print(f'Total permits in database: {total}')

        # Check new permits from today
        result = await conn.execute(text("SELECT COUNT(*) FROM permits WHERE created_at >= CURRENT_DATE"))
        today = result.scalar()
        print(f'Permits added today: {today}')

        # Check entities created
        result = await conn.execute(text("SELECT COUNT(*) FROM entities WHERE created_at >= CURRENT_DATE"))
        entities = result.scalar()
        print(f'Entities created today: {entities}')

        # Sample permits
        result = await conn.execute(text("""
            SELECT
                permit_number,
                permit_type,
                project_value,
                contractor_entity_id
            FROM permits
            WHERE created_at >= CURRENT_DATE
            LIMIT 5
        """))
        print('\nSample permits saved:')
        for row in result:
            print(f'  {row[0]} | {row[1]} | ${row[2] or 0:,.0f} | Contractor: {row[3]}')

asyncio.run(check())
