"""
Dominion Real Estate Intelligence Agent for AWS Bedrock AgentCore

This agent coordinates 10 intelligence tools across 3 Lambda functions:
- Intelligence Lambda: 7 tools (property search, entity analysis, market trends, etc.)
- RAG Lambda: 1 tool (ordinance search)
- Enrichment Lambda: 2 tools (QPublic, SunBiz scraping)

Uses Strands Agents framework with AgentCore runtime.
"""

import json
import os
from typing import Dict, Any

import boto3
from strands import Agent, tool
import structlog

logger = structlog.get_logger()

# Initialize AWS clients with explicit region
# Use us-east-1 where all Lambda functions are deployed
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Lambda function ARNs - Use actual function names with fallback to environment
INTELLIGENCE_FUNCTION_ARN = os.environ.get('INTELLIGENCE_FUNCTION_ARN', 'Dominion-Tools-IntelligenceFunctionF3B7706E-MqwpnWGzHDyP')
RAG_FUNCTION_ARN = os.environ.get('RAG_FUNCTION_ARN', 'Dominion-Tools-RAGFunction89B11B85-269jmrt7KhBO')
ENRICHMENT_FUNCTION_ARN = os.environ.get('ENRICHMENT_FUNCTION_ARN', 'Dominion-Tools-EnrichmentFunction65873741-Nu6t0OWMde2r')


# Tool wrappers that invoke Lambda functions
# Each tool calls the appropriate Lambda function with the tool name and parameters


