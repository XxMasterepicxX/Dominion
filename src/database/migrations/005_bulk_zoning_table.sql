-- Bulk Zoning Data Table
-- Stores zoning districts as polygons for spatial joins with parcels

CREATE TABLE IF NOT EXISTS bulk_gis_zoning (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    zoning_code TEXT NOT NULL,  -- e.g. 'R-1A', 'C-2', 'I-1'
    zoning_name TEXT,           -- e.g. 'Single Family Residential'
    jurisdiction TEXT NOT NULL,

    -- Spatial data
    geometry GEOMETRY(MULTIPOLYGON, 4326),  -- Zoning district boundary
    centroid GEOMETRY(POINT, 4326),

    -- Zoning attributes
    description TEXT,
    min_lot_size DECIMAL,
    max_height DECIMAL,
    max_density DECIMAL,

    -- Tracking
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),
    raw_data JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(zoning_code, jurisdiction, snapshot_id)
);

CREATE INDEX idx_bulk_zoning_code ON bulk_gis_zoning(zoning_code, jurisdiction);
CREATE INDEX idx_bulk_zoning_geometry ON bulk_gis_zoning USING GIST(geometry) WHERE geometry IS NOT NULL;
CREATE INDEX idx_bulk_zoning_snapshot ON bulk_gis_zoning(snapshot_id);


-- Helper view for latest zoning
CREATE OR REPLACE VIEW current_bulk_zoning AS
SELECT bz.*
FROM bulk_gis_zoning bz
JOIN latest_bulk_snapshots lbs ON bz.snapshot_id = lbs.id
WHERE lbs.source_type = 'gis_zoning';


-- Function to enrich parcels with zoning via spatial join
CREATE OR REPLACE FUNCTION enrich_parcels_with_zoning()
RETURNS TABLE(parcels_updated INTEGER) AS $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    -- Update bulk_gis_parcels with zoning info from spatial join
    WITH zoning_join AS (
        SELECT
            p.id as parcel_id,
            z.zoning_code,
            z.zoning_name
        FROM bulk_gis_parcels p
        JOIN current_bulk_zoning z ON ST_Intersects(p.geometry, z.geometry)
        WHERE p.zoning_code IS NULL  -- Only update parcels without zoning
    )
    UPDATE bulk_gis_parcels p
    SET
        zoning_code = zj.zoning_code,
       land_use = COALESCE(p.land_use, zj.zoning_name),
        updated_at = NOW()
    FROM zoning_join zj
    WHERE p.id = zj.parcel_id;

    GET DIAGNOSTICS updated_count = ROW_COUNT;

    RETURN QUERY SELECT updated_count;
END;
$$ LANGUAGE plpgsql;


-- Usage:
-- SELECT * FROM enrich_parcels_with_zoning();
