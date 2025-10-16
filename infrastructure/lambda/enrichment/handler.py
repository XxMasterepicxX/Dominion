"""
Enrichment Lambda Function Handler

Handles 2 tools:
1. enrich_from_qpublic - Get property data from QPublic
2. enrich_from_sunbiz - Get entity data from Florida SunBiz

For hackathon: Returns mock/placeholder data since scrapers need Docker setup.
Will be fully functional after Phase 5 (scraper deployment).
"""

import json
import os
from typing import Dict, Any
from datetime import datetime

# No external dependencies needed for mock responses

def enrich_from_qpublic(params: Dict) -> Dict[str, Any]:
    """
    Enrich property data from QPublic.

    Parameters:
    - parcel_id: str (optional)
    - address: str (optional)
    - jurisdiction: str (default: "Gainesville")

    Returns mock data for hackathon (will be live after scraper deployment).
    """
    parcel_id = params.get('parcel_id')
    address = params.get('address')
    jurisdiction = params.get('jurisdiction', 'Gainesville')

    if not parcel_id and not address:
        return {
            'success': False,
            'error': 'Must provide either parcel_id or address'
        }

    print(f"QPublic enrichment requested: parcel={parcel_id}, address={address}")

    # Mock response for hackathon
    return {
        'success': True,
        'status': 'mock_data',
        'message': 'Live scraping will be available after Phase 5 deployment',
        'note': 'This is placeholder data for hackathon demo',
        'query': {
            'parcel_id': parcel_id,
            'address': address,
            'jurisdiction': jurisdiction
        },
        'mock_data': {
            'parcel_id': parcel_id or 'MOCK-12345',
            'address': address or '123 Main St, Gainesville, FL',
            'owner': 'Demo Owner LLC',
            'assessed_value': 250000,
            'land_value': 100000,
            'improvement_value': 150000,
            'lot_size_sqft': 10000,
            'building_sqft': 2000,
            'year_built': 2005,
            'property_class': 'Single Family',
            'zoning': 'RSF-4',
            'tax_district': 'Gainesville City',
            'last_sale_date': '2020-06-15',
            'last_sale_price': 225000,
            'source': 'qpublic_mock',
            'timestamp': datetime.utcnow().isoformat()
        },
        'next_steps': [
            '1. Deploy scraper infrastructure (Phase 5)',
            '2. Configure Patchright/Crawl4AI dependencies',
            '3. Test live scraping',
            '4. Update this endpoint to use real data'
        ]
    }


def enrich_from_sunbiz(params: Dict) -> Dict[str, Any]:
    """
    Enrich entity data from Florida SunBiz.

    Parameters:
    - entity_name: str (optional)
    - document_number: str (optional)

    Returns mock data for hackathon (will be live after scraper deployment).
    """
    entity_name = params.get('entity_name')
    document_number = params.get('document_number')

    if not entity_name and not document_number:
        return {
            'success': False,
            'error': 'Must provide either entity_name or document_number'
        }

    print(f"SunBiz enrichment requested: entity={entity_name}, doc={document_number}")

    # Mock response for hackathon
    return {
        'success': True,
        'status': 'mock_data',
        'message': 'Live scraping will be available after Phase 5 deployment',
        'note': 'This is placeholder data for hackathon demo',
        'query': {
            'entity_name': entity_name,
            'document_number': document_number
        },
        'mock_data': {
            'entity_name': entity_name or 'Demo Properties LLC',
            'document_number': document_number or 'L21000123456',
            'filing_type': 'Florida Limited Liability Company',
            'status': 'Active',
            'filing_date': '2021-01-15',
            'state_of_formation': 'Florida',
            'principal_address': '456 Business Blvd, Gainesville, FL 32601',
            'mailing_address': 'PO Box 789, Gainesville, FL 32602',
            'registered_agent': {
                'name': 'Legal Services Inc',
                'address': '789 Agent St, Gainesville, FL 32601'
            },
            'officers': [
                {
                    'title': 'Managing Member',
                    'name': 'John Smith',
                    'address': '123 Member Ln, Gainesville, FL 32601'
                }
            ],
            'annual_report': {
                'year': 2024,
                'status': 'Filed',
                'date': '2024-05-01'
            },
            'source': 'sunbiz_mock',
            'timestamp': datetime.utcnow().isoformat()
        },
        'next_steps': [
            '1. Deploy scraper infrastructure (Phase 5)',
            '2. Configure web scraping dependencies',
            '3. Test live SunBiz API/scraping',
            '4. Update this endpoint to use real data'
        ]
    }


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for enrichment tools.

    Event format:
    {
        "tool": "enrich_from_qpublic",
        "parameters": {
            "parcel_id": "12-34-56-78",
            "jurisdiction": "Gainesville"
        }
    }
    """
    try:
        print(f"Enrichment function invoked: {json.dumps(event)}")

        tool_name = event.get('tool')
        parameters = event.get('parameters', {})

        if not tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing tool name'})
            }

        # Route to appropriate tool
        tool_functions = {
            'enrich_from_qpublic': enrich_from_qpublic,
            'enrich_from_sunbiz': enrich_from_sunbiz,
        }

        if tool_name not in tool_functions:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Unknown tool: {tool_name}',
                    'available_tools': list(tool_functions.keys())
                })
            }

        # Execute tool
        result = tool_functions[tool_name](parameters)

        print(f"Enrichment tool executed: {tool_name}")

        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        print(f"Enrichment function error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
