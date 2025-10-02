"""Cleanup database without prompt"""
import asyncio
import asyncpg

async def cleanup_database():
    """Clean all data from database"""
    conn = await asyncpg.connect('postgresql://postgres:dominion@localhost/dominion')

    print("\n" + "=" * 80)
    print("CLEANING DATABASE")
    print("=" * 80)

    tables_to_clean = [
        # Domain tables (in dependency order)
        'permits',
        'properties',
        'crime_reports',
        'news_articles',
        'council_meetings',
        'llc_formations',
        'entity_relationships',
        'entity_review_queue',
        'entity_resolution_log',
        'entities',

        # Raw data
        'raw_facts_partitioned',
        'scraper_runs'
    ]

    total_deleted = 0

    for table in tables_to_clean:
        try:
            count_before = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
            if count_before > 0:
                await conn.execute(f'DELETE FROM {table}')
                print(f"  {table:.<50} {count_before:>10,} deleted")
                total_deleted += count_before
            else:
                print(f"  {table:.<50} (empty)")
        except Exception as e:
            print(f"  {table:.<50} ERROR: {e}")

    print("=" * 80)
    print(f"TOTAL RECORDS DELETED: {total_deleted:,}")
    print("=" * 80)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(cleanup_database())
