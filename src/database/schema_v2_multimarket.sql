-- ============================================================================
-- Dominion Real Estate Intelligence - Multi-Market Database Schema V2
-- ============================================================================
-- ARCHITECTURE: Multi-Market Hybrid Bridge Model
--
-- GLOBAL LAYER: Entities and relationships that span markets
-- MARKET LAYER: Events and properties partitioned by market_id
-- LINKING LAYER: Cross-market portfolio tracking
--
-- Design Principles:
-- 1. Market partitioning for scalability (LIST partitioning by market_id)
-- 2. Global entities with active_markets[] array
-- 3. Immutable raw_facts as source of truth
-- 4. AI/ML tables with confidence scores and provenance
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching
CREATE EXTENSION IF NOT EXISTS "fuzzystrmatch";  -- For phonetic matching

-- ============================================================================
-- GLOBAL LAYER: Cross-Market Tables
-- ============================================================================

-- Markets Registry
-- Central registry of all markets supported by Dominion
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_code TEXT UNIQUE NOT NULL,  -- e.g., 'gainesville_fl', 'tampa_fl'
    market_name TEXT NOT NULL,  -- e.g., 'Gainesville, FL'

    -- Geographic identifiers
    state TEXT NOT NULL,  -- 'FL'
    county TEXT,  -- 'Alachua'
    city TEXT,  -- 'Gainesville'
    metro_area TEXT,  -- For multi-city metros

    -- Market metadata
    is_active BOOLEAN DEFAULT TRUE,
    activation_date TIMESTAMP DEFAULT NOW(),
    deactivation_date TIMESTAMP,

    -- Configuration
    config JSONB DEFAULT '{}',  -- Market-specific config (data sources, URLs, etc.)

    -- Stats
    total_properties INTEGER DEFAULT 0,
    total_entities INTEGER DEFAULT 0,
    last_scrape_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_markets_market_code ON markets(market_code);
CREATE INDEX idx_markets_is_active ON markets(is_active);

-- Entities (People, LLCs, Companies) - GLOBAL
-- Entities exist across markets (e.g., same LLC operates in multiple cities)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'llc', 'corporation', 'partnership', 'government', 'unknown')),
    name TEXT NOT NULL,
    canonical_name TEXT,  -- Normalized version for matching

    -- Definitive identifiers (when available)
    sunbiz_document_number TEXT UNIQUE,  -- Florida LLC/Corp document number
    tax_id TEXT,  -- EIN or SSN (encrypted)
    other_identifiers JSONB DEFAULT '{}',  -- State IDs, license numbers, etc.

    -- Contact information
    primary_address TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,

    -- LLC/Corporation-specific data
    registered_agent TEXT,
    registered_agent_address TEXT,
    officers JSONB DEFAULT '[]',  -- Array of officer objects
    formation_date DATE,
    status TEXT,  -- 'Active', 'Inactive', 'Dissolved'

    -- Multi-market tracking
    active_markets UUID[] DEFAULT ARRAY[]::UUID[],  -- Array of market_ids where this entity operates
    first_seen_market_id UUID REFERENCES markets(id),  -- Where we first discovered this entity

    -- Metadata
    verified BOOLEAN DEFAULT FALSE,
    verification_source TEXT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Enrichment timestamps
    sunbiz_enriched_at TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT NOW(),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_entities_entity_type ON entities(entity_type);
CREATE INDEX idx_entities_canonical_name ON entities(canonical_name);
CREATE INDEX idx_entities_sunbiz_document_number ON entities(sunbiz_document_number) WHERE sunbiz_document_number IS NOT NULL;
CREATE INDEX idx_entities_active_markets ON entities USING GIN(active_markets);
CREATE INDEX idx_entities_name_trgm ON entities USING GIN(name gin_trgm_ops);  -- For fuzzy name search

-- Entity Relationships - GLOBAL
-- Relationships between entities (e.g., LLC owns property, person owns LLC)
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship
    source_entity_id UUID REFERENCES entities(id) NOT NULL,
    target_entity_id UUID REFERENCES entities(id) NOT NULL,
    relationship_type TEXT NOT NULL,  -- 'OWNS', 'CONTRACTED', 'OFFICERS_AT', 'PARTNERS_WITH', 'RELATED_TO'

    -- Context
    supporting_markets UUID[] DEFAULT ARRAY[]::UUID[],  -- Markets where this relationship was observed
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Evidence
    evidence_sources TEXT[],  -- URLs, fact_ids that support this relationship
    derived_from TEXT,  -- 'permit_filing', 'llc_registration', 'property_sale', 'ai_inference'

    -- Temporal
    relationship_start_date DATE,
    relationship_end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT no_self_reference CHECK (source_entity_id != target_entity_id)
);

