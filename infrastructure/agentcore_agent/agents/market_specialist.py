"""
Market Specialist Agent - Market Trends & Valuation Expert
Loads prompt from market_specialist_prompt.md
"""

import json
import uuid
import os
import boto3
from strands import Agent, tool
import structlog

logger = structlog.get_logger()

# AWS Lambda client
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Lambda function ARNs
INTELLIGENCE_FUNCTION_ARN = os.environ.get('INTELLIGENCE_FUNCTION_ARN', 'Dominion-Tools-IntelligenceFunctionF3B7706E-MqwpnWGzHDyP')

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'market_specialist_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Tool definitions for Market Specialist
@tool
def analyze_market_trends(
    city: str,
    property_type: str = None,
    zoning: str = None,
    min_price: float = None,
    max_price: float = None,
    time_period_months: int = 12
) -> dict:
    """
    Analyze market trends with multi-period time-series analysis.

    Returns: 12m/6m/3m/1m trends, absorption rate, market classification,
    velocity, insights, recommendations.
    """
    payload = {
        'tool': 'analyze_market_trends',
        'parameters': {
            'city': city,
            'property_type': property_type,
            'zoning': zoning,
            'min_price': min_price,
            'max_price': max_price,
            'time_period_months': time_period_months
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
    has_pool: bool = None,
    has_garage: bool = None,
    building_condition: str = None,
    neighborhood_desc: str = None,
    latitude: float = None,
    longitude: float = None,
    max_distance_miles: float = 5.0,
    max_age_months: int = 24,
    limit: int = 10
) -> dict:
    """
    Find comparable properties using professional appraisal methodology.

    Uses: Price Match (40%) + Feature Match (40%) + Time-Decay (20%)
    Returns: comps with similarity_score, feature_match, time_weight, distance_meters.
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
            'has_pool': has_pool,
            'has_garage': has_garage,
            'building_condition': building_condition,
            'neighborhood_desc': neighborhood_desc,
            'latitude': latitude,
            'longitude': longitude,
            'max_distance_miles': max_distance_miles,
            'max_age_months': max_age_months,
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
def calculate_absorption_rate(
    city: str,
    property_type: str = None,
    min_price: float = None,
    max_price: float = None
) -> dict:
    """
    Calculate market absorption rate and inventory metrics.

    Returns: absorption rate, inventory count, sales velocity, market classification.
    """
    payload = {
        'tool': 'calculate_absorption_rate',
        'parameters': {
            'city': city,
            'property_type': property_type,
            'min_price': min_price,
            'max_price': max_price
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


# Configure model for Market Specialist - shared across all sessions
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for detailed market analysis
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

market_model = BedrockModel(
    model_id="us.amazon.nova-lite-v1:0",
    max_tokens=10000,  # High limit for detailed market analysis
    temperature=0.2,
    boto_client_config=boto_config
)


def invoke(task: str, session_id: str = None) -> str:
    """
    Invoke the Market Specialist agent with session isolation.

    Args:
        task: Task description from supervisor
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Market analysis results
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    logger.info("Market Specialist invoked", task=task[:100], session_id=session_id)

    # Create fresh agent instance for this session
    market_agent = Agent(
        name=f"MarketSpecialist-{session_id[:8]}",
        model=market_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            analyze_market_trends,
            find_comparable_properties,
            calculate_absorption_rate
        ]
    )

    result = market_agent(task)
    logger.info("Market Specialist completed", session_id=session_id)
    return result.message if hasattr(result, 'message') else str(result)
