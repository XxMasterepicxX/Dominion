"""
Test if Dominion provides ACTUAL value to real investors

Questions to answer:
1. Do we know if properties are for sale?
2. Can we contact owners?
3. Can we identify motivated sellers?
4. Do we have pricing intelligence?
5. Can we find assemblage opportunities?
6. Would someone PAY for this?
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_async_engine(os.getenv('DATABASE_URL'))

async def test_investor_value():
    async with engine.connect() as conn:
        print("="*80)
        print("REAL INVESTOR VALUE TEST")
        print("="*80)
        print("\nTesting our recommendations against what investors actually need...")

        # Get our recommended properties
        result = await conn.execute(text("""
            SELECT
                parcel_id,
                owner_name,
                site_address,
                lot_size_acres,
                land_value,
                last_sale_price,
                last_sale_date,
                property_type,
                land_zoning_code,
                land_zoning_desc,
                trim_notice,
                latitude,
                longitude
            FROM bulk_property_records
            WHERE parcel_id IN ('05303-002-000', '05447-002-000', '05447-000-000')
        """))

        recommendations = [dict(row._mapping) for row in result]

        print("\n" + "="*80)
        print("TEST 1: Can we tell if properties are FOR SALE?")
        print("="*80)

        for prop in recommendations:
            print(f"\nParcel: {prop['parcel_id']}")
            print(f"Owner: {prop['owner_name']}")

            # Check for MLS data
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'bulk_property_records'
                AND (column_name ILIKE '%mls%'
                     OR column_name ILIKE '%sale%'
                     OR column_name ILIKE '%listing%'
                     OR column_name ILIKE '%market%')
            """))
            mls_fields = [row[0] for row in result]

            print(f"  MLS/Listing fields in database: {mls_fields if mls_fields else 'NONE'}")
            print(f"  Last sale: {prop['last_sale_date']} for ${prop['last_sale_price'] or 0:,.0f}")
            print(f"  Conclusion: {'NO - We cannot tell if for sale' if not mls_fields else 'Maybe'}")

        print("\n" + "="*80)
        print("TEST 2: Can we CONTACT the owners?")
        print("="*80)

        for prop in recommendations:
            print(f"\nParcel: {prop['parcel_id']}")
            print(f"Owner: {prop['owner_name']}")

            # Check for contact info in property table
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'bulk_property_records'
                AND (column_name ILIKE '%phone%'
                     OR column_name ILIKE '%email%'
                     OR column_name ILIKE '%contact%'
                     OR column_name ILIKE '%mailing%')
            """))
            contact_fields = [row[0] for row in result]

            print(f"  Contact fields available: {contact_fields}")

            # Check mailing address
            result = await conn.execute(text("""
                SELECT mailing_address FROM bulk_property_records
                WHERE parcel_id = :parcel_id
            """), {'parcel_id': prop['parcel_id']})
            mailing = result.scalar()

            print(f"  Mailing address: {mailing or 'NONE'}")
            print(f"  Conclusion: {'NO - No phone/email data' if not mailing else 'Maybe - have mailing address only'}")

        print("\n" + "="*80)
        print("TEST 3: Can we identify MOTIVATED SELLERS?")
        print("="*80)

        print("\nMotivation Signal #1: Tax Delinquency / Liens")
        for prop in recommendations:
            print(f"\nParcel: {prop['parcel_id']}")
            trim = prop.get('trim_notice') or {}
            delinquent = trim.get('delinquent', {}) if isinstance(trim, dict) else {}

            if delinquent.get('is_delinquent'):
                print(f"  TAX DELINQUENT: ${delinquent.get('amount_owed', 0):,.0f}")
                print(f"  Lien filed: {delinquent.get('lien_filed', False)}")
                print(f"  Certificate sold: {delinquent.get('certificate_sold', False)}")
                print(f"  Motivation: HIGH (needs money)")
            else:
                print(f"  Tax status: Current (no distress)")
                print(f"  Motivation: Unknown")

        print("\nMotivation Signal #2: Estate Sales / Death")
        for prop in recommendations:
            owner = prop['owner_name'] or ''
            if 'ESTATE' in owner.upper() or 'HEIR' in owner.upper():
                print(f"\nParcel: {prop['parcel_id']}")
                print(f"  ESTATE OWNERSHIP detected: {owner}")
                print(f"  Motivation: HIGH (heirs want to liquidate)")

        print("\nMotivation Signal #3: Long Holding Period (Land Banking)")
        for prop in recommendations:
            print(f"\nParcel: {prop['parcel_id']}")
            last_sale = prop['last_sale_date']
            if last_sale:
                from datetime import date
                years_held = (date.today() - last_sale).days / 365
                print(f"  Held for: {years_held:.1f} years")
                if years_held > 10:
                    print(f"  Motivation: MODERATE (may be ready to sell after long hold)")
                else:
                    print(f"  Motivation: LOW (recent purchase)")
            else:
                print(f"  Last sale: Unknown")

        print("\nMotivation Signal #4: Divorce / Ownership Changes")
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'bulk_property_records'
            AND column_name ILIKE '%divorce%'
        """))
        has_divorce = result.scalar() > 0
        print(f"  Divorce data available: {has_divorce}")
        print(f"  Conclusion: {'NO - No divorce/life event data' if not has_divorce else 'YES'}")

        print("\n" + "="*80)
        print("TEST 4: Do we have PRICING INTELLIGENCE?")
        print("="*80)

        # Check for recent comparable sales
        test_parcel = recommendations[0]
        print(f"\nFor parcel {test_parcel['parcel_id']} ({test_parcel['lot_size_acres']:.1f} acres):")

        lot_acres = float(test_parcel['lot_size_acres']) if test_parcel['lot_size_acres'] else 0
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as comp_count,
                AVG(last_sale_price) as avg_price,
                MIN(last_sale_date) as oldest_sale,
                MAX(last_sale_date) as newest_sale
            FROM bulk_property_records
            WHERE lot_size_acres BETWEEN :min_acres AND :max_acres
            AND last_sale_price > 1000
            AND last_sale_date >= CURRENT_DATE - INTERVAL '3 years'
            AND property_type ILIKE '%vacant%'
        """), {
            'min_acres': lot_acres * 0.8,
            'max_acres': lot_acres * 1.2
        })
        comps = result.fetchone()

        print(f"  Recent comps (3 years): {comps[0]} sales")
        if comps[0] > 0:
            print(f"  Average sale price: ${comps[1]:,.0f}")
            print(f"  Date range: {comps[2]} to {comps[3]}")
            print(f"  Our estimate: ${test_parcel['land_value']:,.0f}")
            print(f"  Confidence: {'HIGH' if comps[0] >= 5 else 'MEDIUM' if comps[0] >= 2 else 'LOW'}")
        else:
            print(f"  NO RECENT COMPS - Cannot validate pricing")
            print(f"  Confidence: VERY LOW")

        print("\n" + "="*80)
        print("TEST 5: Can we identify ASSEMBLAGE OPPORTUNITIES?")
        print("="*80)

        print("\nChecking if developers are assembling near our recommendations...")

        # Check for developer activity nearby
        for prop in recommendations:
            if not prop['latitude'] or not prop['longitude']:
                print(f"\nParcel {prop['parcel_id']}: NO COORDINATES - cannot check nearby activity")
                continue

            print(f"\nParcel {prop['parcel_id']} ({prop['owner_name']}):")

            # Find properties within ~1 mile
            result = await conn.execute(text("""
                SELECT
                    parcel_id,
                    owner_name,
                    lot_size_acres,
                    last_sale_date,
                    ST_Distance(
                        ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
                    ) as distance_meters
                FROM bulk_property_records
                WHERE latitude IS NOT NULL
                AND longitude IS NOT NULL
                AND parcel_id != :parcel_id
                AND ST_DWithin(
                    ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                    1609  -- 1 mile in meters
                )
                ORDER BY distance_meters
                LIMIT 10
            """), {
                'lat1': float(prop['latitude']),
                'lon1': float(prop['longitude']),
                'lat2': float(prop['latitude']),
                'lon2': float(prop['longitude']),
                'parcel_id': prop['parcel_id']
            })

            nearby = [dict(row._mapping) for row in result]

            if nearby:
                print(f"  Found {len(nearby)} properties within 1 mile")

                # Check if same owner owns multiple nearby
                owner_counts = {}
                for n in nearby:
                    owner = n['owner_name']
                    owner_counts[owner] = owner_counts.get(owner, 0) + 1

                assembly_detected = [o for o, c in owner_counts.items() if c >= 2]

                if assembly_detected:
                    print(f"  ASSEMBLAGE DETECTED:")
                    for owner in assembly_detected:
                        count = owner_counts[owner]
                        parcels = [n['parcel_id'] for n in nearby if n['owner_name'] == owner]
                        print(f"    {owner}: {count} nearby parcels ({', '.join(parcels[:3])})")
                    print(f"  EXIT STRATEGY: Likely buyer for assemblage completion")
                else:
                    print(f"  No assemblage detected (no repeat owners)")
            else:
                print(f"  No nearby properties found (isolated)")

        print("\n" + "="*80)
        print("TEST 6: What about DEVELOPMENT SIGNALS?")
        print("="*80)

        print("\nChecking for nearby permits (development activity)...")

        for prop in recommendations[:1]:  # Just test one
            print(f"\nParcel {prop['parcel_id']}:")

            # Check if we can link permits to properties
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'permits'
                AND (column_name ILIKE '%parcel%'
                     OR column_name ILIKE '%property%'
                     OR column_name ILIKE '%address%'
                     OR column_name ILIKE '%lat%'
                     OR column_name ILIKE '%lon%')
            """))
            permit_location_fields = [row[0] for row in result]

            print(f"  Permit location fields: {permit_location_fields}")

            if 'parcel_id' in permit_location_fields:
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM permits
                    WHERE parcel_id = :parcel_id
                    AND application_date >= CURRENT_DATE - INTERVAL '2 years'
                """), {'parcel_id': prop['parcel_id']})
                permit_count = result.scalar()
                print(f"  Recent permits on THIS parcel: {permit_count}")
            else:
                print(f"  Cannot link permits to parcels - no parcel_id field")

            print(f"  Conclusion: {'Can track development activity' if 'parcel_id' in permit_location_fields else 'CANNOT track nearby development'}")

        print("\n" + "="*80)
        print("FINAL ASSESSMENT: Would investors PAY for this?")
        print("="*80)

        print("""
