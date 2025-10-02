-- Dominion Database Enhancements
-- Apply AFTER base schema.sql
-- Adds: Partitioning, FTS optimization, improved LLM cache
--
-- Based on DATABASE_ARCHITECTURE_FINAL.md recommendations

-- ============================================================================
-- PART 1: Convert raw_facts to Partitioned Table
-- ============================================================================

-- NOTE: Cannot convert existing table to partitioned
-- Must create new partitioned table, copy data, rename
-- For new database: Replace raw_facts in base schema.sql with this version

-- Drop existing raw_facts (only if starting fresh)
-- DROP TABLE IF EXISTS raw_facts CASCADE;

-- Create partitioned raw_facts table
CREATE TABLE IF NOT EXISTS raw_facts_partitioned (
    id UUID DEFAULT gen_random_uuid(),
    fact_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL,
    parser_version TEXT NOT NULL,
    raw_content JSONB NOT NULL,
    content_hash TEXT NOT NULL,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Partition key must be part of PRIMARY KEY
    PRIMARY KEY (id, scraped_at),
    UNIQUE (content_hash, scraped_at)
) PARTITION BY RANGE (scraped_at);

-- Create partitions for current month + 2 months ahead
-- October 2025
CREATE TABLE IF NOT EXISTS raw_facts_2025_10 PARTITION OF raw_facts_partitioned
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- November 2025
CREATE TABLE IF NOT EXISTS raw_facts_2025_11 PARTITION OF raw_facts_partitioned
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- December 2025
CREATE TABLE IF NOT EXISTS raw_facts_2025_12 PARTITION OF raw_facts_partitioned
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- Create indexes on partitioned table
CREATE INDEX IF NOT EXISTS idx_raw_facts_part_fact_type ON raw_facts_partitioned(fact_type);
CREATE INDEX IF NOT EXISTS idx_raw_facts_part_scraped_at ON raw_facts_partitioned(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_facts_part_content_hash ON raw_facts_partitioned(content_hash);
CREATE INDEX IF NOT EXISTS idx_raw_facts_part_processed ON raw_facts_partitioned(processed_at) WHERE processed_at IS NULL;

-- Set autovacuum settings for better performance with large tables
ALTER TABLE raw_facts_partitioned SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_cost_delay = 10,
    autovacuum_vacuum_cost_limit = 1000
);

-- ============================================================================
-- PART 2: Convert structured_facts to Partitioned Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS structured_facts_partitioned (
    id UUID DEFAULT gen_random_uuid(),
    raw_fact_id UUID NOT NULL,
    entity_type TEXT NOT NULL,
    structured_data JSONB NOT NULL,
    extraction_confidence FLOAT NOT NULL CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    validation_status TEXT DEFAULT 'unvalidated' CHECK (validation_status IN ('unvalidated', 'validated', 'flagged', 'rejected')),
    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions
CREATE TABLE IF NOT EXISTS structured_facts_2025_10 PARTITION OF structured_facts_partitioned
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE TABLE IF NOT EXISTS structured_facts_2025_11 PARTITION OF structured_facts_partitioned
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE IF NOT EXISTS structured_facts_2025_12 PARTITION OF structured_facts_partitioned
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_structured_facts_part_entity_type ON structured_facts_partitioned(entity_type);
CREATE INDEX IF NOT EXISTS idx_structured_facts_part_raw_fact_id ON structured_facts_partitioned(raw_fact_id);
CREATE INDEX IF NOT EXISTS idx_structured_facts_part_confidence ON structured_facts_partitioned(extraction_confidence);

-- Set autovacuum
ALTER TABLE structured_facts_partitioned SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- ============================================================================
-- PART 3: Add Full-Text Search with Materialized tsvector
-- ============================================================================

-- Add generated tsvector column to raw_facts for full-text search
-- NOTE: Only add if raw_facts_partitioned is used as primary table
ALTER TABLE raw_facts_partitioned
ADD COLUMN IF NOT EXISTS search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(raw_content->>'title', '')), 'A') ||
    setweight(to_tsvector('english', coalesce(raw_content->>'content', '')), 'B') ||
    setweight(to_tsvector('english', coalesce(raw_content->>'description', '')), 'C') ||
    setweight(to_tsvector('english', coalesce(raw_content->>'tags', '')), 'D')
) STORED;

-- GIN index on tsvector for fast full-text search
CREATE INDEX IF NOT EXISTS idx_raw_facts_part_fts ON raw_facts_partitioned USING GIN(search_vector);

-- Create text search configuration with local synonyms
CREATE TEXT SEARCH DICTIONARY IF NOT EXISTS local_synonyms (
    TEMPLATE = synonym,
    SYNONYMS = 'dominion_synonyms'
);

-- Note: Create dominion_synonyms.syn file in PostgreSQL tsearch data directory:
-- Example contents:
-- downtown, city center, central district, cbd
-- uf, university of florida, uf campus
-- gnv, gainesville
-- permit, building permit, construction permit

-- ============================================================================
-- PART 4: Improved LLM Cache Structure
-- ============================================================================

-- Drop old llm_cache if exists and replace with improved version
DROP TABLE IF EXISTS llm_cache CASCADE;

CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Complete cache key (all must match exactly)
    model_id TEXT NOT NULL,                    -- 'gemini-2.0-flash'
    model_version TEXT NOT NULL,               -- '20250115' (model release version)
    prompt_template_version TEXT NOT NULL,     -- 'entity_extract_v3' (our template version)
    temperature FLOAT NOT NULL,                -- Even if usually 0.0, must match
    top_p FLOAT NOT NULL,                      -- Sampling parameter
    retrieval_recipe_hash TEXT NOT NULL,       -- Hash of facts used in context

    -- Response data
    response JSONB NOT NULL,
    cost_cents INTEGER,

    -- Metadata (not part of cache key, for observability)
    prompt_preview TEXT,                       -- First 200 chars for debugging
    context_size_bytes INTEGER,                -- Size of context passed to LLM
    response_tokens INTEGER,                   -- Tokens in response
    latency_ms INTEGER,                        -- How long LLM call took

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                      -- Optional expiration
    last_accessed_at TIMESTAMP DEFAULT NOW(),  -- Track cache usage

    -- Composite unique constraint (cache key)
    UNIQUE(model_id, model_version, prompt_template_version, temperature, top_p, retrieval_recipe_hash)
);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_llm_cache_expires ON llm_cache(expires_at) WHERE expires_at IS NOT NULL;

-- Index for cache stats
CREATE INDEX IF NOT EXISTS idx_llm_cache_accessed ON llm_cache(last_accessed_at DESC);

-- Set autovacuum (this table gets many updates for last_accessed_at)
ALTER TABLE llm_cache SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_analyze_scale_factor = 0.01
);

-- ============================================================================
-- PART 5: Partition Management Functions
-- ============================================================================

-- Function to automatically create next month's partition
CREATE OR REPLACE FUNCTION create_next_month_partitions()
RETURNS void AS $$
DECLARE
    next_month_start DATE;
    next_month_end DATE;
    partition_name TEXT;
BEGIN
    -- Calculate next month
    next_month_start := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '2 months');
    next_month_end := next_month_start + INTERVAL '1 month';

    -- Create raw_facts partition
    partition_name := 'raw_facts_' || TO_CHAR(next_month_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF raw_facts_partitioned
         FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        next_month_start,
        next_month_end
    );

    -- Create structured_facts partition
    partition_name := 'structured_facts_' || TO_CHAR(next_month_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF structured_facts_partitioned
         FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        next_month_start,
        next_month_end
    );

    RAISE NOTICE 'Created partitions for %', TO_CHAR(next_month_start, 'YYYY-MM');
END;
$$ LANGUAGE plpgsql;

-- Function to drop old partitions (after archiving to S3)
CREATE OR REPLACE FUNCTION drop_old_partitions(months_to_keep INTEGER DEFAULT 24)
RETURNS void AS $$
DECLARE
    cutoff_date DATE;
    partition_record RECORD;
BEGIN
    cutoff_date := DATE_TRUNC('month', CURRENT_DATE - (months_to_keep || ' months')::INTERVAL);

    -- Drop old raw_facts partitions
    FOR partition_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE 'raw_facts_2%'
        AND tablename < 'raw_facts_' || TO_CHAR(cutoff_date, 'YYYY_MM')
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', partition_record.tablename);
        RAISE NOTICE 'Dropped old partition: %', partition_record.tablename;
    END LOOP;

    -- Drop old structured_facts partitions
    FOR partition_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE 'structured_facts_2%'
        AND tablename < 'structured_facts_' || TO_CHAR(cutoff_date, 'YYYY_MM')
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', partition_record.tablename);
        RAISE NOTICE 'Dropped old partition: %', partition_record.tablename;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PART 6: Monitoring Views
-- ============================================================================

-- View: Partition sizes
CREATE OR REPLACE VIEW partition_sizes AS
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
  AND (tablename LIKE 'raw_facts_%' OR tablename LIKE 'structured_facts_%')
ORDER BY size_bytes DESC;

-- View: LLM Cache statistics
CREATE OR REPLACE VIEW llm_cache_stats AS
SELECT
    model_id,
    model_version,
    COUNT(*) AS cached_responses,
    SUM(cost_cents) AS total_cost_cents,
    AVG(cost_cents) AS avg_cost_cents,
    pg_size_pretty(pg_total_relation_size('llm_cache')) AS cache_size,
    COUNT(*) FILTER (WHERE last_accessed_at > NOW() - INTERVAL '24 hours') AS accessed_last_24h,
    COUNT(*) FILTER (WHERE expires_at < NOW()) AS expired_entries
FROM llm_cache
GROUP BY model_id, model_version;

-- View: Fact processing pipeline status
CREATE OR REPLACE VIEW fact_processing_status AS
SELECT
    fact_type,
    COUNT(*) AS total_facts,
    COUNT(*) FILTER (WHERE processed_at IS NULL) AS unprocessed,
    COUNT(*) FILTER (WHERE processed_at IS NOT NULL) AS processed,
    MIN(scraped_at) AS oldest_fact,
    MAX(scraped_at) AS newest_fact,
    ROUND(100.0 * COUNT(*) FILTER (WHERE processed_at IS NOT NULL) / COUNT(*), 2) AS processing_percentage
FROM raw_facts_partitioned
GROUP BY fact_type
ORDER BY total_facts DESC;

-- ============================================================================
-- PART 7: Usage Instructions
-- ============================================================================

-- After applying this schema:

-- 1. Create monthly partitions automatically:
--    SELECT create_next_month_partitions();
--    (Add to monthly cron job)

-- 2. Migrate data from old raw_facts to raw_facts_partitioned:
--    INSERT INTO raw_facts_partitioned SELECT * FROM raw_facts;
--    (Then rename tables)

-- 3. Drop partitions older than 2 years (after archiving):
--    SELECT drop_old_partitions(24);

-- 4. Monitor partition sizes:
--    SELECT * FROM partition_sizes;

-- 5. Check LLM cache performance:
--    SELECT * FROM llm_cache_stats;

-- 6. Monitor fact processing:
--    SELECT * FROM fact_processing_status;
