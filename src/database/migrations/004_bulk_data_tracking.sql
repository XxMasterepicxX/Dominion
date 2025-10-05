-- Bulk Data Tracking Migration
-- Tracks bulk data downloads, MD5 hashes, and update history

-- =====================================================
-- Bulk Data Metadata (Track downloads and changes)
-- =====================================================
CREATE TABLE IF NOT EXISTS bulk_data_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source_type TEXT NOT NULL,  -- 'sunbiz_sftp', 'property_appraiser', 'gis_parcels'
    source_name TEXT NOT NULL,  -- 'daily_corporate', 'alachua_cama', 'alachua_parcels'

    -- File tracking
    file_url TEXT,
    file_name TEXT,
    file_size_bytes BIGINT,

    -- Change detection
    content_md5 TEXT NOT NULL,  -- MD5 hash of file content
    record_count INTEGER,       -- Number of records in this snapshot

    -- Update tracking
    download_date TIMESTAMP NOT NULL DEFAULT NOW(),
    processing_status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,

    -- Delta tracking (for incremental updates)
    is_initial_load BOOLEAN DEFAULT FALSE,
    previous_snapshot_id UUID REFERENCES bulk_data_snapshots(id),
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_unchanged INTEGER DEFAULT 0,

    -- Metadata
    error_message TEXT,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT ck_processing_status CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE INDEX idx_bulk_snapshots_source ON bulk_data_snapshots(source_type, source_name);
CREATE INDEX idx_bulk_snapshots_md5 ON bulk_data_snapshots(content_md5);
CREATE INDEX idx_bulk_snapshots_download_date ON bulk_data_snapshots(download_date DESC);
CREATE INDEX idx_bulk_snapshots_status ON bulk_data_snapshots(processing_status);


-- =====================================================
-- Bulk Property Records (CAMA Data)
-- =====================================================
CREATE TABLE IF NOT EXISTS bulk_property_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    parcel_id TEXT NOT NULL,
    account_number TEXT,
    jurisdiction TEXT NOT NULL,  -- 'alachua', 'gainesville', etc.

    -- Address
    property_address TEXT NOT NULL,
    city TEXT,
    state TEXT,
    zip_code TEXT,

    -- Ownership
    owner_name TEXT,
    owner_address TEXT,
    owner_city TEXT,
    owner_state TEXT,
    owner_zip TEXT,

    -- Property characteristics
    use_code TEXT,  -- Zoning/land use code
    property_type TEXT,
    year_built INTEGER,
    square_footage DECIMAL,
    lot_size_acres DECIMAL,
    bedrooms INTEGER,
    bathrooms DECIMAL,

    -- Valuations
    assessed_value DECIMAL,
    market_value DECIMAL,
    taxable_value DECIMAL,
    land_value DECIMAL,
    building_value DECIMAL,

    -- Sale information
    last_sale_date DATE,
    last_sale_price DECIMAL,
    deed_book TEXT,
    deed_page TEXT,

    -- Spatial (if available)
    latitude DECIMAL,
    longitude DECIMAL,
    coordinates GEOMETRY(POINT, 4326),

    -- Tracking
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),
    data_date DATE,  -- Date this data represents
    raw_data JSONB,  -- Full source data

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint per snapshot
    UNIQUE(parcel_id, jurisdiction, snapshot_id)
);

CREATE INDEX idx_bulk_property_parcel ON bulk_property_records(parcel_id, jurisdiction);
CREATE INDEX idx_bulk_property_address ON bulk_property_records USING GIN(to_tsvector('english', property_address));
CREATE INDEX idx_bulk_property_owner ON bulk_property_records USING GIN(to_tsvector('english', owner_name));
CREATE INDEX idx_bulk_property_coords ON bulk_property_records USING GIST(coordinates) WHERE coordinates IS NOT NULL;
CREATE INDEX idx_bulk_property_snapshot ON bulk_property_records(snapshot_id);
CREATE INDEX idx_bulk_property_sale_date ON bulk_property_records(last_sale_date) WHERE last_sale_date IS NOT NULL;


