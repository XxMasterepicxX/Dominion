"""
Analyze agent simulation issues to identify problems
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_async_engine(os.getenv('DATABASE_URL'))

async def analyze():
    async with engine.connect() as conn:
        print("="*80)
        print("AGENT SIMULATION QUALITY ANALYSIS")
        print("="*80)

        # ISSUE 1: Developer Detection
        print("\n" + "="*80)
        print("ISSUE 1: Why 0 Developers Found?")
        print("="*80)

        result = await conn.execute(text('''
            SELECT
                COUNT(DISTINCT contractor_entity_id) as unique_contractors,
                COUNT(*) as total_permits
            FROM permits
            WHERE application_date >= CURRENT_DATE - INTERVAL '90 days'
              AND contractor_entity_id IS NOT NULL
        '''))
        row = result.fetchone()
        print(f'\n> Permits with contractors: {row[1]}')
        print(f'> Unique contractor entities: {row[0]}')
        print('\nCONCLUSION: We HAVE contractors in DB, but simulation found 0.')
        print('PROBLEM: Developer detection query in simulation is broken.')

        # Sample top contractors
        result = await conn.execute(text('''
            SELECT e.name, e.entity_type, COUNT(p.id) as permit_count,
                   SUM(p.project_value) as total_value
            FROM entities e
            JOIN permits p ON p.contractor_entity_id = e.id
            WHERE p.application_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY e.id, e.name, e.entity_type
            ORDER BY permit_count DESC
            LIMIT 10
        '''))
        print('\nTop 10 contractors (these SHOULD be detected as developers):')
        for row in result:
            print(f'  {row[0][:50]:50s} | {row[2]:2d} permits | ${row[3] or 0:>12,.0f}')

        # ISSUE 2: Property Recommendations Quality
        print("\n" + "="*80)
        print("ISSUE 2: Are Property Recommendations Realistic?")
        print("="*80)

        result = await conn.execute(text('''
            SELECT
                parcel_id,
                owner_name,
                property_type,
                land_value,
                lot_size_acres,
                last_sale_price,
                last_sale_date
            FROM bulk_property_records
            WHERE parcel_id IN ('16319-001-000', '05949-009-000', '16317-000-000')
            ORDER BY lot_size_acres DESC
        '''))

        print('\nTop 3 recommended properties:')
        for row in result:
            print(f'\n  Parcel: {row[0]}')
            print(f'  Owner: {row[1][:60]}')
            print(f'  Type: {row[2]}')
            print(f'  Land Value: ${row[3]:,.0f}')
            print(f'  Size: {row[4]:,.1f} acres')
            print(f'  Last Sale: ${row[5] or 0:,.0f} on {row[6]}')

            # Identify problems
            problems = []
            if 'COUNTY' in (row[1] or '') or 'STATE' in (row[1] or '') or 'DISTRICT' in (row[1] or ''):
                problems.append('[!] GOVERNMENT/PUBLIC LAND - Not for sale!')
            if row[4] and row[4] > 500:
                problems.append('[!] HUGE SIZE - Unrealistic for typical investor')
            if 'VACANT/XFEATURES' in (row[2] or '') or 'TMBR' in (row[2] or ''):
                problems.append('[!] CONSERVATION/TIMBER - Not development land')
            if row[5] and row[5] < 1000:
                problems.append('[!] SUSPICIOUS SALE PRICE - Non-arms-length transaction')

            if problems:
                print('  ISSUES:')
                for p in problems:
                    print(f'    {p}')

        print('\nCONCLUSION: Recommendations are UNREALISTIC.')
        print('PROBLEM: No filters for government ownership, size, or land type.')

        # ISSUE 3: What should we recommend instead?
        print("\n" + "="*80)
        print("ISSUE 3: What Properties SHOULD We Recommend?")
        print("="*80)

        result = await conn.execute(text('''
            SELECT
                parcel_id,
                owner_name,
                property_type,
                land_value,
                lot_size_acres,
                last_sale_price,
                last_sale_date
            FROM bulk_property_records
            WHERE property_type ILIKE '%VACANT%'
              AND owner_name NOT ILIKE '%COUNTY%'
              AND owner_name NOT ILIKE '%STATE%'
              AND owner_name NOT ILIKE '%DISTRICT%'
              AND owner_name NOT ILIKE '%TRUST%'
              AND owner_name NOT ILIKE '%CHURCH%'
              AND lot_size_acres > 0.25
              AND lot_size_acres < 10
              AND land_value > 10000
              AND land_value < 500000
              AND last_sale_date IS NOT NULL
            ORDER BY land_value / lot_size_acres  -- Value per acre (cheapest first)
            LIMIT 10
        '''))

        print('\nBetter vacant land opportunities (filtered):')
        count = 0
        for row in result:
            count += 1
            value_per_acre = row[3] / row[4] if row[4] else 0
            print(f'\n  #{count} | Parcel: {row[0]}')
            print(f'      Owner: {row[1][:50]}')
            print(f'      Size: {row[4]:,.2f} acres | Value: ${row[3]:,.0f} (${value_per_acre:,.0f}/acre)')
            print(f'      Last Sale: ${row[5] or 0:,.0f} on {row[6]}')

        if count == 0:
            print('  NO RESULTS - Need better filtering criteria')
        else:
            print(f'\nCONCLUSION: Found {count} more realistic opportunities.')

        # ISSUE 4: Scoring logic
        print("\n" + "="*80)
        print("ISSUE 4: Is Scoring Logic Reasonable?")
        print("="*80)

        print('\nCurrent scoring issues:')
        print('  [!] +20 for "Large lot" - but 1249 acres is TOO large')
        print('  [!] +15 for "Strong appreciation" - but based on $100 sale (bad data)')
        print('  [!] No penalty for government ownership')
        print('  [!] No penalty for unrealistic size')
        print('  [!] No bonus for nearby development activity')
        print('  [!] No consideration of zoning appropriateness')

        # Check if we have address data for geo linking
        result = await conn.execute(text('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN property_address IS NOT NULL THEN 1 END) as with_address
            FROM permits
        '''))
        row = result.fetchone()
        print(f'\n  Total permits: {row[0]}')
        print(f'  Permits with property_address: {row[1]}')
        if row[1] == 0:
            print('  [!] No property addresses - cannot find "nearby development"')

        # Summary
        print("\n" + "="*80)
        print("SUMMARY: CRITICAL ISSUES TO FIX")
        print("="*80)
        print('''
1. [CRITICAL] DEVELOPER DETECTION: Simulation says "0 developers" but we have 737
   - FIX: Check simulation's developer query logic

2. [CRITICAL] PROPERTY FILTERS: Recommending government conservation land
   - FIX: Add filters for owner type, size range, land use

3. [CRITICAL] SCORING LOGIC: Rewards bad data (huge parcels, $100 sales)
   - FIX: Cap bonuses, penalize outliers, validate sale prices

4. [WARNING] NO NEARBY ACTIVITY: Cannot find development near parcels
   - FIX: Link permits to nearby properties (geo search)

5. [WARNING] NO ZONING CHECK: Recommending agricultural land for development
   - FIX: Score based on zoning suitability
        ''')

    await engine.dispose()

asyncio.run(analyze())
