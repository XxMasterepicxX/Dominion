#!/usr/bin/env python3
"""
Load ordinance embeddings into PostgreSQL database
Creates table if needed, supports incremental updates
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, delete
from sqlalchemy.dialects.postgresql import insert
import structlog

logger = structlog.get_logger(__name__)


async def create_ordinance_embeddings_table(engine):
    """
    Create ordinance_embeddings table if it doesn't exist
    Uses pgvector extension for similarity search
    """

    async with engine.begin() as conn:
        # Ensure pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Create table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ordinance_embeddings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                -- Source metadata
                ordinance_file TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'FL',

                -- Chunk info
                chunk_number INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_chars INTEGER,
                chunk_words INTEGER,

                -- Embedding
                embedding vector(1024) NOT NULL,

                -- Hashing for deduplication
                content_hash TEXT NOT NULL,

                -- File tracking for updates
                file_modified_timestamp BIGINT,
                scraped_date TEXT,

                -- Rich metadata from ADVANCED chunker
                metadata JSONB,

                -- Timestamps
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                -- Indexes
                UNIQUE(ordinance_file, chunk_number)
            )
        """))

        # Create indexes for fast filtering and search
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ordinance_city
            ON ordinance_embeddings(city)
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ordinance_state
            ON ordinance_embeddings(state)
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ordinance_content_hash
            ON ordinance_embeddings(content_hash)
        """))

        # Create vector index for similarity search (HNSW for fast approximate search)
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ordinance_embedding_hnsw
            ON ordinance_embeddings
            USING hnsw (embedding vector_cosine_ops)
        """))

        logger.info("ordinance_embeddings table created/verified")


