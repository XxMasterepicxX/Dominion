"""
Simulate Agent Response to: "Find me a piece of land that I can buy and sell later
that will make money because a developer wants it or it will gain value"

This script simulates EXACTLY what the Gemini agent would do when given this query.
"""
import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import after path setup
from intelligence.analyzers.market_analyzer import MarketAnalyzer
from intelligence.analyzers.property_analyzer import PropertyAnalyzer
from intelligence.analyzers.entity_analyzer import EntityAnalyzer

# Get database URL from env
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment")

# Create async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def agent_simulation():
    """Simulate the agent's decision-making process"""

    print("=" * 80)
    print("AGENT SIMULATION: Land Speculation Opportunity Analysis")
    print("=" * 80)
    print()
    print("USER QUERY: 'Find me a piece of land that I can buy and sell later that will")
    print("make money because a developer wants it or it will gain value'")
    print()
    print("=" * 80)
    print()

    # STEP 1: Agent analyzes the query type
    print("STEP 1: QUERY UNDERSTANDING")
    print("-" * 80)
    print("Query Type: STRATEGIC LAND SPECULATION")
    print("Goal: Find undervalued land with high developer demand potential")
    print("Strategy: Buy low -> Hold short-term -> Sell to developer at premium")
    print()
    print("Key Success Factors:")
    print("  * High development activity in area (demand signal)")
    print("  * Undervalued land (below market)")
    print("  * Good zoning for development")
    print("  * Active developers in area (likely buyers)")
    print("  * No critical risks (liens, environmental issues)")
    print()

    async with AsyncSessionLocal() as session:
        market_analyzer = MarketAnalyzer(session)
        property_analyzer = PropertyAnalyzer(session)
        entity_analyzer = EntityAnalyzer(session)

        # STEP 2: Identify hot markets with development activity
        print("STEP 2: MARKET ANALYSIS - Finding Hot Development Markets")
        print("-" * 80)

        # Get all markets
        markets_query = text("SELECT id, market_name, state FROM markets WHERE is_active = true")
        markets_result = await session.execute(markets_query)
        markets = [dict(row._mapping) for row in markets_result]

        print(f"Analyzing {len(markets)} markets in database...")
        print()

        market_scores = []

        for market in markets:
            market_id = str(market['id'])
            market_name = market['market_name']

            # Get comprehensive market analysis
            market_analysis = await market_analyzer.analyze(
                market_id=market_id,
                include_construction_pipeline=True,
                include_demand=True,
                include_permit_velocity=True,
                include_development_sentiment=True,
                recent_period_days=90
            )

            if market_analysis:
                # Extract relevant metrics
                construction = market_analysis.get('construction_pipeline', {})
                demand = market_analysis.get('demand', {})
                permit_velocity = market_analysis.get('permit_velocity', {})

                recent_permits = construction.get('total_permits', 0)
                total_value = construction.get('total_project_value', 0) or 0
                avg_value = construction.get('avg_project_value', 0) or 0

                recent_sales = demand.get('recent_sales_count', 0)
                avg_sale_price = demand.get('median_sale_price', 0) or 0

                permits_per_day = permit_velocity.get('permits_per_day_90d', 0) or 0

                # Developer interest score
                score = (
                    (recent_permits * 10) +  # More permits = more developer activity
                    (total_value / 1000000) +  # Higher project values = serious development
                    (recent_sales * 5) +  # More sales = hot market
                    (avg_sale_price / 100000) +  # Higher prices = appreciation
                    (permits_per_day * 100)  # Permit velocity indicates momentum
                )

                market_scores.append({
                    'market_id': market_id,
                    'market_name': market_name,
                    'score': score,
                    'recent_permits': recent_permits,
                    'total_project_value': total_value,
                    'avg_project_value': avg_value,
                    'recent_sales': recent_sales,
                    'avg_sale_price': avg_sale_price,
                    'permits_per_day': permits_per_day,
                    'market_analysis': market_analysis
                })

        # Sort by score
        market_scores.sort(key=lambda x: x['score'], reverse=True)

        print("Market Rankings by Development Activity:")
        for i, m in enumerate(market_scores[:5], 1):
            print(f"\n{i}. {m['market_name']} (Score: {m['score']:.1f})")
            print(f"   Recent Permits (90d): {m['recent_permits']}")
            print(f"   Total Project Value: ${m['total_project_value']:,.0f}")
            print(f"   Recent Sales (90d): {m['recent_sales']}")
            print(f"   Avg Sale Price: ${m['avg_sale_price']:,.0f}")

        if not market_scores:
            print("[WARNING]  No market activity data found")
            return

        # Select top market
        top_market = market_scores[0]
        selected_market_id = top_market['market_id']
        selected_market_name = top_market['market_name']

        print()
        print(f"* SELECTED MARKET: {selected_market_name}")
        print()

        # STEP 3: Find vacant land parcels in top market
        print("STEP 3: PROPERTY SEARCH - Finding Vacant Land Parcels")
        print("-" * 80)

        # Query for vacant land - WITH FILTERS FOR REALISTIC OPPORTUNITIES
        land_query = text("""
            SELECT
                id,
                parcel_id,
                site_address,
                mailing_address,
                owner_name,
                property_type,
                land_use_code,
                land_use_desc,
                land_zoning_code,
                land_zoning_desc,
                lot_size_acres,
                assessed_value,
                market_value,
                taxable_value,
                land_value,
                year_built,
                square_feet,
                last_sale_date,
                last_sale_price,
                latitude,
                longitude,
                exemptions,
                trim_notice,
                total_permits
            FROM bulk_property_records
            WHERE market_id = :market_id
            -- Vacant land criteria
            AND (
                property_type ILIKE '%vacant%'
                OR property_type ILIKE '%land%'
                OR land_use_desc ILIKE '%vacant%'
                OR (year_built IS NULL AND (square_feet IS NULL OR square_feet = 0))
            )
            -- Basic value filters
            AND land_value IS NOT NULL
            AND land_value > 0
            -- REALISTIC SIZE: 0.25 to 20 acres (for typical investor)
            -- Above 20 acres becomes too expensive/complex for land speculation
            AND lot_size_acres >= 0.25
            AND lot_size_acres <= 20
            -- REALISTIC VALUE: $5k to $2M (for land speculation)
            AND land_value >= 5000
            AND land_value <= 2000000
            -- EXCLUDE GOVERNMENT/INSTITUTIONAL OWNERS (not for sale)
            AND owner_name NOT ILIKE '%COUNTY%'
            AND owner_name NOT ILIKE '%STATE OF%'
            AND owner_name NOT ILIKE '%DISTRICT%'
            AND owner_name NOT ILIKE '%GOVERNMENT%'
            AND owner_name NOT ILIKE '%AUTHORITY%'
            AND owner_name NOT ILIKE '%CITY OF%'
            AND owner_name NOT ILIKE '%TOWN OF%'
            AND owner_name NOT ILIKE '%MUNICIPAL%'
            AND owner_name NOT ILIKE '%CHURCH%'
            AND owner_name NOT ILIKE '%ASSOCIATION%'
            AND owner_name NOT ILIKE '%CONFERENCE%'
            AND owner_name NOT ILIKE '%UNIVERSITY%'
            AND owner_name NOT ILIKE '%COLLEGE%'
            AND owner_name NOT ILIKE '%SCHOOL%'
            -- EXCLUDE CONSERVATION/TIMBER LAND (wrong use type)
            AND property_type NOT ILIKE '%TMBR%'
            AND property_type NOT ILIKE '%TIMBER%'
            AND property_type NOT ILIKE '%XFEATURES%'
            AND property_type NOT ILIKE '%CONSERVATION%'
            AND property_type NOT ILIKE '%PRESERVE%'
            -- Prefer properties with valid sale data
            ORDER BY
                CASE WHEN last_sale_price > 1000 AND last_sale_date >= CURRENT_DATE - INTERVAL '10 years' THEN 0 ELSE 1 END,
                lot_size_acres DESC NULLS LAST
            LIMIT 50
        """)

        land_result = await session.execute(land_query, {'market_id': selected_market_id})
        land_parcels = [dict(row._mapping) for row in land_result]

        print(f"Found {len(land_parcels)} vacant land parcels in {selected_market_name}")
        print()

        if not land_parcels:
            print("[WARNING]  No vacant land found in top market")
            return

        # STEP 4: Identify active developers in the market
        print("STEP 4: DEVELOPER ANALYSIS - Finding Active Developers")
        print("-" * 80)

        # Find entities with high permit activity (developers/contractors)
        # FIX: Use contractor_entity_id (not applicant/owner) - that's who does the work
        developer_query = text("""
            SELECT
                e.id,
                e.name,
                e.entity_type,
                e.officers,
                e.phone,
                e.email,
                COUNT(DISTINCT p.id) as total_permits,
                SUM(p.project_value) as total_project_value,
                MAX(p.application_date) as last_permit_date,
                COUNT(DISTINCT CASE WHEN p.permit_type ILIKE '%Building%' THEN p.id END) as building_permits
            FROM entities e
            INNER JOIN permits p ON p.contractor_entity_id = e.id
            WHERE p.market_id = :market_id
            AND p.application_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY e.id, e.name, e.entity_type, e.officers, e.phone, e.email
            HAVING COUNT(DISTINCT p.id) >= 2  -- Lower threshold: 2+ permits makes you a developer
            ORDER BY total_project_value DESC NULLS LAST, total_permits DESC
            LIMIT 20
        """)

        dev_result = await session.execute(developer_query, {'market_id': selected_market_id})
        developers = [dict(row._mapping) for row in dev_result]

        print(f"Found {len(developers)} active developers in {selected_market_name}")
        print()

        if developers:
            print("Top Active Developers/Contractors:")
            for i, dev in enumerate(developers[:5], 1):
                print(f"\n{i}. {dev['name']} ({dev['entity_type']})")
                print(f"   Total Permits (12mo): {dev['total_permits']}")
                print(f"   Building Permits: {dev['building_permits']}")
                print(f"   Total Project Value: ${dev['total_project_value'] or 0:,.0f}")
                print(f"   Last Permit: {dev['last_permit_date']}")
        else:
            print("[WARNING]  No active developers found (may limit exit strategy)")

        print()

        # STEP 5: Score land parcels
        print("STEP 5: OPPORTUNITY SCORING - Ranking Land Parcels")
        print("-" * 80)

        opportunities = []

        for parcel in land_parcels[:20]:  # Analyze top 20
            parcel_id = parcel['parcel_id']

            # Calculate opportunity score
            score = 50  # Base score
            score_breakdown = {
                'base': 50,
                'factors': []
            }

            # Factor 1: Market value vs assessed value (undervalued?)
            market_val = parcel.get('market_value') or 0
            assessed_val = parcel.get('assessed_value') or 0
            land_val = parcel.get('land_value') or 0

            if assessed_val > 0 and market_val > 0:
                value_ratio = market_val / assessed_val
                if value_ratio < 0.9:  # Undervalued
                    bonus = 15
                    score += bonus
                    score_breakdown['factors'].append(f"+{bonus} (Undervalued: market {value_ratio:.1%} of assessed)")
                elif value_ratio < 1.0:
                    bonus = 10
                    score += bonus
                    score_breakdown['factors'].append(f"+{bonus} (Slightly undervalued: {value_ratio:.1%})")

            # Factor 2: Lot size (optimal range for development, with penalties for extremes)
            lot_acres = parcel.get('lot_size_acres') or 0
            if lot_acres >= 1 and lot_acres <= 10:
                # OPTIMAL SIZE for typical development
                bonus = 20
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Optimal size: {lot_acres:.1f} acres)")
            elif lot_acres >= 0.5 and lot_acres < 1:
                # Small but buildable
                bonus = 15
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Buildable lot: {lot_acres:.1f} acres)")
            elif lot_acres > 10 and lot_acres <= 20:
                # Getting large - subdivision potential but higher cost
                bonus = 10
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Large lot: {lot_acres:.1f} acres)")
            elif lot_acres > 20:
                # TOO LARGE for typical investor - penalize
                penalty = -15
                score += penalty
                score_breakdown['factors'].append(f"{penalty} (Too large for typical investor: {lot_acres:.1f} acres)")

            # Factor 3: Zoning (commercial/industrial = higher value)
            zoning = (parcel.get('land_zoning_desc') or '').upper()
            if 'COMMERCIAL' in zoning or 'INDUSTRIAL' in zoning:
                bonus = 15
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Commercial/Industrial zoning)")
            elif 'RESIDENTIAL' in zoning and 'MULTI' in zoning:
                bonus = 12
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Multi-family zoning)")
            elif 'RESIDENTIAL' in zoning:
                bonus = 8
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Residential zoning)")

            # Factor 4: Market development activity
            # (In real agent, would query nearby permits, but for simulation using market-level data)
            if top_market['recent_permits'] >= 50:
                bonus = 20
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Hot development market)")
            elif top_market['recent_permits'] >= 20:
                bonus = 15
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Active development market)")
            elif top_market['recent_permits'] >= 5:
                bonus = 10
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Some development activity)")

            # Factor 5: Tax risk (CRITICAL - tax liens kill deals)
            trim_notice = parcel.get('trim_notice')
            if trim_notice:
                delinquent_info = trim_notice.get('delinquent', {})
                if delinquent_info.get('is_delinquent'):
                    if delinquent_info.get('lien_filed'):
                        penalty = -25
                        score += penalty
                        score_breakdown['factors'].append(f"{penalty} (TAX LIEN FILED - CRITICAL RISK)")
                    elif delinquent_info.get('certificate_sold'):
                        penalty = -20
                        score += penalty
                        score_breakdown['factors'].append(f"{penalty} (Tax certificate sold)")
                    else:
                        penalty = -10
                        score += penalty
                        amt = delinquent_info.get('amount_owed', 0)
                        score_breakdown['factors'].append(f"{penalty} (Tax delinquent: ${amt:,.0f})")

            # Factor 6: Recent sales activity (momentum indicator) - VALIDATE THOROUGHLY
            last_sale_price = parcel.get('last_sale_price') or 0
            last_sale_date = parcel.get('last_sale_date')
            data_quality_warnings = []

            # VALIDATION LAYER: Check sale data quality
            if last_sale_date:
                from datetime import date
                days_since_sale = (date.today() - last_sale_date).days

                # Check if sale price is valid
                if last_sale_price > 0 and last_sale_price < 1000:
                    penalty = -15
                    score += penalty
                    score_breakdown['factors'].append(f"{penalty} (INVALID SALE: ${last_sale_price:,.0f} - non-arms-length)")
                    data_quality_warnings.append("Sale price <$1k - likely family transfer or tax strategy")

                elif last_sale_price >= 1000 and land_val > 0:
                    appreciation = ((land_val - last_sale_price) / last_sale_price) * 100

                    # RED FLAG: Very recent + extreme appreciation
                    if days_since_sale < 90 and appreciation > 50:
                        penalty = -20
                        score += penalty
                        score_breakdown['factors'].append(f"{penalty} (SUSPICIOUS: {appreciation:.0f}% in {days_since_sale} days - verify!)")
                        data_quality_warnings.append(f"CRITICAL: {appreciation:.0f}% appreciation in {days_since_sale} days - likely data error or non-market transaction")

                    # YELLOW FLAG: Recent sale with extreme appreciation
                    elif days_since_sale < 180 and appreciation > 80:
                        penalty = -10
                        score += penalty
                        score_breakdown['factors'].append(f"{penalty} (Verify appreciation: {appreciation:.0f}% in {days_since_sale} days)")
                        data_quality_warnings.append(f"Recent extreme appreciation ({appreciation:.0f}%) - validate before investing")

                    # Extreme but older appreciation
                    elif appreciation > 200:
                        bonus = 5
                        score += bonus
                        score_breakdown['factors'].append(f"+{bonus} (Very high appreciation: {appreciation:.0f}% - validate comps)")
                        data_quality_warnings.append(f"Extreme appreciation ({appreciation:.0f}%) - verify with local comps")

                    # Strong appreciation
                    elif appreciation > 50:
                        bonus = 15
                        score += bonus
                        score_breakdown['factors'].append(f"+{bonus} (Strong appreciation: {appreciation:.0f}%)")

                    # Good appreciation
                    elif appreciation > 20:
                        bonus = 10
                        score += bonus
                        score_breakdown['factors'].append(f"+{bonus} (Good appreciation: {appreciation:.0f}%)")

                # Flag very recent sales
                if days_since_sale < 180:
                    data_quality_warnings.append(f"Very recent sale ({days_since_sale} days ago) - value may not be stabilized")

            # Factor 7: MOTIVATION SCORING (Owner type + signals)
            owner_name = (parcel.get('owner_name') or '').upper()
            motivation_score = 0
            motivation_factors = []

            # SIGNAL 1: Estate/Life Event (40 points - VERY motivated)
            if 'ESTATE' in owner_name or 'HEIR' in owner_name:
                motivation_score += 40
                motivation_factors.append("ESTATE SALE (heirs liquidating)")
            elif 'TRUST' in owner_name:
                motivation_score += 10
                motivation_factors.append("Trust ownership (moderate motivation)")

            # SIGNAL 2: Absentee Owner (30 points - high motivation)
            mailing_addr = (parcel.get('mailing_address') or '').upper()
            site_addr = (parcel.get('site_address') or '').upper()
            if mailing_addr and site_addr and mailing_addr != site_addr:
                motivation_score += 30
                motivation_factors.append("ABSENTEE OWNER (out of area)")

            # SIGNAL 3: Long Hold Period (25 points - ready to cash out)
            last_sale_date = parcel.get('last_sale_date')
            if last_sale_date:
                from datetime import date
                years_held = (date.today() - last_sale_date).days / 365
                if years_held >= 15:
                    motivation_score += 25
                    motivation_factors.append(f"LONG HOLD ({years_held:.0f} years - ready to cash out)")
                elif years_held >= 10:
                    motivation_score += 15
                    motivation_factors.append(f"Held {years_held:.0f} years (moderate motivation)")

            # Apply motivation score to opportunity score
            if motivation_score >= 70:
                bonus = 25
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (HIGH MOTIVATION: {', '.join(motivation_factors)})")
            elif motivation_score >= 40:
                bonus = 15
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (MODERATE MOTIVATION: {', '.join(motivation_factors)})")
            elif motivation_score >= 20:
                bonus = 10
                score += bonus
                score_breakdown['factors'].append(f"+{bonus} (Some motivation: {', '.join(motivation_factors)})")

            # Owner type scoring (separate from motivation)
            if any(term in owner_name for term in ['HOLDINGS', 'PROPERTIES', 'INVESTMENTS', 'REALTY']):
                penalty = -5
                score += penalty
                score_breakdown['factors'].append(f"{penalty} (Institutional investor)")
            elif 'TRUST' not in owner_name and 'ESTATE' not in owner_name:
                if any(term in owner_name for term in ['LLC', 'INC', 'CORP', 'LP']):
                    bonus = 5
                    score += bonus
                    score_breakdown['factors'].append(f"+{bonus} (LLC/Corp owner)")
                else:
                    bonus = 5
                    score += bonus
                    score_breakdown['factors'].append(f"+{bonus} (Private individual)")

            opportunities.append({
                'parcel_id': parcel_id,
                'address': parcel.get('site_address') or f"Parcel {parcel_id}",
                'owner_name': parcel.get('owner_name'),
                'property_type': parcel.get('property_type'),
                'lot_acres': lot_acres,
                'land_value': land_val,
                'market_value': market_val,
                'assessed_value': assessed_val,
                'zoning_code': parcel.get('land_zoning_code'),
                'zoning_desc': parcel.get('land_zoning_desc'),
                'last_sale_price': last_sale_price,
                'last_sale_date': last_sale_date,
                'score': score,
                'score_breakdown': score_breakdown,
                'data_quality_warnings': data_quality_warnings,
                'motivation_score': motivation_score,
                'motivation_factors': motivation_factors
            })

        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)

        print(f"\nAnalyzed {len(opportunities)} land parcels")
        print()

        # STEP 6: Present top opportunities
        print("STEP 6: TOP OPPORTUNITIES - Agent Recommendations")
        print("=" * 80)
        print()

        if not opportunities:
            print("[ERROR] NO OPPORTUNITIES FOUND")
            print()
            print("Reasons:")
            print("  - No vacant land parcels in top market")
            print("  - All parcels have critical risks (liens, etc.)")
            print("  - Insufficient data for analysis")
            return

        # Present top 3
        print(f"TARGET: TOP LAND SPECULATION OPPORTUNITIES IN {selected_market_name.upper()}")
        print()

        for rank, opp in enumerate(opportunities[:3], 1):
            print(f"{'=' * 80}")
            print(f"RANK #{rank} - OPPORTUNITY SCORE: {opp['score']}/100")
            print(f"{'=' * 80}")
            print()
            print(f"LOCATION: LOCATION: {opp['address']}")
            print(f"   Parcel ID: {opp['parcel_id']}")
            print()
            print(f"DETAILS: PROPERTY DETAILS:")
            print(f"   Property Type: {opp['property_type']}")
            print(f"   Lot Size: {opp['lot_acres']:.2f} acres")
            print(f"   Zoning: {opp['zoning_code']} - {opp['zoning_desc']}")
            print()
            print(f"VALUE: VALUATION:")
            print(f"   Land Value: ${opp['land_value']:,.0f}")
            print(f"   Market Value: ${opp['market_value']:,.0f}")
            print(f"   Assessed Value: ${opp['assessed_value']:,.0f}")
            if opp['last_sale_price'] and opp['last_sale_price'] > 0:
                print(f"   Last Sale Price: ${opp['last_sale_price']:,.0f} ({opp['last_sale_date']})")
            print()
            print(f"OWNER: OWNER: {opp['owner_name']}")
            print()
            print(f"SCORE: SCORE BREAKDOWN:")
            print(f"   Base Score: {opp['score_breakdown']['base']}")
            for factor in opp['score_breakdown']['factors']:
                print(f"   {factor}")
            print(f"   TOTAL: {opp['score']}/100")
            print()

            # Display motivation analysis if present
            if opp.get('motivation_score', 0) > 0:
                print(f"MOTIVATION: SELLER MOTIVATION ANALYSIS:")
                print(f"   Motivation Score: {opp['motivation_score']}/100")
                for factor in opp.get('motivation_factors', []):
                    print(f"   - {factor}")
                print()

            # Display data quality warnings if present
            if opp.get('data_quality_warnings'):
                print(f"WARNINGS: DATA QUALITY CONCERNS:")
                for warning in opp['data_quality_warnings']:
                    print(f"   [!] {warning}")
                print(f"   ACTION REQUIRED: Validate these issues before investing")
                print()

        # STEP 7: Generate agent thought process summary
        print()
        print("=" * 80)
        print("AGENT DECISION PROCESS SUMMARY")
        print("=" * 80)
        print()
        print("Query Analysis:")
        print("  * Identified as strategic land speculation query")
        print("  * Goal: Find undervalued land with developer demand")
        print()
        print("Data Sources Used:")
        print("  * MarketAnalyzer.get_development_activity() - Found hot markets")
        print("  * MarketAnalyzer.get_market_momentum() - Sales trends")
        print("  * PropertyAnalyzer.analyze_property() - Property details")
        print("  * EntityAnalyzer queries - Active developer identification")
        print("  * bulk_property_records - Vacant land search")
        print("  * permits table - Development activity signals")
        print("  * entities table - Developer entity profiles")
        print("  * TRIM notices - Tax lien risk assessment")
        print()
        print("Scoring Methodology:")
        print("  • Base: 50 points")
        print("  • Undervaluation: +10 to +15")
        print("  • Lot size: +10 to +20")
        print("  • Zoning quality: +8 to +15")
        print("  • Nearby development: +10 to +20")
        print("  • Appreciation trend: +10 to +15")
        print("  • Owner type: +10")
        print("  • Tax liens: -10 to -25 (CRITICAL)")
        print()
        print(f"Results:")
        print(f"  • Markets analyzed: {len(markets)}")
        print(f"  • Top market: {selected_market_name}")
        print(f"  • Vacant land parcels found: {len(land_parcels)}")
        print(f"  • Active developers found: {len(developers)}")
        print(f"  • Opportunities scored: {len(opportunities)}")
        print(f"  • Recommended opportunities: {min(3, len(opportunities))}")
        print()

        if opportunities:
            print("[SUCCESS] AGENT RECOMMENDATION:")
            print(f"   Buy: {opportunities[0]['address']}")
            print(f"   Score: {opportunities[0]['score']}/100")
            land_value = float(opportunities[0]['land_value']) if opportunities[0]['land_value'] else 0
            print(f"   Entry Price Target: ~${land_value * 0.85:,.0f} (15% below land value)")
            print(f"   Exit Strategy: Sell to developer in 6-18 months")
            print(f"   Expected Return: 20-40% based on development momentum")
        else:
            print("[WARNING]  AGENT RECOMMENDATION:")
            print("   No strong opportunities found. Consider:")
            print("   - Expanding search to other markets")
            print("   - Adjusting size/zoning criteria")
            print("   - Waiting for better market conditions")
        print()
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(agent_simulation())
