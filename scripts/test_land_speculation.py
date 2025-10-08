#!/usr/bin/env python3
"""
Test Strategic Land Speculation Query

Query: "What land should I buy in Gainesville for a developer to buy later?"

This tests the agent's ability to:
1. Understand strategic/investment queries
2. Analyze development patterns
3. Identify undervalued land parcels
4. Recommend specific opportunities
"""

import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db_manager
from src.agent.dominion_agent_v2 import DominionAgent
from src.config.current_market import CurrentMarket


async def test_strategic_land_query():
    """Test: What land should I buy for a developer to buy later?"""
    print("\n" + "=" * 80)
    print("STRATEGIC QUERY: LAND SPECULATION FOR FUTURE DEVELOPER SALE")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        agent = DominionAgent(session)

        # Strategic query
        query = "What land should I buy in Gainesville for a developer to buy later?"

        print(f"\nQuery: {query}\n")
        print("Expected Agent Behavior:")
        print("  1. Identify this as a Type 2 strategic query")
        print("  2. Analyze development patterns in Gainesville")
        print("  3. Look for active developers and their preferences")
        print("  4. Find undervalued land parcels")
        print("  5. Recommend specific opportunities\n")
        print("Note: With limited data, agent may struggle. Full analysis requires:")
        print("  - Complete permit history (development signals)")
        print("  - Entity portfolios (developer preferences)")
        print("  - Historical acquisitions (pattern analysis)\n")
        print("Analyzing...")

        # Run analysis
        result = await agent.analyze(query)

        # Display results
        print("\n" + "=" * 80)
        print("AGENT RESPONSE:")
        print("=" * 80)
        print(json.dumps(result, indent=2, default=str))
        print("=" * 80)

        # Extract key insights
        if 'error' not in result:
            print("\n" + "=" * 80)
            print("KEY INSIGHTS:")
            print("=" * 80)
            print(f"Query Type: {result.get('query_type', 'N/A')}")
            print(f"Recommendation: {result.get('recommendation', 'N/A')}")

            if result.get('reasoning'):
                print(f"\nReasoning:\n{result.get('reasoning')}")

            if result.get('opportunities'):
                print(f"\nOpportunities Found: {len(result.get('opportunities', []))}")
                for i, opp in enumerate(result.get('opportunities', [])[:3], 1):
                    print(f"\n  Opportunity {i}:")
                    print(f"    Type: {opp.get('opportunity_type')}")
                    print(f"    Description: {opp.get('description')}")
                    if opp.get('evidence'):
                        print(f"    Evidence: {opp.get('evidence')}")

            if result.get('model_thoughts'):
                print(f"\n" + "=" * 80)
                print("AGENT'S THOUGHT PROCESS:")
                print("=" * 80)
                print(result.get('model_thoughts')[:1000] + "..." if len(result.get('model_thoughts', '')) > 1000 else result.get('model_thoughts', ''))

        else:
            print(f"\nError: {result.get('error')}")

    await db_manager.close()


