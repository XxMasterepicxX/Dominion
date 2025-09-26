-- Dominion Real Estate Intelligence Database Schema
-- Complete schema supporting facts vs inferences architecture

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- CONTENT SNAPSHOTS TABLE (For Change Detection)
-- ============================================================================

-- Track content changes using MD5 hashing
CREATE TABLE content_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash TEXT NOT NULL,
    url TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    size INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    content_type TEXT,
    response_code INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient change detection queries
CREATE INDEX idx_content_snapshots_url ON content_snapshots(url);
CREATE INDEX idx_content_snapshots_timestamp ON content_snapshots(timestamp DESC);
CREATE INDEX idx_content_snapshots_hash ON content_snapshots(content_hash);
CREATE INDEX idx_content_snapshots_url_timestamp ON content_snapshots(url, timestamp DESC);

-- ============================================================================
-- RAW FACTS TABLES (Immutable, Source-Linked)
-- ============================================================================

-- Immutable facts with full provenance
CREATE TABLE raw_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_type TEXT NOT NULL, -- 'property_sale', 'permit_filing', 'news_article', 'llc_formation', 'council_minutes', 'census_data', 'crime_report'
    source_url TEXT NOT NULL, -- Where this came from
    scraped_at TIMESTAMP NOT NULL, -- When we collected it
    parser_version TEXT NOT NULL, -- Which parser version processed it
    raw_content JSONB NOT NULL, -- Original unprocessed data
    content_hash TEXT NOT NULL UNIQUE, -- MD5 hash for deduplication
    processed_at TIMESTAMP, -- When we extracted structured data
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for efficient querying
CREATE INDEX idx_raw_facts_fact_type ON raw_facts(fact_type);
CREATE INDEX idx_raw_facts_scraped_at ON raw_facts(scraped_at DESC);
CREATE INDEX idx_raw_facts_content_hash ON raw_facts(content_hash);

-- Structured facts extracted from raw data
CREATE TABLE structured_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_fact_id UUID REFERENCES raw_facts(id) NOT NULL,
    entity_type TEXT NOT NULL, -- 'property', 'person', 'company', 'permit', 'sale', 'llc'
    structured_data JSONB NOT NULL, -- Clean, typed data
    extraction_confidence FLOAT NOT NULL CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    validation_status TEXT DEFAULT 'unvalidated' CHECK (validation_status IN ('unvalidated', 'validated', 'flagged', 'rejected')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for efficient structured fact queries
CREATE INDEX idx_structured_facts_entity_type ON structured_facts(entity_type);
CREATE INDEX idx_structured_facts_raw_fact_id ON structured_facts(raw_fact_id);

-- Event sourcing for all data changes
CREATE TABLE fact_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL CHECK (event_type IN ('fact_added', 'fact_updated', 'fact_invalidated')),
    fact_id UUID REFERENCES structured_facts(id),
    event_data JSONB NOT NULL,
    correlation_id UUID, -- Links related operations
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- AI-DERIVED INFERENCES TABLES (Confidence-Scored)
-- ============================================================================

-- AI-generated insights with provenance
CREATE TABLE ai_inferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inference_type TEXT NOT NULL, -- 'relationship', 'prediction', 'pattern', 'risk_assessment', 'assemblage_detection'
    model_version TEXT NOT NULL, -- Which AI model generated this
    model_temperature FLOAT, -- Model settings used
    prompt_hash TEXT, -- Hash of prompt used (for reproducibility)

    -- Confidence and safety
    confidence_score FLOAT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    threshold_met BOOLEAN NOT NULL, -- Did it meet minimum confidence threshold?

    -- Content and reasoning
    inference_content JSONB NOT NULL, -- The actual insight/prediction
    reasoning TEXT, -- AI's explanation of its reasoning
    known_uncertainties TEXT[], -- What the AI identified as uncertain

    -- Provenance tracking
    source_fact_ids UUID[] NOT NULL, -- Which facts this inference is based on
    human_validated BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,

    -- Expiration and refresh
    expires_at TIMESTAMP, -- When this inference should be refreshed
    confidence_decay_rate FLOAT DEFAULT 0.1, -- How fast confidence decays
    last_validated TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Inference relationships (how inferences connect to each other)
CREATE TABLE inference_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_inference_id UUID REFERENCES ai_inferences(id),
    child_inference_id UUID REFERENCES ai_inferences(id),
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('supports', 'contradicts', 'builds_on')),
    strength FLOAT CHECK (strength >= 0 AND strength <= 1),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Track inference performance over time
