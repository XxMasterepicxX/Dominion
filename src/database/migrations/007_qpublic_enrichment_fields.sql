-- Migration 007: Add missing qPublic enrichment fields to bulk_property_records
--
-- The qPublic enrichment service provides valuable data that wasn't in the original schema:
-- - Residential details (bedrooms, bathrooms)
-- - Sales history (last sale date/price)
-- - Property classification (use_code, city)
-- - Complete raw data preservation (raw_data JSONB)
-- - Building details (roofing, HVAC, etc. in building_details JSONB)
--
-- This migration adds those fields so we don't lose any qPublic data.

-- Add direct columns for commonly-queried fields
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS bedrooms INTEGER;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS bathrooms NUMERIC;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS last_sale_date DATE;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS last_sale_price NUMERIC;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS use_code TEXT;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS city TEXT;

-- Add JSONB columns for preservation and flexibility
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS raw_data JSONB;
ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS building_details JSONB;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bulk_property_bedrooms ON bulk_property_records(bedrooms) WHERE bedrooms IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bulk_property_bathrooms ON bulk_property_records(bathrooms) WHERE bathrooms IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bulk_property_last_sale_date ON bulk_property_records(last_sale_date) WHERE last_sale_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bulk_property_use_code ON bulk_property_records(use_code) WHERE use_code IS NOT NULL;

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_bulk_property_raw_data ON bulk_property_records USING GIN (raw_data) WHERE raw_data IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bulk_property_building_details ON bulk_property_records USING GIN (building_details) WHERE building_details IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN bulk_property_records.bedrooms IS 'Number of bedrooms (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.bathrooms IS 'Number of bathrooms (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.last_sale_date IS 'Most recent sale date (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.last_sale_price IS 'Most recent sale price (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.use_code IS 'Property use/zoning code (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.city IS 'City name (from qPublic enrichment)';
COMMENT ON COLUMN bulk_property_records.raw_data IS 'Complete qPublic response JSON - preserves all data for future parsing';
COMMENT ON COLUMN bulk_property_records.building_details IS 'Detailed building characteristics (roofing, HVAC, exterior, etc.) from qPublic';
