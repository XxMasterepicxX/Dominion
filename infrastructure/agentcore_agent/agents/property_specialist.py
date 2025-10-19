"""
Property Specialist Agent - Spatial Analysis & Clustering Expert
Loads prompt from property_specialist_prompt.md
"""

import json
import os
import uuid
import boto3
from strands import Agent, tool
import structlog

logger = structlog.get_logger()

# AWS Lambda client
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Lambda function ARNs
INTELLIGENCE_FUNCTION_ARN = os.environ.get('INTELLIGENCE_FUNCTION_ARN', 'Dominion-Tools-IntelligenceFunctionF3B7706E-MqwpnWGzHDyP')

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'property_specialist_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Tool definitions for Property Specialist
@tool
def search_properties(
    city: str = None,
    min_price: float = None,
    max_price: float = None,
    property_type: str = None,
    min_sqft: int = None,
    max_sqft: int = None,
    min_lot_acres: float = None,
    max_lot_acres: float = None,
    bedrooms: int = None,
    bathrooms: float = None,
    min_bedrooms: int = None,
    min_bathrooms: float = None,
    min_year_built: int = None,
    max_year_built: int = None,
    min_stories: int = None,
    max_stories: int = None,
    has_pool: bool = None,
    has_garage: bool = None,
    has_porch: bool = None,
    has_fence: bool = None,
    has_shed: bool = None,
    building_condition: str = None,
    building_quality: str = None,
    roof_type: str = None,
    heat_type: str = None,
    ac_type: str = None,
    owner_state: str = None,
    owner_name: str = None,
    has_homestead: bool = None,
    exemption_types: str = None,
    min_last_sale_price: float = None,
    max_last_sale_price: float = None,
    min_last_sale_date: str = None,
    max_last_sale_date: str = None,
    sale_qualified: str = None,
    neighborhood_desc: str = None,
    subdivision_desc: str = None,
    min_assessed: float = None,
    max_assessed: float = None,
    limit: int = 100,
    order_by: str = None
) -> dict:
    """
    Search properties with 42 advanced filters.

    Supports: location, price, size, physical features, building quality,
    owner intelligence, tax/exemptions, sales history filters.
    """
    payload = {
        'tool': 'search_properties',
        'parameters': {
            k: v for k, v in locals().items()
            if v is not None and k not in ['payload', 'response', 'result']
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
) -> dict:
    """
    Get complete property details with ALL 80+ database fields.

    Returns: building features, neighborhood, owner, tax, financial data,
    JSONB fields (sales_history, building_details, permit_history).
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
def cluster_properties(
    city: str,
    radius_meters: float = 500,
    min_cluster_size: int = 3,
    property_type: str = None
) -> dict:
    """
    Find geographic clusters of properties using DBSCAN.

    Returns: clusters with centroids, property counts, purity scores.
    """
    payload = {
        'tool': 'cluster_properties',
        'parameters': {
            'city': city,
            'radius_meters': radius_meters,
            'min_cluster_size': min_cluster_size,
            'property_type': property_type
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
) -> dict:
    """
    Find land assemblage opportunities (adjacent parcels by same owner).

    Returns: assemblages with entity_type, total_assemblage_value,
    total_lot_size_acres, property_types breakdown.
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
    parcel_id: str = None,
    address: str = None,
    lat: float = None,
    lon: float = None,
    radius_meters: float = 500,
    limit: int = 50
) -> dict:
    """
    Analyze nearby properties and spatial context.

    Returns: nearby properties with distances, property mix, spatial patterns.
    """
    payload = {
        'tool': 'analyze_location_intelligence',
        'parameters': {
            'parcel_id': parcel_id,
            'address': address,
            'lat': lat,
            'lon': lon,
            'radius_meters': radius_meters,
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


# Configure model for Property Specialist - shared across all sessions
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for comprehensive property analysis
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

property_model = BedrockModel(
    model_id="us.amazon.nova-premier-v1:0",  # Premier required - Lite and Pro both crash on 6-call planning
    max_tokens=10000,  # Using compact output format to stay within limit
    temperature=0.2,
    boto_client_config=boto_config
)


def invoke(task: str, session_id: str = None) -> str:
    """
    Invoke the Property Specialist agent with session isolation.

    Creates a fresh agent instance per session to prevent conversation bleed.

    Args:
        task: Task description from supervisor
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Property analysis results
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    logger.info("Property Specialist invoked", task=task[:100], session_id=session_id)

    # Create fresh agent instance for this session
    property_agent = Agent(
        name=f"PropertySpecialist-{session_id[:8]}",
        model=property_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            search_properties,
            get_property_details,
            cluster_properties,
            find_assemblage_opportunities,
            analyze_location_intelligence
        ]
    )

    result = property_agent(task)
    logger.info("Property Specialist completed", session_id=session_id)
    return result.message if hasattr(result, 'message') else str(result)