WHAT WE HAVE:
  ✓ Property characteristics (size, value, zoning)
  ✓ Owner names
  ✓ Historical sale prices
  ✓ Tax status (TRIM notices for some)
  ✓ Geographic coordinates
  ✓ Active developer list (13 contractors)
  ✓ Market activity metrics (768 permits, $68M)

WHAT WE'RE MISSING (CRITICAL):
  ✗ For-sale status (MLS data)
  ✗ Owner contact info (phone/email)
  ✗ Motivation signals (beyond tax delinquency)
  ✗ Recent market comps (pricing confidence)
  ✗ Nearby permit activity (cannot geolink)
  ✗ Infrastructure plans (water/sewer extensions)
  ✗ Zoning change opportunities
  ✗ Assemblage completion intelligence

CURRENT VALUE: 4/10
  - Can identify properties that MIGHT be opportunities
  - Cannot tell if available or how to contact owner
  - Cannot price accurately (no recent comps)
  - Cannot identify best opportunities (motivation unknown)

NEEDED TO GET TO 9/10:
  1. Add motivated seller scoring (tax + time held + estate)
  2. Enrich with owner contact info (phone/email from public records)
  3. Add market comps analysis (recent sales within 0.5 miles)
  4. Geolink permits to properties (nearby development signal)
  5. Add zoning analysis (development potential score)
  6. Identify assemblage gaps (owners buying adjacent parcels)
  7. Add infrastructure intelligence (upcoming water/sewer)
  8. Score "deal quality" (0-100 with all factors)

WOULD I PAY FOR CURRENT VERSION?
  NO - Too many unknowns. Can't contact owners, can't tell if for sale,
  can't price accurately. It's interesting but not actionable.

WOULD I PAY FOR IMPROVED VERSION?
  YES - If we add contact info, motivation scoring, and assemblage detection,
  this becomes VERY valuable. Finding off-market deals before they list
  is worth $100-500/month subscription.
        """)

    await engine.dispose()

asyncio.run(test_investor_value())