CREATE INDEX idx_entity_relationships_source ON entity_relationships(source_entity_id);
CREATE INDEX idx_entity_relationships_target ON entity_relationships(target_entity_id);
CREATE INDEX idx_entity_relationships_type ON entity_relationships(relationship_type);
CREATE INDEX idx_entity_relationships_markets ON entity_relationships USING GIN(supporting_markets);

-- Users - GLOBAL
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,

    -- User info
    full_name TEXT,
    company TEXT,
    user_type TEXT,  -- 'developer', 'flipper', 'agent', 'investor', 'enterprise'

    -- Subscriptions
    subscribed_markets UUID[] DEFAULT ARRAY[]::UUID[],  -- Markets user has access to
    subscription_tier TEXT DEFAULT 'free',  -- 'free', 'professional', 'enterprise'
    subscription_status TEXT DEFAULT 'active',

    -- Usage tracking
    analyses_run INTEGER DEFAULT 0,
    last_login_at TIMESTAMP,

    -- Security
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscribed_markets ON users USING GIN(subscribed_markets);

-- ============================================================================
-- MARKET LAYER: Partitioned Tables (by market_id)
-- ============================================================================

-- Raw Facts (Immutable Event Log) - PARTITIONED
-- ALL data starts here in original form
CREATE TABLE raw_facts (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Source
    fact_type TEXT NOT NULL,  -- 'city_permit', 'county_permit', 'llc_formation', 'news_article', etc.
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Content
    raw_content JSONB NOT NULL,  -- Original unprocessed data
    content_hash TEXT NOT NULL,  -- MD5 hash for deduplication

    -- Processing
    parser_version TEXT NOT NULL DEFAULT 'v1',
    processed_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_raw_facts_market_id ON raw_facts(market_id);
CREATE INDEX idx_raw_facts_fact_type ON raw_facts(fact_type);
CREATE INDEX idx_raw_facts_scraped_at ON raw_facts(scraped_at DESC);
CREATE INDEX idx_raw_facts_content_hash ON raw_facts(content_hash);

-- Properties - PARTITIONED
CREATE TABLE properties (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Identifiers
    parcel_id TEXT NOT NULL,  -- Official parcel ID
    property_address TEXT,

    -- Location
    coordinates GEOMETRY(POINT, 4326),  -- PostGIS point (lon, lat)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Property details
    property_type TEXT,  -- 'Residential', 'Commercial', 'Industrial', 'Vacant Land'
    year_built INTEGER,
    square_feet INTEGER,
    lot_size_acres DECIMAL(10, 4),
    bedrooms INTEGER,
    bathrooms DECIMAL(3, 1),

    -- Ownership
    owner_entity_id UUID REFERENCES entities(id),
    owner_name TEXT,  -- From property records
    mailing_address TEXT,

    -- Valuation
    assessed_value DECIMAL(12, 2),
    market_value DECIMAL(12, 2),
    last_sale_price DECIMAL(12, 2),
    last_sale_date DATE,

    -- Zoning
    zoning_code TEXT,
    zoning_description TEXT,

    -- Enrichment tracking
    last_enriched_at TIMESTAMP,
    enrichment_source TEXT,  -- 'qpublic', 'cama', 'manual'

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id),
    UNIQUE (parcel_id, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_properties_market_id ON properties(market_id);
CREATE INDEX idx_properties_parcel_id ON properties(parcel_id);
CREATE INDEX idx_properties_owner_entity_id ON properties(owner_entity_id);
CREATE INDEX idx_properties_coordinates ON properties USING GIST(coordinates);
CREATE INDEX idx_properties_property_type ON properties(property_type);

-- Permits - PARTITIONED
CREATE TABLE permits (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Identifiers
    permit_number TEXT NOT NULL,
    permit_type TEXT,  -- 'Building', 'Electrical', 'Plumbing', 'Demolition'
    jurisdiction TEXT,  -- 'city', 'county'

    -- Project details
    project_name TEXT,
    project_description TEXT,
    work_type TEXT,  -- 'New Construction', 'Addition', 'Alteration', 'Repair'

    -- Location
    property_id UUID,  -- FK to properties (same partition)
    site_address TEXT,
    parcel_id TEXT,

    -- Parties
    applicant_entity_id UUID REFERENCES entities(id),
    contractor_entity_id UUID REFERENCES entities(id),
    owner_entity_id UUID REFERENCES entities(id),

    -- Valuation
    project_value DECIMAL(12, 2),
    permit_fee DECIMAL(10, 2),

    -- Status
    status TEXT,  -- 'Submitted', 'Under Review', 'Approved', 'Issued', 'Completed', 'Cancelled'
    application_date DATE,
    issued_date DATE,
    final_inspection_date DATE,

    -- Source
    source_url TEXT,
    raw_fact_id UUID,  -- Link back to raw_facts

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id),
    UNIQUE (permit_number, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_permits_market_id ON permits(market_id);
CREATE INDEX idx_permits_permit_number ON permits(permit_number);
CREATE INDEX idx_permits_property_id ON permits(property_id);
CREATE INDEX idx_permits_contractor_entity_id ON permits(contractor_entity_id);
CREATE INDEX idx_permits_application_date ON permits(application_date DESC);
CREATE INDEX idx_permits_status ON permits(status);

-- LLC Formations (Sunbiz daily scraper) - NOT PARTITIONED (statewide)
CREATE TABLE llc_formations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Sunbiz identifiers
    document_number TEXT UNIQUE NOT NULL,
    filing_type TEXT,  -- 'Domestic LLC', 'Foreign LLC', 'Corporation'

    -- Entity details
    entity_id UUID REFERENCES entities(id),  -- Link to global entity
    name TEXT NOT NULL,
    status TEXT,

    -- Dates
    filing_date DATE,
    effective_date DATE,

    -- Registration
    registered_agent TEXT,
    registered_agent_address TEXT,
    principal_address TEXT,
    mailing_address TEXT,

    -- Officers/Members (from Sunbiz website scrape)
    officers JSONB DEFAULT '[]',

    -- Source
    raw_fact_id UUID,  -- Link to raw_facts in first_seen_market
    scraped_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_llc_formations_document_number ON llc_formations(document_number);
CREATE INDEX idx_llc_formations_entity_id ON llc_formations(entity_id);
CREATE INDEX idx_llc_formations_filing_date ON llc_formations(filing_date DESC);

-- Crime Reports - PARTITIONED
CREATE TABLE crime_reports (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Incident details
    case_number TEXT,
    incident_type TEXT,
    incident_description TEXT,

    -- Location
    incident_address TEXT,
    coordinates GEOMETRY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Temporal
    incident_date TIMESTAMP,
    reported_date TIMESTAMP,

    -- Source
    source_url TEXT,
    raw_fact_id UUID,

    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_crime_reports_market_id ON crime_reports(market_id);
CREATE INDEX idx_crime_reports_incident_date ON crime_reports(incident_date DESC);
CREATE INDEX idx_crime_reports_coordinates ON crime_reports USING GIST(coordinates);

-- Council Meetings - PARTITIONED
CREATE TABLE council_meetings (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Meeting details
    meeting_date DATE,
    meeting_type TEXT,  -- 'Regular', 'Special', 'Workshop'
    agenda_items JSONB DEFAULT '[]',

    -- Content
    minutes_text TEXT,
    summary TEXT,

    -- Extracted entities and topics
    mentioned_entities UUID[],  -- Entity IDs mentioned in meeting
    topics TEXT[],  -- Extracted topics

    -- Source
    source_url TEXT,
    raw_fact_id UUID,

    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_council_meetings_market_id ON council_meetings(market_id);
CREATE INDEX idx_council_meetings_meeting_date ON council_meetings(meeting_date DESC);

-- News Articles - PARTITIONED
CREATE TABLE news_articles (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),

    -- Article details
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_date TIMESTAMP,
    source TEXT,  -- 'Gainesville Sun', 'Business Observer', etc.

    -- Content
    article_text TEXT,
    summary TEXT,

    -- Extracted entities and topics
    mentioned_entities UUID[],  -- Entity IDs mentioned in article
    topics TEXT[],  -- Extracted topics
    relevance_score FLOAT,  -- How relevant to real estate development

    -- Source
    raw_fact_id UUID,

    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id),
    UNIQUE (url, market_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_news_articles_market_id ON news_articles(market_id);
CREATE INDEX idx_news_articles_published_date ON news_articles(published_date DESC);
CREATE INDEX idx_news_articles_relevance_score ON news_articles(relevance_score DESC);

-- ============================================================================
-- BULK DATA LAYER: Snapshots and Historical Records
-- ============================================================================

-- Bulk Data Snapshots (Version tracking)
CREATE TABLE bulk_data_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID REFERENCES markets(id),

    -- Source
    data_source TEXT NOT NULL,  -- 'property_appraiser_cama', 'sunbiz_sftp', 'gis_parcels'
    source_url TEXT,

    -- File info
    file_name TEXT,
    file_size_bytes BIGINT,
    file_hash TEXT NOT NULL,  -- MD5 hash of entire file

    -- Processing
    status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    records_total INTEGER,
    records_inserted INTEGER,
    records_updated INTEGER,
    records_skipped INTEGER,

    -- Timing
    download_started_at TIMESTAMP,
    download_completed_at TIMESTAMP,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,

    -- Metadata
    snapshot_date DATE,  -- Date of the data snapshot
    is_current BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bulk_data_snapshots_market_id ON bulk_data_snapshots(market_id);
CREATE INDEX idx_bulk_data_snapshots_data_source ON bulk_data_snapshots(data_source);
CREATE INDEX idx_bulk_data_snapshots_is_current ON bulk_data_snapshots(is_current) WHERE is_current = TRUE;

-- Bulk Property Records (CAMA + qPublic enrichment) - PARTITIONED
CREATE TABLE bulk_property_records (
    id UUID DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),

    -- Identifiers
    parcel_id TEXT NOT NULL,
    property_id UUID,  -- FK to properties table

    -- CAMA fields (Property Appraiser)
    owner_name TEXT,
    mailing_address TEXT,
    site_address TEXT,
    property_type TEXT,
    year_built INTEGER,
    square_feet INTEGER,
    lot_size_acres DECIMAL(10, 4),
    assessed_value DECIMAL(12, 2),
    market_value DECIMAL(12, 2),
    taxable_value DECIMAL(12, 2),
    exemptions TEXT[],

    -- qPublic enrichment fields
    coordinates GEOMETRY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    sales_history JSONB DEFAULT '[]',  -- Array of past sales
    permit_history JSONB DEFAULT '[]',  -- Permits from qPublic
    trim_notice JSONB,  -- TRIM valuation info

    -- Enrichment tracking
    qpublic_enriched_at TIMESTAMP,
    qpublic_enrichment_status TEXT,  -- 'pending', 'completed', 'failed', 'not_found'

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (id, market_id),
    UNIQUE (parcel_id, market_id, snapshot_id)
) PARTITION BY LIST (market_id);

CREATE INDEX idx_bulk_property_records_market_id ON bulk_property_records(market_id);
CREATE INDEX idx_bulk_property_records_parcel_id ON bulk_property_records(parcel_id);
CREATE INDEX idx_bulk_property_records_snapshot_id ON bulk_property_records(snapshot_id);
CREATE INDEX idx_bulk_property_records_coordinates ON bulk_property_records USING GIST(coordinates);

-- Bulk LLC Records (Sunbiz SFTP monthly dump) - NOT PARTITIONED (statewide)
CREATE TABLE bulk_llc_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),

    -- Sunbiz identifiers
    document_number TEXT NOT NULL,
    filing_type TEXT,

    -- Entity info
    entity_id UUID REFERENCES entities(id),
    name TEXT NOT NULL,
    status TEXT,

    -- Dates
    filing_date DATE,
    last_event_date DATE,

    -- Address
    principal_address TEXT,
    mailing_address TEXT,

    -- Officers (basic from SFTP, enriched from website)
    registered_agent TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (document_number, snapshot_id)
);

CREATE INDEX idx_bulk_llc_records_document_number ON bulk_llc_records(document_number);
CREATE INDEX idx_bulk_llc_records_snapshot_id ON bulk_llc_records(snapshot_id);
CREATE INDEX idx_bulk_llc_records_entity_id ON bulk_llc_records(entity_id);

-- ============================================================================
-- LINKING LAYER: Cross-Market Relationships
-- ============================================================================

-- Entity Market Properties (Portfolio tracking across markets)
CREATE TABLE entity_market_properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id) NOT NULL,
    market_id UUID REFERENCES markets(id) NOT NULL,

    -- Portfolio stats in this market
    total_properties INTEGER DEFAULT 0,
    total_value DECIMAL(15, 2) DEFAULT 0,
    property_ids UUID[] DEFAULT ARRAY[]::UUID[],

    -- Activity tracking
    first_activity_date DATE,
    last_activity_date DATE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (entity_id, market_id)
);