async def analyze_development_patterns():
    """Analyze what development patterns exist in current data"""
    print("\n" + "=" * 80)
    print("DATA ANALYSIS: DEVELOPMENT PATTERNS IN DATABASE")
    print("=" * 80)

    await db_manager.initialize()

    async with db_manager.get_session() as session:
        from sqlalchemy import text

        print("\n1. VACANT LAND AVAILABILITY:")
        print("-" * 80)

        # Find vacant land
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total_vacant,
                AVG(market_value) as avg_value,
                MIN(market_value) as min_value,
                MAX(market_value) as max_value,
                SUM(lot_size_acres) as total_acres
            FROM bulk_property_records
            WHERE property_type ILIKE '%vacant%'
               OR use_code IN ('0001', '0009', '1600', '1700', '1800', '1900')
               OR (year_built IS NULL AND land_value > 0)
        """))
        row = result.fetchone()
        if row and row[0]:
            print(f"  Total Vacant Parcels: {row[0]:,}")
            print(f"  Average Value: ${row[1]:,.0f}" if row[1] else "  Average Value: N/A")
            print(f"  Range: ${row[2]:,.0f} - ${row[3]:,.0f}" if row[2] and row[3] else "  Range: N/A")
            print(f"  Total Acres: {row[4]:,.1f}" if row[4] else "  Total Acres: N/A")
        else:
            print("  No vacant land found")

        print("\n2. ACTIVE DEVELOPERS (Top 5 by properties):")
        print("-" * 80)

        # Find active developers
        result = await session.execute(text("""
            SELECT
                owner_name,
                COUNT(*) as properties,
                SUM(market_value) as total_value,
                COUNT(CASE WHEN property_type ILIKE '%vacant%' THEN 1 END) as vacant_owned
            FROM bulk_property_records
            WHERE owner_name ILIKE '%LLC%'
               OR owner_name ILIKE '%DEVELOPMENT%'
               OR owner_name ILIKE '%BUILDER%'
               OR owner_name ILIKE '%HOMES%'
            GROUP BY owner_name
            HAVING COUNT(*) >= 5
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """))

        developers = result.fetchall()
        if developers:
            for dev in developers:
                print(f"  {dev[0]}")
                print(f"    Properties: {dev[1]}")
                print(f"    Total Value: ${dev[2]:,.0f}" if dev[2] else "    Total Value: N/A")
                print(f"    Vacant Land Owned: {dev[3]}")
                print()
        else:
            print("  No developers found with 5+ properties")

        print("\n3. RECENT DEVELOPMENT ACTIVITY (Last 180 days):")
        print("-" * 80)

        # Check recent permit activity
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total_permits,
                COUNT(DISTINCT contractor_entity_id) as unique_contractors,
                SUM(project_value) as total_value,
                COUNT(CASE WHEN permit_type ILIKE '%new%construction%' THEN 1 END) as new_construction
            FROM permits
            WHERE application_date >= CURRENT_DATE - INTERVAL '180 days'
        """))
        row = result.fetchone()
        if row and row[0]:
            print(f"  Total Permits: {row[0]:,}")
            print(f"  Unique Contractors: {row[1]:,}")
            print(f"  Total Project Value: ${row[2]:,.0f}" if row[2] else "  Total Project Value: N/A")
            print(f"  New Construction Permits: {row[3]:,}")
        else:
            print("  No recent permit activity")

        print("\n4. UNDERVALUED VACANT LAND (Top 5):")
        print("-" * 80)

        # Find undervalued vacant land
        result = await session.execute(text("""
            SELECT
                site_address,
                market_value,
                lot_size_acres,
                land_zoning_desc,
                owner_name
            FROM bulk_property_records
            WHERE (property_type ILIKE '%vacant%'
               OR use_code IN ('0001', '0009', '1600', '1700', '1800', '1900'))
               AND market_value > 0
               AND market_value < 100000
               AND lot_size_acres > 0.5
               AND site_address IS NOT NULL
            ORDER BY market_value / NULLIF(lot_size_acres, 0)
            LIMIT 5
        """))

        parcels = result.fetchall()
        if parcels:
            for parcel in parcels:
                print(f"  {parcel[0]}")
                print(f"    Value: ${parcel[1]:,.0f}" if parcel[1] else "    Value: N/A")
                print(f"    Size: {parcel[2]:.2f} acres" if parcel[2] else "    Size: N/A")
                print(f"    Price/Acre: ${parcel[1]/parcel[2]:,.0f}" if parcel[1] and parcel[2] else "    Price/Acre: N/A")
                print(f"    Zoning: {parcel[3] if parcel[3] else 'Unknown'}")
                print(f"    Owner: {parcel[4]}")
                print()
        else:
            print("  No undervalued vacant land found")

    await db_manager.close()


async def main():
    """Run land speculation tests"""
    print("=" * 80)
    print("LAND SPECULATION QUERY TESTING")
    print("=" * 80)
    print("\nTesting agent's ability to analyze land investment opportunities")
    print("for future resale to developers.\n")

    try:
        # First, analyze what data we have
        await analyze_development_patterns()

        # Then test the agent
        await test_strategic_land_query()

    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
