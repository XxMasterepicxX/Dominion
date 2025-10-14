#!/usr/bin/env python3
"""
FORENSIC AGENT AUDIT - Senior Analyst Verification
DO NOT TRUST THE AGENT. VERIFY EVERY CLAIM.
"""
import json
import sys

def forensic_audit(filepath):
    with open(filepath) as f:
        data = json.load(f)

    print('='*80)
    print('FORENSIC AGENT AUDIT - SENIOR ANALYST VERIFICATION')
    print('TRUST NOTHING. VERIFY EVERYTHING.')
    print('='*80)

    # Get all tool calls
    tool_calls = data.get('tool_calls_made', [])

    # AUDIT 1: COUNT VERIFICATION
    print('\n[AUDIT 1] TOOL CALL COUNT VERIFICATION')
    print('-'*80)

    tool_counts = {}
    for call in tool_calls:
        tool_name = call['tool']
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    print(f'Total tool calls: {len(tool_calls)}')
    for tool, count in sorted(tool_counts.items()):
        print(f'  - {tool}: {count}x')

    # AUDIT 2: ORDINANCES CHECK FOR VACANT LAND
    print('\n[AUDIT 2] VACANT LAND ORDINANCE VERIFICATION')
    print('-'*80)

    search_calls = [c for c in tool_calls if c['tool'] == 'search_properties']
    ordinance_calls = [c for c in tool_calls if c['tool'] == 'search_ordinances']

    if search_calls:
        search_result = search_calls[0].get('result', {})
        props = search_result.get('properties', [])
        vacant_count = sum(1 for p in props if 'VACANT' in p.get('property_type', '').upper())

        print(f'Vacant properties in search: {vacant_count}/{len(props)}')
        print(f'Ordinances checked: {"YES" if ordinance_calls else "NO"}')

        if vacant_count > 0 and not ordinance_calls:
            print('[CRITICAL FAILURE] Agent recommended vacant land WITHOUT ordinance verification!')
            print('Status: UNACCEPTABLE')
        elif vacant_count > 0 and ordinance_calls:
            print('[PASS] Agent checked ordinances for vacant land')
            print('Status: ACCEPTABLE')
        else:
            print('Status: N/A (no vacant land)')

    # AUDIT 3: PROPERTY ANALYSIS COMPLETENESS
    print('\n[AUDIT 3] PROPERTY ANALYSIS COMPLETENESS')
    print('-'*80)

    if search_calls:
        search_result = search_calls[0].get('result', {})
        props = search_result.get('properties', [])
        analyze_calls = [c for c in tool_calls if c['tool'] == 'analyze_property']

        print(f'Properties found in search: {len(props)}')
        print(f'Properties actually analyzed: {len(analyze_calls)}')
        print(f'Analysis rate: {len(analyze_calls)/len(props)*100 if props else 0:.0f}%')

        if len(props) > 0:
            analyzed_parcels = set()
            for call in analyze_calls:
                parcel = call['args'].get('parcel_id')
                if parcel:
                    analyzed_parcels.add(parcel)

            print(f'\nAnalyzed parcels: {list(analyzed_parcels)[:5]}...')

            # Check if best deals were analyzed
            props_sorted = sorted(props, key=lambda x: x.get('market_value', 999999))
            print(f'\nCheapest 3 properties found:')
            for i, prop in enumerate(props_sorted[:3], 1):
                parcel = prop.get('parcel_id')
                value = prop.get('market_value', 0)
                acres = prop.get('lot_size_acres', 0)
                analyzed = 'ANALYZED' if parcel in analyzed_parcels else 'MISSED'
                print(f'  {i}. {parcel}: ${value:,} ({acres:.2f} ac) - {analyzed}')

            # Check for missed opportunities
            missed = [p for p in props if p.get('parcel_id') not in analyzed_parcels]
            if len(missed) > len(props) * 0.5:  # Missed more than 50%
                print(f'\n[WARNING] Agent analyzed only {len(analyze_calls)}/{len(props)} properties')
                print(f'[WARNING] Missed {len(missed)} potential opportunities')

    # AUDIT 4: BUYER COMPARISON VERIFICATION
    print('\n[AUDIT 4] BUYER COMPARISON VERIFICATION')
    print('-'*80)

    market_calls = [c for c in tool_calls if c['tool'] == 'analyze_market']
    entity_calls = [c for c in tool_calls if c['tool'] == 'analyze_entity']

    if market_calls:
        market_result = market_calls[0].get('result', {})
        competition = market_result.get('competition_analysis', {})
        active_buyers = competition.get('active_buyers', [])

        print(f'Active buyers found: {len(active_buyers)}')
        print(f'Buyers actually analyzed: {len(entity_calls)}')

        if len(active_buyers) > 0:
            print(f'\nTop 5 buyers by recent acquisitions:')
            for i, buyer in enumerate(active_buyers[:5], 1):
                name = buyer.get('entity_name', 'Unknown')
                recent = buyer.get('recent_acquisitions', 0)
                analyzed = 'ANALYZED' if any(name in e['args'].get('entity_name', '') for e in entity_calls) else 'NOT ANALYZED'
                print(f'  {i}. {name}: {recent} recent acquisitions - {analyzed}')

        if len(active_buyers) >= 3 and len(entity_calls) == 1:
            print(f'\n[WARNING] Agent analyzed only 1 buyer when {len(active_buyers)} were available')
            print('[WARNING] No comparative buyer analysis shown')

    # AUDIT 5: DATA FABRICATION CHECK
    print('\n[AUDIT 5] DATA FABRICATION VERIFICATION')
    print('-'*80)

    reasoning = data.get('reasoning', '')
    recommendations = data.get('recommendations', [])

    # Extract all parcels mentioned in recommendations
    rec_parcels = set()
    for rec in recommendations:
        if 'parcel_id' in rec:
            rec_parcels.add(rec['parcel_id'])

    # Extract all parcels that were actually analyzed
    analyzed_parcels = set()
    for call in tool_calls:
        if call['tool'] == 'analyze_property':
            parcel = call['args'].get('parcel_id')
            if parcel:
                analyzed_parcels.add(parcel)

    print(f'Parcels mentioned in recommendations: {len(rec_parcels)}')
    print(f'Parcels actually analyzed: {len(analyzed_parcels)}')

    # Check for fabrication
    fabricated = rec_parcels - analyzed_parcels
    if fabricated:
        print(f'\n[CRITICAL FAILURE] FABRICATED DATA DETECTED!')
        print(f'Agent recommended parcels WITHOUT analyzing them: {fabricated}')
        print('Status: UNACCEPTABLE - DATA INTEGRITY VIOLATION')
    else:
        print('\n[PASS] All recommended properties were analyzed')
        print('Status: NO FABRICATION DETECTED')

    # Check numbers in reasoning
    print('\n[AUDIT 5B] NUMERICAL CLAIMS VERIFICATION')
    print('-'*80)

    if market_calls:
        market_result = market_calls[0].get('result', {})

        # Verify sales claim
        actual_sales = market_result.get('market_activity', {}).get('sales_last_6mo', 0)
        if str(actual_sales) in reasoning or f'{actual_sales:,}' in reasoning:
            print(f'[PASS] Sales figure ({actual_sales:,}) matches database')
        else:
            print(f'[VERIFY] Check if agent cited sales figure correctly')

        # Verify permits claim
        actual_permits = market_result.get('development_activity', {}).get('total_permits', 0)
        if str(actual_permits) in reasoning or f'{actual_permits:,}' in reasoning:
            print(f'[PASS] Permits figure ({actual_permits:,}) matches database')
        else:
            print(f'[VERIFY] Check if agent cited permits figure correctly')

    # AUDIT 6: CONFIDENCE APPROPRIATENESS
    print('\n[AUDIT 6] CONFIDENCE APPROPRIATENESS')
    print('-'*80)

    confidence = data.get('confidence', 'unknown')
    deal_prob = data.get('deal_success_probability', 0)

    print(f'Agent confidence: {confidence}')
    print(f'Deal success probability: {deal_prob}%')

    # Check if confidence matches completeness
    has_ordinances = len(ordinance_calls) > 0
    analyzed_multiple_props = len(analyze_calls) > 2 if search_calls else False
    analyzed_multiple_buyers = len(entity_calls) > 1 if market_calls else False

    completeness_score = sum([has_ordinances, analyzed_multiple_props, analyzed_multiple_buyers])

    print(f'\nDue diligence completeness:')
    print(f'  - Ordinances checked: {"YES" if has_ordinances else "NO"}')
    print(f'  - Multiple properties analyzed: {"YES" if analyzed_multiple_props else "NO"}')
    print(f'  - Multiple buyers compared: {"YES" if analyzed_multiple_buyers else "NO"}')
    print(f'  Completeness score: {completeness_score}/3')

    if confidence == 'high' and completeness_score < 2:
        print(f'\n[WARNING] Confidence "{confidence}" may be too high for completeness score {completeness_score}/3')
    elif confidence == 'low' and completeness_score == 3:
        print(f'\n[WARNING] Confidence "{confidence}" may be too low for completeness score {completeness_score}/3')
    else:
        print(f'\n[ACCEPTABLE] Confidence level appropriate for due diligence completeness')

    # FINAL VERDICT
    print('\n' + '='*80)
    print('FINAL SENIOR ANALYST VERDICT')
    print('='*80)

    critical_failures = []
    warnings = []
    passes = []

    if vacant_count > 0 and not ordinance_calls:
        critical_failures.append('No ordinance verification for vacant land')

    if fabricated:
        critical_failures.append('Data fabrication detected')

    if len(props) > 0 and len(analyze_calls) < len(props) * 0.3:
        warnings.append(f'Analyzed only {len(analyze_calls)}/{len(props)} properties')

    if len(active_buyers) >= 3 and len(entity_calls) == 1:
        warnings.append('No comparative buyer analysis')

    if not critical_failures and not fabricated:
        passes.append('No data fabrication')

    if has_ordinances and vacant_count > 0:
        passes.append('Ordinances checked for vacant land')

    print(f'\nCRITICAL FAILURES: {len(critical_failures)}')
    for failure in critical_failures:
        print(f'  [FAIL] {failure}')

    print(f'\nWARNINGS: {len(warnings)}')
    for warning in warnings:
        print(f'  [WARN] {warning}')

    print(f'\nPASSES: {len(passes)}')
    for pass_item in passes:
        print(f'  [PASS] {pass_item}')

    # Calculate trust score
    if critical_failures:
        trust_score = 0
        status = 'DO NOT TRUST'
    elif len(warnings) > 2:
        trust_score = 40
        status = 'UNRELIABLE'
    elif len(warnings) > 0:
        trust_score = 70
        status = 'USE WITH CAUTION'
    else:
        trust_score = 95
        status = 'TRUSTWORTHY'

    print(f'\nTRUST SCORE: {trust_score}/100')
    print(f'STATUS: {status}')

    if trust_score < 60:
        print('\nRECOMMENDATION: DO NOT USE FOR PRODUCTION')
        print('REASON: Critical gaps in analysis or data integrity issues')
    elif trust_score < 80:
        print('\nRECOMMENDATION: Use with manual verification')
        print('REASON: Analysis incomplete, requires human oversight')
    else:
        print('\nRECOMMENDATION: Acceptable for production use')
        print('REASON: Thorough analysis with no critical issues')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        forensic_audit(sys.argv[1])
    else:
        print('Usage: python forensic_agent_audit.py <output_file.json>')
