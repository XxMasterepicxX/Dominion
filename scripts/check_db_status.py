#!/usr/bin/env python3
"""
Quick database status check
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database import DatabaseManager


async def check_status():
    db = DatabaseManager()
    await db.initialize()

    async with db.get_session() as session:
        # Check raw_facts counts
        result = await session.execute(text('''
            SELECT
                fact_type,
                COUNT(*) as count,
                MAX(created_at) as latest
            FROM raw_facts
            GROUP BY fact_type
            ORDER BY fact_type
        '''))

        print('=== Raw Facts by Type ===')
        for row in result:
            print(f'{row[0]}: {row[1]} records (latest: {row[2]})')

        # Check permits with parcel_id
        result = await session.execute(text('''
            SELECT
                COUNT(*) as total,
                COUNT(parcel_id) as with_parcel,
                ROUND(COUNT(parcel_id)::numeric / COUNT(*)::numeric * 100, 1) as percent
            FROM permits
        '''))
        row = result.fetchone()
        print(f'\n=== Domain Objects ===')
        print(f'Permits: {row[0]} total, {row[1]} with parcel_id ({row[2]}%)')

        # Check crime with coordinates
        result = await session.execute(text('''
            SELECT
                COUNT(*) as total,
                COUNT(latitude) as with_coords,
                ROUND(COUNT(latitude)::numeric / COUNT(*)::numeric * 100, 1) as percent
            FROM crime_reports
        '''))
        row = result.fetchone()
        print(f'Crime Incidents: {row[0]} total, {row[1]} with coordinates ({row[2]}%)')

        # Check news with entities
        result = await session.execute(text('''
            SELECT
                COUNT(*) as total,
                COUNT(mentioned_entities) as with_entities,
                ROUND(COUNT(mentioned_entities)::numeric / COUNT(*)::numeric * 100, 1) as percent
            FROM news_articles
        '''))
        row = result.fetchone()
        print(f'News Articles: {row[0]} total, {row[1]} with entities ({row[2]}%)')

        # Check council
        result = await session.execute(text('SELECT COUNT(*) FROM council_meetings'))
        print(f'Council Meetings: {result.scalar()}')

        # Check recent ingestion (last hour)
        result = await session.execute(text('''
            SELECT
                fact_type,
                COUNT(*) as recent_count
            FROM raw_facts
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY fact_type
            ORDER BY fact_type
        '''))

        print(f'\n=== Recent Ingestion (last hour) ===')
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'{row[0]}: {row[1]} records')
        else:
            print('No recent ingestion detected')

    await db.close()


if __name__ == '__main__':
    asyncio.run(check_status())
