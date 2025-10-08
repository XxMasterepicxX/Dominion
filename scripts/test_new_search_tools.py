#!/usr/bin/env python3
"""
Test new search tools added to agent

Tests:
1. search_properties - Find vacant land
2. get_entity_properties - Get D.R. Horton's portfolio
3. Agent using tools autonomously
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


async def test_search_properties_tool():
    """Test the new search_properties tool"""
    print("\n" + "=" * 80)
    print("TEST 1: SEARCH_PROPERTIES TOOL")
    print("=" * 80)

    await db_manager.initialize()

    async with db_manager.get_session() as session:
        from src.agent.tools import AgentTools

        tools = AgentTools(session)

        # Test 1: Search for vacant land under $50k
        print("\nSearching for vacant land under $50k...")
        result = await tools.execute_tool("search_properties", {
            "property_type": "VACANT",
            "max_price": 50000,
            "min_lot_size": 0.5,
            "limit": 5
        })

        print(f"\nFound {result['count']} properties:")
        for i, prop in enumerate(result['properties'][:5], 1):
            print(f"\n{i}. {prop['address']}")
            print(f"   Parcel: {prop['parcel_id']}")
            print(f"   Owner: {prop['owner']}")
            print(f"   Price: ${prop['market_value']:,.0f}")
            print(f"   Size: {prop['lot_size_acres']:.2f} acres")
            print(f"   Zoning: {prop['zoning']}")

    await db_manager.close()


async def test_get_entity_properties_tool():
    """Test the new get_entity_properties tool"""
    print("\n" + "=" * 80)
    print("TEST 2: GET_ENTITY_PROPERTIES TOOL")
    print("=" * 80)

    await db_manager.initialize()

    async with db_manager.get_session() as session:
        from src.agent.tools import AgentTools

        tools = AgentTools(session)

        # Test: Get D.R. Horton's vacant land
        print("\nGetting D.R. Horton's vacant land parcels...")
        result = await tools.execute_tool("get_entity_properties", {
            "entity_name": "D R HORTON",
            "property_type": "VACANT",
            "limit": 10
        })

        print(f"\nEntity: {result['entity_name']}")
        print(f"Total Properties: {result['summary']['total_properties']}")
        print(f"Total Value: ${result['summary']['total_value']:,.0f}")
        print(f"Total Acres: {result['summary']['total_acres']:.2f}")

        print(f"\nSample properties (first 10):")
        for i, prop in enumerate(result['properties'][:10], 1):
            print(f"\n{i}. {prop['address']}")
            print(f"   Parcel: {prop['parcel_id']}")
            print(f"   Purchase Date: {prop['purchase_date']}")
            print(f"   Value: ${prop['market_value']:,.0f}" if prop['market_value'] else "   Value: N/A")

    await db_manager.close()


async def test_agent_with_new_tools():
    """Test agent using new tools autonomously"""
    print("\n" + "=" * 80)
    print("TEST 3: AGENT WITH NEW SEARCH TOOLS")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        agent = DominionAgent(session)

        query = "What land should I buy in Gainesville for future resale to developers?"

        print(f"\nQuery: {query}")
        print("\nExpected behavior:")
        print("  1. Agent calls analyze_market()")
        print("  2. Agent calls get_entity_properties() for D.R. Horton")
        print("  3. Agent calls search_properties() for opportunities")
        print("  4. Agent returns SPECIFIC parcel IDs and addresses\n")
        print("Analyzing...\n")

        result = await agent.analyze(query)

        print("\n" + "=" * 80)
        print("AGENT RESPONSE")
        print("=" * 80)

        if 'error' not in result:
            print(f"\nQuery Type: {result.get('query_type', 'N/A')}")

            # Check if agent used the new tools
            if result.get('tool_calls_made'):
                print(f"\nTools Used ({len(result.get('tool_calls_made', []))}):")
                for i, tool_call in enumerate(result.get('tool_calls_made', []), 1):
                    print(f"  {i}. {tool_call.get('tool')}")
                    if tool_call.get('tool') in ['search_properties', 'get_entity_properties']:
                        print(f"     ✅ NEW TOOL USED!")

            # Extract recommendations
            if result.get('recommendations'):
                print(f"\n{'='*80}")
                print(f"SPECIFIC RECOMMENDATIONS ({len(result.get('recommendations', []))}):")
                print('='*80)
                for i, rec in enumerate(result.get('recommendations', []), 1):
                    print(f"\n{i}. {rec.get('address', 'N/A')}")
                    print(f"   Priority: {rec.get('priority', 'N/A')}")
                    print(f"   Acquisition Probability: {rec.get('acquisition_probability', 'N/A')}")
                    if rec.get('reasoning'):
                        print(f"   Reasoning: {rec.get('reasoning')[:200]}...")
            elif result.get('parcel_mapping'):
                print(f"\n{'='*80}")
                print("PARCEL MAPPING:")
                print('='*80)
                print(json.dumps(result.get('parcel_mapping'), indent=2))

        else:
            print(f"\nError: {result.get('error')}")

    await db_manager.close()


async def main():
    """Run all tests"""
    print("=" * 80)
    print("TESTING NEW SEARCH TOOLS")
    print("=" * 80)
    print("\nThis tests the two new tools added to fix the data gap:")
    print("  1. search_properties - Find properties by criteria")
    print("  2. get_entity_properties - Get actual property lists")

    try:
        # Test individual tools first
        await test_search_properties_tool()
        await test_get_entity_properties_tool()

        # Test agent using tools autonomously
        await test_agent_with_new_tools()

    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
