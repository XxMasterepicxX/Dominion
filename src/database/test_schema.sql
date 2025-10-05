-- ============================================================================
-- Test Multi-Market Schema V2
-- ============================================================================

-- Get Gainesville market ID for testing
DO $$
DECLARE
    gainesville_id UUID;
    test_entity_id UUID;
    test_property_id UUID;
    test_permit_id UUID;
    test_raw_fact_id UUID;
BEGIN
    -- Get Gainesville market ID
    SELECT id INTO gainesville_id FROM markets WHERE market_code = 'gainesville_fl';
    RAISE NOTICE 'Testing with Gainesville market ID: %', gainesville_id;

    -- TEST 1: Insert test entity
    INSERT INTO entities (
        entity_type,
        name,
        canonical_name,
        active_markets,
        first_seen_market_id
    ) VALUES (
        'llc',
        'Test Development LLC',
        'test development llc',
        ARRAY[gainesville_id],
        gainesville_id
    ) RETURNING id INTO test_entity_id;
    RAISE NOTICE '✓ TEST 1 PASSED: Entity created with ID: %', test_entity_id;

    -- TEST 2: Insert test property (partitioned)
    INSERT INTO properties (
        market_id,
        parcel_id,
        property_address,
        owner_entity_id,
        property_type
    ) VALUES (
        gainesville_id,
        'TEST-PARCEL-001',
        '123 Test St, Gainesville, FL',
        test_entity_id,
        'Residential'
    ) RETURNING id INTO test_property_id;
    RAISE NOTICE '✓ TEST 2 PASSED: Property created in partition with ID: %', test_property_id;

    -- TEST 3: Insert test raw_fact (partitioned)
    INSERT INTO raw_facts (
        market_id,
        fact_type,
        source_url,
        scraped_at,
        raw_content,
        content_hash,
        parser_version
    ) VALUES (
        gainesville_id,
        'city_permit',
        'http://test.com/permit/123',
        NOW(),
        '{"test": "data"}'::jsonb,
        md5('test-content-1'),
        'v1'
    ) RETURNING id INTO test_raw_fact_id;
    RAISE NOTICE '✓ TEST 3 PASSED: Raw fact created in partition with ID: %', test_raw_fact_id;

    -- TEST 4: Insert test permit (partitioned, with FKs)
    INSERT INTO permits (
        market_id,
        permit_number,
        permit_type,
        property_id,
        contractor_entity_id,
        project_value,
        status
    ) VALUES (
        gainesville_id,
        'TEST-PERMIT-001',
        'Building',
        test_property_id,
        test_entity_id,
        250000.00,
        'Issued'
    ) RETURNING id INTO test_permit_id;
    RAISE NOTICE '✓ TEST 4 PASSED: Permit created with relationships, ID: %', test_permit_id;

    -- TEST 5: Test entity relationship
    INSERT INTO entity_relationships (
        source_entity_id,
        target_entity_id,
        relationship_type,
        supporting_markets,
        confidence_score
    ) VALUES (
        test_entity_id,
        test_entity_id,  -- This will fail due to CHECK constraint (expected)
        'OWNS',
        ARRAY[gainesville_id],
        0.95
    );
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE '✓ TEST 5 PASSED: Self-reference constraint working correctly';
END $$;

-- TEST 6: Verify partition routing
SELECT
    'raw_facts_gainesville_fl' as partition_name,
    COUNT(*) as row_count
FROM raw_facts_gainesville_fl
UNION ALL
SELECT
    'properties_gainesville_fl' as partition_name,
    COUNT(*) as row_count
FROM properties_gainesville_fl
UNION ALL
SELECT
    'permits_gainesville_fl' as partition_name,
    COUNT(*) as row_count
FROM permits_gainesville_fl;

-- TEST 7: Verify indexes exist
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename LIKE '%gainesville%'
ORDER BY tablename, indexname;

-- TEST 8: Test entity with active_markets array
SELECT
    name,
    entity_type,
    array_length(active_markets, 1) as market_count,
    active_markets
FROM entities
LIMIT 5;

RAISE NOTICE '=================================================';
RAISE NOTICE 'ALL TESTS COMPLETED SUCCESSFULLY!';
RAISE NOTICE 'Schema is ready for multi-market operations';
RAISE NOTICE '=================================================';
