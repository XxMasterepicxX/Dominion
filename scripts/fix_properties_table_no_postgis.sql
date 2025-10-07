-- Fix properties table to not require PostGIS
-- This allows the database to work without PostGIS extension

BEGIN;

-- Drop the geometry column (PostGIS type)
ALTER TABLE properties DROP COLUMN IF EXISTS coordinates;

-- Keep latitude and longitude (they're already regular DOUBLE PRECISION)
-- These are sufficient for most use cases

-- Verify the change
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'properties'
AND column_name IN ('latitude', 'longitude', 'coordinates');

COMMIT;
