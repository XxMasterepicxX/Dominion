-- Migration 009: Add entity_market_properties table
-- This table aggregates entity ownership data by market for portfolio analysis

CREATE TABLE IF NOT EXISTS entity_market_properties (
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

CREATE INDEX IF NOT EXISTS idx_entity_market_properties_entity_id ON entity_market_properties(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_market_properties_market_id ON entity_market_properties(market_id);
