#!/usr/bin/env python3
"""Analyze agent JSON output"""

import sys
import json
from pathlib import Path

def analyze_output(json_file):
    """Analyze agent output JSON file"""

    with open(json_file, 'r') as f:
        data = json.load(f)

    print("=" * 100)
    print("AGENT OUTPUT ANALYSIS")
    print("=" * 100)
    print()

    # Basic info
    print("QUERY CLASSIFICATION:")
    print(f"  Query Type: {data.get('query_type', 'N/A')}")
    print(f"  Recommendation: {data.get('recommendation', 'N/A')}")
    print(f"  Deal Success: {data.get('deal_success_probability', 'N/A')}%")
    print(f"  Confidence: {data.get('confidence', 'N/A')}")
    print()

    # Error check
    if 'error' in data:
        print("ERROR OCCURRED:")
        print(f"  {data['error']}")
        print()
        return

    # Tool calls
    tool_calls = data.get('tool_calls_made', [])
    print(f"TOOL CALLS: {len(tool_calls)} total")
    print()

    for i, call in enumerate(tool_calls, 1):
        tool_name = call.get('tool', 'unknown')
        args = call.get('args', {})
        result = call.get('result', {})

        print(f"{i}. {tool_name}")
        print(f"   Args: {args}")

        # Summarize result based on tool
        if tool_name == 'analyze_market':
            if isinstance(result, dict):
                print(f"   Result: {result.get('total_properties', 0):,} properties in market")
                print(f"           {result.get('sales_last_year', 0):,} sales last year")

        elif tool_name == 'analyze_entity':
            if isinstance(result, dict):
                print(f"   Result: {result.get('total_properties', 0):,} properties owned")
                print(f"           Active in {result.get('markets_count', 0)} markets")

        elif tool_name == 'get_entity_properties':
            if isinstance(result, list):
                print(f"   Result: Found {len(result)} properties")

        elif tool_name == 'search_properties':
            if isinstance(result, list):
                print(f"   Result: Found {len(result)} available properties")
                if result:
                    values = [p.get('market_value', 0) for p in result if p.get('market_value')]
                    if values:
                        print(f"           Price range: ${min(values):,} - ${max(values):,}")

        elif tool_name == 'analyze_property':
            if isinstance(result, dict):
                prop = result.get('property', {})
                print(f"   Result: {prop.get('site_address', 'N/A')}")
                print(f"           Value: ${prop.get('market_value', 0):,}")

        print()

    # Reasoning
    if 'reasoning' in data:
        print("REASONING:")
        reasoning = data['reasoning']
        # Print first 500 chars
        if len(reasoning) > 500:
            print(f"  {reasoning[:500]}...")
            print(f"  (... {len(reasoning) - 500} more characters)")
        else:
            print(f"  {reasoning}")
        print()

    # Investment recommendation
    if 'investment_recommendation' in data:
        print("INVESTMENT RECOMMENDATION:")
        rec = data['investment_recommendation']
        if isinstance(rec, dict):
            for key, value in rec.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {rec}")
        print()

    # Summary
    print("=" * 100)
    print("VERIFICATION CHECKLIST:")
    print("=" * 100)

    checks = []

    # Check for hallucination
    has_search = any(c.get('tool') == 'search_properties' for c in tool_calls)
    has_analyze = any(c.get('tool') == 'analyze_property' for c in tool_calls)

    if has_search:
        checks.append(("Called search_properties()", "PASS", "Agent searched for available properties"))
    else:
        checks.append(("Called search_properties()", "FAIL", "Agent may have hallucinated without searching"))

    if has_analyze:
        checks.append(("Called analyze_property()", "PASS", "Agent verified property details"))
    else:
        checks.append(("Called analyze_property()", "WARN", "Agent may not have verified specific properties"))

    # Check for proper workflow
    has_market = any(c.get('tool') == 'analyze_market' for c in tool_calls)
    if has_market:
        checks.append(("Called analyze_market()", "PASS", "Agent got market context"))

    has_entity = any(c.get('tool') == 'analyze_entity' for c in tool_calls)
    if has_entity:
        checks.append(("Called analyze_entity()", "PASS", "Agent researched smart money"))

    print()
    for check, status, note in checks:
        symbol = "OK" if status == "PASS" else "FAIL" if status == "FAIL" else "WARN"
        print(f"  [{symbol}] {check:<30} {status:<6} - {note}")

    print()
    print("=" * 100)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_agent_output.py <json_file>")
        print()
        print("Available files:")
        script_dir = Path(__file__).parent
        json_files = list(script_dir.glob("agent_output_*.json"))
        for f in sorted(json_files, reverse=True):
            print(f"  {f.name}")
        sys.exit(1)

    json_file = Path(sys.argv[1])
    if not json_file.exists():
        # Try in scripts directory
        json_file = Path(__file__).parent / json_file.name

    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)

    analyze_output(json_file)
