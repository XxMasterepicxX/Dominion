#!/usr/bin/env python3
"""Final land speculation test with full output"""

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
    print("STRATEGIC LAND QUERY - FINAL TEST")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        agent = DominionAgent(session)

        query = "Where should I buy vacant land in Gainesville for future resale to developers?"

        print(f"\nQuery: {query}\n")
        print("Analyzing...\n")

        result = await agent.analyze(query)

        print("\n" + "=" * 80)
        print("FULL AGENT RESPONSE")
        print("=" * 80)

        # Pretty print full response
        print(json.dumps(result, indent=2, default=str))

        print("\n" + "=" * 80)
        print("KEY INSIGHTS")
        print("=" * 80)

        if 'error' not in result:
            print(f"\nQuery Type: {result.get('query_type', 'N/A')}")
            print(f"Recommendation: {result.get('recommendation', 'N/A')}")
            print(f"Deal Success Probability: {result.get('deal_success_probability', 'N/A')}%")
            print(f"Confidence: {result.get('confidence', 'N/A')}")

            if result.get('reasoning'):
                print(f"\n{'='*80}")
                print("REASONING:")
                print('='*80)
                print(result.get('reasoning'))

            if result.get('model_thoughts'):
                print(f"\n{'='*80}")
                print("AGENT THOUGHT PROCESS:")
                print('='*80)
                print(result.get('model_thoughts'))

            if result.get('opportunities'):
                print(f"\n{'='*80}")
                print(f"OPPORTUNITIES IDENTIFIED: {len(result.get('opportunities', []))}")
                print('='*80)
                for i, opp in enumerate(result.get('opportunities', []), 1):
                    print(f"\n{i}. {opp.get('opportunity_type', 'Unknown')}")
                    print(f"   Description: {opp.get('description', 'N/A')}")
                    if opp.get('evidence'):
                        print(f"   Evidence: {opp.get('evidence', 'N/A')}")

            if result.get('tool_calls_made'):
                print(f"\n{'='*80}")
                print(f"TOOLS USED: {len(result.get('tool_calls_made', []))}")
                print('='*80)
                for i, tool_call in enumerate(result.get('tool_calls_made', []), 1):
                    print(f"\n{i}. {tool_call.get('tool', 'Unknown')}")
                    print(f"   Args: {tool_call.get('args', {})}")
        else:
            print(f"\nError: {result.get('error')}")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
