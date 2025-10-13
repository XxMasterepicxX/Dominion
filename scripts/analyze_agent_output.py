#!/usr/bin/env python3
"""
Analyze Agent Investment Output JSON
"""

import json
import sys
from pathlib import Path

def analyze_agent_output(json_file):
    """Analyze agent output and print summary"""

    with open(json_file, 'r') as f:
        data = json.load(f)

    print("=" * 100)
    print("AGENT INVESTMENT ANALYSIS - COMPREHENSIVE SUMMARY")
    print("=" * 100)
    print()

    # 1. Basic info
    print("RECOMMENDATION:")
    print(f"  Type: {data.get('recommendation', 'N/A')}")
    print(f"  Confidence: {data.get('confidence', 'N/A')}")
    print(f"  Deal Success Probability: {data.get('deal_success_probability', 'N/A')}%")
    print()

    # 2. Tool calls summary
    if 'tool_calls_made' in data:
        tool_calls = data['tool_calls_made']
        print(f"TOOL CALLS MADE: {len(tool_calls)} total")
        print()

        # Count by tool
        from collections import Counter
        tool_counts = Counter(t.get('tool', 'unknown') for t in tool_calls)

        print("Tool Usage:")
        for tool_name, count in tool_counts.most_common():
            print(f"  - {tool_name}: {count}x")
        print()

        # Check if search_ordinances was used
        ordinance_calls = [t for t in tool_calls if t.get('tool') == 'search_ordinances']
        if ordinance_calls:
            print(f"[CRITICAL] search_ordinances WAS CALLED! ({len(ordinance_calls)} times)")
            print()
            print("Ordinance Searches:")
            for i, call in enumerate(ordinance_calls, 1):
                query = call.get('args', {}).get('query', 'N/A')
                city = call.get('args', {}).get('city', 'All cities')
                results_found = call.get('result', {}).get('results_found', 0)
                print(f"  {i}. Query: '{query}'")
                print(f"     City: {city}")
                print(f"     Results: {results_found} ordinances")
                print()
        else:
            print("[INFO] search_ordinances was NOT called")
            print("  Agent determined ordinance search was not necessary for this query")
            print()

    # 3. Properties analyzed
    if 'tool_calls_made' in data:
        property_calls = [t for t in tool_calls if t.get('tool') == 'analyze_property']
        if property_calls:
            print(f"PROPERTIES ANALYZED: {len(property_calls)}")
            for i, call in enumerate(property_calls[:10], 1):  # Show first 10
                address = call.get('args', {}).get('property_address', 'N/A')
                print(f"  {i}. {address}")
            if len(property_calls) > 10:
                print(f"  ... and {len(property_calls) - 10} more")
            print()

    # 4. Key reasoning (first 1500 chars)
    if 'reasoning' in data:
        reasoning = data['reasoning']
        print("AGENT REASONING:")
        print("-" * 100)
        print(reasoning[:1500])
        if len(reasoning) > 1500:
            print("...")
            print()
            print(f"(Full reasoning: {len(reasoning)} characters - see JSON file)")
        print("-" * 100)
        print()

    # 5. Key factors
    if 'key_factors' in data:
        print("KEY FACTORS:")
        factors = data['key_factors']
        for key, value in factors.items():
            if isinstance(value, str):
                print(f"  {key}: {value[:150]}" + ("..." if len(value) > 150 else ""))
            elif isinstance(value, list):
                print(f"  {key}: ({len(value)} items)")
                for item in value[:3]:  # Show first 3
                    if isinstance(item, str):
                        print(f"    - {item[:100]}")
                    else:
                        print(f"    - {item}")
                if len(value) > 3:
                    print(f"    ... and {len(value) - 3} more")
            elif isinstance(value, dict):
                print(f"  {key}:")
                for k, v in list(value.items())[:3]:
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")
        print()

    # 6. Recommendations (if property list format)
    if 'recommendations' in data:
        recommendations = data['recommendations']
        print(f"TOP RECOMMENDED PROPERTIES: {len(recommendations)}")
        print()
        for i, prop in enumerate(recommendations[:5], 1):  # Show top 5
            print(f"{i}. {prop.get('address', 'N/A')}")
            print(f"   Parcel: {prop.get('parcel_id', 'N/A')}")
            print(f"   Market Value: ${prop.get('market_value', 0):,}")
            print(f"   Lot Size: {prop.get('lot_size_acres', 0):.2f} acres")
            print(f"   Priority: {prop.get('priority', 'N/A')}")
            print(f"   Why: {prop.get('reasoning', 'N/A')[:200]}")
            print()

        if len(recommendations) > 5:
            print(f"... and {len(recommendations) - 5} more properties in JSON")
            print()

    # 7. Tool call sequence
    print("TOOL CALL SEQUENCE:")
    if 'tool_calls_made' in data:
        for i, call in enumerate(tool_calls[:10], 1):  # Show first 10
            tool = call.get('tool', 'unknown')
            args_preview = str(call.get('args', {}))[:60]
            print(f"  {i}. {tool}({args_preview}...)")
        if len(tool_calls) > 10:
            print(f"  ... and {len(tool_calls) - 10} more tool calls")
    print()

    print("=" * 100)
    print(f"FULL OUTPUT: {json_file}")
    print(f"Size: {Path(json_file).stat().st_size:,} bytes")
    print("=" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find latest file
        import glob
        files = glob.glob("agent_investment_output_*.json")
        if not files:
            print("No agent output files found")
            sys.exit(1)
        json_file = max(files, key=lambda f: Path(f).stat().st_mtime)
        print(f"Using latest file: {json_file}")
        print()
    else:
        json_file = sys.argv[1]

    analyze_agent_output(json_file)