-- =====================================================
-- Bulk LLC Records (Sunbiz SFTP)
-- =====================================================
CREATE TABLE IF NOT EXISTS bulk_llc_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    document_number TEXT NOT NULL,
    entity_name TEXT NOT NULL,

    -- Filing info
    filing_date DATE NOT NULL,
    status TEXT,  -- 'ACTIVE', 'INACTIVE', 'DISSOLVED'
    entity_type TEXT,  -- 'LLC', 'CORP', 'LP', etc.

    -- Registered agent
    registered_agent_name TEXT,
    registered_agent_address TEXT,
    registered_agent_city TEXT,
    registered_agent_state TEXT,
    registered_agent_zip TEXT,

    -- Principal address
    principal_address TEXT,
    principal_city TEXT,
    principal_state TEXT,
    principal_zip TEXT,

    -- Mailing address
    mailing_address TEXT,
    mailing_city TEXT,
    mailing_state TEXT,
    mailing_zip TEXT,

    -- Officers/Members
    officers JSONB,

    -- Additional data
    fei_ein TEXT,
    annual_report_year INTEGER,

    -- Real estate flags
    is_property_related BOOLEAN DEFAULT FALSE,

    -- Tracking
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),
    raw_data JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(document_number, snapshot_id)
);

CREATE INDEX idx_bulk_llc_document ON bulk_llc_records(document_number);
CREATE INDEX idx_bulk_llc_name ON bulk_llc_records USING GIN(to_tsvector('english', entity_name));
CREATE INDEX idx_bulk_llc_status ON bulk_llc_records(status);
CREATE INDEX idx_bulk_llc_filing_date ON bulk_llc_records(filing_date DESC);
CREATE INDEX idx_bulk_llc_snapshot ON bulk_llc_records(snapshot_id);
CREATE INDEX idx_bulk_llc_property_related ON bulk_llc_records(is_property_related) WHERE is_property_related = TRUE;


-- =====================================================
-- Bulk GIS Parcels (Spatial Data)
-- =====================================================
CREATE TABLE IF NOT EXISTS bulk_gis_parcels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    parcel_id TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,

    -- Spatial data (all geometries converted to MULTIPOLYGON using ST_Multi)
    geometry GEOMETRY(MULTIPOLYGON, 4326),  -- Full parcel boundary (always MULTIPOLYGON)
    centroid GEOMETRY(POINT, 4326),         -- Center point

    -- Parcel attributes
    zoning_code TEXT,
    land_use TEXT,
    acreage DECIMAL,

    -- Tracking
    snapshot_id UUID REFERENCES bulk_data_snapshots(id),
    raw_data JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(parcel_id, jurisdiction, snapshot_id)
);

CREATE INDEX idx_bulk_gis_parcel ON bulk_gis_parcels(parcel_id, jurisdiction);
CREATE INDEX idx_bulk_gis_geometry ON bulk_gis_parcels USING GIST(geometry) WHERE geometry IS NOT NULL;
CREATE INDEX idx_bulk_gis_centroid ON bulk_gis_parcels USING GIST(centroid) WHERE centroid IS NOT NULL;
CREATE INDEX idx_bulk_gis_snapshot ON bulk_gis_parcels(snapshot_id);


-- =====================================================
-- Helper Views
-- =====================================================

-- Latest snapshot per source
CREATE OR REPLACE VIEW latest_bulk_snapshots AS
SELECT DISTINCT ON (source_type, source_name)
    id,
    source_type,
    source_name,
    content_md5,
    record_count,
    download_date,
    processing_status
FROM bulk_data_snapshots
WHERE processing_status = 'completed'
ORDER BY source_type, source_name, download_date DESC;

-- Latest property records (current snapshot only)
CREATE OR REPLACE VIEW current_bulk_properties AS
SELECT bp.*
FROM bulk_property_records bp
JOIN latest_bulk_snapshots lbs ON bp.snapshot_id = lbs.id
WHERE lbs.source_type = 'property_appraiser';