async def load_embeddings_from_file(filepath: str) -> Dict[str, Any]:
    """Load embeddings from JSON file"""

    logger.info("loading_embeddings", filepath=filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    embeddings = data.get('embeddings', [])

    logger.info(
        "embeddings_loaded",
        total_chunks=len(embeddings),
        model=metadata.get('model'),
        dimensions=metadata.get('dimensions')
    )

    return {
        'metadata': metadata,
        'embeddings': embeddings
    }


async def insert_embeddings_batch(
    session: AsyncSession,
    embeddings: List[Dict[str, Any]],
    batch_size: int = 100
):
    """
    Insert embeddings in batches using raw SQL
    Uses ON CONFLICT to handle duplicates (upsert)
    """

    total = len(embeddings)
    inserted = 0

    for i in range(0, total, batch_size):
        batch = embeddings[i:i + batch_size]

        for emb in batch:
            # Convert embedding list to string format for vector type
            embedding_str = '[' + ','.join(str(x) for x in emb.get('embedding', [])) + ']'

            # Prepare metadata as JSON string
            metadata_json = json.dumps(emb.get('metadata', {})) if emb.get('metadata') else None

            # Raw SQL for upsert (use CAST for type conversion)
            sql = text("""
                INSERT INTO ordinance_embeddings (
                    ordinance_file, city, state, chunk_number, chunk_text,
                    chunk_chars, chunk_words, embedding, content_hash,
                    file_modified_timestamp, scraped_date, metadata, updated_at
                )
                VALUES (
                    :ordinance_file, :city, :state, :chunk_number, :chunk_text,
                    :chunk_chars, :chunk_words, CAST(:embedding AS vector), :content_hash,
                    :file_modified_timestamp, :scraped_date, CAST(:metadata AS jsonb), NOW()
                )
                ON CONFLICT (ordinance_file, chunk_number)
                DO UPDATE SET
                    chunk_text = EXCLUDED.chunk_text,
                    chunk_chars = EXCLUDED.chunk_chars,
                    chunk_words = EXCLUDED.chunk_words,
                    embedding = EXCLUDED.embedding,
                    content_hash = EXCLUDED.content_hash,
                    file_modified_timestamp = EXCLUDED.file_modified_timestamp,
                    scraped_date = EXCLUDED.scraped_date,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """)

            await session.execute(sql, {
                'ordinance_file': emb.get('ordinance_file'),
                'city': emb.get('city'),
                'state': emb.get('state', 'FL'),
                'chunk_number': emb.get('chunk_number'),
                'chunk_text': emb.get('chunk_text'),
                'chunk_chars': emb.get('chunk_chars'),
                'chunk_words': emb.get('chunk_words'),
                'embedding': embedding_str,
                'content_hash': emb.get('content_hash'),
                'file_modified_timestamp': emb.get('file_modified_timestamp'),
                'scraped_date': emb.get('scraped_date'),
                'metadata': metadata_json
            })

            inserted += 1

        await session.commit()

        logger.info(
            "batch_processed",
            batch_num=i // batch_size + 1,
            batch_size=len(batch),
            total_processed=min(i + batch_size, total),
            total=total
        )

    return {'inserted': inserted, 'updated': 0}


async def verify_embeddings(session: AsyncSession) -> Dict[str, Any]:
    """Verify embeddings were loaded correctly"""

    # Count total
    result = await session.execute(
        text("SELECT COUNT(*) FROM ordinance_embeddings")
    )
    total_count = result.scalar()

    # Count by city
    result = await session.execute(
        text("SELECT city, COUNT(*) FROM ordinance_embeddings GROUP BY city ORDER BY COUNT(*) DESC")
    )
    city_counts = {row[0]: row[1] for row in result}

    # Check vector index
    result = await session.execute(
        text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'ordinance_embeddings'
            AND indexname LIKE '%embedding%'
        """)
    )
    vector_indexes = [row[0] for row in result]

    return {
        'total_chunks': total_count,
        'cities': city_counts,
        'vector_indexes': vector_indexes
    }


async def main():
    if len(sys.argv) < 2:
        print("Usage: python load_embeddings_to_db.py <embeddings_file.json>")
        print("\nExample:")
        print("  python load_embeddings_to_db.py data/embeddings/ordinance_embeddings_20251013_081446.json")
        sys.exit(1)

    filepath = sys.argv[1]

    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    # Database connection (get from config)
    from src.config import settings
    db_url = settings.DATABASE_URL
    print(f"\nConnecting to database: {db_url.split('@')[1]}")  # Hide password
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 80)
    print("LOADING EMBEDDINGS TO DATABASE")
    print("=" * 80)

    try:
        # Step 1: Create table
        print("\n1. Creating/verifying table...")
        await create_ordinance_embeddings_table(engine)
        print("   [OK] Table ready")

        # Step 2: Load embeddings from file
        print("\n2. Loading embeddings from file...")
        data = await load_embeddings_from_file(filepath)
        print(f"   [OK] Loaded {len(data['embeddings'])} chunks")
        print(f"   Model: {data['metadata'].get('model')}")
        print(f"   Dimensions: {data['metadata'].get('dimensions')}")

        # Step 3: Insert into database
        print("\n3. Inserting embeddings into database...")
        async with async_session() as session:
            result = await insert_embeddings_batch(
                session,
                data['embeddings'],
                batch_size=100
            )
            print(f"   [OK] Inserted/Updated {result['inserted']} chunks")

        # Step 4: Verify
        print("\n4. Verifying embeddings...")
        async with async_session() as session:
            verification = await verify_embeddings(session)
            print(f"   [OK] Total chunks in database: {verification['total_chunks']}")
            print(f"\n   Chunks by city:")
            for city, count in verification['cities'].items():
                print(f"      {city:25s}: {count:4d} chunks")
            print(f"\n   Vector indexes: {', '.join(verification['vector_indexes'])}")

        print("\n" + "=" * 80)
        print("[SUCCESS] Embeddings loaded successfully!")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Test similarity search")
        print("  2. Create RAG search tool")
        print("  3. Register with agent")

    except Exception as e:
        print(f"\n[ERROR] Failed to load embeddings: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
