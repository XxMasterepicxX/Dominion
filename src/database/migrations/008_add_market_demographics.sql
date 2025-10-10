-- Migration: Add market demographics table for census data
-- Created: 2025-10-09
-- Purpose: Store census demographic data fetched by census scraper

CREATE TABLE IF NOT EXISTS market_demographics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,

    -- Core census variables (from ACS 5-year estimates)
    total_population INTEGER,
    median_household_income INTEGER,
    median_home_value INTEGER,

    -- Additional demographic data (expandable)
    -- Store any additional census variables here
    census_variables JSONB DEFAULT '{}',

    -- Metadata
    data_year INTEGER NOT NULL,  -- 2022, 2023, etc.
    census_dataset TEXT NOT NULL DEFAULT 'acs5',  -- 'acs5', 'acs1', etc.

    -- Timestamps
    scraped_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Ensure one record per market per year
    UNIQUE (market_id, data_year)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_market_demographics_market_id ON market_demographics(market_id);
CREATE INDEX IF NOT EXISTS idx_market_demographics_data_year ON market_demographics(data_year DESC);
CREATE INDEX IF NOT EXISTS idx_market_demographics_scraped_at ON market_demographics(scraped_at DESC);

-- Comments for documentation
COMMENT ON TABLE market_demographics IS 'Census demographic data for markets, populated by census scraper';
COMMENT ON COLUMN market_demographics.total_population IS 'Census variable B01003_001E - Total population';
COMMENT ON COLUMN market_demographics.median_household_income IS 'Census variable B19013_001E - Median household income in dollars';
COMMENT ON COLUMN market_demographics.median_home_value IS 'Census variable B25077_001E - Median home value in dollars';
COMMENT ON COLUMN market_demographics.census_variables IS 'Additional census variables as key-value pairs';