-- Latest LLC records (current snapshot only)
CREATE OR REPLACE VIEW current_bulk_llcs AS
SELECT bl.*
FROM bulk_llc_records bl
JOIN latest_bulk_snapshots lbs ON bl.snapshot_id = lbs.id
WHERE lbs.source_type = 'sunbiz_sftp';

-- Latest GIS parcels (current snapshot only)
CREATE OR REPLACE VIEW current_bulk_gis AS
SELECT bg.*
FROM bulk_gis_parcels bg
JOIN latest_bulk_snapshots lbs ON bg.snapshot_id = lbs.id
WHERE lbs.source_type = 'gis_parcels';


-- =====================================================
-- Helper Functions
-- =====================================================

-- Function to get latest snapshot MD5 for a source
CREATE OR REPLACE FUNCTION get_latest_bulk_md5(p_source_type TEXT, p_source_name TEXT)
RETURNS TEXT AS $$
    SELECT content_md5
    FROM bulk_data_snapshots
    WHERE source_type = p_source_type
      AND source_name = p_source_name
      AND processing_status = 'completed'
    ORDER BY download_date DESC
    LIMIT 1;
$$ LANGUAGE SQL;


-- Function to mark snapshot as processing
CREATE OR REPLACE FUNCTION start_bulk_processing(p_snapshot_id UUID)
RETURNS VOID AS $$
    UPDATE bulk_data_snapshots
    SET processing_status = 'processing',
        processing_started_at = NOW()
    WHERE id = p_snapshot_id;
$$ LANGUAGE SQL;


-- Function to mark snapshot as completed
CREATE OR REPLACE FUNCTION complete_bulk_processing(
    p_snapshot_id UUID,
    p_record_count INTEGER,
    p_added INTEGER,
    p_updated INTEGER,
    p_unchanged INTEGER
)
RETURNS VOID AS $$
    UPDATE bulk_data_snapshots
    SET processing_status = 'completed',
        processing_completed_at = NOW(),
        record_count = p_record_count,
        records_added = p_added,
        records_updated = p_updated,
        records_unchanged = p_unchanged
    WHERE id = p_snapshot_id;
$$ LANGUAGE SQL;


-- =====================================================
-- Usage Instructions
-- =====================================================

/*
WORKFLOW:

1. Initial Bulk Load:
   - Download Sunbiz SFTP historical file
   - Calculate MD5, create snapshot record
   - Parse and insert into bulk_llc_records
   - Mark snapshot as completed

2. Daily Updates:
   - Download latest Sunbiz file
   - Calculate MD5
   - Compare to latest snapshot MD5
   - If different:
     - Create new snapshot
     - Parse file
     - UPSERT records (match on document_number)
     - Track added/updated/unchanged counts
     - Mark snapshot completed
   - If same: Skip processing

3. Property Enrichment:
   - When creating property from permit:
     - Query current_bulk_properties for match
     - If found: enrich with parcel_id, coordinates, owner

4. LLC Enrichment:
   - When resolving entity:
     - Query current_bulk_llcs for match
     - If found: create LLC with full data

Example Queries:

-- Get latest MD5 for Sunbiz
SELECT get_latest_bulk_md5('sunbiz_sftp', 'daily_corporate');

-- Find property by address in bulk data
SELECT * FROM current_bulk_properties
WHERE to_tsvector('english', property_address) @@ to_tsquery('123 Main St');

-- Find LLC by document number
SELECT * FROM current_bulk_llcs
WHERE document_number = 'L25000442960';

-- Properties missing parcel IDs that could be enriched
SELECT p.id, p.address, bp.parcel_id, bp.coordinates
FROM properties p
JOIN current_bulk_properties bp
  ON similarity(p.address, bp.property_address) > 0.8
WHERE p.parcel_id IS NULL
LIMIT 100;
*/
