#!/usr/bin/env python3
"""Test agent and save JSON output for analysis"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_agent_and_save():
    from src.database.connection import db_manager
    from src.agent.dominion_agent_v2 import DominionAgent
    from src.config import CurrentMarket

    print("=" * 100)
    print("DOMINION AGENT TEST - WITH JSON OUTPUT")
    print("=" * 100)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        # Create agent
        print("\n1. Initializing agent...")
        agent = DominionAgent(session)
        print("   Agent initialized successfully!")

        # Test query
        query = "find something under 100k that will gain value"

        print(f"\n2. Test Query: '{query}'")
        print("\n3. Agent is analyzing...")
        print("   (This may take 2-3 minutes with rate limiting)")
        print()

        # Run analysis
        start_time = datetime.now()
        try:
            result = await agent.analyze(query)
            duration = (datetime.now() - start_time).total_seconds()

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(__file__).parent / f"agent_output_{timestamp}.json"

            with open(output_file, 'w') as f:
                json.dump(result, indent=2, default=str, fp=f)

            print("\n" + "=" * 100)
            print("AGENT COMPLETED!")
            print("=" * 100)
            print(f"\nDuration: {duration:.1f} seconds")
            print(f"Output saved to: {output_file}")
            print()

            # Print summary
            print("SUMMARY:")
            print(f"  Query Type: {result.get('query_type', 'N/A')}")
            print(f"  Recommendation: {result.get('recommendation', 'N/A')}")

            if 'error' not in result:
                if 'deal_success_probability' in result:
                    print(f"  Deal Success: {result['deal_success_probability']}")
                if 'confidence' in result:
                    print(f"  Confidence: {result['confidence']}")

                if 'tool_calls_made' in result:
                    print(f"\n  Tools Called: {len(result['tool_calls_made'])}")
                    for i, tool_call in enumerate(result['tool_calls_made'], 1):
                        print(f"    {i}. {tool_call.get('tool', 'unknown')}")

                if 'reasoning' in result:
                    print(f"\n  Reasoning (first 200 chars):")
                    reasoning = result['reasoning']
                    preview = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning
                    print(f"  {preview}")
            else:
                print(f"\n  ERROR: {result['error']}")

            print()
            print("=" * 100)
            print("To analyze the full output, run:")
            print(f"  python scripts/analyze_agent_output.py {output_file.name}")
            print("=" * 100)

        except Exception as e:
            print(f"\n ERROR during analysis: {str(e)}")
            import traceback
            traceback.print_exc()

    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(test_agent_and_save())