CREATE INDEX idx_entity_market_properties_entity_id ON entity_market_properties(entity_id);
CREATE INDEX idx_entity_market_properties_market_id ON entity_market_properties(market_id);

-- ============================================================================
-- AI/ML LAYER: Placeholder Tables (MVP Week 3+)
-- ============================================================================

-- AI Inferences (Patterns, predictions, recommendations)
CREATE TABLE ai_inferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID REFERENCES markets(id),

    -- Inference details
    inference_type TEXT NOT NULL,  -- 'risk_assessment', 'opportunity_detection', 'pattern_recognition'
    model_version TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Content
    inference_content JSONB NOT NULL,
    reasoning TEXT,
    known_uncertainties TEXT[],

    -- Provenance
    source_fact_ids UUID[],
    source_urls TEXT[],

    -- Validation
    validated BOOLEAN DEFAULT FALSE,
    validation_outcome TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_ai_inferences_market_id ON ai_inferences(market_id);
CREATE INDEX idx_ai_inferences_inference_type ON ai_inferences(inference_type);
CREATE INDEX idx_ai_inferences_confidence_score ON ai_inferences(confidence_score DESC);

-- Embeddings Cache (Document vectors for semantic search)
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash TEXT UNIQUE NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 or similar
    model_version TEXT NOT NULL,
    content_preview TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_embeddings_cache_content_hash ON embeddings_cache(content_hash);