CREATE TABLE inference_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inference_id UUID REFERENCES ai_inferences(id),
    predicted_outcome JSONB, -- What the AI predicted
    actual_outcome JSONB, -- What actually happened
    accuracy_score FLOAT, -- How accurate the prediction was
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- CORE ENTITY TABLES (Built from Facts)
-- ============================================================================

-- Entities derived from structured facts
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'company', 'government', 'developer', 'llc', 'attorney')),
    canonical_name TEXT NOT NULL,
    aliases TEXT[], -- Other names this entity is known by

    -- Fact-based attributes
    fact_based_attributes JSONB, -- Attributes directly from facts
    inferred_attributes JSONB, -- Attributes from AI inference

    -- Confidence and validation
    resolution_confidence FLOAT, -- How confident we are this is one entity
    last_fact_update TIMESTAMP, -- When facts about this entity were last updated

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Full-text search on entity names
CREATE INDEX idx_entities_name_search ON entities USING gin(to_tsvector('english', canonical_name || ' ' || array_to_string(aliases, ' ')));

-- Properties with factual and inferred data
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    parcel_id TEXT UNIQUE,
    coordinates GEOMETRY(POINT, 4326), -- PostGIS point for spatial queries

    -- Fact-based data
    factual_data JSONB, -- Directly from county records, MLS, etc.

    -- Inferred data
    inferred_data JSONB, -- AI-derived insights about this property
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 1), -- AI risk assessment
    opportunity_score FLOAT CHECK (opportunity_score >= 0 AND opportunity_score <= 1), -- AI opportunity assessment

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Spatial index for geographic queries
CREATE INDEX idx_properties_coordinates ON properties USING GIST (coordinates);
CREATE INDEX idx_properties_address ON properties USING gin(to_tsvector('english', address));

-- Relationships between entities (derived from inferences)
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID REFERENCES entities(id),
    to_entity_id UUID REFERENCES entities(id),
    relationship_type TEXT NOT NULL, -- 'owns', 'developed', 'opposed', 'partnered', 'represents'

    -- Supporting evidence
    supporting_inference_ids UUID[], -- Which inferences support this relationship
    supporting_fact_ids UUID[], -- Which facts support this relationship

    -- Confidence and temporal data
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Prevent duplicate relationships
CREATE UNIQUE INDEX idx_entity_relationships_unique ON entity_relationships(from_entity_id, to_entity_id, relationship_type) WHERE is_active = TRUE;

-- ============================================================================
-- SPECIFIC DATA TYPE TABLES
-- ============================================================================

-- Building permits
CREATE TABLE permits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(id),
    permit_number TEXT UNIQUE NOT NULL,
    permit_type TEXT NOT NULL,
    description TEXT,
    applicant_name TEXT,
    contractor_name TEXT,
    issue_date DATE,
    value DECIMAL(12, 2),
    status TEXT,
    jurisdiction TEXT, -- 'city' or 'county'

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Property sales
CREATE TABLE property_sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(id),
    sale_date DATE NOT NULL,
    sale_price DECIMAL(12, 2),
    buyer_name TEXT,
    seller_name TEXT,
    buyer_entity_id UUID REFERENCES entities(id),
    seller_entity_id UUID REFERENCES entities(id),
    deed_book TEXT,
    deed_page TEXT,

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- LLC formations
CREATE TABLE llc_formations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id),
    name TEXT NOT NULL,
    filed_date DATE,
    document_number TEXT UNIQUE,
    agent_name TEXT,
    agent_address TEXT,
    principal_address TEXT,

    -- Analysis flags
    is_property_related BOOLEAN DEFAULT FALSE,
    property_address_in_name BOOLEAN DEFAULT FALSE,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- News articles
CREATE TABLE news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT,
    published_date TIMESTAMP,
    author TEXT,
    source TEXT, -- 'gainesville_sun', 'business_journal', etc.
    url TEXT UNIQUE,

    -- Extracted entities and relationships
    extracted_entities JSONB,
    extracted_relationships JSONB,

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- Council minutes and meetings
CREATE TABLE council_meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_date DATE NOT NULL,
    meeting_type TEXT, -- 'city_council', 'planning_board', etc.
    agenda_items JSONB,
    minutes_text TEXT,
    pdf_url TEXT,

    -- Extracted intelligence
    development_discussions JSONB,
    extracted_entities JSONB,

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- Crime data
CREATE TABLE crime_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_number TEXT UNIQUE,
    report_date DATE,
    offense_type TEXT,
    location_address TEXT,
    coordinates GEOMETRY(POINT, 4326),

    -- Fact reference
    source_fact_id UUID REFERENCES structured_facts(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- CACHING AND PERFORMANCE TABLES
-- ============================================================================

-- LLM response cache to reduce API costs with proper cache key structure
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cache key components (must match exactly)
    provider TEXT NOT NULL,           -- 'gemini', 'openai'
    model_name TEXT NOT NULL,         -- 'gemini-2.0-flash', 'gpt-4o-mini'
    system_role TEXT NOT NULL,        -- 'real_estate_analyst', 'risk_assessor'
    prompt_hash TEXT NOT NULL,        -- hash of normalized prompt
    context_hash TEXT NOT NULL,       -- hash of facts + timestamps (auto-invalidates)
    sampler_profile TEXT NOT NULL DEFAULT 'deterministic', -- 'deterministic', 'creative_v1'

    -- Response data
    response JSONB NOT NULL,
    cost_cents INTEGER,

    -- Metadata (not part of cache key)
    temperature FLOAT,               -- logged for observability only
    prompt_preview TEXT,             -- first 200 chars for debugging

    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,

    -- Fixed unique constraint to match cache key components
    UNIQUE(provider, model_name, system_role, prompt_hash, context_hash, sampler_profile)
);

