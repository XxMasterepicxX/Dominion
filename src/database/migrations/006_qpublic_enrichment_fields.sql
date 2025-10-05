-- Migration: Add qPublic enrichment fields to bulk_property_records
-- These fields store data extracted from qPublic that CAMA doesn't have

BEGIN;

-- Add coordinate fields
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8),
ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8),
ADD COLUMN IF NOT EXISTS state_plane_x DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS state_plane_y DECIMAL(12, 2);

-- Add additional valuation fields
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS improvement_value DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS land_value DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS land_agricultural_value DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS agricultural_market_value DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS exempt_value DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS max_soh_portability DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS taxable_value DECIMAL(12, 2);

-- Add detailed building information
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS exterior_walls VARCHAR(100),
ADD COLUMN IF NOT EXISTS interior_walls VARCHAR(100),
ADD COLUMN IF NOT EXISTS roofing VARCHAR(100),
ADD COLUMN IF NOT EXISTS roof_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS frame VARCHAR(100),
ADD COLUMN IF NOT EXISTS floor_cover VARCHAR(200),
ADD COLUMN IF NOT EXISTS heat VARCHAR(100),
ADD COLUMN IF NOT EXISTS hvac VARCHAR(100),
ADD COLUMN IF NOT EXISTS stories DECIMAL(3, 1),
ADD COLUMN IF NOT EXISTS total_area INTEGER,
ADD COLUMN IF NOT EXISTS effective_year_built INTEGER;

-- Add owner information (more detailed than CAMA)
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS owner_address TEXT;

-- Add JSON fields for complex data structures
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS sales_history JSONB,           -- Array of historical sales
ADD COLUMN IF NOT EXISTS permits JSONB,                 -- Array of building permits
ADD COLUMN IF NOT EXISTS trim_notices JSONB,            -- Array of TRIM notice PDFs
ADD COLUMN IF NOT EXISTS land_info JSONB,               -- Array of land use details
ADD COLUMN IF NOT EXISTS sub_areas JSONB,               -- Array of building sub-areas (porches, etc)
ADD COLUMN IF NOT EXISTS qpublic_links JSONB;           -- Links to tax collector, map, sketches, etc

-- Add enrichment metadata
ALTER TABLE bulk_property_records
ADD COLUMN IF NOT EXISTS qpublic_enriched_at TIMESTAMP,  -- When qPublic data was added
ADD COLUMN IF NOT EXISTS qpublic_source_url TEXT;        -- URL of qPublic detail page

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bulk_property_coords ON bulk_property_records USING btree (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_bulk_property_year_built ON bulk_property_records (year_built) WHERE year_built IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bulk_property_qpublic_enriched ON bulk_property_records (qpublic_enriched_at) WHERE qpublic_enriched_at IS NOT NULL;

-- Create spatial index if PostGIS is available (optional)
-- Uncomment if you have PostGIS installed:
-- ALTER TABLE bulk_property_records ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);
-- CREATE INDEX IF NOT EXISTS idx_bulk_property_geom ON bulk_property_records USING GIST (geom);

-- Add comments for documentation
COMMENT ON COLUMN bulk_property_records.latitude IS 'WGS84 latitude from qPublic map coordinates';
COMMENT ON COLUMN bulk_property_records.longitude IS 'WGS84 longitude from qPublic map coordinates';
COMMENT ON COLUMN bulk_property_records.sales_history IS 'JSON array of historical sales from qPublic';
COMMENT ON COLUMN bulk_property_records.permits IS 'JSON array of building permits from qPublic';
COMMENT ON COLUMN bulk_property_records.trim_notices IS 'JSON array of TRIM notice PDFs with years and URLs';
COMMENT ON COLUMN bulk_property_records.sub_areas IS 'JSON array of building sub-areas (porches, carports, etc)';
COMMENT ON COLUMN bulk_property_records.qpublic_links IS 'JSON object with URLs to tax collector, map viewer, sketches';

COMMIT;

-- Example usage after migration:
/*
-- Update a property with qPublic data
UPDATE bulk_property_records
SET
    latitude = 29.67116581,
    longitude = -82.24485870,
    improvement_value = 188135,
    land_value = 43750,
    exterior_walls = 'HARDIBOARD',
    roofing = 'ASPHALT',
    hvac = 'CENTRAL',
    sales_history = '[
        {"sale_date": "3/13/2003", "sale_price": 65000, "instrument": "WD"},
        {"sale_date": "6/24/1997", "sale_price": 35000, "instrument": "WD"}
    ]'::jsonb,
    permits = '[
        {"permit_number": "2009040247", "type": "POOL RESIDENTIAL", "value": 20000, "issue_date": "4/24/2009"}
    ]'::jsonb,
    qpublic_enriched_at = NOW(),
    qpublic_source_url = 'https://qpublic.schneidercorp.com/...'
WHERE parcel_id = '17757-003-004';

-- Find all properties enriched in last 24 hours
SELECT parcel_id, property_address, market_value, latitude, longitude
FROM bulk_property_records
WHERE qpublic_enriched_at > NOW() - INTERVAL '24 hours';

-- Find properties with sales history
SELECT parcel_id, property_address, jsonb_array_length(sales_history) as num_sales
FROM bulk_property_records
WHERE sales_history IS NOT NULL
ORDER BY num_sales DESC;

-- Find properties with permits
SELECT parcel_id, property_address, jsonb_array_length(permits) as num_permits
FROM bulk_property_records
WHERE permits IS NOT NULL
ORDER BY num_permits DESC;
*/