CREATE INDEX idx_embeddings_cache_embedding ON embeddings_cache USING ivfflat(embedding vector_cosine_ops);

-- LLM Cache (Reduce API costs by caching responses)
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_hash TEXT UNIQUE NOT NULL,
    prompt_preview TEXT,
    response_content TEXT NOT NULL,
    model_version TEXT NOT NULL,
    temperature FLOAT,
    token_count INTEGER,
    cost_cents INTEGER,
    hit_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_llm_cache_prompt_hash ON llm_cache(prompt_hash);
CREATE INDEX idx_llm_cache_last_used_at ON llm_cache(last_used_at DESC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_markets_updated_at BEFORE UPDATE ON markets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entity_relationships_updated_at BEFORE UPDATE ON entity_relationships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA & COMMENTS
-- ============================================================================

COMMENT ON TABLE markets IS 'Central registry of all geographic markets Dominion operates in';
COMMENT ON TABLE entities IS 'Global entities (people, LLCs, companies) that operate across markets';
COMMENT ON TABLE entity_relationships IS 'Relationships between entities with confidence scores';
COMMENT ON TABLE raw_facts IS 'Immutable event log - ALL scraped data starts here';
COMMENT ON TABLE properties IS 'Active properties with current state (market-partitioned)';
COMMENT ON TABLE permits IS 'Building permits from city and county (market-partitioned)';
COMMENT ON TABLE bulk_property_records IS 'CAMA property records enriched with qPublic data';
COMMENT ON TABLE bulk_llc_records IS 'Sunbiz LLC records from monthly SFTP dump';

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- GLOBAL LAYER: 4 tables (markets, entities, entity_relationships, users)
-- MARKET LAYER: 8 partitioned tables (raw_facts, properties, permits, crime_reports, council_meetings, news_articles, bulk_property_records, + linking)
-- STATEWIDE: 2 tables (llc_formations, bulk_llc_records)
-- BULK TRACKING: 1 table (bulk_data_snapshots)
-- AI/ML PLACEHOLDERS: 3 tables (ai_inferences, embeddings_cache, llm_cache)
--
-- TOTAL: 18 tables (down from 52!)
-- ============================================================================
