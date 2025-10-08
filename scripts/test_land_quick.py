#!/usr/bin/env python3
"""Quick land speculation test with corrected query phrasing"""

import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db_manager
from src.agent.dominion_agent_v2 import DominionAgent
from src.config.current_market import CurrentMarket


async def main():
    print("=" * 80)
    print("STRATEGIC LAND QUERY TEST")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        agent = DominionAgent(session)

        # Test multiple query phrasings
        queries = [
            "Where should I buy vacant land in Gainesville for future resale to developers?",
            "What should I buy if I want to flip land to developers?",
            "Where to buy land that developers want?",
        ]

        for query in queries:
            print(f"\n{'=' * 80}")
            print(f"QUERY: {query}")
            print('=' * 80)
            print("\nAnalyzing...\n")

            result = await agent.analyze(query)

            if 'error' in result:
                print(f"Error: {result.get('error')}")
                print(f"Suggestion: {result.get('suggestion')}")
            else:
                print(f"Query Type: {result.get('query_type', 'N/A')}")
                print(f"Recommendation: {result.get('recommendation', 'N/A')}")

                if result.get('reasoning'):
                    print(f"\nReasoning (first 500 chars):")
                    print(result.get('reasoning')[:500])

                if result.get('opportunities'):
                    print(f"\nOpportunities Found: {len(result.get('opportunities', []))}")

                if result.get('model_thoughts'):
                    print(f"\nThoughts (first 500 chars):")
                    print(result.get('model_thoughts')[:500])

            print("\n" + "=" * 80)
            # Just test one for now
            break

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