-- Embeddings cache for vector search
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash TEXT NOT NULL UNIQUE,
    content_preview TEXT, -- First 200 chars for debugging
    embedding vector(1536), -- Configurable dimension
    embedding_provider TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector storage for semantic search
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_id UUID REFERENCES raw_facts(id),
    embedding_cache_id UUID REFERENCES embeddings_cache(id),
    document_type TEXT NOT NULL, -- 'news', 'permit', 'report', 'council_minutes'
    chunk_index INTEGER DEFAULT 0, -- For large documents split into chunks
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- MONITORING AND OPERATIONAL TABLES
-- ============================================================================

-- Scraper health and performance tracking
CREATE TABLE scraper_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraper_name TEXT NOT NULL,
    source_type TEXT NOT NULL, -- 'api', 'web_scrape', 'download'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT CHECK (status IN ('running', 'completed', 'failed', 'timeout')),
    records_processed INTEGER DEFAULT 0,
    records_new INTEGER DEFAULT 0,
    error_message TEXT,
    execution_time_seconds INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Data quality metrics
CREATE TABLE data_quality_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    check_type TEXT NOT NULL, -- 'completeness', 'validity', 'consistency'
    check_result JSONB NOT NULL,
    records_checked INTEGER,
    records_passed INTEGER,
    records_failed INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Intelligence alerts for high-confidence findings
CREATE TABLE intelligence_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type TEXT NOT NULL, -- 'assemblage_detected', 'llc_formation', 'permit_pattern', 'developer_activity'
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    title TEXT NOT NULL,
    description TEXT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Related data
    related_properties UUID[],
    related_entities UUID[],
    related_inferences UUID[],

    -- Alert metadata
    alert_data JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- USER AND AUTHENTICATION TABLES
-- ============================================================================

-- Simple users table for MVP
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    user_type TEXT NOT NULL CHECK (user_type IN ('developer', 'flipper', 'agent', 'investor')),
    subscription_tier TEXT DEFAULT 'on_demand' CHECK (subscription_tier IN ('on_demand', 'professional', 'enterprise')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Simple API keys table for enterprise users
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    key_hash TEXT NOT NULL,
    name TEXT,  -- User-friendly name for the key
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- ADDITIONAL INDEXES FOR PERFORMANCE
-- ============================================================================

-- Performance indexes for common queries
CREATE INDEX idx_permits_property_id ON permits(property_id);
CREATE INDEX idx_permits_issue_date ON permits(issue_date DESC);
CREATE INDEX idx_property_sales_property_id ON property_sales(property_id);
CREATE INDEX idx_property_sales_sale_date ON property_sales(sale_date DESC);
CREATE INDEX idx_llc_formations_filed_date ON llc_formations(filed_date DESC);
CREATE INDEX idx_llc_formations_property_related ON llc_formations(is_property_related) WHERE is_property_related = TRUE;
CREATE INDEX idx_news_articles_published_date ON news_articles(published_date DESC);
CREATE INDEX idx_intelligence_alerts_created_at ON intelligence_alerts(created_at DESC);
CREATE INDEX idx_intelligence_alerts_unresolved ON intelligence_alerts(resolved) WHERE resolved = FALSE;

-- Composite indexes for common query patterns
CREATE INDEX idx_scraper_runs_name_date ON scraper_runs(scraper_name, started_at DESC);
CREATE INDEX idx_ai_inferences_type_confidence ON ai_inferences(inference_type, confidence_score DESC);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_properties_updated_at BEFORE UPDATE ON properties FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_entities_updated_at BEFORE UPDATE ON entities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_entity_relationships_updated_at BEFORE UPDATE ON entity_relationships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_permits_updated_at BEFORE UPDATE ON permits FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();