@tool
def search_properties(
    city: str = None,
    min_price: float = None,
    max_price: float = None,
    property_type: str = None,
    min_sqft: int = None,
    max_sqft: int = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search for properties based on criteria.

    Args:
        city: City name (e.g., "Gainesville")
        min_price: Minimum price
        max_price: Maximum price
        property_type: Type (e.g., "Single Family", "Commercial")
        min_sqft: Minimum square footage
        max_sqft: Maximum square footage
        limit: Maximum results to return

    Returns:
        List of matching properties with details
    """
    payload = {
        'tool': 'search_properties',
        'parameters': {
            'city': city,
            'min_price': min_price,
            'max_price': max_price,
            'property_type': property_type,
            'min_sqft': min_sqft,
            'max_sqft': max_sqft,
            'limit': limit
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def find_entities(
    name: str = None,
    entity_type: str = None,
    min_properties: int = None,
    city: str = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Find property owners and entities.

    Args:
        name: Entity name to search
        entity_type: Type (e.g., "LLC", "Individual", "Trust")
        min_properties: Minimum number of properties owned
        city: City to search in
        limit: Maximum results

    Returns:
        List of entities with property ownership details
    """
    payload = {
        'tool': 'find_entities',
        'parameters': {
            'name': name,
            'entity_type': entity_type,
            'min_properties': min_properties,
            'city': city,
            'limit': limit
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def analyze_market_trends(
    city: str,
    property_type: str = None,
    timeframe_days: int = 365
) -> Dict[str, Any]:
    """
    Analyze real estate market trends.

    Args:
        city: City to analyze
        property_type: Optional property type filter
        timeframe_days: Number of days to analyze

    Returns:
        Market statistics and trends
    """
    payload = {
        'tool': 'analyze_market_trends',
        'parameters': {
            'city': city,
            'property_type': property_type,
            'timeframe_days': timeframe_days
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def cluster_properties(
    city: str,
    radius_meters: float = 500,
    min_cluster_size: int = 3
) -> Dict[str, Any]:
    """
    Find geographic clusters of properties.

    Args:
        city: City to search
        radius_meters: Clustering radius in meters
        min_cluster_size: Minimum properties per cluster

    Returns:
        Property clusters with statistics
    """
    payload = {
        'tool': 'cluster_properties',
        'parameters': {
            'city': city,
            'radius_meters': radius_meters,
            'min_cluster_size': min_cluster_size
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def find_assemblage_opportunities(
    city: str,
    max_distance_meters: float = 200,
    min_parcels: int = 2,
    max_parcels: int = 10
) -> Dict[str, Any]:
    """
    Find land assemblage opportunities (adjacent parcels).

    Args:
        city: City to search
        max_distance_meters: Maximum distance between parcels
        min_parcels: Minimum parcels in assemblage
        max_parcels: Maximum parcels in assemblage

    Returns:
        Assemblage opportunities with combined value
    """
    payload = {
        'tool': 'find_assemblage_opportunities',
        'parameters': {
            'city': city,
            'max_distance_meters': max_distance_meters,
            'min_parcels': min_parcels,
            'max_parcels': max_parcels
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def analyze_location_intelligence(
    address: str = None,
    lat: float = None,
    lon: float = None,
    radius_meters: float = 1000
) -> Dict[str, Any]:
    """
    Analyze location intelligence (nearby properties, demographics, etc.).

    Args:
        address: Address to analyze
        lat: Latitude (if no address)
        lon: Longitude (if no address)
        radius_meters: Analysis radius

    Returns:
        Location intelligence report
    """
    payload = {
        'tool': 'analyze_location_intelligence',
        'parameters': {
            'address': address,
            'lat': lat,
            'lon': lon,
            'radius_meters': radius_meters
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def check_permit_history(
    address: str = None,
    parcel_id: str = None,
    days_back: int = 365
) -> Dict[str, Any]:
    """
    Check building permit history for a property.

    Args:
        address: Property address
        parcel_id: Parcel ID
        days_back: How many days back to search

    Returns:
        Permit history with details
    """
    payload = {
        'tool': 'check_permit_history',
        'parameters': {
            'address': address,
            'parcel_id': parcel_id,
            'days_back': days_back
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def search_ordinances(
    query: str,
    city: str = None,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Search Florida municipal ordinances using RAG.

    Args:
        query: Search query (e.g., "setback requirements")
        city: Optional city filter
        max_results: Maximum results

    Returns:
        Relevant ordinance sections with citations
    """
    payload = {
        'tool': 'search_ordinances',
        'parameters': {
            'query': query,
            'market': f"{city.lower().replace(' ', '_')}_fl" if city else None,
            'max_results': max_results
        }
    }

    response = lambda_client.invoke(
        FunctionName=RAG_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def enrich_from_qpublic(
    parcel_id: str = None,
    address: str = None,
    city: str = "Gainesville"
) -> Dict[str, Any]:
    """
    Enrich property data from QPublic GIS system.

    Args:
        parcel_id: Parcel ID to lookup
        address: Address to lookup
        city: City name

    Returns:
        Enriched property data from QPublic
    """
    payload = {
        'tool': 'enrich_from_qpublic',
        'parameters': {
            'parcel_id': parcel_id,
            'address': address,
            'market': f"{city.lower().replace(' ', '_')}_fl"
        }
    }

    response = lambda_client.invoke(
        FunctionName=ENRICHMENT_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def enrich_from_sunbiz(
    entity_name: str = None,
    document_number: str = None
) -> Dict[str, Any]:
    """
    Enrich entity data from Florida SunBiz.

    Args:
        entity_name: Entity name to search
        document_number: SunBiz document number

    Returns:
        Enriched entity data from SunBiz
    """
    payload = {
        'tool': 'enrich_from_sunbiz',
        'parameters': {
            'entity_name': entity_name,
            'document_number': document_number
        }
    }

    response = lambda_client.invoke(
        FunctionName=ENRICHMENT_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


# System prompt for Dominion agent
SYSTEM_PROMPT = """You are Dominion, an expert Florida real estate intelligence agent.

You have access to comprehensive real estate data including:
- 108,380 properties across Florida municipalities
- 89,189 property owners and entities
- 2,588 municipal ordinance sections
- Building permits, sales history, and market trends

Your capabilities:
1. Property Search: Find properties by location, price, size, type
2. Entity Analysis: Identify property owners, find portfolios
3. Market Intelligence: Analyze trends, pricing, inventory
4. Geographic Analysis: Cluster analysis, assemblage opportunities
5. Ordinance Search: Look up zoning, setbacks, regulations
6. Data Enrichment: Pull live data from QPublic and SunBiz

When answering questions:
- Be specific and data-driven
- Cite sources and provide parcel IDs
- Explain zoning/ordinance implications
- Identify investment opportunities
- Always verify ordinances for up-to-date regulations

You are helpful, professional, and focused on actionable intelligence."""


# Create Strands agent
agent = Agent(
    name="Dominion",
    model="us.amazon.nova-premier-v1:0",
    system_prompt=SYSTEM_PROMPT,  # Fixed: was 'instructions', should be 'system_prompt'
    tools=[
        search_properties,
        find_entities,
        analyze_market_trends,
        cluster_properties,
        find_assemblage_opportunities,
        analyze_location_intelligence,
        check_permit_history,
        search_ordinances,
        enrich_from_qpublic,
        enrich_from_sunbiz,
    ],
)


# AgentCore HTTP server wrapper using BedrockAgentCoreApp
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    AgentCore entrypoint using BedrockAgentCoreApp SDK.

    Automatically provides /invocations and /ping HTTP endpoints.

    Payload format from AgentCore:
    {
        "prompt": "Find vacant land under $100k in Gainesville",
        "session_id": "session-123",
        "user_id": "user-456"
    }
    """
    try:
        logger.info("Dominion agent invoked", payload=payload)

        prompt = payload.get('prompt')
        session_id = payload.get('session_id', 'default')

        if not prompt:
            logger.error("Missing prompt in payload")
            return {
                'success': False,
                'error': 'Missing prompt in payload'
            }

        # Run the Strands agent
        result = agent(prompt)

        logger.info("Agent completed successfully",
                   tool_calls=len(result.tool_calls) if hasattr(result, 'tool_calls') else 0)

        return {
            'success': True,
            'message': result.message if hasattr(result, 'message') else str(result),
            'tool_calls': len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
        }

    except Exception as e:
        logger.error("Agent error", error=str(e), exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Start HTTP server on port 8080 when run directly
    app.run()
