#!/usr/bin/env python3
"""
Test Dominion Agent with Real Data

Tests both query types:
1. Specific property analysis
2. Strategic analysis
"""

import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import DatabaseManager
from src.agent.dominion_agent_v2 import DominionAgent
from src.config.current_market import CurrentMarket


async def test_property_query():
    """Test specific property analysis"""
    print("\n" + "=" * 80)
    print("TEST 1: SPECIFIC PROPERTY ANALYSIS")
    print("=" * 80)

    # Import db_manager singleton
    from src.database.connection import db_manager

    # Initialize database
    await db_manager.initialize()

    # Initialize market
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        # Create agent
        agent = DominionAgent(session)

        # Test query
        query = "Should I buy 9420 SW 35TH LN?"

        print(f"\nQuery: {query}\n")
        print("Analyzing...")

        # Run analysis
        result = await agent.analyze(query)

        # Display results
        print("\n" + "-" * 80)
        print("ANALYSIS RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        print("-" * 80)

        # Extract key insights
        if 'error' not in result:
            print("\nKEY INSIGHTS:")
            print(f"  Property: {result.get('property_analyzed', 'N/A')}")
            print(f"  Recommendation: {result.get('recommendation', 'N/A')}")
            print(f"  Deal Success Probability: {result.get('deal_success_probability', 'N/A')}")
            print(f"  Context Provided:")
            context = result.get('context_provided', {})
            for key, value in context.items():
                print(f"    - {key}: {value}")

    await db_manager.close()


async def test_strategic_query():
    """Test strategic analysis"""
    print("\n" + "=" * 80)
    print("TEST 2: STRATEGIC QUERY (Tool Calling)")
    print("=" * 80)

    from src.database.connection import db_manager

    await db_manager.initialize()

    # Initialize market
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        # Create agent
        agent = DominionAgent(session)

        # Test strategic query
        query = "Where should I buy to follow the pattern of HOME BUILDER 1, LLC?"

        print(f"\nQuery: {query}\n")
        print("Note: This query will trigger autonomous tool calling")
        print("The agent will:")
        print("  1. Parse the entity name (HOME BUILDER 1, LLC)")
        print("  2. Call analyze_entity tool to get their portfolio")
        print("  3. Analyze patterns in their purchases")
        print("  4. Recommend similar opportunities")
        print("\nAnalyzing...")

        # Run analysis
        result = await agent.analyze(query)

        # Display results
        print("\n" + "-" * 80)
        print("ANALYSIS RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        print("-" * 80)

        # Extract key insights
        if 'error' not in result:
            print("\nKEY INSIGHTS:")
            print(f"  Query Type: {result.get('query_type', 'N/A')}")
            print(f"  Recommendation: {result.get('recommendation', 'N/A')}")

    await db_manager.close()


async def test_entity_portfolio():
    """Test entity analysis directly"""
    print("\n" + "=" * 80)
    print("TEST 3: ENTITY PORTFOLIO ANALYSIS")
    print("=" * 80)

    from src.database.connection import db_manager

    await db_manager.initialize()

    # Initialize market
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        from src.intelligence.analyzers import EntityAnalyzer

        analyzer = EntityAnalyzer(session)

        entity_name = "HOME BUILDER 1, LLC"
        print(f"\nAnalyzing entity: {entity_name}\n")

        # Get entity analysis
        result = await analyzer.analyze(entity_name=entity_name)

        print("ENTITY ANALYSIS:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        print("-" * 80)

        if 'error' not in result:
            print("\nQUICK STATS:")
            entity = result.get('entity', {})
            portfolio = result.get('portfolio', {})

            print(f"  Name: {entity.get('name', 'N/A')}")
            print(f"  Type: {entity.get('entity_type', 'N/A')}")
            print(f"  Total Properties: {portfolio.get('total_properties', 0)}")
            print(f"  Total Value: ${portfolio.get('total_value', 0):,.0f}" if portfolio.get('total_value') else "  Total Value: N/A")
            print(f"  Active Markets: {entity.get('active_markets', [])}")

    await db_manager.close()


async def main():
    """Run all tests"""
    print("=" * 80)
    print("DOMINION AGENT TESTING SUITE")
    print("=" * 80)
    print("\nTesting agent with current database data...")
    print("Note: Some features may not work fully if backfill is incomplete")

    try:
        # Test 1: Simple property query
        await test_property_query()

        # Test 2: Entity portfolio (shows what data agent has)
        await test_entity_portfolio()

        # Test 3: Strategic query with tool calling
        # await test_strategic_query()  # Skip for now - requires Gemini API

    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
