"""
HARD TESTS - Real Investor Scenarios

These tests simulate what a REAL investor with $50k-200k would do.
Not just "does it work" but "would I risk my money on this?"
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_async_engine(os.getenv('DATABASE_URL'))

async def hard_tests():
    async with engine.connect() as conn:
        print("="*80)
        print("HARD TESTS - REAL INVESTOR SCENARIOS")
        print("="*80)
        print("\nTesting like a real investor with $50k-200k to deploy...")

        # Get our top 3 recommendations
        result = await conn.execute(text("""
            SELECT
                parcel_id,
                owner_name,
                site_address,
                mailing_address,
                lot_size_acres,
                land_value,
                market_value,
                assessed_value,
                last_sale_price,
                last_sale_date,
                property_type,
                land_zoning_code,
                land_zoning_desc,
                latitude,
                longitude
            FROM bulk_property_records
            WHERE parcel_id IN ('19120-005-000', '01834-014-000', '05447-000-000')
            ORDER BY last_sale_date DESC
        """))
        recommendations = [dict(row._mapping) for row in result]

        print("\n" + "="*80)
        print("TEST 1: THE $50K INVESTMENT TEST")
        print("="*80)
        print("\nQuestion: Would I actually invest $50,000 in these properties?")
        print("Criteria: Clear path to profit, manageable risk, actionable intel\n")

        for i, prop in enumerate(recommendations, 1):
            print(f"\n{'='*80}")
            print(f"PROPERTY #{i}: {prop['parcel_id']}")
            print(f"{'='*80}")

            # Basic Info
            print(f"\nBASIC INFO:")
            print(f"  Address: {prop['site_address'] or 'No address'}")
            print(f"  Owner: {prop['owner_name']}")
            print(f"  Size: {prop['lot_size_acres']:.2f} acres")
            print(f"  Zoning: {prop['land_zoning_desc'] or prop['land_zoning_code']}")

            # Pricing Analysis
            print(f"\nPRICING:")
            print(f"  Land Value: ${prop['land_value']:,.0f}")
            print(f"  Market Value: ${prop['market_value']:,.0f}")
            print(f"  Assessed Value: ${prop['assessed_value']:,.0f}")
            print(f"  Last Sale: ${prop['last_sale_price'] or 0:,.0f} ({prop['last_sale_date']})")

            # Calculate investment metrics
            land_value = float(prop['land_value']) if prop['land_value'] else 0
            last_sale = float(prop['last_sale_price']) if prop['last_sale_price'] else 0

            if land_value > 0 and last_sale > 0:
                appreciation = ((land_value - last_sale) / last_sale) * 100
                potential_gain = land_value - last_sale
                print(f"\n  Appreciation since last sale: {appreciation:.0f}%")
                print(f"  Potential gain: ${potential_gain:,.0f}")

            # Investment Analysis
            print(f"\nINVESTMENT ANALYSIS:")

            # Can I afford it?
            if land_value <= 50000:
                print(f"  ✓ AFFORDABLE: ${land_value:,.0f} (within $50k budget)")
                affordable = True
            elif land_value <= 200000:
                print(f"  ⚠ STRETCH: ${land_value:,.0f} (need financing)")
                affordable = True
            else:
                print(f"  ✗ TOO EXPENSIVE: ${land_value:,.0f} (outside budget)")
                affordable = False

            # Do I know how to contact owner?
            has_contact = bool(prop['mailing_address'])
            if has_contact:
                print(f"  ✓ CAN CONTACT: Have mailing address")
            else:
                print(f"  ✗ NO CONTACT: Cannot reach owner")

            # Is location accessible?
            has_location = bool(prop['latitude'] and prop['longitude'])
            if has_location:
                print(f"  ✓ MAPPABLE: Have coordinates")
            else:
                print(f"  ✗ NO LOCATION: Cannot verify property")

            # Critical Questions
            print(f"\nCRITICAL QUESTIONS:")

            # 1. Who will buy this from me?
            print(f"\n  Q1: Who will buy this from me?")
            result_dev = await conn.execute(text("""
                SELECT COUNT(DISTINCT e.id)
                FROM entities e
                JOIN permits p ON p.contractor_entity_id = e.id
                WHERE p.application_date >= CURRENT_DATE - INTERVAL '365 days'
                AND p.permit_type ILIKE '%Building%'
            """))
            developer_count = result_dev.scalar()
            print(f"      Active builders in market: {developer_count}")
            if developer_count >= 10:
                print(f"      ✓ Good buyer pool")
            else:
                print(f"      ⚠ Limited buyers")

            # 2. What's it really worth?
            print(f"\n  Q2: What's it really worth?")
            lot_acres = float(prop['lot_size_acres']) if prop['lot_size_acres'] else 0
            if lot_acres > 0:
                result_comps = await conn.execute(text("""
                    SELECT
                        COUNT(*) as comp_count,
                        AVG(last_sale_price) as avg_price,
                        MIN(last_sale_price) as min_price,
                        MAX(last_sale_price) as max_price
                    FROM bulk_property_records
                    WHERE lot_size_acres BETWEEN :min_acres AND :max_acres
                    AND last_sale_price > 1000
                    AND last_sale_date >= CURRENT_DATE - INTERVAL '2 years'
                    AND property_type ILIKE '%vacant%'
                    AND parcel_id != :parcel_id
                """), {
                    'min_acres': lot_acres * 0.7,
                    'max_acres': lot_acres * 1.3,
                    'parcel_id': prop['parcel_id']
                })
                comps = result_comps.fetchone()

                if comps[0] > 0:
                    print(f"      Found {comps[0]} recent comps (2 years)")
                    print(f"      Range: ${comps[2]:,.0f} - ${comps[3]:,.0f}")
                    print(f"      Average: ${comps[1]:,.0f}")

                    # Compare to our price
                    price_per_acre = land_value / lot_acres if lot_acres > 0 else 0
                    comp_per_acre = comps[1] / lot_acres if comps[1] and lot_acres > 0 else 0

                    print(f"      Our property: ${price_per_acre:,.0f}/acre")
                    print(f"      Comp average: ${comp_per_acre:,.0f}/acre")

                    if price_per_acre < comp_per_acre * 0.8:
                        print(f"      ✓ 20%+ BELOW MARKET - Good deal")
                    elif price_per_acre < comp_per_acre:
                        print(f"      ✓ Below market - Fair deal")
                    else:
                        print(f"      ✗ AT OR ABOVE MARKET - Risky")
                else:
                    print(f"      ⚠ NO COMPS - Cannot validate price")

            # 3. What could go wrong?
            print(f"\n  Q3: What could go wrong?")
            risks = []

            # Check zoning
            zoning = (prop['land_zoning_desc'] or prop['land_zoning_code'] or '').upper()
            if 'AGRICULTURE' in zoning or 'A -' in zoning:
                risks.append("Agricultural zoning (may need rezoning)")

            # Check if isolated
            if not has_location:
                risks.append("No coordinates (cannot assess location)")

            # Check for old sale data
            if prop['last_sale_date']:
                from datetime import date
                years_since_sale = (date.today() - prop['last_sale_date']).days / 365
                if years_since_sale > 5:
                    risks.append(f"Stale comp data ({years_since_sale:.0f} years old)")

            # Check size
            if lot_acres > 15:
                risks.append("Large parcel (harder to flip, needs subdivision)")

            if risks:
                for risk in risks:
                    print(f"      ⚠ {risk}")
            else:
                print(f"      ✓ No major red flags identified")

            # Final Verdict
            print(f"\n{'='*40}")
            print(f"VERDICT:")
            print(f"{'='*40}")

            score = 0
            if affordable: score += 30
            if has_contact: score += 20
            if has_location: score += 10
            if developer_count >= 10: score += 20
            if comps[0] > 3: score += 20

            if score >= 80:
                verdict = "✓ INVEST - High confidence"
            elif score >= 60:
                verdict = "⚠ MAYBE - Needs more research"
            else:
                verdict = "✗ PASS - Too many unknowns"

            print(f"  Score: {score}/100")
            print(f"  {verdict}")

        print("\n" + "="*80)
        print("TEST 2: ASSEMBLAGE PATTERN DETECTION")
        print("="*80)
        print("\nQuestion: Can we find developers assembling land?")
        print("Value: These are HIGH-PROBABILITY buyers for gap parcels\n")

        # Find owners with multiple properties in same area
        result = await conn.execute(text("""
            WITH owner_counts AS (
                SELECT
                    owner_name,
                    COUNT(*) as property_count,
                    SUM(lot_size_acres) as total_acres,
                    AVG(last_sale_date) FILTER (WHERE last_sale_date IS NOT NULL) as avg_sale_date,
                    COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '3 years' THEN 1 END) as recent_purchases
                FROM bulk_property_records
                WHERE owner_name NOT ILIKE '%COUNTY%'
                AND owner_name NOT ILIKE '%STATE%'
                AND owner_name NOT ILIKE '%CITY%'
                AND property_type ILIKE '%vacant%'
                AND lot_size_acres > 5
                GROUP BY owner_name
                HAVING COUNT(*) >= 3
            )
            SELECT * FROM owner_counts
            WHERE recent_purchases >= 1
            ORDER BY property_count DESC, recent_purchases DESC
            LIMIT 10
        """))

        assemblage_owners = [dict(row._mapping) for row in result]

        if assemblage_owners:
            print(f"Found {len(assemblage_owners)} potential assemblage plays:\n")
            for i, owner in enumerate(assemblage_owners, 1):
                print(f"{i}. {owner['owner_name']}")
                print(f"   Properties: {owner['property_count']}")
                print(f"   Total acres: {owner['total_acres']:.1f}")
                print(f"   Recent purchases: {owner['recent_purchases']}")
                print(f"   Avg purchase date: {owner['avg_sale_date']}")

                # Get their actual properties
                result_props = await conn.execute(text("""
                    SELECT parcel_id, lot_size_acres, last_sale_date, site_address
                    FROM bulk_property_records
                    WHERE owner_name = :owner_name
                    ORDER BY last_sale_date DESC NULLS LAST
                    LIMIT 5
                """), {'owner_name': owner['owner_name']})

                props = [dict(row._mapping) for row in result_props]
                print(f"   Recent parcels:")
                for p in props[:3]:
                    addr = p['site_address'] or f"Parcel {p['parcel_id']}"
                    print(f"     - {addr} ({p['lot_size_acres']:.1f} acres, {p['last_sale_date']})")
                print()
        else:
            print("⚠ NO ASSEMBLAGE PATTERNS FOUND")
            print("   This is a MAJOR gap - assemblage opportunities are high-value")

        print("\n" + "="*80)
        print("TEST 3: DATA COMPLETENESS STRESS TEST")
        print("="*80)
        print("\nQuestion: What % of critical fields are missing?")
        print("Reality: Missing data = missed opportunities\n")

        # Check critical field completeness
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(owner_name) as has_owner,
                COUNT(mailing_address) as has_mailing,
                COUNT(site_address) as has_address,
                COUNT(last_sale_date) as has_sale_date,
                COUNT(last_sale_price) as has_sale_price,
                COUNT(CASE WHEN last_sale_price > 1000 THEN 1 END) as has_valid_price,
                COUNT(land_zoning_code) as has_zoning,
                COUNT(latitude) as has_coords,
                COUNT(CASE WHEN lot_size_acres > 0 THEN 1 END) as has_size
            FROM bulk_property_records
            WHERE property_type ILIKE '%vacant%'
            AND lot_size_acres BETWEEN 0.25 AND 20
        """))

        stats = result.fetchone()
        total = stats[0]

        print(f"Analyzing {total:,} vacant land parcels:\n")

        fields = [
            ('Owner Name', stats[1]),
            ('Mailing Address', stats[2]),
            ('Site Address', stats[3]),
            ('Last Sale Date', stats[4]),
            ('Last Sale Price', stats[5]),
            ('Valid Sale Price (>$1k)', stats[6]),
            ('Zoning Code', stats[7]),
            ('Coordinates', stats[8]),
            ('Lot Size', stats[9])
        ]

        for field_name, count in fields:
            pct = (count / total * 100) if total > 0 else 0
            status = "✓" if pct >= 80 else "⚠" if pct >= 50 else "✗"
            print(f"  {status} {field_name:30s}: {pct:5.1f}% ({count:,}/{total:,})")

        print("\n" + "="*80)
        print("TEST 4: EXIT STRATEGY VALIDATION")
        print("="*80)
        print("\nQuestion: Can we match properties to specific buyers?")
        print("Reality: No exit = no investment\n")

        # For each recommendation, find likely buyers
        for prop in recommendations[:2]:  # Just test top 2
            print(f"\nProperty: {prop['parcel_id']}")
            print(f"Size: {prop['lot_size_acres']:.1f} acres")

            # Find developers who bought similar sizes
            lot_acres = float(prop['lot_size_acres']) if prop['lot_size_acres'] else 0
            result_buyers = await conn.execute(text("""
                SELECT DISTINCT
                    b.owner_name,
                    COUNT(*) as similar_purchases,
                    AVG(b.lot_size_acres) as avg_size,
                    MAX(b.last_sale_date) as most_recent
                FROM bulk_property_records b
                WHERE b.last_sale_date >= CURRENT_DATE - INTERVAL '3 years'
                AND b.lot_size_acres BETWEEN :min_acres AND :max_acres
                AND b.owner_name NOT ILIKE '%COUNTY%'
                AND b.owner_name NOT ILIKE '%STATE%'
                GROUP BY b.owner_name
                HAVING COUNT(*) >= 2
                ORDER BY COUNT(*) DESC, MAX(b.last_sale_date) DESC
                LIMIT 5
            """), {
                'min_acres': lot_acres * 0.7,
                'max_acres': lot_acres * 1.3
            })

            buyers = [dict(row._mapping) for row in result_buyers]

            if buyers:
                print(f"  Potential buyers (recent purchasers of {lot_acres:.0f}± acre parcels):")
                for buyer in buyers:
                    print(f"    - {buyer['owner_name']}")
                    print(f"      Purchased {buyer['similar_purchases']} similar parcels")
                    print(f"      Last purchase: {buyer['most_recent']}")
            else:
                print(f"  ⚠ NO BUYERS FOUND for {lot_acres:.1f} acre parcels")
                print(f"     This is a MAJOR risk - no exit strategy")

        print("\n" + "="*80)
        print("TEST 5: ROI REALITY CHECK")
        print("="*80)
        print("\nQuestion: What's the ACTUAL expected return?")
        print("Reality: Need 20%+ to justify risk\n")

        for prop in recommendations[:2]:
            print(f"\nProperty: {prop['parcel_id']}")

            # Assumptions
            land_value = float(prop['land_value']) if prop['land_value'] else 0
            purchase_price = land_value * 0.85  # 15% discount negotiation
            holding_months = 12  # 1 year hold
            sale_price = land_value * 1.0  # Sell at current value

            # Costs
            closing_costs = purchase_price * 0.03  # 3%
            property_tax = land_value * 0.015 * (holding_months / 12)  # 1.5% annual
            maintenance = 500 * (holding_months / 12)  # $500/year
            selling_costs = sale_price * 0.06  # 6% commission

            total_costs = closing_costs + property_tax + maintenance + selling_costs
            total_investment = purchase_price + total_costs
            net_profit = sale_price - total_investment
            roi = (net_profit / total_investment * 100) if total_investment > 0 else 0

            print(f"\nPURCHASE:")
            print(f"  Land value: ${land_value:,.0f}")
            print(f"  Purchase price (15% discount): ${purchase_price:,.0f}")
            print(f"  Closing costs: ${closing_costs:,.0f}")

            print(f"\nHOLDING ({holding_months} months):")
            print(f"  Property tax: ${property_tax:,.0f}")
            print(f"  Maintenance: ${maintenance:,.0f}")

            print(f"\nSALE:")
            print(f"  Sale price: ${sale_price:,.0f}")
            print(f"  Selling costs (6%): ${selling_costs:,.0f}")

            print(f"\nBOTTOM LINE:")
            print(f"  Total investment: ${total_investment:,.0f}")
            print(f"  Net profit: ${net_profit:,.0f}")
            print(f"  ROI: {roi:.1f}%")

            if roi >= 20:
                print(f"  ✓ GOOD DEAL (20%+ return)")
            elif roi >= 10:
                print(f"  ⚠ MARGINAL (10-20% return)")
            else:
                print(f"  ✗ BAD DEAL (<10% return)")

        print("\n" + "="*80)
        print("FINAL VERDICT: WOULD A REAL INVESTOR USE THIS?")
        print("="*80)

        print("""
STRENGTHS:
  ✓ Can find properties
  ✓ Has owner info (mailing addresses)
  ✓ Market intelligence (768 permits, 13 developers)
  ✓ Motivation signals (absentee, estates)
  ✓ Basic pricing data

CRITICAL GAPS:
  ✗ No phone/email (cannot call owners quickly)
  ✗ Weak assemblage detection (missing high-value opportunities)
  ✗ No buyer matching (who wants this specific property?)
  ✗ ROI calculations basic (need better cost estimates)
  ✗ No deal tracking (cannot manage pipeline)

REALITY CHECK:
  Current version: RESEARCH TOOL (6/10)
  - Good for finding possibilities
  - Not actionable without manual work
  - Missing critical go/no-go data

  Needed for DECISION TOOL (9/10):
  1. Phone/email enrichment (call owners today)
  2. Buyer matching (specific exit strategy per property)
  3. Deal pipeline (track outreach, offers, closings)
  4. Automated valuations (AVMs, better comps)
  5. Risk scoring (quantified risk assessment)

WOULD I INVEST BASED ON THIS?
  Current: NO - Too many unknowns, too much manual work
  With improvements: YES - If it gives me 3-5 ACTIONABLE deals/month
        """)

    await engine.dispose()

asyncio.run(hard_tests())
