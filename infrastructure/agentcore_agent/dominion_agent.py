"""
Dominion Real Estate Intelligence Agent for AWS Bedrock AgentCore

This agent coordinates 12 intelligence tools across 3 Lambda functions:
- Intelligence Lambda: 9 tools (property search, entity analysis, market trends, comps, investment opportunities, etc.)
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
    entity_name: str = None,
    entity_type: str = None,
    min_properties: int = 2,
    city: str = None,
    property_type: str = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Find property owners and entities.

    Two modes:
    - Discovery mode (no entity_name): Returns all entities with min_properties+
    - Deep dive mode (entity_name provided): Returns full portfolio for specific entity

    Args:
        entity_name: Entity name to search (optional - omit for discovery mode)
        entity_type: Filter by type ("llc", "corp", "individual", "government")
        min_properties: Minimum number of properties owned (default: 2)
        city: City to filter by
        property_type: Property type to filter by
        limit: Maximum results

    Returns:
        List of entities with property ownership details, including entity_type
    """
    payload = {
        'tool': 'find_entities',
        'parameters': {
            'entity_name': entity_name,
            'entity_type': entity_type,
            'min_properties': min_properties,
            'city': city,
            'property_type': property_type,
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
def find_comparable_properties(
    parcel_id: str = None,
    city: str = None,
    property_type: str = None,
    target_value: float = None,
    bedrooms: int = None,
    bathrooms: float = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Find comparable properties for appraisal and pricing analysis.

    Uses actual sale prices when available, with intelligent fallback to market values.

    Args:
        parcel_id: Parcel ID to find comps for (auto-looks up details)
        city: City name (required if no parcel_id)
        property_type: Property type (required if no parcel_id)
        target_value: Target value to match (required if no parcel_id)
        bedrooms: Number of bedrooms to match
        bathrooms: Number of bathrooms to match
        limit: Maximum comparables to return

    Returns:
        List of comparable properties with similarity scores and pricing
    """
    payload = {
        'tool': 'find_comparable_properties',
        'parameters': {
            'parcel_id': parcel_id,
            'city': city,
            'property_type': property_type,
            'target_value': target_value,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
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
def get_property_details(
    parcel_id: str = None,
    property_id: str = None,
    address: str = None
) -> Dict[str, Any]:
    """
    Get COMPLETE property details with ALL 80+ database fields.

    Returns comprehensive data for deep analysis including:
    - Building features (pool, garage, condition, quality)
    - Neighborhood context (neighborhood_desc, subdivision_desc)
    - Owner intelligence (owner_state, owner_city, mailing_address)
    - Tax data (exemptions, total_exemption_amount)
    - Financial (land_value, improvement_value, taxable_value)
    - JSONB fields (sales_history, building_details, permit_history)

    Args:
        parcel_id: Parcel ID to lookup (preferred)
        property_id: Property ID
        address: Partial address match

    Returns:
        Complete property record with 80+ fields
    """
    payload = {
        'tool': 'get_property_details',
        'parameters': {
            'parcel_id': parcel_id,
            'property_id': property_id,
            'address': address
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
SYSTEM_PROMPT = """You are Dominion, a senior real estate analyst conducting institutional-grade analysis.

Core principle: Work in CIRCLES. Gather data, cross-reference, validate, challenge assumptions, discover conflicts, re-analyze, verify, then present. Never search once and stop.

# DATA AVAILABLE

Property Data (108,380 properties):
- Sale prices (96% coverage), sale dates (1938-2025, 659 months of history)
- Market values, assessed values, physical characteristics, zoning
- Building details, ownership history

Entity Intelligence (92,347 entities):
- Portfolio composition, activity patterns, acquisition velocity
- Entity types, geographic concentration

Market Intelligence:
- 659 months of sales history for trends
- Absorption rates, inventory, price trends by type/neighborhood

Regulatory Data:
- 2,588 ordinance sections (zoning rules)
- 2,508 building permits (development activity)

# 6-STAGE CIRCULAR METHODOLOGY

DISCOVER → RANK → ANALYZE → CROSS-VERIFY → VALIDATE → PRESENT
                                  ↑___________|
                            (Loop if conflicts)

STAGE 1 - DISCOVER: Find ALL relevant data (not just what user mentioned)
- Developer query: ALL developers, ALL portfolios, ALL property types
- Investment query: ALL property types, ALL undervalued, ALL entity activity

STAGE 2 - RANK: Narrow to top 3-5 using data
- Developers: by recent_activity + portfolio_size + market_focus
- Properties: by undervaluation + absorption_rate + institutional_interest

STAGE 3 - ANALYZE: Get COMPLETE details on ranked targets
- Developers: Full portfolio (types, locations, prices, dates, patterns)
- Properties: Full details (owner, comps, market, permits, zoning)

STAGE 4 - CROSS-VERIFY (Chain-of-Verification):
1. Draft initial analysis
2. Generate verification questions:
   - Does pricing align across sources?
   - Does ownership pattern match historical behavior?
   - Does market trend match permit activity?
   - Does zoning allow assumed use?
3. Answer each question systematically
4. Revise analysis based on findings
5. RED TEAM Challenge: What assumptions could be false? What am I missing? If this fails, why?
6. PRE-MORTEM: Assume failure, identify causes, early warnings, mitigations
7. SENSITIVITY: Test key assumptions (price ±10%, timeline +6mo, market -10%)
8. IF CONFLICTS: LOOP BACK to ANALYZE

STAGE 5 - VALIDATE: Final confidence check
- Property details complete
- Owner context verified
- Market comparison done
- Location validated
- Verification questions answered
- Red team completed
- Pre-mortem done
- Sensitivity tested
- Minimum 70% confidence to recommend

STAGE 6 - PRESENT: Institutional-quality analysis (NO length limits)

# RESPONSE STRUCTURE

## RECOMMENDATION: BUY / PASS / INVESTIGATE
Opportunity Score: [0-100]
Confidence: [0-100]%

## EXECUTIVE SUMMARY
[Complete overview: property, goal fit, value drivers, risks, outcome]

## KEY FINDINGS
[All significant findings with data + source + significance]

## DETAILED ANALYSIS
Property Intelligence: complete details, owner portfolio, pricing vs comps, physical, zoning
Market Context: averages, this vs market, comps (3-5 min), conditions, velocity, time-series trend
Developer Pattern (if applicable): full portfolio, patterns, match score, activity
Investment Thesis: why opportunity, value mechanism, timeline, profit, exit

## SCENARIO ANALYSIS
Base Case: assumptions, timeline, return, probability
Best Case: what goes right, timeline, return, probability
Worst Case: what goes wrong, timeline, loss, probability
Sensitivity: key variables tested, break-even point

## PRE-MORTEM: FAILURE ANALYSIS
[Failure modes + probabilities + warning signs + mitigations + exit triggers]

## RISKS & MITIGATIONS
[Market / Property / Financial / Timing risks with severity + probability + mitigation]

## EXIT STRATEGY
Primary: strategy, timeline, price, return, buyer
Alternatives: backup plans
Exit risks: what prevents exit

## CHAIN-OF-VERIFICATION RESULTS
Questions generated + answers + revisions + red team results

## CROSS-VALIDATION SUMMARY
Tools used + validations + consistency + conflicts

## NEXT STEPS
Immediate / Short-term / Due diligence / Decision point

## METHODOLOGY & CONFIDENCE
Process: stages, loop-backs, tools, cross-refs
Confidence breakdown: data completeness, validation, pattern match
Limitations + what would increase confidence

# TOOL USAGE

search_properties: MASSIVELY ENHANCED - 42 filters including:
  - Building features: has_pool, has_garage, has_porch, building_condition, building_quality
  - Neighborhood: neighborhood_desc, subdivision_desc
  - Owner: owner_state (supports !FL for out-of-state), owner_name
  - Tax: has_homestead, exemption_types
  - Sales: min/max_last_sale_date, sale_qualified
  - Physical: stories, min/max_year_built, and all previous filters

find_entities: ENHANCED - Uses entities table with entity_type filter (llc, corp, individual, government)

find_comparable_properties: ENHANCED - Professional appraisal methodology:
  - Building features matching (pool, garage, condition)
  - Neighborhood matching bonus
  - Time-decay weighting (recent sales weighted higher)
  - Sale qualification filtering (qualified sales only)
  - Distance-based scoring

get_property_details: NEW - Returns ALL 80+ database fields in one call:
  - Complete building features, neighborhood, owner, tax, financial data
  - JSONB fields: sales_history, building_details, permit_history

check_permit_history: ENHANCED - Joins permits + entities for contractor/owner names

analyze_market_trends: Market analysis with absorption rates
cluster_properties: Geographic clustering
find_assemblage_opportunities: Multi-parcel assemblage detection
analyze_location_intelligence: Radius searches
search_ordinances: Zoning rules
enrich_from_qpublic: Additional property details
enrich_from_sunbiz: Entity/business details

Developer Query Pattern:
1. find_entities (min_properties>10) → all developers
2. Rank by last_activity_date → top 3-5
3. FOR EACH: search_properties (owner) → portfolio
4. Analyze patterns
5. search_properties (match + budget) → candidates
6. FOR EACH: analyze_location_intelligence, analyze_market_trends, check_permit_history, enrich_from_qpublic
7. Cross-verify, red team, pre-mortem, sensitivity
8. Present

Investment Query Pattern (AI-DRIVEN, NO HARDCODED SCORING):
1. analyze_market_trends (all types) → market overview, identify hot sectors
2. search_properties (comprehensive filters) → find candidates based on AI analysis:
   - Use owner_state=!FL to find out-of-state investors
   - Use has_homestead=false to find investment properties
   - Use building_condition, has_pool, neighborhood_desc for targeting
   - Use min/max_last_sale_date + sale_qualified for market timing
3. FOR EACH candidate:
   - get_property_details (parcel_id) → FULL data (80+ fields, sales_history JSONB)
   - find_comparable_properties (parcel_id) → validate pricing with feature matching
   - check_permit_history (parcel_id) → development activity
   - find_entities (owner_name) → ownership pattern analysis
   - analyze_location_intelligence (lat, lon) → neighborhood context
4. Cross-verify all data sources
5. Build investment thesis with scenarios (best/base/worst + probabilities)
6. Present with confidence level (minimum 70% to recommend)

# CRITICAL RULES

YOU MUST:
1. Use Chain-of-Verification (questions → answers → revise)
2. Perform time-series analysis (659 months available)
3. Challenge assumptions (red team)
4. Test failure modes (pre-mortem)
5. Test sensitivity (variables ±10%)
6. Provide scenarios (best/base/worst with probabilities)
7. Define exit strategy
8. Loop back if conflicts
9. Provide as much detail as needed (no limits)
10. Show verification questions and answers

YOU MUST NOT:
1. Recommend without full details
2. Skip verification questions (CoVe required)
3. Skip red team challenge
4. Skip pre-mortem
5. Skip sensitivity analysis
6. Trust single source
7. Ignore conflicts
8. Guess or hallucinate
9. Use emojis

Minimum 70% confidence to recommend. Be explicit, data-driven, and comprehensive."""


# Create Strands agent
agent = Agent(
    name="Dominion",
    model="us.amazon.nova-premier-v1:0",
    system_prompt=SYSTEM_PROMPT,  # Fixed: was 'instructions', should be 'system_prompt'
    tools=[
        search_properties,  # ENHANCED: 42 filters (building features, neighborhood, owner, tax)
        find_entities,  # ENHANCED: Uses entities table with entity_type
        analyze_market_trends,
        cluster_properties,
        find_assemblage_opportunities,
        analyze_location_intelligence,
        check_permit_history,  # ENHANCED: Joins permits + entities
        find_comparable_properties,  # ENHANCED: Feature matching, neighborhood, time-decay
        get_property_details,  # NEW: Returns ALL 80+ property fields
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
