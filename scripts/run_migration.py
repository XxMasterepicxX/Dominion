"""
Run a database migration file
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from sqlalchemy import text


async def run_migration(migration_file: str):
    """Run a migration SQL file"""
    migration_path = Path(__file__).parent.parent / migration_file

    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_path}")
        return False

    print(f"Running migration: {migration_path.name}")
    print("=" * 80)

    # Read migration SQL
    with open(migration_path, 'r') as f:
        sql = f.read()

    # Initialize database
    await db_manager.initialize()

    try:
        async with db_manager.get_session() as session:
            # Split SQL into individual statements
            # Remove comments and split by semicolons
            statements = []
            for line in sql.split('\n'):
                line = line.strip()
                # Skip comments and empty lines
                if line.startswith('--') or not line:
                    continue
                statements.append(line)

            # Join and split by semicolons
            full_sql = ' '.join(statements)
            individual_statements = [s.strip() for s in full_sql.split(';') if s.strip()]

            print(f"Executing {len(individual_statements)} SQL statements...")

            # Execute each statement separately
            for i, stmt in enumerate(individual_statements, 1):
                print(f"  [{i}/{len(individual_statements)}] {stmt[:60]}...")
                await session.execute(text(stmt))

            await session.commit()
            print("\nMigration completed successfully!")
            return True

    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    finally:
        await db_manager.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "src/database/migrations/007_qpublic_enrichment_fields.sql"

    success = asyncio.run(run_migration(migration_file))
    sys.exit(0 if success else 1)
