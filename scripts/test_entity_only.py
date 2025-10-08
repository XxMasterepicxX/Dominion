#!/usr/bin/env python3
"""Quick entity analysis test"""

import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db_manager
from src.intelligence.analyzers import EntityAnalyzer
from src.config.current_market import CurrentMarket


async def main():
    print("=" * 80)
    print("ENTITY ANALYZER TEST")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')

    async with db_manager.get_session() as session:
        analyzer = EntityAnalyzer(session)

        entity_name = "HOME BUILDER 1, LLC"
        print(f"\nAnalyzing: {entity_name}\n")

        result = await analyzer.analyze(entity_name=entity_name)

        print("RESULT:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        print("-" * 80)

        if 'error' not in result:
            entity = result.get('entity', {})
            portfolio = result.get('portfolio', {})
            print(f"\nName: {entity.get('name')}")
            print(f"Type: {entity.get('entity_type')}")
            print(f"Properties: {portfolio.get('total_properties', 0)}")
            print(f"Total Value: ${portfolio.get('total_value', 0):,.0f}" if portfolio.get('total_value') else "Value: N/A")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
