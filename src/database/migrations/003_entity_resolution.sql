-- Entity Resolution Support Tables
-- For logging decisions and managing review queue

-- =====================================================
-- Entity Resolution Log (Training Data for Week 3 ML)
-- =====================================================
CREATE TABLE IF NOT EXISTS entity_resolution_log (
    id UUID PRIMARY KEY,

    -- What we scraped
    scraped_features JSONB NOT NULL,

    -- What we matched it to
    matched_entity_id UUID REFERENCES entities(id),

    -- How confident we were
    confidence FLOAT NOT NULL,

    -- Which signals contributed
    signals JSONB NOT NULL,  -- [{"name": "address_match", "value": 0.95, "weight": 0.35}]

    -- Method used (definitive, multi_signal, llm, needs_review)
    method TEXT NOT NULL,

    -- Was this auto-accepted or human-reviewed?
    auto_accepted BOOLEAN NOT NULL,

    -- Human validation (filled in later if reviewed)
    human_validated BOOLEAN,
    human_correct BOOLEAN,  -- Was the auto-decision correct?
    validated_by UUID REFERENCES users(id),
    validated_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes for querying training data
    CONSTRAINT ck_resolution_method CHECK (method IN ('definitive', 'multi_signal', 'llm', 'needs_review', 'creation'))
);

CREATE INDEX idx_resolution_log_confidence ON entity_resolution_log(confidence);
CREATE INDEX idx_resolution_log_method ON entity_resolution_log(method);
CREATE INDEX idx_resolution_log_auto_accepted ON entity_resolution_log(auto_accepted);
CREATE INDEX idx_resolution_log_created_at ON entity_resolution_log(created_at);

-- Index for finding training data
CREATE INDEX idx_resolution_log_validated ON entity_resolution_log(human_validated, human_correct)
    WHERE human_validated IS NOT NULL;


-- =====================================================
-- Entity Review Queue (Human Review for Uncertain Cases)
-- =====================================================
CREATE TABLE IF NOT EXISTS entity_review_queue (
    id UUID PRIMARY KEY,

    -- Scraped data
    scraped_features JSONB NOT NULL,

    -- Candidate match (or NULL if creating new)
    candidate_entity_id UUID REFERENCES entities(id),

    -- Scoring results
    confidence FLOAT NOT NULL,
    signals JSONB NOT NULL,

    -- Review status
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 3,  -- 1=high, 2=medium, 3=low

    -- Review decision
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    decision TEXT,  -- 'accept', 'reject', 'create_new'
    notes TEXT,

    -- Resolution
    resolved_entity_id UUID REFERENCES entities(id),

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT ck_review_status CHECK (status IN ('pending', 'in_review', 'completed', 'skipped')),
    CONSTRAINT ck_review_decision CHECK (decision IS NULL OR decision IN ('accept', 'reject', 'create_new'))
);

CREATE INDEX idx_review_queue_status ON entity_review_queue(status);
CREATE INDEX idx_review_queue_priority ON entity_review_queue(priority, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_review_queue_confidence ON entity_review_queue(confidence)
    WHERE status = 'pending';


-- =====================================================
-- Known Registered Agent Services (Auto-populated)
-- =====================================================
CREATE TABLE IF NOT EXISTS known_agent_services (
    id UUID PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,

    -- Detected automatically when same agent appears for 10+ different companies
    detection_count INTEGER DEFAULT 0,

    -- Can be manually flagged
    manually_flagged BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_known_agents_name ON known_agent_services(LOWER(service_name));

-- Pre-populate with known services
INSERT INTO known_agent_services (id, service_name, manually_flagged)
VALUES
    (gen_random_uuid(), 'CT Corporation System', TRUE),
    (gen_random_uuid(), 'Incorp Services, Inc.', TRUE),
    (gen_random_uuid(), 'National Registered Agents, Inc.', TRUE),
    (gen_random_uuid(), 'Harvard Business Services, Inc.', TRUE),
    (gen_random_uuid(), 'Registered Agent Solutions, Inc.', TRUE),
    (gen_random_uuid(), 'Corporation Service Company', TRUE),
    (gen_random_uuid(), 'CSC', TRUE),
    (gen_random_uuid(), 'Northwest Registered Agent', TRUE)
ON CONFLICT (service_name) DO NOTHING;


-- =====================================================
-- Entity Resolution Metrics (For monitoring quality)
-- =====================================================
CREATE TABLE IF NOT EXISTS entity_resolution_metrics (
    id UUID PRIMARY KEY,

    -- Time window
    date DATE NOT NULL,
    hour INTEGER,  -- NULL for daily aggregates

    -- Counts by method
    total_resolutions INTEGER NOT NULL DEFAULT 0,
    definitive_matches INTEGER NOT NULL DEFAULT 0,
    multi_signal_matches INTEGER NOT NULL DEFAULT 0,
    llm_matches INTEGER NOT NULL DEFAULT 0,
    new_entities_created INTEGER NOT NULL DEFAULT 0,
    queued_for_review INTEGER NOT NULL DEFAULT 0,

    -- Confidence distribution
    high_confidence_count INTEGER NOT NULL DEFAULT 0,  -- >= 0.95
    medium_confidence_count INTEGER NOT NULL DEFAULT 0,  -- 0.70-0.94
    low_confidence_count INTEGER NOT NULL DEFAULT 0,  -- < 0.70

    -- Average confidence
    avg_confidence FLOAT,

    -- Human validation stats (filled in as reviews complete)
    human_validations_completed INTEGER DEFAULT 0,
    human_validations_correct INTEGER DEFAULT 0,
    precision FLOAT,  -- correct / completed

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(date, hour)
);

CREATE INDEX idx_resolution_metrics_date ON entity_resolution_metrics(date);


-- =====================================================
-- Helper function to auto-detect agent services
-- =====================================================
CREATE OR REPLACE FUNCTION detect_agent_services()
RETURNS void AS $$
BEGIN
    -- Find registered agents used by 10+ different entities
    INSERT INTO known_agent_services (id, service_name, detection_count)
    SELECT
        gen_random_uuid(),
        fact_based_attributes->>'registered_agent' as service_name,
        COUNT(DISTINCT id) as detection_count
    FROM entities
    WHERE fact_based_attributes->>'registered_agent' IS NOT NULL
    GROUP BY fact_based_attributes->>'registered_agent'
    HAVING COUNT(DISTINCT id) >= 10
    ON CONFLICT (service_name)
    DO UPDATE SET
        detection_count = EXCLUDED.detection_count,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Run weekly via cron or scheduler
-- SELECT detect_agent_services();
