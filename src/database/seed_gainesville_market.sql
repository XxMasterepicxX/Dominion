-- ============================================================================
-- Seed Gainesville Market and Create Partitions
-- ============================================================================

-- Insert Gainesville market
INSERT INTO markets (
    market_code,
    market_name,
    state,
    county,
    city,
    is_active,
    config
) VALUES (
    'gainesville_fl',
    'Gainesville, FL',
    'FL',
    'Alachua',
    'Gainesville',
    TRUE,
    '{"property_appraiser_url": "https://qpublic.schneidercorp.com/Application.aspx?AppID=1081", "city_permits_api": "https://data.cityofgainesville.org/Building-Development/Building-Permits/p798-x3nx", "county_permits_url": "https://growth-management.alachuacounty.us/PermitTracker"}'::jsonb
);

-- Get the Gainesville market_id for partition creation
DO $$
DECLARE
    gainesville_market_id UUID;
BEGIN
    -- Get Gainesville market ID
    SELECT id INTO gainesville_market_id
    FROM markets
    WHERE market_code = 'gainesville_fl';

    -- Create partition for raw_facts
    EXECUTE format('CREATE TABLE raw_facts_gainesville_fl PARTITION OF raw_facts FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for properties
    EXECUTE format('CREATE TABLE properties_gainesville_fl PARTITION OF properties FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for permits
    EXECUTE format('CREATE TABLE permits_gainesville_fl PARTITION OF permits FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for crime_reports
    EXECUTE format('CREATE TABLE crime_reports_gainesville_fl PARTITION OF crime_reports FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for council_meetings
    EXECUTE format('CREATE TABLE council_meetings_gainesville_fl PARTITION OF council_meetings FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for news_articles
    EXECUTE format('CREATE TABLE news_articles_gainesville_fl PARTITION OF news_articles FOR VALUES IN (%L)', gainesville_market_id);

    -- Create partition for bulk_property_records
    EXECUTE format('CREATE TABLE bulk_property_records_gainesville_fl PARTITION OF bulk_property_records FOR VALUES IN (%L)', gainesville_market_id);

    RAISE NOTICE 'Gainesville market created with ID: %', gainesville_market_id;
    RAISE NOTICE 'All 7 partitions created successfully for Gainesville';
END $$;

-- Verify partitions created
SELECT
    tablename,
    schemaname
FROM pg_tables
WHERE tablename LIKE '%gainesville%'
ORDER BY tablename;

-- Show market details
SELECT
    market_code,
    market_name,
    state,
    county,
    city,
    is_active,
    id
FROM markets;
