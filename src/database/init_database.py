"""Create all database tables from SQLAlchemy models"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database import Base, DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_all_tables():
    """Initialize all database tables from SQLAlchemy models"""
    logger.info("Initializing database manager...")
    dm = DatabaseManager()
    await dm.initialize()

    # Enable required extensions
    logger.info("Enabling required PostgreSQL extensions...")
    async with dm.get_connection() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")
    logger.info("✓ Extensions enabled")

    # Check existing tables
    async with dm.get_connection() as conn:
        existing_tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)
        existing_table_names = {row['tablename'] for row in existing_tables}
        logger.info(f"Found {len(existing_table_names)} existing tables")

    # Drop conflicting indexes from old schema
    logger.info("Dropping old spatial indexes if they exist...")
    async with dm.get_connection() as conn:
        try:
            await conn.execute("DROP INDEX IF EXISTS idx_properties_coordinates")
            logger.info("✓ Old indexes dropped")
        except Exception as e:
            logger.warning(f"Could not drop old indexes: {e}")

    # Create tables (checkfirst=True ensures idempotency)
    logger.info("Creating new tables from SQLAlchemy models...")
    try:
        async with dm.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        logger.info("✓ All tables created successfully!")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        await dm.close()
        raise

    # Verify all expected tables now exist
    async with dm.get_connection() as conn:
        final_tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        final_table_names = [row['tablename'] for row in final_tables]
        new_count = len(final_table_names) - len(existing_table_names)
        logger.info(f"✓ Database now has {len(final_table_names)} tables ({new_count} newly created)")
        logger.info(f"Tables: {', '.join(final_table_names)}")

    await dm.close()

if __name__ == "__main__":
    asyncio.run(create_all_tables())
