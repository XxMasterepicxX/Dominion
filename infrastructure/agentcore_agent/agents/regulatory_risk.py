"""
Regulatory & Risk Specialist Agent - Zoning Compliance & Risk Assessment Expert
Loads prompt from regulatory_risk_specialist_prompt.md
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
RAG_FUNCTION_ARN = os.environ.get('RAG_FUNCTION_ARN', 'Dominion-Tools-RAGFunction89B11B85-269jmrt7KhBO')
ENRICHMENT_FUNCTION_ARN = os.environ.get('ENRICHMENT_FUNCTION_ARN', 'Dominion-Tools-EnrichmentFunction65873741-Nu6t0OWMde2r')

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'regulatory_risk_specialist_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Tool definitions for Regulatory & Risk Specialist
@tool
def check_permit_history(
    parcel_id: str = None,
    address: str = None,
    days_back: int = 730
) -> dict:
    """
    Check building permit history for a property.

    Fixed to query via parcel_id (joins bulk_property_records → permits).
    Coverage: 2,508 permits across Gainesville and Alachua County.

    Returns: permit type, date, status, cost, description, contractor.
    """
    payload = {
        'tool': 'check_permit_history',
        'parameters': {
            'parcel_id': parcel_id,
            'address': address,
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
) -> dict:
    """
    Search municipal ordinances using RAG (5,176 chunks across 9 jurisdictions).

    Jurisdictions: Gainesville, Alachua County, Archer, Hawthorne, High Springs,
    Micanopy, Newberry, Waldo, Alachua (city).

    Returns: relevant ordinance text, zoning rules, dimensional requirements,
    regulatory context, source citations.
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
    city: str = None
) -> dict:
    """
    Enrich property data from QPublic GIS system.

    Returns: additional property details, tax status, legal descriptions, ownership.
    """
    payload = {
        'tool': 'enrich_from_qpublic',
        'parameters': {
            'parcel_id': parcel_id,
            'address': address,
            'market': f"{city.lower().replace(' ', '_')}_fl" if city else None
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
def analyze_location_intelligence(
    parcel_id: str = None,
    address: str = None,
    lat: float = None,
    lon: float = None,
    radius_meters: float = 250,
    limit: int = 50
) -> dict:
    """
    Analyze nearby properties for neighborhood context and risk assessment.

    Returns: nearby properties, property mix, compatible uses, nuisance risks.
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


# Create Regulatory & Risk Specialist Agent
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for comprehensive regulatory analysis
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

regulatory_model = BedrockModel(
    model_id="us.amazon.nova-lite-v1:0",
    max_tokens=10000,  # High limit for comprehensive regulatory analysis
    temperature=0.2,
    boto_client_config=boto_config
)

def invoke(task: str, session_id: str = None) -> str:
    """
    Invoke the Regulatory & Risk Specialist agent with session isolation.

    Args:
        task: Task description from supervisor
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Regulatory & risk analysis results
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    logger.info("Regulatory & Risk invoked", task=task[:100], session_id=session_id)

    # Create fresh agent instance for this session
    regulatory_agent = Agent(
        name=f"RegulatoryRisk-{session_id[:8]}",
        model=regulatory_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            check_permit_history,
            search_ordinances,
            enrich_from_qpublic,
            analyze_location_intelligence
        ]
    )

    result = regulatory_agent(task)
    logger.info("Regulatory & Risk completed", session_id=session_id)

    # Convert AgentResult to dict
    if hasattr(result, 'model_dump'):
        result_dict = result.model_dump()
    elif hasattr(result, 'to_dict'):
        result_dict = result.to_dict()
    elif hasattr(result, 'dict'):
        result_dict = result.dict()
    elif isinstance(result, dict):
        result_dict = result
    else:
        result_dict = dict(result) if hasattr(result, '__iter__') else {'message': str(result)}

    # Extract text from dict structure
    if 'content' in result_dict:
        content = result_dict['content']
        if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict) and 'text' in content[0]:
            return content[0]['text']
        return str(content)
    elif 'message' in result_dict:
        return result_dict['message']
    return str(result_dict)
